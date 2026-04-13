"""Tests for Cursor CLI LLM backend (mocked subprocess)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.cursor_cli_executor import (
    DEFAULT_CURSOR_CLI_MODEL,
    CursorCliExecutor,
    _cursor_cli_timeout_seconds,
    _resolve_cursor_cli_executable,
)


@pytest.fixture(autouse=True)
def _stable_cursor_cli_bin(mocker):
    """Pin resolved binary so tests expect ``cursor`` + subcommand ``agent``."""
    mocker.patch(
        "src.cursor_cli_executor._resolve_cursor_cli_executable",
        return_value="cursor",
    )


def test_cursor_cli_success(mocker, monkeypatch, tmp_path):
    monkeypatch.delenv("CURSOR_CLI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("LLM_HTTP_READ_TIMEOUT_SECONDS", "99")
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "argv_tail")
    monkeypatch.delenv("CURSOR_AGENT_EXTRA_ARGS_JSON", raising=False)
    monkeypatch.delenv("CURSOR_AGENT_EXTRA_ARGS", raising=False)

    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(
            returncode=0,
            stdout="## Done\nok",
            stderr="",
        ),
    )

    exe = CursorCliExecutor(model="x", project_root=tmp_path)
    out = exe.ask_ai("hello")

    assert out == "## Done\nok"
    mock_run.assert_called_once()
    _args, kwargs = mock_run.call_args
    assert kwargs.get("input") is None
    assert kwargs["cwd"] == str(tmp_path.resolve())
    assert kwargs["timeout"] == 120.0  # max(99, 120) from _cursor_cli_timeout_seconds
    argv = _args[0]
    assert argv[0] == "cursor"
    assert argv[1] == "agent"
    assert argv[-1] == "hello"


def test_cursor_cli_stdin_dash(mocker, monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "stdin_dash")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    )
    exe = CursorCliExecutor(project_root=tmp_path)
    exe.ask_ai("prompt text")
    args, kwargs = mock_run.call_args
    assert kwargs["input"] == "prompt text"
    assert args[0][-1] == "-"


def test_cursor_cli_timeout(mocker, monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "argv_tail")
    monkeypatch.setenv("CURSOR_CLI_TIMEOUT_SECONDS", "5")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="cursor", timeout=5),
    )
    exe = CursorCliExecutor(project_root=tmp_path)
    result = exe.ask_ai("x")
    assert "timed out" in result.lower()
    assert "CURSOR_CLI_TIMEOUT_SECONDS" in result


def test_cursor_cli_os_error(mocker, monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "argv_tail")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        side_effect=OSError("not found"),
    )
    exe = CursorCliExecutor(project_root=tmp_path)
    result = exe.ask_ai("x")
    assert "Could not start Cursor CLI" in result
    mock_run.assert_called_once()


def test_cursor_cli_nonzero_exit(mocker, monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "argv_tail")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="bad"),
    )
    exe = CursorCliExecutor(project_root=tmp_path)
    result = exe.ask_ai("x")
    assert "exited with code 1" in result
    assert "bad" in result


def test_cursor_cli_empty_stdout_uses_stderr(mocker, monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "argv_tail")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr="from stderr"),
    )
    exe = CursorCliExecutor(project_root=tmp_path)
    assert exe.ask_ai("x") == "from stderr"


def test_cursor_cli_extra_args_json(mocker, monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_AGENT_EXTRA_ARGS_JSON", '["--foo", "bar"]')
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "argv_tail")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    )
    exe = CursorCliExecutor(project_root=tmp_path)
    exe.ask_ai("z")
    argv = mock_run.call_args[0][0]
    assert argv[:4] == ["cursor", "agent", "--foo", "bar"]


def test_create_llm_factory_cursor(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLFLOW_LLM_BACKEND", "cursor_cli")
    from src.llm_factory import create_llm_executor
    from src.cursor_cli_executor import CursorCliExecutor

    ex = create_llm_executor(
        project_root=tmp_path,
        llm_api_url="http://ignore",
        llm_model="m",
    )
    assert isinstance(ex, CursorCliExecutor)


def test_create_llm_factory_http(monkeypatch, tmp_path):
    monkeypatch.delenv("SKILLFLOW_LLM_BACKEND", raising=False)
    from src.llm_factory import create_llm_executor
    from src.executor import CopilotExecutor

    ex = create_llm_executor(
        project_root=tmp_path,
        llm_api_url="http://x",
        llm_model="m",
    )
    assert isinstance(ex, CopilotExecutor)


def test_cursor_cli_timeout_helper(monkeypatch):
    monkeypatch.setenv("CURSOR_CLI_TIMEOUT_SECONDS", "77")
    assert _cursor_cli_timeout_seconds() == 77.0


def test_resolve_cursor_cli_executable_prefers_env(mocker, monkeypatch):
    mocker.stopall()  # disable autouse stable bin for this test
    monkeypatch.setenv("CURSOR_CLI_BIN", r"C:\custom\agent.exe")
    assert _resolve_cursor_cli_executable() == r"C:\custom\agent.exe"


def test_resolve_cursor_cli_executable_prefers_agent_when_both_exist(mocker, monkeypatch):
    mocker.stopall()

    def _which(cmd: str):
        return {"agent": r"C:\fake\agent.exe", "cursor": r"C:\fake\cursor.cmd"}.get(cmd)

    monkeypatch.delenv("CURSOR_CLI_BIN", raising=False)
    mocker.patch("src.cursor_cli_executor.shutil.which", side_effect=_which)
    assert _resolve_cursor_cli_executable() == r"C:\fake\agent.exe"


def test_resolve_cursor_cli_executable_falls_back_to_cursor_when_agent_missing(
    mocker, monkeypatch
):
    mocker.stopall()

    def _which(cmd: str):
        if cmd == "agent":
            return None
        if cmd == "cursor":
            return r"C:\fake\cursor.cmd"
        return None

    monkeypatch.delenv("CURSOR_CLI_BIN", raising=False)
    mocker.patch("src.cursor_cli_executor.shutil.which", side_effect=_which)
    assert _resolve_cursor_cli_executable() == r"C:\fake\cursor.cmd"


def test_standalone_agent_cli_omits_subcommand(mocker, monkeypatch, tmp_path):
    # Path basename must be ``agent`` so ``Path(...).stem == "agent"`` on Linux CI and Windows.
    fake_agent = "/tmp/skillflow-test-bin/agent"
    mocker.patch(
        "src.cursor_cli_executor._resolve_cursor_cli_executable",
        return_value=fake_agent,
    )
    monkeypatch.setenv("CURSOR_CLI_PROMPT_MODE", "stdin_dash")
    monkeypatch.delenv("CURSOR_CLI_SUBCOMMAND", raising=False)
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    )
    CursorCliExecutor(project_root=tmp_path).ask_ai("p")
    assert mock_run.call_args[0][0] == [fake_agent, "-"]


def test_headless_print_default_uses_p_and_workspace(mocker, monkeypatch, tmp_path):
    """Matches Cursor headless global options: -p, --output-format, --trust, --workspace."""
    mocker.patch(
        "src.cursor_cli_executor._resolve_cursor_cli_executable",
        return_value="cursor",
    )
    monkeypatch.delenv("CURSOR_CLI_PROMPT_MODE", raising=False)
    monkeypatch.delenv("CURSOR_AGENT_EXTRA_ARGS_JSON", raising=False)
    monkeypatch.delenv("CURSOR_AGENT_EXTRA_ARGS", raising=False)
    monkeypatch.delenv("CURSOR_CLI_NO_TRUST", raising=False)
    monkeypatch.delenv("CURSOR_CLI_MODEL", raising=False)
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    )
    exe = CursorCliExecutor(model="qwen-ignored", project_root=tmp_path)
    exe.ask_ai("short prompt")
    argv = mock_run.call_args[0][0]
    assert argv[:3] == ["cursor", "agent", "-p"]
    assert "--output-format" in argv and "text" in argv
    assert "--trust" in argv
    assert "--workspace" in argv
    ws_idx = argv.index("--workspace")
    assert argv[ws_idx + 1] == str(tmp_path.resolve())
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == DEFAULT_CURSOR_CLI_MODEL
    assert argv[-1] == "short prompt"


def test_headless_print_cursor_cli_model_overrides_default(mocker, monkeypatch, tmp_path):
    mocker.patch(
        "src.cursor_cli_executor._resolve_cursor_cli_executable",
        return_value="cursor",
    )
    monkeypatch.delenv("CURSOR_CLI_PROMPT_MODE", raising=False)
    monkeypatch.setenv("CURSOR_CLI_MODEL", "auto")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    )
    CursorCliExecutor(model="", project_root=tmp_path).ask_ai("hi")
    argv = mock_run.call_args[0][0]
    assert argv[argv.index("--model") + 1] == "auto"


def test_headless_print_large_prompt_uses_stdin(mocker, monkeypatch, tmp_path):
    mocker.patch(
        "src.cursor_cli_executor._resolve_cursor_cli_executable",
        return_value="cursor",
    )
    monkeypatch.delenv("CURSOR_CLI_PROMPT_MODE", raising=False)
    monkeypatch.setenv("CURSOR_CLI_MAX_ARGV_PROMPT_BYTES", "10")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    )
    CursorCliExecutor(model="", project_root=tmp_path).ask_ai("x" * 50)
    _a, kwargs = mock_run.call_args
    assert kwargs["input"] == "x" * 50
    assert mock_run.call_args[0][0][-1] == "-"


def test_headless_print_skips_trust_when_no_trust(mocker, monkeypatch, tmp_path):
    mocker.patch(
        "src.cursor_cli_executor._resolve_cursor_cli_executable",
        return_value="cursor",
    )
    monkeypatch.delenv("CURSOR_CLI_PROMPT_MODE", raising=False)
    monkeypatch.setenv("CURSOR_CLI_NO_TRUST", "1")
    mock_run = mocker.patch(
        "src.cursor_cli_executor.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="ok", stderr=""),
    )
    CursorCliExecutor(project_root=tmp_path).ask_ai("hi")
    argv = mock_run.call_args[0][0]
    assert "-p" in argv
    assert "--trust" not in argv
