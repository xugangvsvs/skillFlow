"""Resolve the on-disk directory for SKILL.md discovery (local or GitLab clone target)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from src.skillflow_config import pick_str


def resolve_skill_repo_dir(
    project_root: Path,
    skill_path_override: str = "",
    file_cfg: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Resolve the directory that holds SKILL.md trees (clone target when using GitLab).

    Order of precedence:
    1. Non-empty ``skill_path_override`` (tests or ``create_app(skill_path=...)``).
    2. ``SKILLS_PATH`` env or ``skills_path`` in ``file_cfg``.
    3. If ``GITLAB_REPO_URL`` env or ``gitlab_repo_url`` in config: ``GITLAB_SKILLS_CACHE`` /
       ``gitlab_skills_cache`` or ``<project_root>/var/gitlab-skills``.
    4. Default ``<project_root>/dev-skills``.

    Env vars override YAML (see :func:`src.skillflow_config.pick_str`).

    Returns an absolute, resolved path. Parent directories are not created here.
    """
    fc = file_cfg or {}

    if (skill_path_override or "").strip():
        raw = Path(skill_path_override)
        return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()

    skills_path_val = pick_str("SKILLS_PATH", fc, "skills_path", "")
    if skills_path_val:
        raw = Path(skills_path_val)
        return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()

    gitlab_url = pick_str("GITLAB_REPO_URL", fc, "gitlab_repo_url", "")
    if gitlab_url:
        cache = pick_str("GITLAB_SKILLS_CACHE", fc, "gitlab_skills_cache", "")
        if cache:
            raw = Path(cache)
            return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()
        return (project_root / "var" / "gitlab-skills").resolve()

    return (project_root / "dev-skills").resolve()
