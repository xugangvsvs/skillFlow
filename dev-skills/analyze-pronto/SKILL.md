---
name: analyze-pronto
description: >-
  Analyze a Pronto defect: summarize context, likely causes, verification steps, and
  information still needed.
inputs:
  - name: pronto_id
    type: text
    label: Pronto ID
    placeholder: e.g. PR12345678
  - name: pronto_attachment
    type: file
    label: Export or screenshot (optional)
    accept: .md,.txt,.pdf,.log,.zip,.png,.jpg,.jpeg
---

# Analyze Pronto

## Goal

From pasted Pronto text, logs, or attachment descriptions, produce actionable **analysis and next steps**.

## Rules

- Summarize: symptom, impact, environment/version, actions already tried (if stated).
- Distinguish facts from hypotheses; mark hypotheses *to be verified* with a suggested check.
- Provide an **ordered investigation plan** (cheap checks first): what to verify, how, expected outcome.
- If information is insufficient, list **minimal follow-up questions** that unblock analysis.
- Do not fabricate versions, stack traces, or ticket links that do not appear in the input.

## Output

Markdown: *Summary*, *Timeline and facts*, *Hypotheses (ranked)*, *Suggested verification*, *Missing information*.
