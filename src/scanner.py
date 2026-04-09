import logging
import os
import subprocess
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("skillflow.scanner")


def _parse_skills_under(root: Path) -> List[Dict[str, Any]]:
    """Load all valid SKILL.md documents under ``root`` (recursive)."""
    skills: List[Dict[str, Any]] = []
    if not root.is_dir():
        return skills
    for md_file in root.glob("**/SKILL.md"):
        try:
            with open(md_file, encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            log.warning("could not read %s: %s", md_file, exc)
            continue
        if content.startswith("---"):
            parts = content.split("---")
            if len(parts) >= 3:
                data = yaml.safe_load(parts[1])
                if data:
                    data["abs_path"] = str(md_file)
                    data["full_content"] = content
                    skills.append(data)
    return skills


def _skill_name_key(skill: Dict[str, Any]) -> Optional[str]:
    """Return lowercase merge key from ``name``, or None if missing or blank."""
    n = skill.get("name")
    if n is None:
        return None
    s = str(n).strip()
    return s.lower() if s else None


def _merge_skills(primary: List[Dict[str, Any]], supplemental: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Append supplemental skills whose ``name`` is not already taken (case-insensitive)."""
    seen: set[str] = set()
    for sk in primary:
        k = _skill_name_key(sk)
        if k is not None:
            seen.add(k)
    out = list(primary)
    for sk in supplemental:
        k = _skill_name_key(sk)
        if k is None:
            out.append(sk)
            continue
        if k not in seen:
            seen.add(k)
            out.append(sk)
    return out


class SkillScanner:
    """Discover and parse SKILL.md files from a local directory or remote GitLab repo.

    When ``gitlab_repo_url`` is provided the scanner will:
    - ``git clone`` the repo to ``repo_path`` on the first run (directory absent or no .git).
    - ``git pull --ff-only`` on subsequent runs (directory already cloned).

    Sync failures are logged and do not stop startup; existing cache files are still scanned.

    Set ``GITLAB_TOKEN`` environment variable for private repo access.  The token
    is injected into the HTTPS clone URL as a credentials placeholder and is never logged.
    """

    def __init__(
        self,
        repo_path: str,
        gitlab_repo_url: Optional[str] = None,
        gitlab_branch: str = "main",
        supplement_repo_paths: Optional[List[str]] = None,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.gitlab_repo_url = gitlab_repo_url
        self.gitlab_branch = gitlab_branch
        self.supplement_repo_paths: List[str] = list(supplement_repo_paths or [])

    def _authenticated_url(self, url: str) -> str:
        """Inject GITLAB_TOKEN into the HTTPS clone URL if available."""
        token = os.environ.get("GITLAB_TOKEN", "")
        if token and url.startswith("https://"):
            return url.replace("https://", f"https://oauth2:{token}@", 1)
        return url

    def _sync_from_gitlab(self) -> None:
        """Clone or pull latest skills from GitLab; logs a warning on failure."""
        repo_dir = str(self.repo_path)
        is_cloned = (self.repo_path / ".git").exists()

        try:
            if is_cloned:
                log.info(
                    "GitLab sync: pulling latest from %s branch=%s",
                    self.gitlab_repo_url,
                    self.gitlab_branch,
                )
                subprocess.run(
                    ["git", "-C", repo_dir, "pull", "--ff-only", "origin", self.gitlab_branch],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                log.info("GitLab sync: pull complete")
            else:
                log.info("GitLab sync: cloning %s to %s", self.gitlab_repo_url, repo_dir)
                auth_url = self._authenticated_url(self.gitlab_repo_url or "")
                subprocess.run(
                    ["git", "clone", "--branch", self.gitlab_branch, "--depth", "1", auth_url, repo_dir],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                log.info("GitLab sync: clone complete")
        except subprocess.CalledProcessError as exc:
            stderr_msg = (exc.stderr or "").strip()
            log.warning(
                "GitLab skill sync failed for %s: %s — continuing with on-disk cache and supplements",
                self.gitlab_repo_url,
                stderr_msg,
            )

    def scan(self) -> List[Dict[str, Any]]:
        if self.gitlab_repo_url:
            self._sync_from_gitlab()

        primary = _parse_skills_under(self.repo_path)
        merged = list(primary)

        for raw in self.supplement_repo_paths:
            sup = Path(raw).resolve()
            if sup == self.repo_path:
                continue
            if not sup.is_dir():
                log.debug("supplement skills path missing or not a directory: %s", sup)
                continue
            extra = _parse_skills_under(sup)
            if extra:
                log.info(
                    "merging %d skill(s) from supplement %s (GitLab primary wins on duplicate names)",
                    len(extra),
                    sup,
                )
            merged = _merge_skills(merged, extra)

        return merged


def match_skill(skills, user_input):
    """Minimal, robust skill matcher for CLI-style input."""
    if not user_input:
        return None

    query = user_input.lower()

    for skill in skills:
        # A: keywords (highest priority) — normalize to list
        kws = skill.get("keywords") or []
        if isinstance(kws, str):
            kws = [kws]

        if any(str(k).lower() in query for k in kws if k):
            return skill

        # B: description
        desc = skill.get("description") or ""
        if query in str(desc).lower():
            return skill

        # C: name (fallback)
        name = skill.get("name") or ""
        if query in str(name).lower():
            return skill

    return None
