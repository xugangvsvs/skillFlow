---
name: icfs-to-code-ut-sct
description: >-
  From an ICFS, draft implementation code, unit tests (UT), and system/scenario test (SCT)
  guidance, following stated conventions and testability.
inputs:
  - name: icfs_attachment
    type: file
    label: ICFS document (optional)
    accept: .md,.txt,.pdf,.doc,.docx,.xml,.json
  - name: language_stack
    type: text
    label: Language or framework (optional)
    placeholder: e.g. Python 3.11 / C++17 / Java 17
---

# ICFS to code, UT, and SCT

## Goal

From the ICFS and user instructions, deliver:

1. **Implementation** draft (single file or multi-file as needed).
2. **UT**: case table (Given/When/Then or equivalent), key assertions, mock/stub boundaries.
3. **SCT**: end-to-end or system-level scenarios, prerequisites, expected observables (logs, metrics, external behavior).

## Rules

- Code must align with the ICFS; use `TODO` where details are missing and state the dependency.
- UT should cover happy path, main error paths, and boundaries; avoid vague assertions.
- SCT items should trace to ICFS clauses or requirement IDs when the user provides them.
- Do not assume unstated internal class names, paths, or build systems; use placeholders if needed.

## Output

Markdown in four sections: *Code*, *UT design*, *SCT design*, *Assumptions and risks*.
