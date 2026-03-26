# Copilot Project Instructions

Always apply the repository rules in `AGENTS.md` before generating or editing code.

## Tool Behavior
- Treat `AGENTS.md` as the primary source of project constraints.
- Use `docs/plan.md` for current priorities and milestones.
- If direct user instructions conflict with `AGENTS.md`, follow the user instruction for that task.
- Before `git push` in this environment, configure local Git proxy: `git config --local http.proxy http://10.144.1.10:8080; git config --local https.proxy http://10.144.1.10:8080`.

## Code Generation Defaults
- Prefer minimal, safe changes.
- Preserve existing project structure and naming patterns.
- Add or update tests when behavior changes.
