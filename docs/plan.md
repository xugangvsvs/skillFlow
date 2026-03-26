# SkillFlow Plan

## Delivery Workflow
- TDD first: write or update tests before implementation.
- Keep all work under Git version control with clear, focused commits.
- Push changes to GitHub regularly through branch/PR workflow.
- Run regression testing on each push via CI and block merges on failures.

## North Star
- Build a reliable workflow that maps user input to the correct skill and returns useful AI analysis output.

## Current Milestones

### M1. Core Stability
- [ ] Verify scanner coverage for all folders under `dev-skills/`.
- [ ] Validate matching quality for common telecom keywords.
- [ ] Improve error messages for missing or malformed skill files.

### M2. Prompt and Execution Quality
- [ ] Standardize prompt construction in executor.
- [ ] Add guardrails for oversized skill context.
- [ ] Improve user-facing analysis formatting.

### M3. Test Coverage
- [ ] Expand unit tests for skill matching edge cases.
- [ ] Add tests for scanner parsing failures.
- [ ] Add executor tests with mocked AI responses.

### M4. CI and Regression Guardrails
- [x] Add GitHub Actions workflow for pytest on push and pull_request.
- [x] Add a baseline regression test suite and keep it updated with bug fixes.
- [ ] Define merge gate: CI must pass before merge.

## Backlog
- [ ] Add config file for repo path and runtime options.
- [ ] Add optional multilingual CLI text mode.
- [ ] Add structured logging mode for debugging.

## Notes
- Keep this file for evolving priorities.
- Keep stable coding rules in `AGENTS.md`.
