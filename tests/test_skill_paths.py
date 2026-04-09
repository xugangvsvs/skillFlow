"""Tests for skill repo path resolution (local vs GitLab clone target)."""

from pathlib import Path

import pytest

from src.skill_paths import resolve_skill_repo_dir, supplement_dev_skills_dirs


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


def test_gitlab_from_yaml_only(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITLAB_REPO_URL", raising=False)
    monkeypatch.delenv("SKILLS_PATH", raising=False)
    monkeypatch.delenv("GITLAB_SKILLS_CACHE", raising=False)
    fc = {"gitlab_repo_url": "https://gitlab.example.com/group/dev-skills.git"}
    expected = project_root / "var" / "gitlab-skills"
    assert resolve_skill_repo_dir(project_root, "", fc) == expected.resolve()


def test_skills_path_from_yaml(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SKILLS_PATH", raising=False)
    monkeypatch.delenv("GITLAB_REPO_URL", raising=False)
    d = project_root / "from-yaml"
    d.mkdir()
    fc = {"skills_path": "from-yaml"}
    assert resolve_skill_repo_dir(project_root, "", fc) == d.resolve()


def test_env_overrides_yaml_skills_path(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SKILLS_PATH", "from-env")
    d = project_root / "from-env"
    d.mkdir()
    fc = {"skills_path": "from-yaml-should-lose"}
    (project_root / "from-yaml-should-lose").mkdir()
    assert resolve_skill_repo_dir(project_root, "", fc) == d.resolve()


def test_supplement_dev_skills_dirs_with_gitlab_and_folder(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SKILLS_PATH", raising=False)
    monkeypatch.setenv("GITLAB_REPO_URL", "https://gitlab.example.com/group/dev-skills.git")
    (project_root / "dev-skills").mkdir()
    expected = str((project_root / "dev-skills").resolve())
    assert supplement_dev_skills_dirs(project_root, "", {}) == [expected]


def test_supplement_dev_skills_dirs_empty_without_gitlab(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITLAB_REPO_URL", raising=False)
    monkeypatch.delenv("SKILLS_PATH", raising=False)
    (project_root / "dev-skills").mkdir()
    assert supplement_dev_skills_dirs(project_root, "", {}) == []


def test_supplement_dev_skills_dirs_empty_when_skills_path_set(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GITLAB_REPO_URL", "https://gitlab.example.com/group/dev-skills.git")
    only = project_root / "only-here"
    only.mkdir()
    monkeypatch.setenv("SKILLS_PATH", str(only))
    (project_root / "dev-skills").mkdir()
    assert supplement_dev_skills_dirs(project_root, "", {}) == []


def test_supplement_dev_skills_dirs_empty_with_skill_path_override(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GITLAB_REPO_URL", "https://gitlab.example.com/group/dev-skills.git")
    (project_root / "dev-skills").mkdir()
    assert supplement_dev_skills_dirs(project_root, "custom-skills", {}) == []
