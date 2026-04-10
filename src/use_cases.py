"""Fixed use-case catalog: maps scenario ids to underlying SKILL.md ``name`` values.

Use cases are defined in code (not YAML or GitLab). Edit ``FIXED_USE_CASE_DEFINITIONS`` to
change titles or mapping; skills themselves still come from ``dev-skills/`` or GitLab sync.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple

log = logging.getLogger("skillflow.use_cases")

# Fixed catalog — ids are stable API/UI keys; skill_name must match a loaded SKILL.md ``name``.
FIXED_USE_CASE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "id": "efs-to-pfs",
        "title": "Write PFS from EFS",
        "description": (
            "Produce or update a Product Feature Specification (PFS) from an "
            "Engineering Feature Specification (EFS)."
        ),
        "skill_name": "efs-to-pfs",
    },
    {
        "id": "pfs-to-icfs",
        "title": "Write ICFS from PFS",
        "description": (
            "Derive an Interface Control Functional Specification (ICFS) from a PFS."
        ),
        "skill_name": "pfs-to-icfs",
    },
    {
        "id": "icfs-to-code-ut-sct",
        "title": "Code, unit tests, and SCT from ICFS",
        "description": (
            "Generate implementation code, unit tests (UT), and system/scenario test (SCT) "
            "artifacts from an ICFS."
        ),
        # Must match SKILL.md ``name`` under icfs-to-code-ut-sct/ (same id as use case is fine).
        "skill_name": "icfs-to-code-ut-sct",
        "prompt_prefix": (
            "Context: SkillFlow only generates Markdown (implementation drafts, UT design, SCT "
            "design) from the skill and your input. It does not compile code, run tests, SSH, or "
            "execute nrm. When the server sets GERRIT_FETCH_ENABLED=1 and HTTP credentials, it may "
            "attach a Gerrit patch from a pasted URL; otherwise paste spec text in the main input. "
            "Use repo_layout_hint for code paths. You apply the output in your own checkout."
        ),
        "inputs": [
            {
                "name": "gerrit_url",
                "type": "text",
                "label": "Gerrit change URL (optional)",
                "placeholder": "e.g. https://gerrit.example.com/gerrit/c/PROJECT/+/12345",
                "description": (
                    "If GERRIT_FETCH_ENABLED=1 and credentials are configured, the server fetches "
                    "the current revision patch and injects it into the prompt. Otherwise ignored."
                ),
            },
            {
                "name": "gerrit_change_id",
                "type": "text",
                "label": "Gerrit change number (optional)",
                "placeholder": "e.g. 9818348 — or paste full URL in Gerrit URL; needs GERRIT_BASE_URL if numeric only",
                "description": (
                    "Traceability in the prompt. If fetch is enabled, a numeric ID also triggers fetch "
                    "when GERRIT_BASE_URL (and optionally GERRIT_DEFAULT_PROJECT) is set."
                ),
            },
            {
                "name": "language_stack",
                "type": "text",
                "label": "Language or framework (optional)",
                "placeholder": "e.g. Python 3.11 / C++17 / Java 17",
            },
            {
                "name": "repo_layout_hint",
                "type": "text",
                "label": "Optional repository context",
                "placeholder": "e.g. src/, test/ut/, module names",
                "description": (
                    "Optional hints for file placement (paths, modules). No remote execution."
                ),
            },
        ],
    },
    {
        "id": "analyze-pronto",
        "title": "Analyze Pronto",
        "description": (
            "Analyze a Pronto defect: impact, reproduction steps, and investigation guidance."
        ),
        "skill_name": "analyze-pronto",
    },
]


def _find_skill_by_configured_name(
    skill_by_name: Dict[str, Mapping[str, Any]],
    skill_by_lower: Dict[str, Mapping[str, Any]],
    skill_name: str,
) -> Optional[Mapping[str, Any]]:
    """Match use-case ``skill_name`` to a loaded skill (exact, then case-insensitive)."""
    if not skill_name:
        return None
    hit = skill_by_name.get(skill_name)
    if hit is not None:
        return hit
    return skill_by_lower.get(skill_name.lower())


def build_use_case_index(
    definitions: List[Mapping[str, Any]],
    skills: List[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Build API payload list and internal id -> {skill_name, prompt_prefix, available}.

    If an entry has no non-empty ``inputs`` list, ``inputs`` are copied from the
    skill with matching ``skill_name``.
    """
    skill_by_name: Dict[str, Mapping[str, Any]] = {}
    skill_by_lower: Dict[str, Mapping[str, Any]] = {}
    for s in skills:
        n = s.get("name")
        if n:
            key = str(n)
            skill_by_name[key] = s
            skill_by_lower[key.lower()] = s

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

        skill = _find_skill_by_configured_name(skill_by_name, skill_by_lower, skill_name)
        available = skill is not None
        if skill_name and not available:
            log.warning(
                "use case %r expects skill_name %r but it was not among %d loaded skills. "
                "If GITLAB_REPO_URL / gitlab_repo_url is set, skills come from that clone "
                "(e.g. var/gitlab-skills), not from dev-skills/ in the app repo — add the "
                "SKILL.md there or set SKILLS_PATH / skills_path to your local skills tree.",
                uc_id,
                skill_name,
                len(skills),
            )

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


def prepare_use_cases(
    skills: List[Mapping[str, Any]],
    definitions: Optional[List[Mapping[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Merge fixed (or test-supplied) definitions with loaded skills."""
    defs = definitions if definitions is not None else FIXED_USE_CASE_DEFINITIONS
    api_list, by_id = build_use_case_index(list(defs), skills)
    log.info("prepared %d use cases from fixed catalog", len(api_list))
    return api_list, by_id


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
