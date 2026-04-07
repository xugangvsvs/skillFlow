---
name: efs-to-pfs
description: >-
  Draft or update a Product Feature Specification (PFS) from an Engineering Feature
  Specification (EFS). Keep terminology consistent; label assumptions and open points.
inputs:
  - name: efs_attachment
    type: file
    label: EFS document (optional)
    accept: .md,.txt,.pdf,.doc,.docx,.xml,.json
  - name: product_area
    type: text
    label: Product or module scope (optional)
    placeholder: e.g. 5G L2 / specific network element
---

# EFS to PFS

## Goal

From the user’s EFS content and context, produce a structured **PFS** draft suitable for review.

## Rules

- Separate: facts stated in EFS, design inferences (mark as *inference*), and items pending product/architecture confirmation (own list).
- PFS should cover: scope and objectives, feature list, interface/interaction summary, non-functional constraints if present in EFS (performance, reliability, security), acceptance highlights.
- If input is incomplete, list **minimum follow-up information** while still providing a reviewable PFS skeleton.
- Match the user’s terminology; do not invent parameter values or external system behavior not supported by the EFS.

## Output

Markdown with clear headings, ready to paste into a document system.
