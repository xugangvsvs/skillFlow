# Project AI Rules

This file is the tool-agnostic rule source for AI coding assistants in this repository.

## Project Context
- This project is a Python-based SkillFlow tool.
- Core runtime modules are under `src/`.
- Test files are under `tests/`.
- Skill definitions are under `dev-skills/`.

## Priorities
- Keep behavior stable unless user explicitly asks for changes.
- Prefer small, focused edits over large refactors.
- Keep CLI output and user-facing messages clear and consistent.
- Follow a TDD-first workflow: write tests before implementation.

## Coding Rules
- Follow PEP 8 style and keep functions cohesive.
- Add type hints for new or modified Python functions when practical.
- Keep imports minimal and remove unused imports.
- Avoid hardcoded absolute paths; use repository-relative paths or config.
- Do not introduce breaking API changes without clear need.

## Error Handling Rules
- Fail with actionable messages, not silent failures.
- Catch specific exceptions where possible.
- Keep retry and fallback logic explicit.

## Testing Rules
- For behavior changes, add or update pytest tests in `tests/`.
- Prefer deterministic tests and avoid network-dependent test logic.
- Run relevant tests before finalizing changes when possible.
- Add regression tests for every bug fix to prevent recurrence.
- New features should start with failing tests, then implementation, then refactor.

## Version Control and CI Rules
- Use Git for all code changes and keep commits focused and reviewable.
- Keep repository ready for GitHub collaboration and pull request workflows.
- Every push to GitHub should trigger regression testing in CI.
- Treat CI failures as blockers; fix test failures before merge.

## SkillFlow-Specific Rules
- Scanner changes must preserve compatibility with existing `SKILL.md` files.
- Matching logic should stay case-insensitive unless explicitly changed.
- Executor changes should preserve prompt intent and avoid leaking sensitive data.

## Change Management
- Do not modify unrelated files.
- Keep diffs concise and explain non-obvious decisions in code comments.
- When uncertain, choose the least risky implementation.

## Planning
- Keep active plan and milestones in `docs/plan.md`.
- Keep this rules file stable; avoid mixing transient task notes here.
