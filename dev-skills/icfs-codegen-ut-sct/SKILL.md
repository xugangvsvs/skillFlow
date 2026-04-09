---
name: icfs-codegen-ut-sct
description: >-
  From an ICFS or feature description, produce implementation drafts, gtest-oriented unit test
  design, and system/scenario test (SCT) design as Markdown. No build or remote execution —
  SkillFlow only generates text for the user to apply in their environment.
inputs:
  - name: gerrit_change_id
    type: text
    label: Gerrit ICFS/PFS change ID (optional)
    placeholder: e.g. 12345 — for traceability in the prompt only
  - name: language_stack
    type: text
    label: Language or framework (optional)
    placeholder: e.g. C++17 / gtest / Nokia nrm-style layout
  - name: repo_layout_hint
    type: text
    label: Optional repository context
    placeholder: e.g. src/, test/ut/, module names — helps placement of suggested files
---

# ICFS / spec → implementation, UT, and SCT (LLM-only)

## Goal

Given an **ICFS**, **PFS**, user story, bug description, or pasted specification fragments, produce **Markdown deliverables** the user can copy into their real repository:

1. **Implementation** — `.cpp` / `.h` (or equivalent) drafts, aligned with stated interfaces.
2. **Unit tests (UT)** — **gtest-style** cases and file layout (`test/ut/{feature}_test.cpp` convention where applicable).
3. **SCT design** — system/scenario-level cases, prerequisites, expected observables (no container/podman execution).

SkillFlow **does not** run compilers, `nrm`, SSH, or shell scripts. **Do not** instruct the user to run `dev-build.sh`, `dev-ut.sh`, `dev-sct-setup.sh`, or `nrm` from this skill — those belong to a full agentic environment outside SkillFlow.

## Phase A — Understand (from prompt only)

- Use **user input**, optional **Gerrit change ID** (as a label for requirements; SkillFlow does not fetch Gerrit), and optional **repository context** to infer:
  - Relevant directories (`src/`, `include/`, `test/ut/`, CMake layout hints).
  - Interface definitions, method signatures, error handling, sequencing.
- If information is missing, state assumptions explicitly and use `TODO` with the dependency.

## Phase B — Generate / modify code (text only)

- Propose **implementation** files with paths relative to a typical repo root (e.g. `{repo}/src/.../name.cpp`).
- Match **include style**, error-handling idioms, and logging patterns **as described or reasonably inferred** from the user — do not invent internal Nokia class names not implied by the spec.
- If CMake or `target_sources` updates are needed, give a **concise snippet or bullet list** of what to add (no requirement that `CMakeLists.txt` exists at a fixed path).

## Phase C — Unit tests (gtest-oriented)

Design `test/ut/{feature}_test.cpp` (name `{feature}` from the feature or spec) covering:

- Happy path and main error paths.
- Boundaries: empty input, null/zero, limits where relevant.
- **Assertions** that map to ICFS / requirement IDs when the user provides them.

Output **test case names** and **Given/When/Then** (or equivalent) plus key `EXPECT_*` / `ASSERT_*` ideas — not a guarantee the code compiles without local integration.

## Phase D — SCT design (optional section)

If integration testing is in scope:

- Scenarios: prerequisites, steps, expected logs/metrics/external behavior.
- Trace to spec clauses or IDs.
- **Do not** assume podman, `.netrc`, or `dev-sct-run.sh`; describe scenarios abstractly.

## Rules

- Align all code and tests with the **stated** specification; mark gaps with `TODO`.
- No binary patches; no shell one-liners that download or execute remote code.
- Prefer **clear, reviewable** Markdown over volume.

## Output format (required structure)

Return **one** Markdown document with these sections in order:

1. `## Implementation` — code blocks or clearly labeled file excerpts.
2. `## Unit tests (gtest-oriented)` — file path suggestion + cases.
3. `## SCT design` — omit only if user explicitly excludes integration scope; otherwise write `*(not requested)*` or short N/A.
4. `## Assumptions and risks`
5. `## Suggested file checklist` *(optional)* — table: path | action (create/modify) | note

End with a one-line reminder that the user must **apply** changes in their own workspace and run their own build/UT/SCT tooling.
