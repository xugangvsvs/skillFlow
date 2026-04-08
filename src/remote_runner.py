"""Phase-1 remote execution: SSH to LinSee and run whitelisted nrm-coding-workflow scripts.

Disabled unless ``SKILLFLOW_REMOTE_SSH_ENABLED`` is truthy. Requires OpenSSH client
(``ssh``) on the SkillFlow host and a deployable private key (``SKILLFLOW_REMOTE_SSH_IDENTITY``).
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("skillflow.remote_runner")

# Whitelisted actions → script basename under remote scripts directory.
NRM_WORKFLOW_ACTIONS: Dict[str, str] = {
    "dev_status": "dev-status.sh",
    "dev_build": "dev-build.sh",
    "dev_ut": "dev-ut.sh",
}

# Safe path segments for remote work_dir, repo_name, scripts_dir (no shell metacharacters).
_SAFE_PATH_RE = re.compile(r"^[/A-Za-z0-9_.$+~-]+$")
_MAX_PATH_LEN = 512


def remote_ssh_enabled() -> bool:
    raw = (os.environ.get("SKILLFLOW_REMOTE_SSH_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _truthy_env(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def default_ssh_user() -> str:
    return (os.environ.get("SKILLFLOW_REMOTE_SSH_USER") or "").strip()


def default_identity_path() -> str:
    return (os.environ.get("SKILLFLOW_REMOTE_SSH_IDENTITY") or "").strip()


def default_scripts_dir() -> str:
    return (
        os.environ.get("SKILLFLOW_REMOTE_NRM_SCRIPTS") or ""
    ).strip() or "$HOME/.copilot/skills/nrm-coding-workflow/scripts"


def default_timeout_sec(action: str) -> int:
    raw = (os.environ.get("SKILLFLOW_REMOTE_SSH_TIMEOUT_SEC") or "").strip()
    if raw.isdigit():
        return max(30, int(raw))
    if action == "dev_status":
        return 300
    return 3600


def host_allowlist() -> List[str]:
    raw = (os.environ.get("SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST") or "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def validate_safe_path(name: str, value: str) -> Optional[str]:
    if not value or len(value) > _MAX_PATH_LEN:
        return f"{name} is missing or too long"
    if not _SAFE_PATH_RE.match(value):
        return f"{name} contains disallowed characters"
    if ".." in value:
        return f"{name} must not contain '..'"
    return None


def fix_host_allowlist_validation(host: str) -> Optional[str]:
    """Return None if host passes allowlist, else an error message."""
    patterns = host_allowlist()
    if not patterns:
        return None
    for raw in patterns:
        p = raw.strip()
        if not p:
            continue
        if host == p:
            return None
        if p.startswith(".") and host.endswith(p):
            return None
        if not p.startswith(".") and host.endswith("." + p):
            return None
    return "linsee_ssh_host is not allowed by SKILLFLOW_REMOTE_SSH_HOST_ALLOWLIST"


def validate_host(host: str) -> Optional[str]:
    host = (host or "").strip()
    if not host or len(host) > 253:
        return "linsee_ssh_host is missing or invalid"
    if not re.match(r"^[a-zA-Z0-9._-]+$", host):
        return "linsee_ssh_host has invalid characters"
    return fix_host_allowlist_validation(host)


def build_ssh_command(
    host: str,
    ssh_user: str,
    identity_path: str,
    remote_bash_lc: str,
) -> List[str]:
    cmd: List[str] = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={os.environ.get('SKILLFLOW_REMOTE_SSH_CONNECT_TIMEOUT', '30')}",
    ]
    if _truthy_env("SKILLFLOW_REMOTE_SSH_USE_KNOWN_HOSTS_ONLY"):
        cmd[cmd.index("StrictHostKeyChecking=accept-new")] = "StrictHostKeyChecking=yes"
    if identity_path:
        cmd.extend(["-i", identity_path])
    target = f"{ssh_user}@{host}" if ssh_user else host
    cmd.extend([target, "bash", "-lc", remote_bash_lc])
    return cmd


def run_nrm_workflow_remote(
    *,
    host: str,
    ssh_user: str,
    identity_path: str,
    scripts_dir: str,
    work_dir: str,
    repo_name: str,
    action: str,
    ut_test_filter: str = "*",
    timeout_sec: Optional[int] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Run one whitelisted script on the remote host via SSH.

    Returns (result_dict, error_message). error_message set on validation or transport failure.
    """
    if not remote_ssh_enabled():
        return {}, "Remote SSH is disabled (set SKILLFLOW_REMOTE_SSH_ENABLED=1)"

    script_file = NRM_WORKFLOW_ACTIONS.get(action)
    if not script_file:
        return {}, f"Unknown action {action!r}; allowed: {sorted(NRM_WORKFLOW_ACTIONS)}"

    err = validate_host(host)
    if err:
        return {}, err

    for label, val in (
        ("work_dir", work_dir),
        ("repo_name", repo_name),
        ("scripts_dir", scripts_dir),
    ):
        e2 = validate_safe_path(label, val)
        if e2:
            return {}, e2

    if not ssh_user:
        return {}, "ssh_user is missing (set SKILLFLOW_REMOTE_SSH_USER or pass ssh_user in the request)"

    if not identity_path or not os.path.isfile(identity_path):
        return (
            {},
            "SSH identity file missing (set SKILLFLOW_REMOTE_SSH_IDENTITY to a readable private key path)",
        )

    script_path = f"{scripts_dir.rstrip('/')}/{script_file}"
    wd = shlex.quote(work_dir)
    rn = shlex.quote(repo_name)
    sp = script_path  # may contain $HOME — do not shlex.quote so shell expands

    if action == "dev_ut":
        filt = shlex.quote(ut_test_filter or "*")
        inner = f"exec {sp} {wd} {rn} {filt}"
    else:
        inner = f"exec {sp} {wd} {rn}"

    cmd = build_ssh_command(host, ssh_user, identity_path, inner)
    log.info("remote_runner: action=%s host=%s user=%s", action, host, ssh_user)
    timeout = timeout_sec if timeout_sec is not None else default_timeout_sec(action)

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err_b = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return {
            "action": action,
            "host": host,
            "returncode": -1,
            "timed_out": True,
            "stdout": out,
            "stderr": err_b or f"SSH timed out after {timeout}s",
        }, None

    except FileNotFoundError:
        return {}, "ssh executable not found; install OpenSSH client on the SkillFlow host"

    except OSError as exc:
        return {}, f"Failed to run ssh: {exc}"

    return {
        "action": action,
        "host": host,
        "returncode": completed.returncode,
        "timed_out": False,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }, None
