"""Load optional ``config/skillflow.yaml``; merge with environment (env wins)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml


def load_skillflow_config(project_root: Path) -> dict[str, Any]:
    """Parse YAML config if present; return {} if file missing or invalid.

    Set ``SKILLFLOW_CONFIG`` to an absolute or project-relative path to use another file.
    """
    override = (os.environ.get("SKILLFLOW_CONFIG") or "").strip()
    if override:
        p = Path(override)
        cfg_path = p if p.is_absolute() else (project_root / p)
    else:
        cfg_path = project_root / "config" / "skillflow.yaml"

    if not cfg_path.is_file():
        return {}

    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return dict(data) if isinstance(data, dict) else {}


def pick_str(
    env_key: str,
    file_cfg: Mapping[str, Any],
    yaml_key: str,
    default: str = "",
) -> str:
    """Prefer environment variable, then YAML value, then ``default``."""
    raw_env = os.environ.get(env_key)
    if raw_env is not None and str(raw_env).strip():
        return str(raw_env).strip()
    v = file_cfg.get(yaml_key) if file_cfg is not None else None
    if v is not None and str(v).strip():
        return str(v).strip()
    return default
