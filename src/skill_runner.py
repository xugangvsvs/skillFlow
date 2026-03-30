import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional

import yaml


class SkillRunner:
    """Adapter-driven tool execution layer for tool-first skills."""

    def __init__(self, adapter_path: str = "./config/skill_adapters.yaml"):
        self.adapter_path = adapter_path
        self.adapters = self._load_adapters(adapter_path)

    def _load_adapters(self, adapter_path: str) -> Dict[str, Any]:
        if not os.path.exists(adapter_path):
            return {}

        with open(adapter_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        if isinstance(data, dict) and "skills" in data and isinstance(data["skills"], dict):
            return data["skills"]

        if isinstance(data, dict):
            return data

        return {}

    def get_adapter(self, skill_name: str) -> Optional[Dict[str, Any]]:
        adapter = self.adapters.get(skill_name)
        if isinstance(adapter, dict):
            return adapter
        return None

    def _resolve_tool_command(self, tool_cfg: Dict[str, Any]) -> str:
        """Resolve tool command from candidates, environment variables, and PATH."""
        command = str(tool_cfg.get("command") or "").strip()
        candidates = tool_cfg.get("command_candidates") or []

        ordered_candidates = []
        if command:
            ordered_candidates.append(command)
        ordered_candidates.extend(str(item).strip() for item in candidates if str(item).strip())

        for candidate in ordered_candidates:
            expanded = os.path.expandvars(candidate)
            expanded = expanded.replace("{IMS2_BIN_DIR}", os.environ.get("IMS2_BIN_DIR", "")).strip()
            if not expanded:
                continue

            # Absolute path candidate
            if os.path.isabs(expanded) and os.path.exists(expanded):
                return expanded

            # Relative path candidate
            if os.path.exists(expanded):
                return os.path.abspath(expanded)

            # PATH lookup candidate
            resolved = shutil.which(expanded)
            if resolved:
                return resolved

        return ""

    def run_tool_if_configured(
        self,
        skill_name: str,
        file_name: str = "",
        file_bytes: Optional[bytes] = None,
    ) -> Dict[str, str]:
        """
        Try tool-first execution when adapter declares it.

        Returns:
            {
              "mode": "tool-first" | "fallback",
              "tool_output": "...",
              "note": "..."
            }
        """
        adapter = self.get_adapter(skill_name)
        if not adapter:
            return {"mode": "fallback", "tool_output": "", "note": "No adapter configured"}

        if adapter.get("execution_mode") != "tool-first":
            return {"mode": "fallback", "tool_output": "", "note": "Adapter mode is not tool-first"}

        tool_cfg = adapter.get("tool") or {}
        command = self._resolve_tool_command(tool_cfg)
        args_template = tool_cfg.get("args_template") or []
        timeout_sec = int(tool_cfg.get("timeout_sec") or 90)

        if not command:
            return {
                "mode": "fallback",
                "tool_output": "",
                "note": "Tool command could not be resolved (check adapter command_candidates, IMS2_TOOL_PATH, IMS2_BIN_DIR, or PATH)",
            }

        if not file_bytes:
            return {"mode": "fallback", "tool_output": "", "note": "No uploaded file provided for tool-first mode"}

        suffix = os.path.splitext(file_name)[1] if file_name else ".log"
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name

            args = [
                str(arg)
                .replace("{log_file_path}", tmp_path)
                .replace("{file_name}", file_name or os.path.basename(tmp_path))
                for arg in args_template
            ]
            cmd = [command] + args

            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=False,
            )

            if completed.returncode != 0:
                note = completed.stderr.strip() or f"Tool exited with code {completed.returncode}"
                return {"mode": "fallback", "tool_output": "", "note": note}

            return {
                "mode": "tool-first",
                "tool_output": completed.stdout.strip(),
                "note": f"Tool '{command}' executed successfully",
            }
        except subprocess.TimeoutExpired:
            return {"mode": "fallback", "tool_output": "", "note": "Tool execution timed out"}
        except Exception as exc:
            return {"mode": "fallback", "tool_output": "", "note": f"Tool execution error: {exc}"}
        finally:
            if tmp_file is not None:
                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    pass
