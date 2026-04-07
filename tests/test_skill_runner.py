from pathlib import Path
import os
from types import SimpleNamespace

import pytest

from src.skill_runner import SkillRunner, _select_args_list, _substitution_map
import src.skill_runner as skill_runner_module


def test_load_adapters_from_yaml(tmp_path: Path):
    adapter_file = tmp_path / "adapters.yaml"
    adapter_file.write_text(
        "skills:\n"
        "  analyze-ims2:\n"
        "    execution_mode: tool-first\n"
        "    tool:\n"
        "      command: ims2_tool\n"
        "      args_template: ['analyzer', '--input', '{log_file_path}']\n",
        encoding="utf-8",
    )

    runner = SkillRunner(adapter_path=str(adapter_file))
    adapter = runner.get_adapter("analyze-ims2")

    assert adapter is not None
    assert adapter["execution_mode"] == "tool-first"


def test_run_tool_returns_fallback_without_adapter(tmp_path: Path):
    runner = SkillRunner(adapter_path=str(tmp_path / "missing.yaml"))

    result = runner.run_tool_if_configured("analyze-ims2", file_name="a.ims2", file_bytes=b"123")

    assert result["mode"] == "fallback"
    assert "No adapter" in result["note"]


def test_run_tool_fallback_when_command_missing(tmp_path: Path):
    adapter_file = tmp_path / "adapters.yaml"
    adapter_file.write_text(
        "skills:\n"
        "  analyze-ims2:\n"
        "    execution_mode: tool-first\n"
        "    tool:\n"
        "      command: __missing_tool__\n"
        "      args_template: ['--input', '{log_file_path}']\n",
        encoding="utf-8",
    )

    runner = SkillRunner(adapter_path=str(adapter_file))
    result = runner.run_tool_if_configured("analyze-ims2", file_name="a.ims2", file_bytes=b"123")

    assert result["mode"] == "fallback"
    assert "could not be resolved" in result["note"].lower()


def test_resolve_tool_command_from_ims2_tool_path_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool_file = tmp_path / "ims2_tool"
    tool_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("IMS2_TOOL_PATH", str(tool_file))

    adapter_file = tmp_path / "adapters.yaml"
    adapter_file.write_text(
        "skills:\n"
        "  analyze-ims2:\n"
        "    execution_mode: tool-first\n"
        "    tool:\n"
        "      command: ims2_tool\n"
        "      command_candidates: ['${IMS2_TOOL_PATH}', 'ims2_tool']\n"
        "      args_template: ['--input', '{log_file_path}']\n",
        encoding="utf-8",
    )

    runner = SkillRunner(adapter_path=str(adapter_file))
    adapter = runner.get_adapter("analyze-ims2")
    resolved = runner._resolve_tool_command(adapter.get("tool") or {})

    assert resolved == str(tool_file)


def test_resolve_tool_command_by_auto_discovery(tmp_path: Path):
    auto_root = tmp_path / "tools"
    nested = auto_root / "imsParser"
    nested.mkdir(parents=True)
    discovered_tool = nested / "ims2_tool.exe"
    discovered_tool.write_text("", encoding="utf-8")

    adapter_file = tmp_path / "adapters.yaml"
    adapter_file.write_text(
        "skills:\n"
        "  analyze-ims2:\n"
        "    execution_mode: tool-first\n"
        "    tool:\n"
        "      command: ims2_tool\n"
        "      command_candidates: ['ims2_tool']\n"
        "      args_template: ['--input', '{log_file_path}']\n",
        encoding="utf-8",
    )

    runner = SkillRunner(adapter_path=str(adapter_file), search_roots=[str(auto_root)])
    adapter = runner.get_adapter("analyze-ims2")
    resolved = runner._resolve_tool_command(adapter.get("tool") or {})

    assert resolved == str(discovered_tool)


def test_select_args_list_uses_mode_from_input_params():
    tool_cfg = {
        "mode_param": "analysis_mode",
        "args_by_mode": {
            "topology": ["--input", "{log_file_path}", "analyzer"],
            "state": ["--input", "{log_file_path}", "query", "-r", "{focus_object}"],
        },
    }
    topo = _select_args_list(tool_cfg, {"analysis_mode": "topology"})
    assert topo[-1] == "analyzer"
    state = _select_args_list(tool_cfg, {"analysis_mode": "state"})
    assert "query" in state


def test_select_args_list_unknown_mode_falls_back_to_topology():
    tool_cfg = {
        "mode_param": "analysis_mode",
        "args_by_mode": {
            "topology": ["top-arg"],
            "state": ["state-arg"],
        },
    }
    out = _select_args_list(tool_cfg, {"analysis_mode": "not-a-real-mode"})
    assert out == ["top-arg"]


def test_substitution_map_includes_input_params_and_default_focus():
    m = _substitution_map("/tmp/x.ims2", "snap.ims2", {"analysis_mode": "state", "focus_object": "RMOD.*"})
    assert m["log_file_path"] == "/tmp/x.ims2"
    assert m["file_name"] == "snap.ims2"
    assert m["analysis_mode"] == "state"
    assert m["focus_object"] == "RMOD.*"


def test_substitution_map_default_focus_when_missing():
    m = _substitution_map("/tmp/a", "a.ims2", {"analysis_mode": "transitions"})
    assert m["focus_object"] == ".*"


def test_run_tool_builds_cmd_from_args_by_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool_dir = tmp_path / "bin"
    tool_dir.mkdir()
    tool_cmd = tool_dir / "ims2_tool.exe"
    tool_cmd.write_text("", encoding="utf-8")

    adapter_file = tmp_path / "adapters.yaml"
    adapter_file.write_text(
        "skills:\n"
        "  analyze-ims2:\n"
        "    execution_mode: tool-first\n"
        "    tool:\n"
        "      command: ims2_tool\n"
        "      mode_param: analysis_mode\n"
        "      args_by_mode:\n"
        "        topology: ['--input', '{log_file_path}', 'analyzer']\n"
        "        state: ['--input', '{log_file_path}', 'query', '-r', '{focus_object}', '-m', 'last']\n",
        encoding="utf-8",
    )

    runner = SkillRunner(adapter_path=str(adapter_file))
    monkeypatch.setattr(runner, "_resolve_tool_command", lambda _: str(tool_cmd))

    captured = {}

    def fake_run(cmd, capture_output, text, timeout, shell, cwd, env):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(skill_runner_module.subprocess, "run", fake_run)

    runner.run_tool_if_configured(
        "analyze-ims2",
        file_name="s.ims2",
        file_bytes=b"123",
        input_params={"analysis_mode": "state", "focus_object": "CELL_M-1"},
    )

    assert "query" in captured["cmd"]
    assert "CELL_M-1" in captured["cmd"]
    assert any(str(x).endswith(".ims2") for x in captured["cmd"])


def test_run_tool_uses_tool_dir_as_cwd_and_enables_rust_backtrace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tool_dir = tmp_path / "imsParser"
    tool_dir.mkdir(parents=True)
    tool_cmd = tool_dir / "ims2_tool.exe"
    tool_cmd.write_text("", encoding="utf-8")

    adapter_file = tmp_path / "adapters.yaml"
    adapter_file.write_text(
        "skills:\n"
        "  analyze-ims2:\n"
        "    execution_mode: tool-first\n"
        "    tool:\n"
        "      command: ims2_tool\n"
        "      args_template: ['--input', '{log_file_path}', 'analyzer']\n",
        encoding="utf-8",
    )

    runner = SkillRunner(adapter_path=str(adapter_file))
    monkeypatch.setattr(runner, "_resolve_tool_command", lambda _: str(tool_cmd))

    captured = {}

    def fake_run(cmd, capture_output, text, timeout, shell, cwd, env):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        return SimpleNamespace(returncode=1, stdout="", stderr="thread 'main' panicked")

    monkeypatch.setattr(skill_runner_module.subprocess, "run", fake_run)

    result = runner.run_tool_if_configured(
        "analyze-ims2",
        file_name="sample.ims2",
        file_bytes=b"123",
    )

    assert result["mode"] == "fallback"
    assert result["reason"] == "tool_error"
    assert captured["cwd"] == str(tool_dir)
    assert captured["env"]["RUST_BACKTRACE"] == "1"
