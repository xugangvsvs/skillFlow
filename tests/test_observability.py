"""Tests for /health, correlation id, and SKILLFLOW_LOG_LEVEL."""

import json
import logging
from unittest.mock import patch

import pytest

from src.app import configure_logging, create_app


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_correlation_id_echoed_on_response_header(client):
    response = client.get("/health", headers={"X-Request-ID": "client-req-99"})
    assert response.headers.get("X-Request-ID") == "client-req-99"


def test_correlation_id_from_alternate_header(client):
    response = client.get("/health", headers={"X-Correlation-ID": "corr-88"})
    assert response.headers.get("X-Request-ID") == "corr-88"


def test_analyze_logs_contain_correlation_id(client, caplog):
    with patch("src.app.CopilotExecutor.ask_ai", return_value="ok"), patch(
        "src.app.SkillRunner.run_tool_if_configured",
        return_value={
            "mode": "fallback",
            "reason": "no_adapter",
            "tool_output": "",
            "note": "no adapter",
        },
    ):
        with caplog.at_level(logging.INFO, logger="skillflow.app"):
            client.post(
                "/api/analyze",
                json={"skill_name": "analyze-ims2", "user_input": "x"},
                headers={"X-Request-ID": "trace-abc"},
            )
    assert any(getattr(r, "correlation_id", None) == "trace-abc" for r in caplog.records)


def test_configure_logging_reads_skillflow_log_level(monkeypatch):
    monkeypatch.setenv("SKILLFLOW_LOG_LEVEL", "DEBUG")
    root = logging.getLogger("skillflow")
    root.handlers.clear()
    configure_logging()
    assert root.level == logging.DEBUG
