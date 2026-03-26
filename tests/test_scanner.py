import pytest
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
