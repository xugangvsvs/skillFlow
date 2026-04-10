"""Optional Gerrit REST fetch for ICFS use case (patch text for LLM context).

Disabled unless ``GERRIT_FETCH_ENABLED`` is truthy. Requires HTTP digest credentials
(``GERRIT_HTTP_USER`` / ``GERRIT_HTTP_PASSWORD``) for private servers.

Does not log passwords or full patch bodies.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests
from requests.auth import HTTPDigestAuth

log = logging.getLogger("skillflow.gerrit_fetch")

_DEFAULT_ALLOWLIST = "gerrit.ext.net.nokia.com"
_DEFAULT_TIMEOUT = 30
_DEFAULT_MAX_PATCH_BYTES = 384 * 1024

_BROWSER_GERRIT_C = re.compile(
    r"^https?://(?P<host>[^/]+)/(?:gerrit/)?c/(?P<proj>.+)/\+/(?P<num>\d+)/?\s*$",
    re.IGNORECASE,
)


def gerrit_fetch_enabled() -> bool:
    raw = (os.environ.get("GERRIT_FETCH_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _allowed_hosts() -> List[str]:
    raw = (os.environ.get("GERRIT_HOST_ALLOWLIST") or _DEFAULT_ALLOWLIST).strip()
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def _http_credentials() -> Optional[Tuple[str, str]]:
    user = (os.environ.get("GERRIT_HTTP_USER") or "").strip()
    password = (os.environ.get("GERRIT_HTTP_PASSWORD") or "").strip()
    if user and password:
        return user, password
    return None


def _max_patch_bytes() -> int:
    raw = (os.environ.get("GERRIT_PATCH_MAX_BYTES") or "").strip()
    if raw.isdigit():
        return max(4096, int(raw))
    return _DEFAULT_MAX_PATCH_BYTES


def _api_base_from_host(host: str) -> str:
    """Build https://host root (Gerrit REST lives under /a/)."""
    host = host.strip().lower()
    if "://" in host:
        parsed = urlparse(host)
        netloc = parsed.netloc or parsed.path
        scheme = parsed.scheme or "https"
        return f"{scheme}://{netloc}".rstrip("/")
    return f"https://{host}".rstrip("/")


def parse_gerrit_url(url: str) -> Optional[Dict[str, str]]:
    """Parse a browser-style Gerrit change URL into host, project, change number.

    Example:
        https://gerrit.ext.net.nokia.com/gerrit/c/MN/OAM/DOCS/boam/+/9818348
    """
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u.lower().startswith(("http://", "https://")):
        return None
    parsed = urlparse(u)
    path = (parsed.path or "").rstrip("/")
    # Strip query-only URLs that still match /c/.../+/N
    fake = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    m = _BROWSER_GERRIT_C.match(fake)
    if not m:
        return None
    return {
        "host": m.group("host").lower(),
        "project": m.group("proj").strip("/"),
        "change_num": m.group("num"),
        "scheme": parsed.scheme or "https",
    }


def _host_allowed(host: str) -> bool:
    h = host.lower().strip()
    return any(h == a or h.endswith("." + a) for a in _allowed_hosts())


def _strip_gerrit_json_prefix(text: str) -> str:
    if text.startswith(")]}'"):
        idx = text.find("\n")
        return text[idx + 1 :] if idx >= 0 else text[4:]
    return text


def _change_query(project: Optional[str], change_num: str) -> str:
    if project:
        return f"project:{project} change:{change_num}"
    return f"change:{change_num}"


def fetch_change_patch_text(
    *,
    host: str,
    project: Optional[str],
    change_num: str,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Tuple[str, Optional[str]]:
    """Fetch current revision unified patch text from Gerrit.

    Returns:
        (patch_or_empty, error_message). On success error_message is None.
    """
    if not _host_allowed(host):
        return "", f"Gerrit host {host!r} is not in GERRIT_HOST_ALLOWLIST"

    base = _api_base_from_host(host)
    creds = _http_credentials()
    if not creds:
        return "", "Gerrit fetch skipped: set GERRIT_HTTP_USER and GERRIT_HTTP_PASSWORD"

    auth = HTTPDigestAuth(creds[0], creds[1])
    q = _change_query(project, change_num)
    try:
        r = requests.get(
            f"{base}/a/changes/",
            params={"q": q, "n": 1},
            auth=auth,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        log.warning("Gerrit list changes request failed: %s", exc)
        return "", f"Gerrit request failed: {exc}"

    if r.status_code in (401, 403):
        log.warning("Gerrit auth failed for change query (HTTP %s)", r.status_code)
        return "", f"Gerrit returned HTTP {r.status_code} (check credentials and change access)"

    if r.status_code != 200:
        log.warning("Gerrit list changes HTTP %s", r.status_code)
        return "", f"Gerrit list changes failed: HTTP {r.status_code}"

    try:
        body = _strip_gerrit_json_prefix(r.text)
        data: Any = json.loads(body)
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Gerrit invalid JSON for change query: %s", exc)
        return "", "Gerrit returned invalid JSON for change list"

    if not isinstance(data, list) or not data:
        return "", "No Gerrit change matched the query"

    ch = data[0]
    if not isinstance(ch, dict):
        return "", "Unexpected Gerrit change list shape"

    change_id = ch.get("id")
    current_rev = ch.get("current_revision")
    if not change_id or not current_rev:
        return "", "Gerrit change missing id or current_revision"

    # ``id`` from Gerrit JSON is already URL-safe for the path segment.
    patch_url = f"{base}/a/changes/{change_id}/revisions/{current_rev}/patch"
    try:
        pr = requests.get(
            patch_url,
            params={"zip": "0"},
            auth=auth,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        log.warning("Gerrit patch request failed: %s", exc)
        return "", f"Gerrit patch request failed: {exc}"

    if pr.status_code != 200:
        log.warning("Gerrit patch HTTP %s", pr.status_code)
        return "", f"Gerrit patch failed: HTTP {pr.status_code}"

    patch_text = pr.text or ""
    max_b = _max_patch_bytes()
    truncated = False
    if len(patch_text.encode("utf-8")) > max_b:
        patch_text = patch_text.encode("utf-8")[:max_b].decode("utf-8", errors="ignore")
        truncated = True
        patch_text += f"\n\n...[patch truncated to ~{max_b} bytes for prompt size]...\n"

    note = ""
    if truncated:
        note = " (truncated)"
    log.info(
        "Gerrit patch fetched for change %s revision %s%s",
        change_num,
        str(current_rev)[:12],
        note,
    )
    return patch_text, None


def _params_from_numeric_change_id(change_num: str) -> Optional[Dict[str, str]]:
    """Use ``GERRIT_BASE_URL`` and optional ``GERRIT_DEFAULT_PROJECT`` when only a number is given."""
    if not change_num.isdigit():
        return None
    base_raw = (os.environ.get("GERRIT_BASE_URL") or "").strip()
    if not base_raw:
        return None
    if "://" not in base_raw:
        base_raw = f"https://{base_raw}"
    parsed = urlparse(base_raw)
    host = (parsed.netloc or "").strip().lower()
    if not host:
        return None
    proj = (os.environ.get("GERRIT_DEFAULT_PROJECT") or "").strip() or None
    return {"host": host, "project": proj, "change_num": change_num}


def extract_gerrit_fetch_params(input_params: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Derive host, project, change_num from ``gerrit_url`` or URL-like ``gerrit_change_id``."""
    url = (input_params.get("gerrit_url") or "").strip()
    cid = (input_params.get("gerrit_change_id") or "").strip()
    if url:
        parsed = parse_gerrit_url(url)
        if parsed:
            return {
                "host": parsed["host"],
                "project": parsed["project"],
                "change_num": parsed["change_num"],
            }
    if cid.lower().startswith(("http://", "https://")):
        parsed = parse_gerrit_url(cid)
        if parsed:
            return {
                "host": parsed["host"],
                "project": parsed["project"],
                "change_num": parsed["change_num"],
            }
    if cid.isdigit():
        return _params_from_numeric_change_id(cid)
    return None


def icfs_may_omit_user_text(use_case_id: str, input_params: Mapping[str, Any]) -> bool:
    """True when ICFS + fetch enabled + parsable Gerrit target (URL or numeric + base URL)."""
    if (use_case_id or "").strip() != "icfs-to-code-ut-sct":
        return False
    if not gerrit_fetch_enabled():
        return False
    params = dict(input_params) if input_params else {}
    return extract_gerrit_fetch_params(params) is not None


def maybe_append_gerrit_patch_to_user_input(
    use_case_id: str,
    user_input: str,
    input_params: Dict[str, Any],
) -> Tuple[str, Optional[str]]:
    """If ICFS + fetch enabled + parsable Gerrit params, append patch block to user input.

    Returns:
        (possibly_extended_user_input, client_warning_or_none)
    """
    if (use_case_id or "").strip() != "icfs-to-code-ut-sct":
        return user_input, None
    if not gerrit_fetch_enabled():
        return user_input, None

    spec = extract_gerrit_fetch_params(input_params)
    if not spec:
        return user_input, None

    patch, err = fetch_change_patch_text(
        host=spec["host"],
        project=spec.get("project"),
        change_num=spec["change_num"],
    )
    header = (
        "\n\n### Fetched from Gerrit\n\n"
        f"Change: {spec['change_num']} (project: {spec.get('project') or 'n/a'})\n\n"
    )
    if err:
        warn = f"Gerrit fetch: {err}"
        log.info("%s", warn)
        return (
            user_input
            + header
            + "[Could not fetch patch from Gerrit. Paste the ICFS/spec text above or fix credentials/network.]\n"
            + f"Details: {err}\n",
            warn,
        )

    return user_input + header + "```diff\n" + patch + "\n```\n", None
