"""Tests for skill repo path resolution (local vs GitLab clone target)."""

from pathlib import Path

import pytest

from src.skill_paths import resolve_skill_repo_dir


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    return root


def test_override_wins(project_root: Path):
    custom = project_root / "my-skills"
    custom.mkdir()
    assert resolve_skill_repo_dir(project_root, str(custom)) == custom.resolve()


def test_skills_path_env(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITLAB_REPO_URL", raising=False)
    monkeypatch.setenv("SKILLS_PATH", "custom-env-skills")
    d = project_root / "custom-env-skills"
    d.mkdir()
    assert resolve_skill_repo_dir(project_root, "") == d.resolve()


def test_gitlab_uses_var_gitlab_skills_by_default(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SKILLS_PATH", raising=False)
    monkeypatch.delenv("GITLAB_SKILLS_CACHE", raising=False)
    monkeypatch.setenv("GITLAB_REPO_URL", "https://gitlab.example.com/group/dev-skills.git")
    expected = project_root / "var" / "gitlab-skills"
    assert resolve_skill_repo_dir(project_root, "") == expected.resolve()


def test_gitlab_respects_gitlab_skills_cache_env(project_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("SKILLS_PATH", raising=False)
    monkeypatch.setenv("GITLAB_REPO_URL", "https://gitlab.example.com/group/dev-skills.git")
    cache = tmp_path / "skill-cache"
    monkeypatch.setenv("GITLAB_SKILLS_CACHE", str(cache))
    assert resolve_skill_repo_dir(project_root, "") == cache.resolve()
