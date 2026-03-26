import pytest

from src.scanner import SkillScanner, match_skill


@pytest.mark.regression
def test_regression_scan_and_match_description(tmp_path):
    """Guard the end-to-end flow: scan SKILL.md metadata then match by description."""
    skill_dir = tmp_path / "ims"
    skill_dir.mkdir()

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "id: ims2-regression\n"
        "name: analyze-ims2\n"
        "description: Use when analyzing IMS2 snapshots\n"
        "keywords:\n"
        "  - ims2\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    scanner = SkillScanner(tmp_path)
    skills = scanner.scan()

    matched = match_skill(skills, "IMS2 snapshots")

    assert len(skills) == 1
    assert matched is not None
    assert matched["id"] == "ims2-regression"
