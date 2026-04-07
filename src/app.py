from flask import Flask, g, jsonify, request, Response, send_from_directory
from pathlib import Path
from typing import Any, Dict, Optional
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

log = logging.getLogger("skillflow.app")


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
) -> Flask:
    """
    Factory function to create and configure the Flask application.
    
    Args:
        skill_path: Path to the dev-skills directory for skill discovery.
        When empty, falls back to GITLAB_REPO_URL env var (GitLab mode) or
        the local './dev-skills' directory.
    
    Returns:
        Configured Flask app instance.
    """
    configure_logging()

    project_root = Path(__file__).resolve().parent.parent
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

    # GitLab integration: read env vars for remote skill sync
    gitlab_repo_url: str = os.environ.get("GITLAB_REPO_URL", "")
    gitlab_branch: str = os.environ.get("GITLAB_BRANCH", "main")
    resolved_skill_path: str = skill_path or os.environ.get("SKILLS_PATH", "./dev-skills")

    # Initialize scanner and executor at app startup
    scanner = SkillScanner(
        repo_path=resolved_skill_path,
        gitlab_repo_url=gitlab_repo_url or None,
        gitlab_branch=gitlab_branch,
    )
    skills = scanner.scan()
    executor = CopilotExecutor()
    skill_runner = SkillRunner(adapter_path=adapter_path)
    
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
        skill_name = ""
        user_input = ""
        input_params: Dict[str, Any] = {}
        uploaded_log_text = ""
        uploaded_file_name = ""
        uploaded_file_bytes = b""

        if request.is_json:
            data = request.get_json(silent=True) or {}
            skill_name = (data.get("skill_name") or "").strip()
            user_input = (data.get("user_input") or "").strip()
            raw_params = data.get("input_params")
            if isinstance(raw_params, dict):
                input_params = raw_params
            return (
                skill_name,
                user_input,
                input_params,
                uploaded_log_text,
                uploaded_file_name,
                uploaded_file_bytes,
                None,
            )

        # Support multipart/form-data for file upload use cases.
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
            skill_name,
            user_input,
            input_params,
            uploaded_log_text,
            uploaded_file_name,
            uploaded_file_bytes,
            None,
        )
    
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
        Endpoint to analyze user input using a selected skill.
        
        Expected payload:
            {
                "skill_name": "analyze-ims2",
                "user_input": "text to analyze"
            }
        
        Returns:
            JSON with analysis result or error message.
        """
        (
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

        if not skill_name or not user_input:
            return jsonify({"error": "Missing required fields: skill_name, user_input"}), 400
        
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
            "analyze request: skill=%s mode=%s file=%s input_params_keys=%s input_len=%d",
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
        
        Expected payload:
            {
                "skill_name": "analyze-ims2",
                "user_input": "text to analyze"
            }
        
        Returns:
            Streamed response chunks as SSE.
        """
        (
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

        if not skill_name or not user_input:
            return jsonify({"error": "Missing required fields: skill_name, user_input"}), 400
        
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
