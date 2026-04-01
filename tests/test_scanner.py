import pytest
import subprocess
from unittest.mock import patch
from src.scanner import SkillScanner, match_skill

def test_scanner_basic(tmp_path):
    """验证 YAML 解析"""
    d = tmp_path / "sub"
    d.mkdir()
    f = d / "SKILL.md"
    f.write_text("---\nid: test\nname: test-skill\n---\nbody", encoding="utf-8")
    
    scanner = SkillScanner(tmp_path)
    skills = scanner.scan()
    assert len(skills) == 1
    assert skills[0]['id'] == 'test'

def test_match_skill_with_none_keywords():
    """验证当 keywords 为 None 时不崩溃"""
    skills = [{"id": "empty", "keywords": None, "name": "Empty Skill"}]
    assert match_skill(skills, "hello") is None

def test_match_skill_by_description():
    """验证从描述中匹配 (解决你刚才的失败项)"""
    mock_skills = [{
        "name": "analyze-ims2",
        "description": "Use when analyzing IMS2 snapshots",
        "keywords": []
    }]
    # 模拟输入 "ims2"
    result = match_skill(mock_skills, "ims2")
    assert result is not None
    assert result['name'] == "analyze-ims2"

def test_match_skill_case_insensitive():
    """验证大小写不敏感"""
    skills = [{"name": "NETWORK", "keywords": ["PING"]}]
    # 输入小写，匹配大写
    assert match_skill(skills, "ping") is not None
    assert match_skill(skills, "network") is not None


def test_scan_with_gitlab_clones_when_cache_missing(tmp_path):
    """When GitLab mode is enabled and cache is absent, scanner should clone first."""
    cache_dir = tmp_path / "cache-dev-skills"

    with patch("src.scanner.subprocess.run") as mock_run:
        def _run_side_effect(cmd, check, capture_output, text):
            if cmd[:2] == ["git", "clone"]:
                (cache_dir / ".git").mkdir(parents=True, exist_ok=True)
                skill_dir = cache_dir / "demo"
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(
                    "---\n"
                    "id: demo\n"
                    "name: demo-skill\n"
                    "description: demo\n"
                    "---\n"
                    "body\n",
                    encoding="utf-8",
                )
            return subprocess.CompletedProcess(cmd, 0, "", "")

        mock_run.side_effect = _run_side_effect

        scanner = SkillScanner(
            repo_path=str(cache_dir),
            gitlab_repo_url="https://git.example.com/group/dev-skills.git",
            gitlab_branch="main",
        )
        skills = scanner.scan()

    assert len(skills) == 1
    assert skills[0]["name"] == "demo-skill"
    clone_calls = [c[0][0] for c in mock_run.call_args_list if c[0] and c[0][0][:2] == ["git", "clone"]]
    assert len(clone_calls) == 1


def test_scan_with_gitlab_pulls_when_cache_exists(tmp_path):
    """When GitLab mode is enabled and cache exists, scanner should pull latest."""
    cache_dir = tmp_path / "cache-dev-skills"
    (cache_dir / ".git").mkdir(parents=True)
    skill_dir = cache_dir / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "id: demo\n"
        "name: demo-skill\n"
        "description: demo\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    with patch("src.scanner.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(["git"], 0, "", "")
        scanner = SkillScanner(
            repo_path=str(cache_dir),
            gitlab_repo_url="https://git.example.com/group/dev-skills.git",
            gitlab_branch="main",
        )
        skills = scanner.scan()

    assert len(skills) == 1
    assert skills[0]["name"] == "demo-skill"
    pull_calls = [
        c[0][0]
        for c in mock_run.call_args_list
        if c[0] and len(c[0][0]) >= 5 and c[0][0][:5] == ["git", "-C", str(cache_dir), "pull", "--ff-only"]
    ]
    assert len(pull_calls) == 1


def test_scan_with_gitlab_returns_actionable_error_on_git_failure(tmp_path):
    """Git command failures should surface with clear actionable context."""
    cache_dir = tmp_path / "cache-dev-skills"
    with patch("src.scanner.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "clone"],
            stderr="fatal: repository not found",
        )
        scanner = SkillScanner(
            repo_path=str(cache_dir),
            gitlab_repo_url="https://git.example.com/group/dev-skills.git",
            gitlab_branch="main",
        )

        with pytest.raises(RuntimeError) as exc:
            scanner.scan()

    assert "GitLab skill sync failed" in str(exc.value)
    assert "repository not found" in str(exc.value)
