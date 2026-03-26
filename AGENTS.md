# Project AI Rules

This file is the tool-agnostic rule source for AI coding assistants in this repository.

## Project Context
- This project is a Python-based SkillFlow tool targeting enterprise intranet use.
- Core runtime modules are under `src/`.
- Test files are under `tests/`.
- Skill definitions are under `dev-skills/` (sourced from GitLab in production).
- The AI backend is the Nokia internal LLM API (`hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions`), model `qwen/qwen3-32b`. No external API key required.
- Long-term goal: evolve from CLI tool into a Web-based AI assistant with four core modules (see Architecture below).

## Architecture

The system is composed of four modules:

### A. Skill Discovery & Sync — "The Scout"
- Crawls `dev-skills/` (or GitLab repo) for directories containing `SKILL.md`.
- Parses YAML front-matter: id, name, description, keywords, input parameters.
- Caches parsed skill list in memory (or DB) for fast query.
- Module boundary: `src/scanner.py`

### B. Dynamic UI Rendering — "The Face"
- Skill Explorer: displays all available skill cards.
- Auto-Form: generates input fields from `SKILL.md` parameter definitions.
- Stream Terminal: real-time progress display (dark terminal style).
- Module boundary: future `web/` layer; currently CLI in `src/main.py`.

### C. Core Execution Engine — "The Brain"
- Prompt Wrapper: combines SKILL.md rules + user log input + internal context into a single AI prompt.
- HTTP Bridge: calls the internal Nokia LLM API (`hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions`) via `requests.post`.
- Model: `qwen/qwen3-32b` (configurable via `LLM_MODEL` env var).
- API URL is configurable via `LLM_API_URL` env var; no secrets hardcoded.
- Result Extractor: reads `choices[0].message.content` from the OpenAI-compatible response.
- Module boundary: `src/executor.py`

### D. Environment & Auth Layer — "The Guard"
- Auth Manager: verifies LLM API reachability before any AI call.
- Access Control: restrict web UI to internal (Nokia SSO) users only when deployed.
- No secrets hardcoded in source; API URL and model configurable via environment variables (`LLM_API_URL`, `LLM_MODEL`).

## Business Data Flow
1. User selects a skill (e.g. "IMS2 call drop analysis") and uploads a log.
2. Backend locates `dev-skills/analyze-ims2/SKILL.md` and reads its rules.
3. Backend builds prompt: `"Based on rules: {SKILL_CONTENT}, analyze this log: {USER_LOG}"`.
4. Backend calls Nokia LLM API via `requests.post` with the prompt.
5. Result Extractor reads `choices[0].message.content` and returns clean Markdown to frontend for rendering.

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
