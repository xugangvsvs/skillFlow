"""Unit tests for Phase-1 SSH remote runner (whitelisted nrm scripts)."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from src.remote_runner import (
    fix_host_allowlist_validation,
    remote_ssh_enabled,
    run_nrm_workflow_remote,
    validate_host,
    validate_safe_path,
)


def test_validate_safe_path_rejects_dotdot() -> None:
    assert validate_safe_path("work_dir", "/foo/../bar") is not None


def test_validate_safe_path_allows_repo_hyphen() -> None:
    assert validate_safe_path("repo_name", "netconf-agent") is None


def test_allowlist_suffix_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST", "linsee.dyn.nesc.nokia.net")
    assert validate_host("hzlinc01-boam.linsee.dyn.nesc.nokia.net") is None


def test_allowlist_dot_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST", ".linsee.example.net")
    assert validate_host("host.linsee.example.net") is None


def test_allowlist_rejects_unknown_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST", "linsee.dyn.nesc.nokia.net")
    assert validate_host("evil.com") is not None


def test_fix_host_allowlist_empty_means_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST", raising=False)
    assert fix_host_allowlist_validation("any.host.example") is None


def test_remote_ssh_enabled_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLFLOW_REMOTE_SSH_ENABLED", "1")
    assert remote_ssh_enabled() is True
    monkeypatch.setenv("SKILLFLOW_REMOTE_SSH_ENABLED", "0")
    assert remote_ssh_enabled() is False


@patch("src.remote_runner.subprocess.run")
def test_run_nrm_workflow_remote_success(
    mock_run: object,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SKILLFLOW_REMOTE_SSH_ENABLED", "1")
    monkeypatch.delenv("SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST", raising=False)
    key = tmp_path / "id_rsa"
    key.write_text("NOT_A_REAL_KEY", encoding="utf-8")
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="STATUS=OK\n", stderr=""
    )
    out, err = run_nrm_workflow_remote(
        host="build.example.net",
        ssh_user="me",
        identity_path=str(key),
        scripts_dir="$HOME/.copilot/skills/nrm-coding-workflow/scripts",
        work_dir="/data/ws",
        repo_name="netconf-agent",
        action="dev_status",
    )
    assert err is None
    assert out["returncode"] == 0
    assert out["stdout"] == "STATUS=OK\n"
    assert mock_run.called


def test_run_unknown_action(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLFLOW_REMOTE_SSH_ENABLED", "1")
    key = tmp_path / "k"
    key.write_text("x", encoding="utf-8")
    out, err = run_nrm_workflow_remote(
        host="h",
        ssh_user="u",
        identity_path=str(key),
        scripts_dir="$HOME/s",
        work_dir="/w",
        repo_name="r",
        action="dev_hack",
    )
    assert out == {}
    assert err and "Unknown action" in err
