# SkillFlow — Enterprise Intranet AI Assistant

SkillFlow is a Python-based web application that maps user requests to pre-defined "skills" (AI-powered analysis modules) and delivers results via Nokia's internal LLM API. Built for enterprise intranet use with zero external API dependencies.

## Architecture

- **Scout** (`src/scanner.py`): Discovers and parses skill definitions from `dev-skills/` directories.
- **Brain** (`src/executor.py`): Calls Nokia internal LLM API (`qwen/qwen3-32b`) with structured prompts.
- **Face** (`web/index.html` + Flask): Web UI for skill selection, log upload, and result display.
- **Guard** (`src/skill_runner.py`): Tool-first execution layer with fallback to LLM-only mode.

## Features

- 🔍 **Skill Discovery**: Auto-scan `SKILL.md` files for skill definitions.
- 📝 **Dynamic Forms**: Auto-generate input fields from SKILL.md metadata.
- 🔧 **Tool-First Execution**: Run external tools (e.g., `ims2_tool`) with graceful LLM fallback.
- 📤 **File Upload**: Analyze logs, snapshots, or binary files via web UI.
- 🚀 **Intranet Ready**: Uses Nokia internal LLM API; no external keys.

## Quick Start

### Option 1: Docker (Recommended for Production/CI)

```bash
# Build and run in one command
docker-compose up --build

# Or just run (uses cached image if built)
docker-compose up

# Access web UI at http://localhost:5000/
```

### Option 2: Local Python

```bash
# Install dependencies
pip install -r requirements.txt --proxy http://10.144.1.10:8080

# Run Flask app
python -m src.app

# Access web UI at http://localhost:5000/
```

## Project Structure

```
skillFlow/
├── src/
│   ├── main.py              # CLI entry point
│   ├── app.py               # Flask web app
│   ├── scanner.py           # SKILL.md parser
│   ├── executor.py          # LLM API caller
│   └── skill_runner.py      # Tool-first execution layer
├── dev-skills/              # Skill definitions
│   └── analyze-ims2/        # Example: IMS2 analysis skill
│       └── SKILL.md
├── config/
│   └── skill_adapters.yaml  # Tool execution config
├── web/
│   └── index.html           # Web UI (Vanilla JS)
├── tests/                   # Unit tests
├── Dockerfile               # Multi-stage Docker build
├── docker-compose.yml       # Docker Compose config
└── requirements.txt         # Python dependencies
```

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_API_URL` | `http://hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions` | Nokia internal LLM endpoint |
| `LLM_MODEL` | `qwen/qwen3-32b` | LLM model name |
| `FLASK_ENV` | `production` | Flask environment (set to `development` for debug) |
| `GITLAB_REPO_URL` | *(empty)* | If set, skills are loaded from this GitLab repo: clone on first start, `git pull --ff-only` on each app start. Use HTTPS URL (e.g. `https://gitlab.example.com/group/dev-skills.git`). Leave empty to use only local `dev-skills/`. |
| `GITLAB_BRANCH` | `main` | Branch to clone/pull when `GITLAB_REPO_URL` is set. |
| `GITLAB_TOKEN` | *(empty)* | GitLab personal access token (PAT) for private repos. Injected as `oauth2:<token>@` in the clone URL — never logged. |
| `GITLAB_SKILLS_CACHE` | *(empty)* | When `GITLAB_REPO_URL` is set: directory to clone into. Default: `<repo>/var/gitlab-skills` (avoids overwriting the bundled `dev-skills/` tree). |
| `SKILLS_PATH` | *(see below)* | If set, **always** use this directory for skills (no GitLab sync). If unset and `GITLAB_REPO_URL` is set, uses `GITLAB_SKILLS_CACHE` or `var/gitlab-skills`. If both unset, uses `dev-skills/` under the project root. |
| `SKILLFLOW_LOG_LEVEL` | `INFO` | Root log level for `skillflow.*` loggers (`DEBUG`, `INFO`, `WARNING`, …). |

### Load skills from GitLab

Skills are discovered from any `**/SKILL.md` under the resolved skills directory. To use the **real** skill repo on GitLab instead of (or in addition to) the sample tree under `dev-skills/`:

1. Set `GITLAB_REPO_URL` to the HTTPS clone URL of your skills repository.
2. For private repos, set `GITLAB_TOKEN` (PAT). It is embedded in the clone URL and never logged.
3. Leave `SKILLS_PATH` **unset** so the app can clone/pull into the default cache: `<project_root>/var/gitlab-skills` (override with `GITLAB_SKILLS_CACHE` if needed).
4. On each process start, SkillFlow runs `git pull --ff-only` if the cache already exists, or `git clone` on first run.

If you **set `SKILLS_PATH`**, that directory is used as-is and **GitLab sync is not run** (offline / custom layout).

Example (local run from the repository root):

```bash
set GITLAB_REPO_URL=https://your.gitlab.example.com/group/dev-skills.git
set GITLAB_BRANCH=main
set GITLAB_TOKEN=your_pat_if_private
python -m src.app
```

With Docker Compose, define the same variables in a `.env` file or your environment; the compose file mounts `./var/gitlab-skills` so clones survive container restarts.

### Git Configuration (Intranet Proxy)

Before `git push`, configure local proxy:

```bash
git config --local http.proxy http://10.144.1.10:8080
git config --local https.proxy http://10.144.1.10:8080
```

## Development

### Running Tests

```bash
pytest -q
```

### Adding a New Skill

1. Create `dev-skills/my-skill/SKILL.md` with YAML front-matter:

```yaml
---
id: my-skill
name: My Analysis Skill
description: What this skill does
inputs:
  - name: param1
    type: text
    label: Parameter 1
    placeholder: Enter something...
  - name: param2
    type: select
    label: Choose Mode
    options: [mode-a, mode-b]
    default: mode-a
---

# Skill Documentation

Your analysis instructions and guidelines here.
```

2. Optionally add tool execution in `config/skill_adapters.yaml`:

```yaml
skills:
  my-skill:
    execution_mode: tool-first
    tool:
      command: my_tool
      args_template:
        - --input
        - "{log_file_path}"
        - "{param1}"
      timeout_sec: 90
    fallback: llm-only
```

3. Restart the app — skill will appear in the web UI automatically.

## Deployment

### Docker (Recommended)

```bash
# Build production-ready image
docker build -t skillflow:latest .

# Run with environment overrides
docker run -p 5000:5000 \
  -e LLM_API_URL=http://your-llm-endpoint:8080/v1/chat/completions \
  skillflow:latest
```

### Health Check

The container includes a built-in health check. View status:

```bash
docker ps
# or
docker inspect --format='{{.State.Health.Status}}' skillflow-app
```

## Troubleshooting

### LLM API Connection Error (504 Gateway Timeout)

- **Cause**: System proxy intercepting intranet calls.
- **Fix**: Executor uses `proxies={"http": "", "https": ""}` to bypass system proxy for intranet access.

### Tool Execution Returns Non-Zero Exit

- Check tool stderr in `execution_note` response.
- Enable `RUST_BACKTRACE=1` in tool environment (Dockerfile sets this).
- For reproducible crashes, check tool compatibility with input file format.

### Import Errors When Running Directly

- Ensure `python -m src.app` (module mode) is used, not `python src/app.py`.
- If needed, `sys.path` injection in `src/app.py` handles both modes.

## Testing & CI

Unit tests are in `tests/` and run on every commit:

```bash
pytest -q                           # All tests
pytest -q -m "not regression"      # Exclude slow regression tests
pytest tests/test_app.py -v        # Verbose single file
```

GitHub Actions (`.github/workflows/`) runs tests on push and blocks merges on failure.

## Code Rules

See `AGENTS.md` for project constraints and best practices:
- TDD-first: tests before implementation.
- No hardcoded secrets; use environment variables.
- Tool-first behavior is adapter-driven (not hardcoded by skill name).
- Keep comments in English.

## Roadmap

- [x] **Phase 1**: Flask REST API backends (`/api/skills`, `/api/analyze`, `/api/analyze/stream`).
- [x] **Phase 2**: Web UI with skill explorer, search, file upload, terminal display.
- [x] **Phase 3**: Dynamic forms from SKILL.md metadata; adapter-driven tool execution.
- [x] **Phase 4a**: Docker containerization (Dockerfile, docker-compose); structured logging to stdout; request correlation id; `GET /health`; `SKILLFLOW_LOG_LEVEL`.
- [ ] **Phase 4b** (later): HTTPS/TLS termination at reverse proxy, Nokia SSO for web access.

### Streaming API note

`POST /api/analyze/stream` returns **Server-Sent Events**, but the LLM response is sent as **one complete `chunk` event** after the model finishes (not token-by-token streaming). The main UI uses synchronous `POST /api/analyze`.

## Support

For issues or questions:
1. Check `docs/plan.md` for current priorities.
2. Review `AGENTS.md` for project rules.
3. Run tests: `pytest -q` → ensure baseline is green.
4. Enable debug logs in Flask: set `FLASK_ENV=development`.

## License

Internal use only. © Nokia.
