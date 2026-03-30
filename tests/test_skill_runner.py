from pathlib import Path

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
    assert "not found" in result["note"].lower()
