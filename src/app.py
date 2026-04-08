from __future__ import annotations

from flask import Flask, g, jsonify, request, Response, send_from_directory
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
try:
    from src.scanner import SkillScanner
    from src.executor import CopilotExecutor
    from src.skill_runner import SkillRunner
except ModuleNotFoundError:
    # Allow running directly as 'python src/app.py' from project root
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.scanner import SkillScanner
    from src.executor import CopilotExecutor
    from src.skill_runner import SkillRunner
import json
import logging
import os

from src.logging_context import CorrelationIdFilter, correlation_id_var, get_or_create_correlation_id
from src.skillflow_config import load_skillflow_config, pick_str
from src.skill_paths import resolve_skill_repo_dir
from src import remote_patch
from src import remote_runner
from src.use_cases import apply_use_case, prepare_use_cases

log = logging.getLogger("skillflow.app")

_DEFAULT_LLM_API_URL = "http://hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions"
_DEFAULT_LLM_MODEL = "qwen/qwen3-32b"


def configure_logging(level: Optional[str] = None) -> None:
    """Configure structured logging for the SkillFlow application.

    Call once at startup (e.g. in __main__ or a WSGI entry point).
    All skillflow.* loggers will emit timestamped lines to stdout.
    Log level defaults to ``SKILLFLOW_LOG_LEVEL`` env (or INFO). Lines include
    request correlation id when set via :func:`correlation_id_var`.
    """
    if level is None:
        level = os.environ.get("SKILLFLOW_LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    root = logging.getLogger("skillflow")
    root.setLevel(numeric_level)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.addFilter(CorrelationIdFilter())
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            handler.setFormatter(formatter)
            if not any(isinstance(f, CorrelationIdFilter) for f in handler.filters):
                handler.addFilter(CorrelationIdFilter())


MAX_FALLBACK_LOG_CHARS = 120000


def summarize_uploaded_log(log_text: str, max_chars: int = MAX_FALLBACK_LOG_CHARS) -> str:
    """Bound uploaded log text for fallback prompt path to avoid oversized payloads."""
    if len(log_text) <= max_chars:
        return log_text

    head = max_chars // 2
    tail = max_chars - head
    omitted = len(log_text) - max_chars
    return (
        f"{log_text[:head]}\n\n"
        f"...[truncated {omitted} chars for payload safety]...\n\n"
        f"{log_text[-tail:]}"
    )


def create_app(
    skill_path: str = "",
    adapter_path: str = "./config/skill_adapters.yaml",
    use_case_definitions: Optional[List[Mapping[str, Any]]] = None,
) -> Flask:
    """
    Factory function to create and configure the Flask application.
    
    Args:
        skill_path: Path to the skills directory for discovery. When empty, see
        ``skill_paths.resolve_skill_repo_dir`` (``SKILLS_PATH``, GitLab cache, or ``dev-skills``).
        use_case_definitions: Optional override of the fixed use-case list (tests only).
    
    Returns:
        Configured Flask app instance.
    """
    project_root = Path(__file__).resolve().parent.parent
    file_cfg = load_skillflow_config(project_root)
    log_level_cfg = pick_str("SKILLFLOW_LOG_LEVEL", file_cfg, "log_level", "")
    configure_logging(level=log_level_cfg if log_level_cfg else None)

    web_root = project_root / "web"
    app = Flask(__name__, static_folder=str(web_root), static_url_path="/web")

    @app.before_request
    def _assign_correlation_id() -> None:
        hdr = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
        cid = get_or_create_correlation_id(hdr)
        g.correlation_id = cid
        correlation_id_var.set(cid)

    @app.after_request
    def _echo_correlation_id(response: Response) -> Response:
        cid = getattr(g, "correlation_id", None)
        if cid:
            response.headers["X-Request-ID"] = str(cid)
        return response

    gitlab_repo_url = pick_str("GITLAB_REPO_URL", file_cfg, "gitlab_repo_url", "")
    gitlab_branch = pick_str("GITLAB_BRANCH", file_cfg, "gitlab_branch", "main")
    skills_dir = resolve_skill_repo_dir(project_root, skill_path, file_cfg)
    skills_dir.parent.mkdir(parents=True, exist_ok=True)

    llm_url = pick_str("LLM_API_URL", file_cfg, "llm_api_url", _DEFAULT_LLM_API_URL)
    llm_model = pick_str("LLM_MODEL", file_cfg, "llm_model", _DEFAULT_LLM_MODEL)

    # Initialize scanner and executor at app startup
    scanner = SkillScanner(
        repo_path=str(skills_dir),
        gitlab_repo_url=(gitlab_repo_url or None),
        gitlab_branch=gitlab_branch,
    )
    skills = scanner.scan()
    executor = CopilotExecutor(api_url=llm_url, model=llm_model)
    skill_runner = SkillRunner(adapter_path=adapter_path)
    use_cases_list, use_cases_by_id = prepare_use_cases(skills, use_case_definitions)
    
    # Helper: find skill by name
    def find_skill_by_name(name: str):
        """Find a skill in the loaded skills list by name."""
        for skill in skills:
            if skill.get("name") == name:
                return skill
        return None

    def build_prompt(
        skill_content: str,
        user_input: str,
        tool_run: dict,
        uploaded_log_text: str,
        input_params: Dict[str, Any],
    ) -> str:
        """Build the LLM prompt based on tool execution outcome.

        When the external tool crashed or could not be found, binary file content
        is NOT included — sending unreadable bytes causes the LLM to hallucinate.
        Instead, the tool error is embedded and LLM is instructed not to fabricate.
        """
        prompt = f"Using this skill spec:\n{skill_content}\n\nAnalyze this user query: {user_input}"
        reason = tool_run.get("reason", "")

        if input_params:
            param_lines = []
            for key, value in input_params.items():
                if value is None:
                    continue
                value_str = str(value).strip()
                if value_str:
                    param_lines.append(f"- {key}: {value_str}")
            if param_lines:
                prompt += "\n\nInput parameters:\n" + "\n".join(param_lines)

        if tool_run["mode"] == "tool-first":
            prompt += f"\n\nTool output (tool-first mode):\n{tool_run['tool_output']}"
        elif reason in ("tool_error", "command_not_found", "tool_timeout"):
            # Tool was attempted but failed — binary file content is not useful to LLM.
            prompt += (
                f"\n\n[NOTE: The external analysis tool failed with the following error:\n"
                f"{tool_run['note']}\n"
                f"The uploaded file is a binary format that cannot be read as plain text. "
                f"Do NOT fabricate specific values, object names, paths, or measurements. "
                f"Instead, explain what this error means and suggest concrete steps to resolve it.]"
            )
        elif uploaded_log_text:
            prompt += f"\n\nAttached log content:\n{uploaded_log_text}"

        return prompt

    def parse_analyze_request():
        """Parse analyze payload from JSON or multipart form data."""
        use_case_id = ""
        skill_name = ""
        user_input = ""
        input_params: Dict[str, Any] = {}
        uploaded_log_text = ""
        uploaded_file_name = ""
        uploaded_file_bytes = b""

        if request.is_json:
            data = request.get_json(silent=True) or {}
            use_case_id = (data.get("use_case_id") or "").strip()
            skill_name = (data.get("skill_name") or "").strip()
            user_input = (data.get("user_input") or "").strip()
            raw_params = data.get("input_params")
            if isinstance(raw_params, dict):
                input_params = raw_params
            return (
                use_case_id,
                skill_name,
                user_input,
                input_params,
                uploaded_log_text,
                uploaded_file_name,
                uploaded_file_bytes,
                None,
            )

        # Support multipart/form-data for file upload use cases.
        use_case_id = (request.form.get("use_case_id") or "").strip()
        skill_name = (request.form.get("skill_name") or "").strip()
        user_input = (request.form.get("user_input") or "").strip()
        raw_params = request.form.get("input_params")
        if raw_params:
            try:
                parsed = json.loads(raw_params)
                if isinstance(parsed, dict):
                    input_params = parsed
            except (TypeError, ValueError):
                input_params = {}
        uploaded_file = request.files.get("log_file")

        if uploaded_file and uploaded_file.filename:
            uploaded_file_name = uploaded_file.filename
            raw_bytes = uploaded_file.read()
            if not raw_bytes:
                return (
                    use_case_id,
                    skill_name,
                    user_input,
                    input_params,
                    uploaded_log_text,
                    uploaded_file_name,
                    uploaded_file_bytes,
                    "Uploaded log file is empty",
                )
            uploaded_file_bytes = raw_bytes
            uploaded_log_text = summarize_uploaded_log(
                raw_bytes.decode("utf-8", errors="replace")
            )

        return (
            use_case_id,
            skill_name,
            user_input,
            input_params,
            uploaded_log_text,
            uploaded_file_name,
            uploaded_file_bytes,
            None,
        )

    def resolve_analyze_target(
        use_case_id: str,
        skill_name: str,
        user_input: str,
    ) -> tuple[str, str, Optional[tuple[Any, int]]]:
        """Return (skill_name, effective_user_input, error_pair) error_pair is (jsonify(...), status)."""
        uc = (use_case_id or "").strip()
        sn = (skill_name or "").strip()
        if uc and sn:
            return (
                "",
                user_input,
                (jsonify({"error": "Send only one of use_case_id or skill_name, not both"}), 400),
            )
        if uc:
            resolved_skill, effective_input, err = apply_use_case(
                uc, user_input, use_cases_by_id
            )
            if err:
                status = 404 if err.startswith("Unknown use_case_id") else 400
                return "", user_input, (jsonify({"error": err}), status)
            return resolved_skill, effective_input, None
        if not sn:
            return (
                "",
                user_input,
                (
                    jsonify(
                        {
                            "error": (
                                "Missing required field: provide use_case_id or skill_name "
                                "together with user_input"
                            )
                        }
                    ),
                    400,
                ),
            )
        return sn, user_input, None

    @app.route("/api/skills", methods=["GET"])
    def get_skills():
        """
        Endpoint to fetch all available skills.
        
        Returns:
            JSON list of skills with basic metadata (name, description, id).
        """
        skill_list = [
            {
                "name": s.get("name"),
                "description": s.get("description"),
                "id": s.get("id"),
                "inputs": s.get("inputs") or [],
            }
            for s in skills
        ]
        return jsonify(skill_list), 200

    @app.route("/api/use-cases", methods=["GET"])
    def get_use_cases():
        """List business use cases (each maps to a loaded skill by name)."""
        return jsonify(use_cases_list), 200

    @app.route("/api/remote/nrm-workflow/status", methods=["GET"])
    def remote_nrm_workflow_status():
        """Whether Phase-1 remote SSH execution is enabled and minimally configured."""
        ident = remote_runner.default_identity_path()
        return jsonify(
            {
                "enabled": remote_runner.remote_ssh_enabled(),
                "identity_configured": bool(ident and os.path.isfile(ident)),
                "ssh_user_configured": bool(remote_runner.default_ssh_user()),
                "allowed_actions": sorted(remote_runner.NRM_WORKFLOW_ACTIONS.keys()),
                "phase2_patch_apply": remote_runner.remote_ssh_enabled(),
                "phase3_suggest_patch": remote_patch.suggest_patch_enabled(),
                "max_agent_iterations": remote_patch.default_max_agent_iterations(),
                "max_patch_bytes": remote_patch.max_patch_bytes(),
            }
        ), 200

    @app.route("/api/remote/nrm-workflow", methods=["POST"])
    def remote_nrm_workflow():
        """Run a whitelisted nrm-coding-workflow script on LinSee via SSH (Phase 1).

        JSON body: use_case_id (must be icfs-to-code-ut-sct), linsee_ssh_host, work_dir,
        repo_name, remote_action (dev_status|dev_build|dev_ut), remote_run_confirmed (true).
        Optional: ssh_user, remote_scripts_dir, ut_test_filter (for dev_ut).

        Requires SKILLFLOW_REMOTE_SSH_ENABLED=1, SKILLFLOW_REMOTE_SSH_IDENTITY, and
        SKILLFLOW_REMOTE_SSH_USER (or ssh_user per request). Optional host allowlist via
        SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST.
        """
        if not remote_runner.remote_ssh_enabled():
            return jsonify(
                {
                    "error": (
                        "Remote SSH is disabled. Set SKILLFLOW_REMOTE_SSH_ENABLED=1 and configure "
                        "SKILLFLOW_REMOTE_SSH_IDENTITY (and user)."
                    )
                }
            ), 403

        data = request.get_json(silent=True) or {}
        if data.get("remote_run_confirmed") is not True:
            return jsonify({"error": "remote_run_confirmed must be true"}), 400

        uc = str(data.get("use_case_id") or "").strip()
        if uc != "icfs-to-code-ut-sct":
            return jsonify({"error": "use_case_id must be icfs-to-code-ut-sct"}), 400

        host = str(data.get("linsee_ssh_host") or "").strip()
        work_dir = str(data.get("work_dir") or "").strip()
        repo_name = str(data.get("repo_name") or "").strip()
        action = str(data.get("remote_action") or data.get("action") or "").strip()
        scripts_dir = str(data.get("remote_scripts_dir") or "").strip() or remote_runner.default_scripts_dir()
        if (data.get("remote_scripts_dir") or "").strip():
            sd_err = remote_runner.validate_safe_path("remote_scripts_dir", scripts_dir)
            if sd_err:
                return jsonify({"error": sd_err}), 400

        ssh_user = str(data.get("ssh_user") or "").strip() or remote_runner.default_ssh_user()
        ut_filter = str(data.get("ut_test_filter") or "*").strip() or "*"

        ident = remote_runner.default_identity_path()
        payload, err = remote_runner.run_nrm_workflow_remote(
            host=host,
            ssh_user=ssh_user,
            identity_path=ident,
            scripts_dir=scripts_dir,
            work_dir=work_dir,
            repo_name=repo_name,
            action=action,
            ut_test_filter=ut_filter,
        )
        if err:
            return jsonify({"error": err}), 400
        return jsonify(payload), 200

    @app.route("/api/remote/nrm-workflow/validate-patch", methods=["POST"])
    def remote_validate_patch():
        """Phase 2 — validate unified diff size and paths (no SSH)."""
        data = request.get_json(silent=True) or {}
        uc = str(data.get("use_case_id") or "").strip()
        if uc != "icfs-to-code-ut-sct":
            return jsonify({"error": "use_case_id must be icfs-to-code-ut-sct"}), 400
        diff = str(data.get("unified_diff") or "").replace("\r\n", "\n")
        verr, paths = remote_patch.validate_unified_diff(diff)
        if verr:
            return jsonify({"ok": False, "error": verr, "paths": paths}), 200
        return jsonify({"ok": True, "paths": paths}), 200

    @app.route("/api/remote/nrm-workflow/apply-patch", methods=["POST"])
    def remote_apply_patch():
        """Phase 2 — ``scp`` diff to LinSee and ``git apply`` under ``work_dir``."""
        if not remote_runner.remote_ssh_enabled():
            return jsonify({"error": "Remote SSH is disabled"}), 403
        data = request.get_json(silent=True) or {}
        if data.get("patch_apply_confirmed") is not True:
            return jsonify({"error": "patch_apply_confirmed must be true"}), 400
        uc = str(data.get("use_case_id") or "").strip()
        if uc != "icfs-to-code-ut-sct":
            return jsonify({"error": "use_case_id must be icfs-to-code-ut-sct"}), 400

        host = str(data.get("linsee_ssh_host") or "").strip()
        work_dir = str(data.get("work_dir") or "").strip()
        ssh_user = str(data.get("ssh_user") or "").strip() or remote_runner.default_ssh_user()
        ident = remote_runner.default_identity_path()
        diff = str(data.get("unified_diff") or "")

        payload, err = remote_runner.apply_unified_diff_remote(
            host=host,
            ssh_user=ssh_user,
            identity_path=ident,
            work_dir=work_dir,
            unified_diff=diff,
        )
        if err:
            return jsonify({"error": err}), 400
        return jsonify(payload), 200

    @app.route("/api/remote/nrm-workflow/suggest-patch", methods=["POST"])
    def remote_suggest_patch():
        """Phase 3 — ask LLM for a unified diff; client reviews before apply-patch."""
        if not remote_patch.suggest_patch_enabled():
            return jsonify({"error": "Suggest-patch is disabled (SKILLFLOW_REMOTE_SUGGEST_PATCH_ENABLED=0)"}), 403

        data = request.get_json(silent=True) or {}
        max_it = remote_patch.default_max_agent_iterations()
        try:
            iteration_index = int(data.get("iteration_index") or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "iteration_index must be an integer"}), 400
        if iteration_index < 0 or iteration_index >= max_it:
            return jsonify(
                {"error": f"iteration_index must be in range 0 .. {max_it - 1} (max {max_it} rounds)"}
            ), 400

        uc = str(data.get("use_case_id") or "").strip()
        if uc != "icfs-to-code-ut-sct":
            return jsonify({"error": "use_case_id must be icfs-to-code-ut-sct"}), 400

        user_input = str(data.get("user_input") or "").strip()
        if not user_input:
            return jsonify({"error": "user_input is required"}), 400

        skill = find_skill_by_name("nrm-coding-workflow")
        if not skill:
            return jsonify({"error": "nrm-coding-workflow skill is not loaded"}), 404

        skill_body = skill.get("full_content") or ""
        if len(skill_body) > 100000:
            skill_body = skill_body[:100000] + "\n\n...[skill truncated for prompt size]...\n"

        out = str(data.get("remote_last_stdout") or "")[:24000]
        err_tail = str(data.get("remote_last_stderr") or "")[:24000]
        rc = data.get("remote_last_returncode")
        gerrit = str(data.get("gerrit_change_id") or "").strip()

        prompt = (
            "Using this skill specification:\n"
            f"{skill_body}\n\n"
            "Task: propose code changes as a single unified diff (git format) relative to the "
            "repository root on the remote LinSee workspace. The user will run `git apply` from that root.\n\n"
            f"User instructions / goal:\n{user_input}\n\n"
        )
        if gerrit:
            prompt += f"Gerrit ICFS/PFS change ID (context only; SkillFlow does not fetch Gerrit): {gerrit}\n\n"
        prompt += (
            "Last remote command output (stdout, may be truncated):\n"
            f"{out or '(none)'}\n\n"
            "Last remote command output (stderr, may be truncated):\n"
            f"{err_tail or '(none)'}\n\n"
            f"Last remote exit code: {rc!r}\n\n"
            "Rules:\n"
            "- Output ONLY one markdown fenced code block starting with ```diff containing the full unified diff.\n"
            "- Paths in the diff must be relative (e.g. src/foo.cpp), no .. segments, no absolute paths.\n"
            "- Do not include binary patches.\n"
            "- If no patch is appropriate, reply with exactly: NO_DIFF\n"
            "  followed by a short explanation (no code fence).\n"
        )

        raw = executor.ask_ai(prompt)
        if (raw or "").strip().upper().startswith("NO_DIFF"):
            return jsonify(
                {
                    "proposed_diff": None,
                    "raw_response": raw,
                    "parse_note": "no_diff",
                    "iteration_index": iteration_index,
                }
            ), 200

        extracted, perr = remote_patch.extract_diff_from_llm_response(raw)
        if not extracted:
            return jsonify(
                {
                    "proposed_diff": None,
                    "raw_response": raw,
                    "parse_note": perr or "unparsed",
                    "iteration_index": iteration_index,
                }
            ), 200

        verr, paths = remote_patch.validate_unified_diff(extracted.replace("\r\n", "\n"))
        return jsonify(
            {
                "proposed_diff": extracted,
                "paths": paths,
                "validation_error": verr,
                "raw_response": raw,
                "iteration_index": iteration_index,
            }
        ), 200

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        """Liveness probe: process up; does not call external LLM."""
        return jsonify({"status": "ok"}), 200

    @app.route("/", methods=["GET"])
    def web_home():
        """Serve the web UI home page for Phase 2 (Option B)."""
        return send_from_directory(str(web_root), "index.html")
    
    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        """
        Endpoint to analyze user input using a selected skill or use case.

        Provide exactly one of:
            - ``skill_name`` + ``user_input``, or
            - ``use_case_id`` + ``user_input`` (resolves to a skill; optional ``prompt_prefix`` from YAML).

        Optional: ``input_params`` (dict), file field ``log_file`` (multipart).
        """
        (
            use_case_id,
            skill_name,
            user_input,
            input_params,
            uploaded_log_text,
            uploaded_file_name,
            uploaded_file_bytes,
            request_error,
        ) = parse_analyze_request()

        if request_error:
            return jsonify({"error": request_error}), 400

        if not user_input:
            return jsonify({"error": "Missing required field: user_input"}), 400

        skill_name, user_input, err_resp = resolve_analyze_target(
            use_case_id, skill_name, user_input
        )
        if err_resp:
            body, status = err_resp
            return body, status

        # Find the skill
        skill = find_skill_by_name(skill_name)
        if not skill:
            return jsonify({"error": f"Skill '{skill_name}' not found"}), 404
        
        # Build prompt: combine skill metadata with user input
        skill_content = skill.get("full_content", "")

        tool_run = skill_runner.run_tool_if_configured(
            skill_name=skill_name,
            file_name=uploaded_file_name,
            file_bytes=uploaded_file_bytes,
            input_params=input_params,
        )

        log.info(
            "analyze request: use_case_id=%s skill=%s mode=%s file=%s input_params_keys=%s input_len=%d",
            use_case_id or "-",
            skill_name,
            tool_run["mode"],
            uploaded_file_name or "none",
            sorted(input_params.keys()) if input_params else [],
            len(user_input),
        )

        prompt = build_prompt(skill_content, user_input, tool_run, uploaded_log_text, input_params)

        # Call LLM executor
        result = executor.ask_ai(prompt)

        return jsonify(
            {
                "result": result,
                "mode": tool_run["mode"],
                "execution_note": tool_run["note"],
            }
        ), 200
    
    @app.route("/api/analyze/stream", methods=["POST"])
    def analyze_stream():
        """
        Endpoint to analyze user input with Server-Sent Events (SSE).

        The LLM result is returned as a **single** ``data:`` event after the model
        completes (not token-by-token streaming). See README for details.
        
        Same payload rules as ``/api/analyze`` (``skill_name`` or ``use_case_id`` with ``user_input``).

        Returns:
            Streamed response chunks as SSE.
        """
        (
            use_case_id,
            skill_name,
            user_input,
            input_params,
            uploaded_log_text,
            uploaded_file_name,
            uploaded_file_bytes,
            request_error,
        ) = parse_analyze_request()

        if request_error:
            return jsonify({"error": request_error}), 400

        if not user_input:
            return jsonify({"error": "Missing required field: user_input"}), 400

        skill_name, user_input, err_resp = resolve_analyze_target(
            use_case_id, skill_name, user_input
        )
        if err_resp:
            body, status = err_resp
            return body, status

        skill = find_skill_by_name(skill_name)
        if not skill:
            return jsonify({"error": f"Skill '{skill_name}' not found"}), 404

        # Build prompt
        skill_content = skill.get("full_content", "")

        tool_run = skill_runner.run_tool_if_configured(
            skill_name=skill_name,
            file_name=uploaded_file_name,
            file_bytes=uploaded_file_bytes,
            input_params=input_params,
        )

        prompt = build_prompt(skill_content, user_input, tool_run, uploaded_log_text, input_params)
        
        # Call LLM executor
        # Note: For now, we'll return the full result in chunks
        # Future: implement true streaming from the LLM API
        result = executor.ask_ai(prompt)
        
        def generate():
            """Generator function for SSE."""
            yield f"data: {json.dumps({'chunk': result})}\n\n"
        
        return Response(generate(), mimetype="text/event-stream"), 200
    
    return app


if __name__ == "__main__":
    import sys
    import os
    # Ensure project root is in sys.path when run directly as 'python src/app.py'
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
