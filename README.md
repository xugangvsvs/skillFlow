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
| `GITLAB_REPO_URL` | *(empty)* | GitLab HTTPS clone URL for remote skill definitions (e.g. `https://gitlabe2.ext.net.nokia.com/boam-fh-ai/dev-skills.git`). Leave empty to use local `dev-skills/` directory. |
| `GITLAB_BRANCH` | `main` | Branch to clone/pull from when `GITLAB_REPO_URL` is set. |
| `GITLAB_TOKEN` | *(empty)* | GitLab personal access token (PAT) for private repos. Injected as `oauth2:<token>@` in the clone URL — never logged. |
| `SKILLS_PATH` | `./dev-skills` | Local path to skill definitions; overridden by `GITLAB_REPO_URL` if set. |

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
- [ ] **Phase 4**: Docker containerization, HTTPS/TLS, Nokia SSO auth, structured logging.

## Support

For issues or questions:
1. Check `docs/plan.md` for current priorities.
2. Review `AGENTS.md` for project rules.
3. Run tests: `pytest -q` → ensure baseline is green.
4. Enable debug logs in Flask: set `FLASK_ENV=development`.

## License

Internal use only. © Nokia.
