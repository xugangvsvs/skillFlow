"""Unit tests for use case catalog loading and resolution."""

from pathlib import Path

import pytest

from src.use_cases import (
    apply_use_case,
    build_use_case_index,
    load_use_case_definitions,
    resolve_use_cases_file,
)


def test_resolve_use_cases_file_override(tmp_path: Path) -> None:
    p = tmp_path / "custom.yaml"
    p.write_text("use_cases: []\n", encoding="utf-8")
    got = resolve_use_cases_file(tmp_path, {}, path_override=str(p))
    assert got.resolve() == p.resolve()


def test_resolve_use_cases_file_falls_back_to_example() -> None:
    """When use_cases.yaml missing, use committed example."""
    root = Path(__file__).resolve().parent.parent
    p = resolve_use_cases_file(root, {}, path_override="")
    assert p.name in ("use_cases.yaml", "use_cases.example.yaml")
    assert p.is_file()


def test_build_use_case_index_inherits_inputs_from_skill() -> None:
    skills = [
        {
            "name": "my-skill",
            "inputs": [{"name": "x", "type": "text", "label": "X"}],
        }
    ]
    definitions = [
        {
            "id": "uc1",
            "title": "T1",
            "skill_name": "my-skill",
        }
    ]
    api_list, by_id = build_use_case_index(definitions, skills)
    assert len(api_list) == 1
    assert api_list[0]["available"] is True
    assert api_list[0]["inputs"][0]["name"] == "x"
    assert by_id["uc1"]["skill_name"] == "my-skill"


def test_build_use_case_index_unavailable_when_skill_missing() -> None:
    definitions = [{"id": "orphan", "title": "O", "skill_name": "missing-skill"}]
    api_list, by_id = build_use_case_index(definitions, [])
    assert api_list[0]["available"] is False
    assert by_id["orphan"]["available"] is False


def test_build_use_case_index_duplicate_id_skipped() -> None:
    definitions = [
        {"id": "dup", "title": "A", "skill_name": "s"},
        {"id": "dup", "title": "B", "skill_name": "s"},
    ]
    skills = [{"name": "s", "inputs": []}]
    api_list, _ = build_use_case_index(definitions, skills)
    assert len(api_list) == 1
    assert api_list[0]["title"] == "A"


def test_build_use_case_index_explicit_inputs_override() -> None:
    skills = [{"name": "s", "inputs": [{"name": "old", "type": "text"}]}]
    definitions = [
        {
            "id": "u",
            "title": "U",
            "skill_name": "s",
            "inputs": [{"name": "new_field", "type": "text", "label": "New"}],
        }
    ]
    api_list, _ = build_use_case_index(definitions, skills)
    assert len(api_list[0]["inputs"]) == 1
    assert api_list[0]["inputs"][0]["name"] == "new_field"


def test_apply_use_case_unknown_id() -> None:
    sn, ui, err = apply_use_case("nope", "hello", {})
    assert sn is None
    assert err and "Unknown use_case_id" in err


def test_apply_use_case_unavailable() -> None:
    by_id = {
        "x": {"skill_name": "s", "prompt_prefix": "", "available": False},
    }
    sn, ui, err = apply_use_case("x", "hi", by_id)
    assert sn is None
    assert err and "unavailable" in err.lower()


def test_apply_use_case_prefix() -> None:
    by_id = {
        "x": {
            "skill_name": "analyze-ims2",
            "prompt_prefix": "Scenario intro.",
            "available": True,
        },
    }
    sn, ui, err = apply_use_case("x", "user body", by_id)
    assert err is None
    assert sn == "analyze-ims2"
    assert ui.startswith("Scenario intro.")
    assert "user body" in ui


def test_load_use_case_definitions_missing_file(tmp_path: Path) -> None:
    assert load_use_case_definitions(tmp_path / "nope.yaml") == []
