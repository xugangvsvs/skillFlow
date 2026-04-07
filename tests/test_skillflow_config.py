"""Tests for config/skillflow.yaml loading and env override rules."""

from pathlib import Path

import pytest
import yaml

from src.skillflow_config import load_skillflow_config, pick_str


def test_load_missing_file_returns_empty_dict(project_root: Path):
    assert load_skillflow_config(project_root) == {}


def test_load_skillflow_yaml(project_root: Path):
    cfg_dir = project_root / "config"
    cfg_dir.mkdir()
    data = {
        "gitlab_repo_url": "https://gitlab.example.com/skills.git",
        "gitlab_branch": "develop",
        "skills_path": "my-skills",
        "llm_model": "custom-model",
    }
    (cfg_dir / "skillflow.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    loaded = load_skillflow_config(project_root)
    assert loaded["gitlab_repo_url"] == "https://gitlab.example.com/skills.git"
    assert loaded["gitlab_branch"] == "develop"


def test_skillflow_config_path_override(project_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    alt = tmp_path / "other.yaml"
    alt.write_text(yaml.safe_dump({"gitlab_branch": "override-branch"}), encoding="utf-8")
    monkeypatch.setenv("SKILLFLOW_CONFIG", str(alt))
    loaded = load_skillflow_config(project_root)
    assert loaded["gitlab_branch"] == "override-branch"


def test_pick_str_env_overrides_yaml(monkeypatch: pytest.MonkeyPatch):
    cfg = {"gitlab_repo_url": "https://file.example.com/a.git"}
    monkeypatch.setenv("GITLAB_REPO_URL", "https://env.example.com/b.git")
    assert pick_str("GITLAB_REPO_URL", cfg, "gitlab_repo_url", "") == "https://env.example.com/b.git"


def test_pick_str_yaml_fallback():
    cfg = {"gitlab_branch": "release"}
    assert pick_str("GITLAB_BRANCH", cfg, "gitlab_branch", "main") == "release"


def test_pick_str_default():
    assert pick_str("GITLAB_BRANCH", {}, "gitlab_branch", "main") == "main"
