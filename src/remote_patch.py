"""Unified diff validation for Phase-2 remote ``git apply`` (LinSee)."""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

# Max patch payload (UTF-8 bytes).
_MAX_PATCH_BYTES = int(os.environ.get("SKILLFLOW_REMOTE_PATCH_MAX_BYTES", str(512 * 1024)))

_DIFF_FENCE_RE = re.compile(r"```(?:diff)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def max_patch_bytes() -> int:
    return max(4096, _MAX_PATCH_BYTES)


def validate_unified_diff_size(diff: str) -> Optional[str]:
    if not diff or not diff.strip():
        return "unified_diff is empty"
    raw = diff.encode("utf-8", errors="strict")
    if len(raw) > max_patch_bytes():
        return f"unified_diff exceeds max size ({max_patch_bytes()} bytes)"
    return None


def reject_disallowed_patch_content(diff: str) -> Optional[str]:
    if "\x00" in diff:
        return "binary content is not allowed in unified_diff"
    if "GIT binary patch" in diff or "literal " in diff and "zlib" in diff:
        return "git binary patches are not supported"
    return None


def extract_paths_from_unified_diff(diff: str) -> List[str]:
    """Collect relative paths from unified diff headers (git format)."""
    seen: List[str] = []
    dup: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith("+++ "):
            continue
        rest = line[4:].strip()
        if rest == "/dev/null":
            continue
        if rest.startswith("b/"):
            p = rest[2:].lstrip("/")
        elif rest.startswith("a/"):
            p = rest[2:].lstrip("/")
        else:
            p = rest.lstrip("/")
        if p and p not in dup:
            dup.add(p)
            seen.append(p)
    return seen


def relative_repo_path_is_safe(path: str) -> bool:
    p = path.replace("\\", "/").strip()
    if not p or p.startswith("/"):
        return False
    parts = [x for x in p.split("/") if x != ""]
    if ".." in parts:
        return False
    return bool(parts)


def validate_patch_paths(paths: List[str]) -> Optional[str]:
    if not paths:
        return "no file paths found in unified_diff (expected git-style +++ b/... headers)"
    for p in paths:
        if not relative_repo_path_is_safe(p):
            return f"unsafe or absolute path in diff: {p!r}"
    return None


def validate_unified_diff(diff: str) -> Tuple[Optional[str], List[str]]:
    """Return (error_message, paths) — error_message is None if OK."""
    err = validate_unified_diff_size(diff)
    if err:
        return err, []
    err = reject_disallowed_patch_content(diff)
    if err:
        return err, []
    paths = extract_paths_from_unified_diff(diff)
    err = validate_patch_paths(paths)
    if err:
        return err, paths
    return None, paths


def extract_diff_from_llm_response(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse LLM output: return (diff_or_none, error_or_none).

    If the model returns NO_DIFF, returns (None, None) with caller checking prefix.
    """
    stripped = (text or "").strip()
    if stripped.upper().startswith("NO_DIFF"):
        return None, "no_diff"
    m = _DIFF_FENCE_RE.search(text)
    if not m:
        return None, "no_diff_fence"
    body = m.group(1).strip()
    if not body:
        return None, "empty_fence"
    return body, None


def default_max_agent_iterations() -> int:
    """Upper bound (exclusive) for ``iteration_index``: valid indices are ``0 .. max-1``."""
    raw = (os.environ.get("SKILLFLOW_REMOTE_AGENT_MAX_ITERATIONS") or "").strip()
    if raw.isdigit():
        return max(1, min(50, int(raw)))
    return 8


def suggest_patch_enabled() -> bool:
    raw = (os.environ.get("SKILLFLOW_REMOTE_SUGGEST_PATCH_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")
