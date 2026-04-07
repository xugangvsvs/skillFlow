"""Resolve the on-disk directory for SKILL.md discovery (local or GitLab clone target)."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_skill_repo_dir(project_root: Path, skill_path_override: str = "") -> Path:
    """Resolve the directory that holds SKILL.md trees (clone target when using GitLab).

    Order of precedence:
    1. Non-empty ``skill_path_override`` (tests or ``create_app(skill_path=...)``).
    2. ``SKILLS_PATH`` environment variable if set.
    3. If ``GITLAB_REPO_URL`` is set: ``GITLAB_SKILLS_CACHE`` or
       ``<project_root>/var/gitlab-skills`` (avoids cloning into bundled ``dev-skills/``).
    4. Default ``<project_root>/dev-skills``.

    Returns an absolute, resolved path. Parent directories are not created here.
    """
    if (skill_path_override or "").strip():
        raw = Path(skill_path_override)
        return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()

    env_skills = (os.environ.get("SKILLS_PATH") or "").strip()
    if env_skills:
        raw = Path(env_skills)
        return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()

    gitlab_url = (os.environ.get("GITLAB_REPO_URL") or "").strip()
    if gitlab_url:
        cache = (os.environ.get("GITLAB_SKILLS_CACHE") or "").strip()
        if cache:
            raw = Path(cache)
            return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()
        return (project_root / "var" / "gitlab-skills").resolve()

    return (project_root / "dev-skills").resolve()
