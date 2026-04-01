import logging
import os
import subprocess
import yaml
from pathlib import Path
from typing import Optional

log = logging.getLogger("skillflow.scanner")


class SkillScanner:
    """Discover and parse SKILL.md files from a local directory or remote GitLab repo.

    When ``gitlab_repo_url`` is provided the scanner will:
    - ``git clone`` the repo to ``repo_path`` on the first run (directory absent or no .git).
    - ``git pull --ff-only`` on subsequent runs (directory already cloned).

    Set ``GITLAB_TOKEN`` environment variable for private repo access.  The token
    is injected into the HTTPS URL as a credentials placeholder and is never logged.
    """

    def __init__(
        self,
        repo_path: str,
        gitlab_repo_url: Optional[str] = None,
        gitlab_branch: str = "main",
    ):
        self.repo_path = Path(repo_path)
        self.gitlab_repo_url = gitlab_repo_url
        self.gitlab_branch = gitlab_branch

    def _authenticated_url(self, url: str) -> str:
        """Inject GITLAB_TOKEN into the HTTPS clone URL if available."""
        token = os.environ.get("GITLAB_TOKEN", "")
        if token and url.startswith("https://"):
            # https://token@host/path
            return url.replace("https://", f"https://oauth2:{token}@", 1)
        return url

    def _sync_from_gitlab(self) -> None:
        """Clone or pull latest skills from GitLab; raises RuntimeError on failure."""
        repo_dir = str(self.repo_path)
        is_cloned = (self.repo_path / ".git").exists()

        try:
            if is_cloned:
                log.info("GitLab sync: pulling latest from %s branch=%s", self.gitlab_repo_url, self.gitlab_branch)
                subprocess.run(
                    ["git", "-C", repo_dir, "pull", "--ff-only", "origin", self.gitlab_branch],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                log.info("GitLab sync: pull complete")
            else:
                log.info("GitLab sync: cloning %s to %s", self.gitlab_repo_url, repo_dir)
                auth_url = self._authenticated_url(self.gitlab_repo_url)
                subprocess.run(
                    ["git", "clone", "--branch", self.gitlab_branch, "--depth", "1", auth_url, repo_dir],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                log.info("GitLab sync: clone complete")
        except subprocess.CalledProcessError as exc:
            stderr_msg = (exc.stderr or "").strip()
            raise RuntimeError(
                f"GitLab skill sync failed for {self.gitlab_repo_url}: {stderr_msg}"
            ) from exc

    def scan(self):
        if self.gitlab_repo_url:
            self._sync_from_gitlab()

        skills = []
        for md_file in self.repo_path.glob("**/SKILL.md"):
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.startswith("---"):
                    parts = content.split("---")
                    if len(parts) >= 3:
                        data = yaml.safe_load(parts[1])
                        if data:
                            data['abs_path'] = str(md_file)
                            data['full_content'] = content
                            skills.append(data)
        return skills

def match_skill(skills, user_input):
    """
    极简、健壮的匹配引擎
    """
    if not user_input:
        return None
    
    # 1. 统一转小写
    query = user_input.lower()
    
    for skill in skills:
        # --- 维度 A: Keywords (最优先) ---
        # 使用 or [] 确保哪怕 YAML 没填内容，keywords 也是个列表
        kws = skill.get('keywords') or []
        if isinstance(kws, str):
            kws = [kws]
        
        # 只要有一个 keyword 被包含在用户输入中
        if any(str(k).lower() in query for k in kws if k):
            return skill

        # --- 维度 B: Description (次优先) ---
        desc = skill.get('description') or ""
        if query in str(desc).lower():
            return skill

        # --- 维度 C: Name (保底) ---
        name = skill.get('name') or ""
        if query in str(name).lower():
            return skill
            
    return None
