"""Unit tests for fixed use-case catalog and resolution."""

import pytest

from src.use_cases import (
    FIXED_USE_CASE_DEFINITIONS,
    apply_use_case,
    build_use_case_index,
    prepare_use_cases,
)


def test_fixed_definitions_has_four_entries() -> None:
    assert len(FIXED_USE_CASE_DEFINITIONS) == 4
    ids = {d["id"] for d in FIXED_USE_CASE_DEFINITIONS}
    assert ids == {"efs-to-pfs", "pfs-to-icfs", "icfs-to-code-ut-sct", "analyze-pronto"}


def test_prepare_use_cases_matches_fixed_length() -> None:
    skills = [{"name": "efs-to-pfs", "inputs": []}]
    api_list, by_id = prepare_use_cases(skills)
    assert len(api_list) == len(FIXED_USE_CASE_DEFINITIONS)
    assert by_id["efs-to-pfs"]["available"] is True
    assert by_id["pfs-to-icfs"]["available"] is False


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


def test_build_use_case_index_skill_name_case_insensitive() -> None:
    skills = [{"name": "ICFS-To-Code-UT-SCT", "inputs": [{"name": "x", "type": "text"}]}]
    definitions = [{"id": "uc", "title": "T", "skill_name": "icfs-to-code-ut-sct"}]
    api_list, by_id = build_use_case_index(definitions, skills)
    assert api_list[0]["available"] is True
    assert by_id["uc"]["available"] is True


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
