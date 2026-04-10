"""Unit tests for optional Gerrit REST fetch (ICFS use case)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src import gerrit_fetch


def test_parse_gerrit_url_nokia_style() -> None:
    u = "https://gerrit.ext.net.nokia.com/gerrit/c/MN/OAM/DOCS/boam/+/9818348"
    p = gerrit_fetch.parse_gerrit_url(u)
    assert p is not None
    assert p["host"] == "gerrit.ext.net.nokia.com"
    assert p["project"] == "MN/OAM/DOCS/boam"
    assert p["change_num"] == "9818348"


def test_parse_gerrit_url_short_path() -> None:
    u = "https://review.example.com/c/my/project/+/42"
    p = gerrit_fetch.parse_gerrit_url(u)
    assert p is not None
    assert p["host"] == "review.example.com"
    assert p["project"] == "my/project"
    assert p["change_num"] == "42"


def test_parse_gerrit_url_rejects_non_url() -> None:
    assert gerrit_fetch.parse_gerrit_url("9818348") is None
    assert gerrit_fetch.parse_gerrit_url("") is None


def test_extract_params_from_gerrit_url_field() -> None:
    p = gerrit_fetch.extract_gerrit_fetch_params(
        {
            "gerrit_url": "https://gerrit.ext.net.nokia.com/gerrit/c/A/B/+/1",
        }
    )
    assert p is not None
    assert p["change_num"] == "1"
    assert p["project"] == "A/B"


def test_extract_params_change_id_as_url() -> None:
    p = gerrit_fetch.extract_gerrit_fetch_params(
        {
            "gerrit_change_id": "https://gerrit.ext.net.nokia.com/gerrit/c/X/+/9",
        }
    )
    assert p is not None
    assert p["change_num"] == "9"


def test_extract_params_numeric_with_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_BASE_URL", "https://gerrit.ext.net.nokia.com")
    monkeypatch.setenv("GERRIT_DEFAULT_PROJECT", "MN/OAM/DOCS/boam")
    p = gerrit_fetch.extract_gerrit_fetch_params({"gerrit_change_id": "9818348"})
    assert p is not None
    assert p["change_num"] == "9818348"
    assert p["host"] == "gerrit.ext.net.nokia.com"
    assert p["project"] == "MN/OAM/DOCS/boam"


def test_extract_params_numeric_without_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GERRIT_BASE_URL", raising=False)
    assert gerrit_fetch.extract_gerrit_fetch_params({"gerrit_change_id": "99"}) is None


def test_fetch_change_patch_text_rejects_host_not_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_HOST_ALLOWLIST", "gerrit.ext.net.nokia.com")
    text, err = gerrit_fetch.fetch_change_patch_text(
        host="evil.example.com", project="p", change_num="1"
    )
    assert text == ""
    assert err and "not in" in err.lower()


def test_fetch_change_patch_text_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_HOST_ALLOWLIST", "gerrit.ext.net.nokia.com")
    monkeypatch.delenv("GERRIT_HTTP_USER", raising=False)
    monkeypatch.delenv("GERRIT_HTTP_PASSWORD", raising=False)
    text, err = gerrit_fetch.fetch_change_patch_text(
        host="gerrit.ext.net.nokia.com", project="p", change_num="1"
    )
    assert text == ""
    assert err and "GERRIT_HTTP" in err


def test_fetch_change_patch_text_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_HOST_ALLOWLIST", "review.example.com")
    monkeypatch.setenv("GERRIT_HTTP_USER", "u")
    monkeypatch.setenv("GERRIT_HTTP_PASSWORD", "p")

    list_body = ")]}'\n" + json.dumps(
        [
            {
                "id": "proj%2Fdemo~master~Iabc",
                "current_revision": "deadbeef",
            }
        ]
    )
    patch_body = "diff --git a/x b/x\n"

    class FakeResp:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

    calls: list = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "/patch" in url:
            return FakeResp(200, patch_body)
        return FakeResp(200, list_body)

    with patch("src.gerrit_fetch.requests.get", side_effect=fake_get):
        text, err = gerrit_fetch.fetch_change_patch_text(
            host="review.example.com", project="demo", change_num="1"
        )

    assert err is None
    assert "diff --git" in text
    assert len(calls) == 2


def test_fetch_change_patch_text_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_HOST_ALLOWLIST", "review.example.com")
    monkeypatch.setenv("GERRIT_HTTP_USER", "u")
    monkeypatch.setenv("GERRIT_HTTP_PASSWORD", "p")
    monkeypatch.setenv("GERRIT_PATCH_MAX_BYTES", "5000")

    huge = "x" * 12000
    list_body = ")]}'\n" + json.dumps(
        [{"id": "p~m~I1", "current_revision": "a" * 40}],
    )

    def fake_get(url, **kwargs):
        if "/patch" in url:
            return type("R", (), {"status_code": 200, "text": huge})()
        return type("R", (), {"status_code": 200, "text": list_body})()

    with patch("src.gerrit_fetch.requests.get", side_effect=fake_get):
        text, err = gerrit_fetch.fetch_change_patch_text(
            host="review.example.com", project=None, change_num="1"
        )

    assert err is None
    assert "truncated" in text.lower()


def test_maybe_append_gerrit_patch_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GERRIT_FETCH_ENABLED", raising=False)
    out, w = gerrit_fetch.maybe_append_gerrit_patch_to_user_input(
        "icfs-to-code-ut-sct",
        "hello",
        {"gerrit_url": "https://gerrit.ext.net.nokia.com/gerrit/c/A/B/+/1"},
    )
    assert out == "hello"
    assert w is None


def test_maybe_append_gerrit_patch_inserts_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_FETCH_ENABLED", "1")
    monkeypatch.setenv("GERRIT_HOST_ALLOWLIST", "gerrit.ext.net.nokia.com")
    monkeypatch.setenv("GERRIT_HTTP_USER", "u")
    monkeypatch.setenv("GERRIT_HTTP_PASSWORD", "p")

    with patch(
        "src.gerrit_fetch.fetch_change_patch_text",
        return_value=("PATCH_BODY", None),
    ):
        out, w = gerrit_fetch.maybe_append_gerrit_patch_to_user_input(
            "icfs-to-code-ut-sct",
            "note",
            {
                "gerrit_url": "https://gerrit.ext.net.nokia.com/gerrit/c/P/+/2",
            },
        )

    assert w is None
    assert "Fetched from Gerrit" in out
    assert "PATCH_BODY" in out


def test_maybe_append_gerrit_patch_warns_on_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_FETCH_ENABLED", "1")
    with patch(
        "src.gerrit_fetch.fetch_change_patch_text",
        return_value=("", "network down"),
    ):
        out, w = gerrit_fetch.maybe_append_gerrit_patch_to_user_input(
            "icfs-to-code-ut-sct",
            "x",
            {"gerrit_url": "https://gerrit.ext.net.nokia.com/gerrit/c/P/+/2"},
        )
    assert w == "Gerrit fetch: network down"
    assert "Could not fetch patch" in out


def test_icfs_may_omit_user_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GERRIT_FETCH_ENABLED", "1")
    assert gerrit_fetch.icfs_may_omit_user_text(
        "icfs-to-code-ut-sct",
        {"gerrit_url": "https://gerrit.ext.net.nokia.com/gerrit/c/A/B/+/1"},
    )
    assert not gerrit_fetch.icfs_may_omit_user_text("efs-to-pfs", {"gerrit_url": "https://x/c/A/+/1"})
