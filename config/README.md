# Configuration directory

## `skillflow.yaml` — application settings (you create this)

1. **Copy** `skillflow.example.yaml` → **`skillflow.yaml`** (same folder).
2. **Edit** `skillflow.yaml`: e.g. `gitlab_repo_url`, `gitlab_branch`, optional `llm_api_url` / `llm_model`.
3. **`skillflow.yaml` is gitignored** so your URLs and choices stay local; only the example file is tracked in git.

**Secrets:** do not put tokens in YAML. Use the **`GITLAB_TOKEN`** environment variable for private GitLab.

**Overrides:** any non-empty environment variable still wins over the YAML value.

Full documentation: repository **[README.md](../README.md)** → sections *First-time configuration* and *Configuration file*.

## `skill_adapters.yaml`

Maps skills to external tools (tool-first execution). Keys must match **`name`** in each skill’s `SKILL.md`. See the main README.

## Use cases

Use cases are **not** configured here. They are fixed in **[`../src/use_cases.py`](../src/use_cases.py)** (`FIXED_USE_CASE_DEFINITIONS`). Each `skill_name` in that list must match a loaded `SKILL.md` **`name`** (and adapter keys when using tools).
