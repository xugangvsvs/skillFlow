"""Load use case catalog: maps scenario ids to underlying SKILL.md ``name`` values."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple

import yaml

log = logging.getLogger("skillflow.use_cases")


def resolve_use_cases_file(
    project_root: Path,
    file_cfg: Mapping[str, Any],
    path_override: str = "",
) -> Path:
    """Resolve the YAML file for use cases.

    Precedence:
    1. Non-empty ``path_override`` (tests / ``create_app(use_cases_path=...)``).
    2. ``SKILLFLOW_USE_CASES_PATH`` or ``USE_CASES_PATH`` environment variable.
    3. ``use_cases_path`` in ``skillflow.yaml`` (relative to project root if not absolute).
    4. ``config/use_cases.yaml`` if it exists.
    5. ``config/use_cases.example.yaml`` (committed default).
    """
    if (path_override or "").strip():
        raw = Path(path_override.strip())
        return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()

    env = (os.environ.get("SKILLFLOW_USE_CASES_PATH") or os.environ.get("USE_CASES_PATH") or "").strip()
    if env:
        raw = Path(env)
        return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()

    yaml_path = file_cfg.get("use_cases_path") if file_cfg is not None else None
    if yaml_path is not None and str(yaml_path).strip():
        raw = Path(str(yaml_path).strip())
        return raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()

    primary = (project_root / "config" / "use_cases.yaml").resolve()
    if primary.is_file():
        return primary
    return (project_root / "config" / "use_cases.example.yaml").resolve()


def load_use_case_definitions(path: Path) -> List[MutableMapping[str, Any]]:
    """Parse use case entries from YAML; returns [] if file missing or invalid."""
    if not path.is_file():
        log.warning("use cases file not found: %s", path)
        return []

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return []

    raw = data.get("use_cases")
    if not isinstance(raw, list):
        return []

    return [e for e in raw if isinstance(e, dict)]


def build_use_case_index(
    definitions: List[Mapping[str, Any]],
    skills: List[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Build API payload list and internal id -> {skill_name, prompt_prefix, available}.

    If an entry has no non-empty ``inputs`` list, ``inputs`` are copied from the
    skill with matching ``skill_name``.
    """
    skill_by_name: Dict[str, Mapping[str, Any]] = {}
    for s in skills:
        n = s.get("name")
        if n:
            skill_by_name[str(n)] = s

    seen: set[str] = set()
    api_list: List[Dict[str, Any]] = []
    by_id: Dict[str, Dict[str, Any]] = {}

    for d in definitions:
        uc_id = str(d.get("id") or "").strip()
        if not uc_id:
            log.warning("use case entry missing id, skipped")
            continue
        if uc_id in seen:
            log.warning("duplicate use case id %r skipped", uc_id)
            continue
        seen.add(uc_id)

        skill_name = str(d.get("skill_name") or "").strip()
        title = str(d.get("title") or uc_id).strip()
        description = str(d.get("description") or "").strip()
        prompt_prefix = str(d.get("prompt_prefix") or "").strip()

        skill = skill_by_name.get(skill_name) if skill_name else None
        available = skill is not None

        inputs_override = d.get("inputs")
        if isinstance(inputs_override, list) and len(inputs_override) > 0:
            inputs: List[Any] = list(inputs_override)
        else:
            inputs = list((skill or {}).get("inputs") or [])

        api_list.append(
            {
                "id": uc_id,
                "title": title,
                "description": description,
                "inputs": inputs,
                "available": available,
            }
        )
        by_id[uc_id] = {
            "skill_name": skill_name,
            "prompt_prefix": prompt_prefix,
            "available": available,
        }

    return api_list, by_id


def load_prepared_use_cases(
    project_root: Path,
    file_cfg: Mapping[str, Any],
    skills: List[Mapping[str, Any]],
    path_override: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], Path]:
    """Load YAML, merge with skills, return (api_list, by_id, path_used)."""
    path = resolve_use_cases_file(project_root, file_cfg, path_override)
    definitions = load_use_case_definitions(path)
    api_list, by_id = build_use_case_index(definitions, skills)
    log.info("loaded %d use cases from %s", len(api_list), path)
    return api_list, by_id, path


def apply_use_case(
    use_case_id: str,
    user_input: str,
    use_cases_by_id: Mapping[str, Mapping[str, Any]],
) -> Tuple[Optional[str], str, Optional[str]]:
    """Resolve use case to skill_name and optional prefixed user_input.

    Returns:
        (skill_name, effective_user_input, error_message)
        error_message set if id unknown or target skill not available.
    """
    entry = use_cases_by_id.get(use_case_id.strip())
    if not entry:
        return None, user_input, f"Unknown use_case_id: {use_case_id!r}"

    if not entry.get("available"):
        return None, user_input, (
            f"Use case {use_case_id!r} is unavailable (underlying skill "
            f"{entry.get('skill_name')!r} not found in loaded skills)"
        )

    skill_name = str(entry.get("skill_name") or "").strip()
    if not skill_name:
        return None, user_input, f"Use case {use_case_id!r} has no skill_name configured"

    prefix = str(entry.get("prompt_prefix") or "").strip()
    if prefix:
        effective = f"{prefix}\n\n{user_input}"
    else:
        effective = user_input

    return skill_name, effective, None
