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
- **B. Face** (future `web/`): Skill explorer UI, auto-generated input forms, stream terminal.
- **C. Brain** (`src/executor.py`): Prompt builder, HTTP call to Nokia LLM API (`qwen/qwen3-32b`), result extractor.
- **D. Guard** (env/auth layer): LLM API reachability check, Nokia SSO for web access, no hardcoded secrets.

## Current Milestones

### Phase 1: Web Backend API Skeleton
- [x] Create Flask app with `/api/skills` endpoint (GET)
- [x] Create `/api/analyze` endpoint (POST) for synchronous AI calls
- [x] Create `/api/analyze/stream` endpoint (POST) for SSE streaming (placeholder)
- [ ] Write comprehensive unit tests for API endpoints
- [ ] Test locally with curl or Postman

### Phase 2: Frontend (Vue 3 + Element Plus)
- [x] Option B kickoff: Flask-served web entry page (`web/index.html`)
- [x] Skill Explorer: card list with click-to-select
- [x] Skill Detail: selected skill indicator
- [x] Auto-Form (MVP): text input + Analyze button
- [x] Stream Terminal (MVP): response panel with incremental logs
- [ ] Optional migration: Vue 3 + Vite frontend split (later)

### Phase 3: Dynamic Forms (Future)
- [ ] Extend SKILL.md with `inputs` field for parameter definitions
- [ ] Auto-generate form fields based on inputs metadata
- [ ] Support file upload, text, select types

### Phase 4: Deployment & Polish
- [ ] Docker containerization
- [ ] HTTPS/TLS for production
- [ ] Authentication & SSO (future)
- [ ] Logging & monitoring

## Backlog
- [ ] Add config file for repo path and runtime options.
- [ ] Add optional multilingual CLI text mode.
- [ ] Add structured logging mode for debugging.

## Notes
- Keep this file for evolving priorities.
- Keep stable coding rules in `AGENTS.md`.
