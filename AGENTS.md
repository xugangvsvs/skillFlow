# Project AI Rules

This file is the tool-agnostic rule source for AI coding assistants in this repository.

## Project Context
- This project is a Python-based SkillFlow tool targeting enterprise intranet use.
- Core runtime modules are under `src/`.
- Test files are under `tests/`.
- Skill definitions: local `dev-skills/` by default, or set `GITLAB_REPO_URL` to clone/pull from GitLab into `var/gitlab-skills` (see README).
- The AI backend is the Nokia internal LLM API (`hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions`), model `qwen/qwen3-32b`. No external API key required.
- Primary user-facing entry: **Flask web app** (`python -m src.app`, `src/app.py`) with static UI under `web/`. The CLI in `src/main.py` remains for scripting and quick checks.

## Architecture

The system is composed of four modules:

### A. Skill Discovery & Sync — "The Scout"
- Crawls `dev-skills/` (or GitLab repo) for directories containing `SKILL.md`.
- Parses YAML front-matter: **name** (required for API `skill_name`; must match `config/skill_adapters.yaml` keys when using tools), optional **id**, description, keywords, input parameters.
- Caches parsed skill list in memory (or DB) for fast query.
- Module boundary: `src/scanner.py`

### B. Dynamic UI Rendering — "The Face"
- Skill Explorer: displays all available skill cards.
- Auto-Form: generates input fields from `SKILL.md` parameter definitions.
- Stream Terminal: response / progress display (dark terminal style in `web/index.html`).
- Module boundary: `web/index.html` (static) + REST in `src/app.py`.

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
- For this environment, configure Git proxy before push (`http://10.144.1.10:8080`) to avoid HTTPS timeout.
- Use this push template when needed:
	`git config --local http.proxy http://10.144.1.10:8080; git config --local https.proxy http://10.144.1.10:8080; git push`
- For this environment, always install Python packages via corporate proxy:
  `pip install <package> --proxy http://10.144.1.10:8080`

## SkillFlow-Specific Rules
- Scanner changes must preserve compatibility with existing `SKILL.md` files.
- Matching logic should stay case-insensitive unless explicitly changed.
- Executor changes should preserve prompt intent and avoid leaking sensitive data.
- Tool-first behavior should be adapter-driven via `config/skill_adapters.yaml`, not hardcoded by skill name.

## Change Management
- Do not modify unrelated files.
- Keep diffs concise and explain non-obvious decisions in code comments.
- When uncertain, choose the least risky implementation.

## Planning
- Keep active plan and milestones in `docs/plan.md`.
- Keep this rules file stable; avoid mixing transient task notes here.
