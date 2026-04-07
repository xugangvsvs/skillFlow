---
name: pfs-to-icfs
description: >-
  Write an Interface Control Functional Specification (ICFS) from a PFS, focusing on
  interfaces, messages, state, and error semantics.
inputs:
  - name: pfs_attachment
    type: file
    label: PFS document (optional)
    accept: .md,.txt,.pdf,.doc,.docx,.xml,.json
  - name: interface_scope
    type: text
    label: Interface scope (optional)
    placeholder: e.g. northbound API / between module X and Y
---

# PFS to ICFS

## Goal

Extract interface-related behavior from the PFS and produce an **ICFS** draft that can guide implementation and integration.

## Rules

- ICFS should cover: interface identifiers, request/response or message layout, field semantics, defaults, optionality, error codes or failure semantics, sequencing or state machines where applicable.
- Where the PFS is silent, use **TBD** and list questions for PFS/architecture—do not invent protocol details.
- If naming conflicts with existing systems, add a *Naming and compatibility* subsection with options and a recommendation.

## Output

Markdown in three parts: *Interface inventory*, *Per-interface specification*, *Open questions*.
