import pytest
import subprocess
from unittest.mock import patch
from src.scanner import SkillScanner, match_skill

def test_scanner_basic(tmp_path):
    """YAML front matter is parsed into skill metadata."""
    d = tmp_path / "sub"
    d.mkdir()
    f = d / "SKILL.md"
    f.write_text("---\nid: test\nname: test-skill\n---\nbody", encoding="utf-8")
    
    scanner = SkillScanner(tmp_path)
    skills = scanner.scan()
    assert len(skills) == 1
    assert skills[0]['id'] == 'test'

def test_match_skill_with_none_keywords():
    """None keywords do not crash the matcher."""
    skills = [{"id": "empty", "keywords": None, "name": "Empty Skill"}]
    assert match_skill(skills, "hello") is None

def test_match_skill_by_description():
    """Substring of description matches user query."""
    mock_skills = [{
        "name": "analyze-ims2",
        "description": "Use when analyzing IMS2 snapshots",
        "keywords": []
    }]
    result = match_skill(mock_skills, "ims2")
    assert result is not None
    assert result['name'] == "analyze-ims2"

def test_match_skill_case_insensitive():
    """Matching is case-insensitive for keywords and names."""
    skills = [{"name": "NETWORK", "keywords": ["PING"]}]
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


def test_scan_with_gitlab_continues_on_git_failure_with_supplement(tmp_path, caplog):
    """Git sync failure logs a warning; supplement trees still load."""
    caplog.set_level("WARNING")
    cache_dir = tmp_path / "cache-dev-skills"
    cache_dir.mkdir()
    supp_root = tmp_path / "dev-skills"
    skill_dir = supp_root / "local"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: only-local\n---\n", encoding="utf-8")

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
            supplement_repo_paths=[str(supp_root)],
        )
        skills = scanner.scan()

    assert len(skills) == 1
    assert skills[0]["name"] == "only-local"
    assert any("GitLab skill sync failed" in r.message for r in caplog.records)
    assert any("repository not found" in r.message for r in caplog.records)


def test_scan_merges_supplement_without_overlapping_names(tmp_path):
    """Supplement path adds skills whose names are not in the primary tree."""
    primary = tmp_path / "primary"
    supp = tmp_path / "supp"
    (primary / "a").mkdir(parents=True)
    (primary / "a" / "SKILL.md").write_text("---\nname: from-primary\n---\n", encoding="utf-8")
    (supp / "b").mkdir(parents=True)
    (supp / "b" / "SKILL.md").write_text("---\nname: from-supplement\n---\n", encoding="utf-8")
    scanner = SkillScanner(str(primary), supplement_repo_paths=[str(supp)])
    skills = scanner.scan()
    names = {s["name"] for s in skills}
    assert names == {"from-primary", "from-supplement"}


def test_scan_merge_duplicate_name_keeps_primary(tmp_path):
    """When primary and supplement define the same ``name``, primary wins."""
    primary = tmp_path / "primary"
    supp = tmp_path / "supp"
    primary.mkdir()
    supp.mkdir()
    (primary / "SKILL.md").write_text(
        "---\nname: dup\nfrom_tree: primary\n---\n",
        encoding="utf-8",
    )
    (supp / "SKILL.md").write_text(
        "---\nname: dup\nfrom_tree: supplement\n---\n",
        encoding="utf-8",
    )
    scanner = SkillScanner(str(primary), supplement_repo_paths=[str(supp)])
    skills = scanner.scan()
    assert len(skills) == 1
    assert skills[0]["from_tree"] == "primary"
