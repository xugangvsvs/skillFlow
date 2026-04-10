from __future__ import annotations

from flask import Flask, g, jsonify, request, Response, send_from_directory
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple
try:
    from src.scanner import SkillScanner
    from src.llm_factory import create_llm_executor
    from src.skill_runner import SkillRunner
except ModuleNotFoundError:
    # Allow running directly as 'python src/app.py' from project root
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.scanner import SkillScanner
    from src.llm_factory import create_llm_executor
    from src.skill_runner import SkillRunner
import json
import logging
import os

from src.logging_context import CorrelationIdFilter, correlation_id_var, get_or_create_correlation_id
from src.skillflow_config import load_skillflow_config, pick_str
from src.gerrit_fetch import icfs_may_omit_user_text, maybe_append_gerrit_patch_to_user_input
from src.skill_paths import resolve_skill_repo_dir, supplement_dev_skills_dirs
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
    supplement_paths = supplement_dev_skills_dirs(project_root, skill_path, file_cfg)

    llm_url = pick_str("LLM_API_URL", file_cfg, "llm_api_url", _DEFAULT_LLM_API_URL)
    llm_model = pick_str("LLM_MODEL", file_cfg, "llm_model", _DEFAULT_LLM_MODEL)

    # Initialize scanner and executor at app startup
    scanner = SkillScanner(
        repo_path=str(skills_dir),
        gitlab_repo_url=(gitlab_repo_url or None),
        gitlab_branch=gitlab_branch,
        supplement_repo_paths=supplement_paths,
    )
    skills = scanner.scan()
    executor = create_llm_executor(
        project_root=project_root,
        llm_api_url=llm_url,
        llm_model=llm_model,
    )
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

    def _err_body_dict(body: Any) -> Dict[str, Any]:
        if hasattr(body, "get_json"):
            parsed = body.get_json(silent=True)
            if isinstance(parsed, dict):
                return parsed
        return {"error": "Request failed"}

    def iter_analyze_events() -> Iterator[Tuple[str, ...]]:
        """Shared analyze pipeline.

        Yields:
            (\"status\", message: str) — progress for SSE / logs
            (\"fail\", err_dict: dict, http_status: int)
            (\"done\", payload: dict) — same shape as ``/api/analyze`` JSON body
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
            yield ("fail", {"error": request_error}, 400)
            return

        if not (user_input or "").strip():
            if icfs_may_omit_user_text(use_case_id, input_params):
                user_input = (
                    "(No additional free-text instructions; Gerrit patch will be attached below.)"
                )
            else:
                yield ("fail", {"error": "Missing required field: user_input"}, 400)
                return
        else:
            user_input = (user_input or "").strip()

        skill_name, user_input, err_resp = resolve_analyze_target(
            use_case_id, skill_name, user_input
        )
        if err_resp:
            body, status = err_resp
            yield ("fail", _err_body_dict(body), status)
            return

        yield ("status", "Enriching prompt (Gerrit change patch, if configured)…")

        log.info(
            "analyze: Gerrit/prompt enrichment step starting (use_case_id=%s skill=%s)",
            use_case_id or "-",
            skill_name,
        )
        user_input, gerrit_warning = maybe_append_gerrit_patch_to_user_input(
            (use_case_id or "").strip(), user_input, input_params
        )
        log.info(
            "analyze: enrichment done user_input_len=%d gerrit_warning=%s",
            len(user_input),
            bool(gerrit_warning),
        )

        skill = find_skill_by_name(skill_name)
        if not skill:
            yield ("fail", {"error": f"Skill '{skill_name}' not found"}, 404)
            return

        yield ("status", f"Skill loaded: {skill_name}")

        skill_content = skill.get("full_content", "")

        tool_run = skill_runner.run_tool_if_configured(
            skill_name=skill_name,
            file_name=uploaded_file_name,
            file_bytes=uploaded_file_bytes,
            input_params=input_params,
        )

        note = (tool_run.get("note") or "").strip()
        if len(note) > 120:
            note = note[:117] + "…"
        tool_msg = f"Tool / adapter phase: {tool_run['mode']}"
        if note:
            tool_msg += f" — {note}"
        yield ("status", tool_msg)

        log.info(
            "analyze request: use_case_id=%s skill=%s mode=%s file=%s input_params_keys=%s input_len=%d",
            use_case_id or "-",
            skill_name,
            tool_run["mode"],
            uploaded_file_name or "none",
            sorted(input_params.keys()) if input_params else [],
            len(user_input),
        )

        prompt = build_prompt(
            skill_content, user_input, tool_run, uploaded_log_text, input_params
        )

        yield (
            "status",
            f"Invoking LLM / Cursor ({len(prompt)} chars; may take several minutes)…",
        )

        log.info("analyze: calling LLM executor prompt_len=%d", len(prompt))
        result = executor.ask_ai(prompt)
        log.info("analyze: LLM returned result_len=%d", len(result or ""))

        payload: Dict[str, Any] = {
            "result": result,
            "mode": tool_run["mode"],
            "execution_note": tool_run["note"],
        }
        if gerrit_warning:
            payload["gerrit_warning"] = gerrit_warning
        yield ("done", payload)

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
        for evt in iter_analyze_events():
            kind = evt[0]
            if kind == "status":
                log.info("analyze progress: %s", evt[1])
            elif kind == "fail":
                return jsonify(evt[1]), evt[2]
            elif kind == "done":
                return jsonify(evt[1]), 200
        return jsonify({"error": "Internal error: analyze pipeline produced no result"}), 500

    @app.route("/api/analyze/stream", methods=["POST"])
    def analyze_stream():
        """
        Analyze with Server-Sent Events (SSE).

        Emits ``type: status`` lines during the pipeline, then ``type: complete``
        with the same fields as ``/api/analyze`` (``result``, ``mode``,
        ``execution_note``, optional ``gerrit_warning``). The LLM answer is still
        one block after the model finishes (not token streaming).

        If the request fails before streaming starts (validation, unknown skill at
        resolve time, etc.), returns normal JSON with the same status codes as
        ``/api/analyze``. Mid-pipeline failures after the first SSE line use
        ``type: error`` on the stream.
        """
        pipeline = iter_analyze_events()
        first = next(pipeline, None)
        if first is None:
            return jsonify({"error": "Internal error: empty analyze pipeline"}), 500
        if first[0] == "fail":
            return jsonify(first[1]), first[2]

        def generate() -> Iterator[str]:
            evt: Tuple[Any, ...] = first
            while True:
                kind = evt[0]
                if kind == "status":
                    yield (
                        "data: "
                        + json.dumps({"type": "status", "message": evt[1]})
                        + "\n\n"
                    )
                elif kind == "fail":
                    err_obj: Dict[str, Any] = {"type": "error", "error": "Request failed"}
                    if isinstance(evt[1], dict) and evt[1].get("error"):
                        err_obj["error"] = evt[1]["error"]
                    err_obj["http_status"] = evt[2]
                    yield "data: " + json.dumps(err_obj) + "\n\n"
                    return
                elif kind == "done":
                    p: Dict[str, Any] = evt[1]
                    complete: Dict[str, Any] = {
                        "type": "complete",
                        "result": p["result"],
                        "mode": p["mode"],
                        "execution_note": p["execution_note"],
                    }
                    if "gerrit_warning" in p:
                        complete["gerrit_warning"] = p["gerrit_warning"]
                    yield "data: " + json.dumps(complete) + "\n\n"
                    return
                else:
                    log.error("analyze_stream: unknown pipeline event %r", evt)
                    yield (
                        "data: "
                        + json.dumps(
                            {"type": "error", "error": "Internal pipeline error"}
                        )
                        + "\n\n"
                    )
                    return
                try:
                    evt = next(pipeline)
                except StopIteration:
                    return

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        ), 200
    
    return app


if __name__ == "__main__":
    import sys
    import os
    # Ensure project root is in sys.path when run directly as 'python src/app.py'
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
