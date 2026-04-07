import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

log = logging.getLogger("skillflow.skill_runner")


def _substitution_map(
    tmp_path: str,
    file_name: str,
    input_params: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Build placeholder map for args_template / args_by_mode (plus safe defaults)."""
    merged: Dict[str, str] = {
        "log_file_path": tmp_path,
        "file_name": file_name or os.path.basename(tmp_path),
    }
    if input_params:
        for key, value in input_params.items():
            if value is None:
                continue
            text = str(value).strip()
            if text:
                merged[str(key)] = text
    merged.setdefault("focus_object", ".*")
    return merged


def _select_args_list(tool_cfg: Dict[str, Any], input_params: Optional[Dict[str, Any]]) -> List[Any]:
    """Pick argument template list: args_by_mode[analysis_mode] or legacy args_template."""
    args_by_mode = tool_cfg.get("args_by_mode")
    mode_param = str(tool_cfg.get("mode_param") or "analysis_mode")
    if isinstance(args_by_mode, dict) and args_by_mode:
        mode_raw = (input_params or {}).get(mode_param)
        mode = str(mode_raw).strip() if mode_raw is not None else ""
        if mode not in args_by_mode:
            for candidate in ("topology", "state", "transitions", "metadata"):
                if candidate in args_by_mode:
                    mode = candidate
                    break
            else:
                mode = next(iter(args_by_mode))
        return list(args_by_mode[mode])
    return list(tool_cfg.get("args_template") or [])


def _format_arg_list(args_list: List[Any], merged: Dict[str, str]) -> List[str]:
    formatted: List[str] = []
    for arg in args_list:
        s = str(arg)
        for key, value in merged.items():
            s = s.replace("{" + key + "}", value)
        formatted.append(s)
    return formatted


class SkillRunner:
    """Adapter-driven tool execution layer for tool-first skills."""

    def __init__(
        self,
        adapter_path: str = "./config/skill_adapters.yaml",
        search_roots: Optional[List[str]] = None,
    ):
        self.adapter_path = adapter_path
        self.adapters = self._load_adapters(adapter_path)
        self.search_roots = search_roots or self._default_search_roots(adapter_path)
        self._resolved_tool_cache: Dict[str, str] = {}

    def _default_search_roots(self, adapter_path: str) -> List[str]:
        """Return default roots for tool auto-discovery."""
        workspace_root = str(Path(adapter_path).resolve().parent.parent)
        return [
            workspace_root,
            os.path.join(workspace_root, "tools"),
            r"C:\radio_ctrl\tools",
        ]

    def _discover_tool_in_roots(self, command_name: str) -> str:
        """Search known roots for command_name and return first executable match."""
        if command_name in self._resolved_tool_cache:
            return self._resolved_tool_cache[command_name]

        probe_names = [command_name]
        if not command_name.lower().endswith(".exe"):
            probe_names.append(f"{command_name}.exe")

        for root in self.search_roots:
            if not root or not os.path.exists(root):
                continue
            for current_root, _, files in os.walk(root):
                file_set = set(files)
                for probe in probe_names:
                    if probe in file_set:
                        resolved = os.path.join(current_root, probe)
                        self._resolved_tool_cache[command_name] = resolved
                        return resolved

        return ""

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

            # Built-in auto-discovery in known roots
            discovered = self._discover_tool_in_roots(expanded)
            if discovered:
                return discovered

        return ""

    def run_tool_if_configured(
        self,
        skill_name: str,
        file_name: str = "",
        file_bytes: Optional[bytes] = None,
        input_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Try tool-first execution when adapter declares it.

        Returns:
            {
              "mode": "tool-first" | "fallback",
                            "reason": "...",
              "tool_output": "...",
              "note": "..."
            }
        """
        log.debug("run_tool_if_configured: skill=%s file=%s", skill_name, file_name)
        adapter = self.get_adapter(skill_name)
        if not adapter:
            log.debug("No adapter configured for skill '%s', falling back to LLM", skill_name)
            return {"mode": "fallback", "reason": "no_adapter", "tool_output": "", "note": "No adapter configured"}

        if adapter.get("execution_mode") != "tool-first":
            log.debug("Adapter mode is not tool-first for '%s'", skill_name)
            return {"mode": "fallback", "reason": "not_tool_first", "tool_output": "", "note": "Adapter mode is not tool-first"}

        tool_cfg = adapter.get("tool") or {}
        command = self._resolve_tool_command(tool_cfg)
        timeout_sec = int(tool_cfg.get("timeout_sec") or 90)

        if not command:
            log.warning("Tool command could not be resolved for skill '%s'", skill_name)
            return {
                "mode": "fallback",
                "reason": "command_not_found",
                "tool_output": "",
                "note": "Tool command could not be resolved (check adapter command_candidates, IMS2_TOOL_PATH, IMS2_BIN_DIR, or PATH)",
            }

        if not file_bytes:
            log.debug("No file bytes provided for tool-first execution of '%s'", skill_name)
            return {"mode": "fallback", "reason": "no_file", "tool_output": "", "note": "No uploaded file provided for tool-first mode"}

        suffix = os.path.splitext(file_name)[1] if file_name else ".log"
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            args_list = _select_args_list(tool_cfg, input_params)
            merged = _substitution_map(tmp_path, file_name, input_params)
            args = _format_arg_list(args_list, merged)
            cmd = [command] + args

            tool_cwd = os.path.dirname(command) or None
            tool_env = os.environ.copy()
            # Enable Rust backtrace by default for parser crash diagnostics.
            tool_env.setdefault("RUST_BACKTRACE", "1")

            log.info("Executing tool: cmd=%s cwd=%s", cmd, tool_cwd)
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                shell=False,
                cwd=tool_cwd,
                env=tool_env,
            )

            if completed.returncode != 0:
                note = completed.stderr.strip() or f"Tool exited with code {completed.returncode}"
                if tool_cwd:
                    note = f"{note}\n(tool cwd: {tool_cwd}, RUST_BACKTRACE={tool_env.get('RUST_BACKTRACE', '')})"
                log.warning("Tool exited with error: skill=%s returncode=%d", skill_name, completed.returncode)
                return {"mode": "fallback", "reason": "tool_error", "tool_output": "", "note": note}

            log.info("Tool executed successfully: skill=%s output_len=%d", skill_name, len(completed.stdout))
            return {
                "mode": "tool-first",
                "reason": "tool_success",
                "tool_output": completed.stdout.strip(),
                "note": f"Tool '{command}' executed successfully",
            }
        except subprocess.TimeoutExpired:
            log.warning("Tool execution timed out: skill=%s timeout=%ds", skill_name, timeout_sec)
            return {"mode": "fallback", "reason": "tool_timeout", "tool_output": "", "note": "Tool execution timed out"}
        except Exception as exc:
            log.warning("Tool execution error: skill=%s error=%s", skill_name, exc)
            return {"mode": "fallback", "reason": "tool_error", "tool_output": "", "note": f"Tool execution error: {exc}"}
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
