# SkillFlow — Enterprise Intranet AI Assistant

SkillFlow is a Python-based web application that maps user requests to pre-defined "skills" (AI-powered analysis modules) and delivers results via Nokia's internal LLM API. Built for enterprise intranet use with zero external API dependencies.

## First-time configuration (read this)

| If you want… | Do this |
|--------------|---------|
| **Skills from GitLab** (recommended in many deployments) | Copy [`config/skillflow.example.yaml`](config/skillflow.example.yaml) to **`config/skillflow.yaml`**, set `gitlab_repo_url` (and branch if needed). See [Configuration file](#configuration-file-configskillflowyaml). Private repos: set **`GITLAB_TOKEN`** in the environment only. |
| **Skills only from this repo’s sample tree** | You can skip the file: defaults use `dev-skills/` with no GitLab sync. |
| **Custom LLM URL / model** | Same YAML file: `llm_api_url` / `llm_model`, or use environment variables. |
| **Use cases tab / `use_case_id` API** | Optional: copy [`config/use_cases.example.yaml`](config/use_cases.example.yaml) to **`config/use_cases.yaml`**, or set `use_cases_path` in `skillflow.yaml`. See [Use cases](#use-cases-business-scenarios). |

More detail: **[Configuration](#configuration)** (YAML + env vars) and the short guide in **[`config/README.md`](config/README.md)**.

## Architecture

- **Scout** (`src/scanner.py`): Discovers and parses skill definitions from `dev-skills/`, or from GitLab when configured via **`config/skillflow.yaml`** (or env vars).
- **Brain** (`src/executor.py`): Calls Nokia internal LLM API (`qwen/qwen3-32b`) with structured prompts.
- **Face** (`web/index.html` + Flask): Web UI for skill or **use case** selection (tabs), log upload, and result display.
- **Guard** (`src/skill_runner.py`): Tool-first execution layer with fallback to LLM-only mode.

## Features

- 🔍 **Skill Discovery**: Auto-scan `SKILL.md` files for skill definitions.
- 📝 **Dynamic Forms**: Auto-generate input fields from SKILL.md metadata.
- 🔧 **Tool-First Execution**: Run external tools (e.g., `ims2_tool`) with graceful LLM fallback.
- 📤 **File Upload**: Analyze logs, snapshots, or binary files via web UI.
- **Use cases**: Optional catalog (`config/use_cases.yaml`) maps friendly scenario ids to underlying `SKILL.md` **`name`** values (same names as GitLab-synced skills). Web UI **Use cases** tab; API `GET /api/use-cases` and `use_case_id` on `POST /api/analyze` (see below).
- 🚀 **Intranet Ready**: Uses Nokia internal LLM API; no external keys.

## Quick Start

### Option 1: Docker (Recommended for Production/CI)

For GitLab skills or non-default LLM settings, create **`config/skillflow.yaml`** first (copy from `config/skillflow.example.yaml`). See [First-time configuration](#first-time-configuration-read-this).

```bash
# Build and run in one command
docker-compose up --build

# Or just run (uses cached image if built)
docker-compose up

# Access web UI at http://localhost:5000/
```

### Option 2: Local Python

Create **`config/skillflow.yaml`** when you need GitLab or overrides (copy from `config/skillflow.example.yaml`). Optional if you only use bundled `dev-skills/`.

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
│   ├── skill_runner.py      # Tool-first execution layer
│   ├── skill_paths.py       # Resolve local vs GitLab clone directory
│   ├── skillflow_config.py  # Load config/skillflow.yaml (env overrides)
│   └── use_cases.py         # Use case catalog → skill_name resolution
├── dev-skills/              # Skill definitions
│   └── analyze-ims2/        # Example: IMS2 analysis skill
│       └── SKILL.md
├── config/
│   ├── README.md            # Pointers: skillflow.yaml setup
│   ├── skill_adapters.yaml  # Tool execution config
│   ├── use_cases.example.yaml  # Copy to use_cases.yaml for use-case catalog
│   └── skillflow.example.yaml  # Copy to skillflow.yaml for local settings
├── web/
│   └── index.html           # Web UI (Vanilla JS)
├── tests/                   # Unit tests
├── Dockerfile               # Multi-stage Docker build
├── docker-compose.yml       # Docker Compose config
└── requirements.txt         # Python dependencies
```

## Configuration

### Configuration file (`config/skillflow.yaml`)

You can store non-secret defaults in YAML instead of exporting many environment variables.

1. Copy the template: `config/skillflow.example.yaml` → `config/skillflow.yaml`
2. Edit `gitlab_repo_url`, `gitlab_branch`, optional `skills_path` / `gitlab_skills_cache`, optional `use_cases_path`, optional `llm_api_url` / `llm_model`, optional `log_level`.
3. **Do not** put `GITLAB_TOKEN` or other secrets in this file — use environment variables for those.

**Precedence:** for each setting, if the **environment variable** is set and non-empty, it **overrides** the YAML value.

**Alternate path:** set `SKILLFLOW_CONFIG` to another YAML file (absolute path or path relative to the project root).

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SKILLFLOW_CONFIG` | *(empty)* | Optional path to a YAML file instead of `config/skillflow.yaml`. |
| `LLM_API_URL` | `http://hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions` | Nokia internal LLM endpoint (overrides `llm_api_url` in YAML). |
| `LLM_MODEL` | `qwen/qwen3-32b` | LLM model name (overrides `llm_model` in YAML). |
| `FLASK_ENV` | `production` | Flask environment (set to `development` for debug) |
| `GITLAB_REPO_URL` | *(empty)* | Same as YAML `gitlab_repo_url`: clone/pull skills from this HTTPS URL. |
| `GITLAB_BRANCH` | `main` | Same as YAML `gitlab_branch`. |
| `GITLAB_TOKEN` | *(empty)* | GitLab personal access token (PAT) for private repos. Injected as `oauth2:<token>@` in the clone URL — never logged. **Env only — not read from YAML.** |
| `GITLAB_SKILLS_CACHE` | *(empty)* | Same as YAML `gitlab_skills_cache` when using GitLab. |
| `SKILLS_PATH` | *(see below)* | Same as YAML `skills_path`: if set, that directory is used and GitLab sync is skipped. |
| `SKILLFLOW_LOG_LEVEL` | `INFO` | Same as YAML `log_level` for `skillflow.*` loggers. |
| `SKILLFLOW_USE_CASES_PATH` or `USE_CASES_PATH` | *(empty)* | Optional path to a use-case YAML file (overrides `use_cases_path` in `skillflow.yaml`). |

### Use cases (business scenarios)

Use cases wrap **existing** skills: each entry points at a `skill_name` that must match the **`name`** field in a `SKILL.md` loaded from `dev-skills/` or GitLab (and, for tool-first runs, the same key in `config/skill_adapters.yaml`).

The committed example catalog defines four scenarios: **EFS→PFS**, **PFS→ICFS**, **ICFS→Code/UT/SCT**, and **Pronto analysis**, with matching sample skills under `dev-skills/`. When you use GitLab, keep the same `name` values in your remote `SKILL.md` files (or edit `use_cases.yaml` to point at your names).

1. Copy [`config/use_cases.example.yaml`](config/use_cases.example.yaml) to **`config/use_cases.yaml`** (gitignored), or set `use_cases_path` in `skillflow.yaml` / `SKILLFLOW_USE_CASES_PATH`.
2. If neither `use_cases.yaml` nor `use_cases_path` exists, the app falls back to the committed **`use_cases.example.yaml`**.
3. **Web UI:** open the **Use cases** tab, pick a scenario, fill dynamic inputs (inherited from the skill unless overridden in YAML), then **Analyze**.
4. **API:** `GET /api/use-cases` returns `{ id, title, description, inputs, available }`. Submit analysis with JSON or multipart field **`use_case_id`** (and **`user_input`**). Do not send **`skill_name`** in the same request as **`use_case_id`**.
5. Optional **`prompt_prefix`** in YAML is prepended to `user_input` on the server only (trusted configuration).

### Load skills from GitLab

Skills are discovered from any `**/SKILL.md` under the resolved skills directory. To use the **real** skill repo on GitLab instead of the sample tree under `dev-skills/`:

**Option A — config file:** in `config/skillflow.yaml` set `gitlab_repo_url` (and optionally `gitlab_branch`, `gitlab_skills_cache`). For a private repo, still set `GITLAB_TOKEN` in the environment.

**Option B — environment only:** set `GITLAB_REPO_URL` (and optional vars as below).

1. For private repos, set `GITLAB_TOKEN` (PAT). It is embedded in the clone URL and never logged.
2. Leave `skills_path` / `SKILLS_PATH` **unset** so the app can clone/pull into the default cache: `<project_root>/var/gitlab-skills` (override with `gitlab_skills_cache` / `GITLAB_SKILLS_CACHE` if needed).
3. On each process start, SkillFlow runs `git pull --ff-only` if the cache already exists, or `git clone` on first run.

If you **set `skills_path` / `SKILLS_PATH`**, that directory is used as-is and **GitLab sync is not run** (offline / custom layout).

Example (environment variables, local run from the repository root):

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
1. **Configuration:** [First-time configuration](#first-time-configuration-read-this) and [`config/README.md`](config/README.md).
2. Check `docs/plan.md` for current priorities.
3. Review `AGENTS.md` for project rules.
4. Run tests: `pytest -q` → ensure baseline is green.
5. Enable debug logs in Flask: set `FLASK_ENV=development`.

## License

Internal use only. © Nokia.
