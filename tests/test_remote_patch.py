"""Tests for unified diff validation (Phase 2)."""

from __future__ import annotations

import pytest

from src import remote_patch


def test_validate_unified_diff_ok() -> None:
    diff = """diff --git a/src/a.cpp b/src/a.cpp
--- a/src/a.cpp
+++ b/src/a.cpp
@@ -1 +1 @@
-old
+new
"""
    err, paths = remote_patch.validate_unified_diff(diff)
    assert err is None
    assert "src/a.cpp" in paths


def test_validate_rejects_parent_dir() -> None:
    diff = "+++ b/../../etc/passwd\n"
    err, paths = remote_patch.validate_unified_diff(diff)
    assert err is not None


def test_extract_diff_from_fence() -> None:
    text = """Here is the patch:
```diff
--- a/x.txt
+++ b/x.txt
@@ -1 +1 @@
-a
+b
```
Done.
"""
    body, perr = remote_patch.extract_diff_from_llm_response(text)
    assert perr is None
    assert body is not None
    assert "x.txt" in body


def test_extract_no_diff() -> None:
    body, perr = remote_patch.extract_diff_from_llm_response("NO_DIFF\nexplain")
    assert body is None
    assert perr == "no_diff"


def test_iteration_bounds() -> None:
    assert remote_patch.default_max_agent_iterations() >= 1
