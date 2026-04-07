# SkillFlow Plan

## Delivery Workflow
- TDD first: write or update tests before implementation.
- Keep all work under Git version control with clear, focused commits.
- Push changes to GitHub regularly through branch/PR workflow.
- Before `git push` in this environment, set local Git proxy to `http://10.144.1.10:8080`.
- Run regression testing on each push via CI and block merges on failures.

## North Star
- Build a reliable enterprise intranet AI assistant that maps user input to the correct skill and returns useful AI analysis.
- Core idea: "GitLab provides the brain (Skills), Nokia internal LLM provides the intelligence, the Web app provides the face (UI)."
- No external API key required: uses Nokia internal LLM API (`qwen/qwen3-32b`) on the intranet.
- Zero-cost skill extension: adding a new folder with `SKILL.md` in GitLab instantly adds a new capability.

## Target Architecture Modules
- **A. Scout** (`src/scanner.py`): Skill discovery, YAML parsing, local cache.
- **B. Face** (`web/index.html` + `src/app.py` REST): Skill explorer UI, auto-generated input forms, stream terminal.
- **C. Brain** (`src/executor.py`): Prompt builder, HTTP call to Nokia LLM API (`qwen/qwen3-32b`), result extractor.
- **D. Guard** (env/auth layer): LLM API reachability check, Nokia SSO for web access, no hardcoded secrets.

## Current Milestones

### Phase 1: Web Backend API Skeleton
- [x] Create Flask app with `/api/skills` endpoint (GET)
- [x] Create `/api/analyze` endpoint (POST) for synchronous AI calls
- [x] Create `/api/analyze/stream` endpoint (POST) for SSE streaming (placeholder)
- [x] Unit tests for API endpoints (`tests/test_app.py` and related)
- [x] `GET /health` liveness endpoint

### Phase 2: Frontend (Vue 3 + Element Plus)
- [x] Option B kickoff: Flask-served web entry page (`web/index.html`)
- [x] Skill Explorer: card list with click-to-select
- [x] Skill Explorer: keyword search filter
- [x] Skill Detail: selected skill indicator
- [x] Auto-Form (MVP): text input + optional log file upload + Analyze button
- [x] Stream Terminal (MVP): response panel with incremental logs
- [ ] Optional migration: Vue 3 + Vite frontend split (later)

### Phase 3: Dynamic Forms (Future)
- [x] Add adapter-driven tool-first mechanism (`config/skill_adapters.yaml` + `src/skill_runner.py`)
- [x] Return execution mode (`tool-first`/`fallback`) in analyze API response
- [x] Extend SKILL.md with `inputs` field for parameter definitions
- [x] Auto-generate form fields based on inputs metadata
- [x] Support file upload, text, select types

### Phase 4: Deployment & Polish
- [x] Docker containerization (Dockerfile, docker-compose.yml, README)
- [x] Baseline logging to stdout; correlation id on requests; `SKILLFLOW_LOG_LEVEL`; `GET /health`
- [ ] HTTPS/TLS for production (typically at reverse proxy)
- [ ] Authentication & SSO (future)

## Backlog
- [ ] Add config file for repo path and runtime options.
- [ ] Add optional multilingual CLI text mode.
- [ ] Token-level LLM streaming for `/api/analyze/stream` (optional; current SSE sends one complete chunk).

## Notes
- Keep this file for evolving priorities.
- Keep stable coding rules in `AGENTS.md`.
- Historical logging change log: see `LOGGING_CHANGES.md` (optional; not required reading for milestones).
