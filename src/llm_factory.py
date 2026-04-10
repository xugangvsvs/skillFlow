"""Construct the active LLM executor (HTTP chat vs Cursor CLI)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from src.cursor_cli_executor import CursorCliExecutor
from src.executor import CopilotExecutor


def create_llm_executor(
    *,
    project_root: Path,
    llm_api_url: str,
    llm_model: str,
) -> Union[CopilotExecutor, CursorCliExecutor]:
    backend = (os.environ.get("SKILLFLOW_LLM_BACKEND") or "http").strip().lower()
    if backend in ("cursor_cli", "cursor"):
        return CursorCliExecutor(model=llm_model, project_root=project_root)
    return CopilotExecutor(api_url=llm_api_url, model=llm_model)
