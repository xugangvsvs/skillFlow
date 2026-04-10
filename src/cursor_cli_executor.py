"""Run Cursor terminal agent via subprocess (optional SkillFlow LLM backend).

Default invocation follows Cursor headless docs: ``-p`` / ``--print``, ``--output-format``,
``--trust``, ``--workspace`` (see https://cursor.com/docs/cli/headless ).

Does not pass ``--force`` / ``--yolo`` from SkillFlow (no auto-approved writes).
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from src.executor import llm_request_timeout

log = logging.getLogger("skillflow.cursor_cli")

# Cursor agent CLI model id (not LLM_MODEL / DashScope). Override with CURSOR_CLI_MODEL.
DEFAULT_CURSOR_CLI_MODEL = "composer-2"


def _resolve_cursor_cli_executable() -> str:
    """Executable path or name for the Cursor / Agent CLI.

    If ``CURSOR_CLI_BIN`` is unset, use the first found on ``PATH``: **``agent``**
    then ``cursor``. On Windows, ``cursor`` is often the IDE/Electron launcher; it
    does not handle ``-p`` / headless flags (you see "passed to Electron/Chromium").
    The standalone **Cursor CLI** is typically invoked as ``agent``.
    """
    env = (os.environ.get("CURSOR_CLI_BIN") or "").strip()
    if env:
        return env
    for cand in ("agent", "cursor"):
        found = shutil.which(cand)
        if found:
            log.info("Resolved Cursor CLI to %s (via which(%r))", found, cand)
            if cand == "cursor":
                log.warning(
                    "Only the IDE `cursor` launcher was found on PATH (no `agent`). "
                    "Headless flags (-p, --print) are often ignored and passed to Electron — "
                    "install the Cursor **agent** CLI, put `agent` on PATH before `cursor`, "
                    "or set CURSOR_CLI_BIN to the real agent executable."
                )
            return found
    return "agent"


def _effective_subcommand(bin_path: str) -> Optional[str]:
    """Subcommand after the binary, or ``None`` when using the standalone ``agent`` CLI.

    Standalone ``agent`` (``agent --version``) does not use ``agent`` as a second
    token; IDE-style launchers use ``cursor agent ...``.

    Override with ``CURSOR_CLI_SUBCOMMAND`` (set to empty to force no subcommand).
    """
    raw = os.environ.get("CURSOR_CLI_SUBCOMMAND")
    if raw is not None:
        s = raw.strip()
        return s if s else None
    stem = Path(bin_path).stem.lower()
    if stem == "agent":
        return None
    return "agent"


def _cursor_cli_timeout_seconds() -> float:
    raw = (os.environ.get("CURSOR_CLI_TIMEOUT_SECONDS") or "").strip()
    if raw:
        try:
            return max(10.0, float(raw))
        except ValueError:
            pass
    _, read = llm_request_timeout()
    # Agent runs are usually slower than a single chat completion.
    return max(float(read), 120.0)


def _headless_print_flags(workspace: Path) -> List[str]:
    """Global options for non-interactive ``--print`` runs (before the prompt).

    ``--model`` uses ``CURSOR_CLI_MODEL`` when set, otherwise ``DEFAULT_CURSOR_CLI_MODEL`` (``composer-2``).
    ``LLM_MODEL`` is for the HTTP backend only and is never passed here.
    """
    fmt = (os.environ.get("CURSOR_CLI_OUTPUT_FORMAT") or "text").strip().lower()
    if fmt not in ("text", "json", "stream-json"):
        log.warning("CURSOR_CLI_OUTPUT_FORMAT=%r invalid; using text", fmt)
        fmt = "text"
    parts: List[str] = ["-p", "--output-format", fmt]
    no_trust = (os.environ.get("CURSOR_CLI_NO_TRUST") or "").strip().lower()
    if no_trust not in ("1", "true", "yes", "on"):
        parts.append("--trust")
    parts.extend(["--workspace", str(workspace.resolve())])
    cli_model = (os.environ.get("CURSOR_CLI_MODEL") or "").strip() or DEFAULT_CURSOR_CLI_MODEL
    parts.extend(["--model", cli_model])
    return parts


def _max_argv_prompt_bytes() -> int:
    raw = (os.environ.get("CURSOR_CLI_MAX_ARGV_PROMPT_BYTES") or "").strip()
    if raw:
        try:
            v = int(raw)
            return max(1, min(v, 2_000_000))
        except ValueError:
            pass
    return 28000


def _parse_extra_args() -> List[str]:
    j = (os.environ.get("CURSOR_AGENT_EXTRA_ARGS_JSON") or "").strip()
    if j:
        try:
            parsed = json.loads(j)
        except json.JSONDecodeError as exc:
            log.warning("CURSOR_AGENT_EXTRA_ARGS_JSON is not valid JSON: %s", exc)
            return []
        if not isinstance(parsed, list):
            log.warning("CURSOR_AGENT_EXTRA_ARGS_JSON must be a JSON array of strings")
            return []
        return [str(x) for x in parsed]
    line = (os.environ.get("CURSOR_AGENT_EXTRA_ARGS") or "").strip()
    if not line:
        return []
    return shlex.split(line, posix=os.name != "nt")


def _build_argv_and_input(
    prompt: str,
    *,
    workspace: Path,
) -> Tuple[List[str], Optional[str], Optional[Path]]:
    """Return (argv, stdin_text, temp_path_to_unlink).

    ``temp_path_to_unlink`` is set when a temp file was created for the prompt.
    """
    bin_name = _resolve_cursor_cli_executable()
    sub = _effective_subcommand(bin_name)
    extra = _parse_extra_args()
    base = [bin_name] + ([sub] if sub else []) + extra
    mode = (os.environ.get("CURSOR_CLI_PROMPT_MODE") or "headless_print").strip().lower()

    if mode in ("headless_print", "print"):
        mid = base + _headless_print_flags(workspace)
        if len(prompt.encode("utf-8")) <= _max_argv_prompt_bytes():
            return (mid + [prompt], None, None)
        return (mid + ["-"], prompt, None)

    if mode == "stdin_dash":
        return (base + ["-"], prompt, None)

    if mode == "argv_tail":
        return (base + [prompt], None, None)

    if mode == "atfile":
        fd, path = tempfile.mkstemp(prefix="skillflow_cursor_", suffix=".txt", text=True)
        os.close(fd)
        p = Path(path)
        p.write_text(prompt, encoding="utf-8")
        return (base + [f"@{path}"], None, p)

    if mode == "file_positional":
        fd, path = tempfile.mkstemp(prefix="skillflow_cursor_", suffix=".txt", text=True)
        os.close(fd)
        p = Path(path)
        p.write_text(prompt, encoding="utf-8")
        return (base + [str(p)], None, p)

    log.warning("Unknown CURSOR_CLI_PROMPT_MODE=%r; using headless_print", mode)
    mid = base + _headless_print_flags(workspace)
    if len(prompt.encode("utf-8")) <= _max_argv_prompt_bytes():
        return (mid + [prompt], None, None)
    return (mid + ["-"], prompt, None)


class CursorCliExecutor:
    """LLM backend that shells out to ``cursor agent`` or standalone ``agent`` CLI."""

    def __init__(self, model: str = "", project_root: Optional[Path] = None) -> None:
        self.model = model
        self.project_root = Path(project_root or os.getcwd()).resolve()

    def ask_ai(self, prompt: str) -> str:
        timeout = _cursor_cli_timeout_seconds()
        cwd = (os.environ.get("CURSOR_CLI_WORKDIR") or "").strip()
        workspace = Path(cwd).resolve() if cwd else self.project_root
        run_cwd = str(workspace)
        argv, stdin_text, tmp_path = _build_argv_and_input(prompt, workspace=workspace)

        log.info(
            "Calling Cursor CLI: argv0=%s len=%d cwd=%s timeout=%s prompt_len=%d",
            argv[0],
            len(argv),
            run_cwd,
            timeout,
            len(prompt),
        )

        env = os.environ.copy()

        tmp_to_clean: Optional[Path] = tmp_path
        try:
            proc = subprocess.run(
                argv,
                input=stdin_text,
                text=True,
                cwd=run_cwd,
                env=env,
                timeout=timeout,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            log.warning("Cursor CLI subprocess timed out after %ss", timeout)
            return (
                "ERROR: Cursor CLI timed out. "
                "Increase CURSOR_CLI_TIMEOUT_SECONDS or LLM_HTTP_READ_TIMEOUT_SECONDS."
            )
        except OSError as exc:
            log.warning("Cursor CLI failed to start: %s", exc)
            return f"ERROR: Could not start Cursor CLI ({argv[0]}): {exc}"
        finally:
            if tmp_to_clean is not None:
                try:
                    tmp_to_clean.unlink(missing_ok=True)
                except OSError:
                    pass

        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            log.warning(
                "Cursor CLI exit=%s stderr_len=%d stdout_len=%d",
                proc.returncode,
                len(err),
                len(out),
            )
            tail = (err or out)[:1200]
            return f"ERROR: Cursor CLI exited with code {proc.returncode}: {tail}"

        if not out and err:
            # Some builds log the answer to stderr
            out = err
        if not out:
            return (
                "ERROR: Cursor CLI returned no stdout text. "
                "Check headless mode (-p) and CURSOR_API_KEY; try CURSOR_CLI_OUTPUT_FORMAT=json or "
                "legacy CURSOR_CLI_PROMPT_MODE=stdin_dash (see README / cursor.com/docs/cli/headless)."
            )
        log.info("Cursor CLI response: result_len=%d", len(out))
        return out
