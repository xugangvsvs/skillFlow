"""Tests for structured logging across executor, skill_runner, and app."""
import logging
import pytest
from unittest.mock import patch, MagicMock
from src.executor import CopilotExecutor
from src.skill_runner import SkillRunner


class TestExecutorLogging:
    def test_logs_api_call_start(self, caplog):
        with caplog.at_level(logging.INFO, logger="skillflow.executor"):
            with patch("requests.post") as mock_post:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": "ok"}}]
                }
                mock_post.return_value = mock_resp
                executor = CopilotExecutor(api_url="http://test", model="test-model")
                executor.ask_ai("prompt")
        assert any("LLM" in r.message or "calling" in r.message.lower() for r in caplog.records)

    def test_logs_connection_error(self, caplog):
        import requests
        with caplog.at_level(logging.WARNING, logger="skillflow.executor"):
            with patch("requests.post", side_effect=requests.exceptions.ConnectionError("conn failed")):
                executor = CopilotExecutor(api_url="http://test", model="test-model")
                result = executor.ask_ai("prompt")
        assert "ERROR" in result
        assert any("connect" in r.message.lower() or "error" in r.message.lower() for r in caplog.records)

    def test_logs_timeout(self, caplog):
        import requests
        with caplog.at_level(logging.WARNING, logger="skillflow.executor"):
            with patch("requests.post", side_effect=requests.exceptions.Timeout("timed out")):
                executor = CopilotExecutor(api_url="http://test", model="test-model")
                result = executor.ask_ai("prompt")
        assert "ERROR" in result
        assert any("timeout" in r.message.lower() for r in caplog.records)


class TestSkillRunnerLogging:
    def test_logs_tool_fallback_no_adapter(self, caplog, tmp_path):
        with caplog.at_level(logging.DEBUG, logger="skillflow.skill_runner"):
            runner = SkillRunner(adapter_path=str(tmp_path / "missing.yaml"))
            runner.run_tool_if_configured("analyze-ims2", file_name="f.ims2", file_bytes=b"123")
        assert any("fallback" in r.message.lower() or "no adapter" in r.message.lower() for r in caplog.records)

    def test_logs_tool_command_resolved(self, tmp_path, caplog):
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
        with caplog.at_level(logging.DEBUG, logger="skillflow.skill_runner"):
            runner = SkillRunner(adapter_path=str(adapter_file))
            runner.run_tool_if_configured("analyze-ims2", file_name="f.ims2", file_bytes=b"123")
        assert any(r.levelno >= logging.DEBUG for r in caplog.records if "skillflow" in r.name)


class TestAppRequestLogging:
    def test_analyze_endpoint_logs_request(self, caplog):
        import json
        from src.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            with caplog.at_level(logging.INFO, logger="skillflow.app"):
                with patch("src.executor.CopilotExecutor.ask_ai", return_value="ok"), \
                     patch("src.app.SkillRunner.run_tool_if_configured", return_value={
                         "mode": "fallback", "reason": "no_adapter",
                         "tool_output": "", "note": "no adapter",
                     }):
                    client.post("/api/analyze", json={
                        "skill_name": "analyze-ims2",
                        "user_input": "test",
                    })
        assert any("analyze-ims2" in r.message or "analyze" in r.message.lower() for r in caplog.records)
