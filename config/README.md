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

## `use_cases.yaml` — optional (you create this)

1. **Copy** `use_cases.example.yaml` → **`use_cases.yaml`** (same folder), or set `use_cases_path` in `skillflow.yaml`.
2. Each entry has **`id`**, **`title`**, **`skill_name`** (must match a loaded skill’s `name`), optional **`description`**, **`prompt_prefix`**, and optional **`inputs`** (if omitted, inputs are copied from that skill).
3. **`use_cases.yaml` is gitignored**; the example file stays in git.

Align **`skill_name`** with GitLab `SKILL.md` **`name`** and with **`skill_adapters.yaml`** keys when using tools.
