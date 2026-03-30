from pathlib import Path
import os

import pytest

from src.skill_runner import SkillRunner


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
