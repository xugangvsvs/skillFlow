#!/usr/bin/env python3
"""Minimal check that the configured OpenAI-compatible LLM (e.g. DashScope) works.

Uses the same env vars as SkillFlow: LLM_API_URL, LLM_MODEL, LLM_API_KEY / DASHSCOPE_API_KEY,
and the same read/connect timeouts as ``src.executor`` (``LLM_HTTP_*_TIMEOUT``).
On corporate networks, set HTTPS_PROXY / HTTP_PROXY if needed.

  python scripts/test_dashscope_llm.py
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import requests
    except ImportError:
        print("ERROR: Install requests (e.g. pip install requests)", file=sys.stderr)
        return 1

    _repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo not in sys.path:
        sys.path.insert(0, _repo)
    from src.executor import llm_request_timeout

    url = (os.environ.get("LLM_API_URL") or "").strip()
    if not url:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    model = (os.environ.get("LLM_MODEL") or "").strip() or "qwen3.6-plus"
    key = (os.environ.get("LLM_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or "").strip()
    if not key:
        print(
            "ERROR: Set DASHSCOPE_API_KEY or LLM_API_KEY in the environment.",
            file=sys.stderr,
        )
        return 1

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly one word: OK"}],
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    timeout = llm_request_timeout()
    print(f"POST {url}")
    print(f"model={model!r} timeout={timeout!r} (connect, read seconds)")
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        print(
            "ERROR: Request timed out. Try LLM_HTTP_READ_TIMEOUT_SECONDS=300 or HTTPS_PROXY on corporate Wi‑Fi.",
            file=sys.stderr,
        )
        return 1
    except requests.exceptions.ConnectionError as exc:
        print(f"ERROR: Cannot connect: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:1200])
        return 1

    try:
        data = r.json()
        msg = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        print(f"ERROR: Unexpected response JSON: {exc}", file=sys.stderr)
        print(r.text[:800])
        return 1

    print("reply:", msg[:500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
