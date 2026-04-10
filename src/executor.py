from __future__ import annotations

import logging
import os
from typing import Dict, Optional
from urllib.parse import urlparse

import requests

log = logging.getLogger("skillflow.executor")

LLM_API_URL = os.environ.get(
    "LLM_API_URL",
    "http://hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions"
)
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3-32b")


def _llm_bearer_token() -> str:
    """OpenAI-compatible ``Authorization: Bearer`` token (e.g. Alibaba DashScope API key).

    ``LLM_API_KEY`` is checked first, then ``DASHSCOPE_API_KEY`` (per Alibaba docs).
    """
    for key in ("LLM_API_KEY", "DASHSCOPE_API_KEY"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            return raw
    return ""


def _llm_request_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = _llm_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _llm_should_bypass_proxy(api_url: str) -> bool:
    """Use empty proxies (no HTTP(S)_PROXY) for known intranet hosts.

    Public endpoints (e.g. DashScope) default to ``trust_env`` so corporate
    ``HTTPS_PROXY`` works. Set ``LLM_BYPASS_PROXY=1`` to force direct connection.
    """
    flag = (os.environ.get("LLM_BYPASS_PROXY") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    try:
        host = (urlparse(api_url).hostname or "").lower()
    except ValueError:
        return False
    intranet_markers = ("nokia.net", "hzllmapi", "localhost", "127.0.0.1")
    return any(m in host for m in intranet_markers)


def _llm_proxies_for_url(api_url: str) -> Optional[Dict[str, str]]:
    if _llm_should_bypass_proxy(api_url):
        return {"http": "", "https": ""}
    return None


def llm_request_timeout() -> tuple[float, float]:
    """``requests`` timeout as ``(connect, read)`` in seconds.

    Short prompts often finish in seconds; use cases with large logs or Gerrit
    patches routinely exceed 60s generation time on cloud APIs.

    Env:
    - ``LLM_HTTP_READ_TIMEOUT_SECONDS`` or ``LLM_HTTP_TIMEOUT_SECONDS``: read
      timeout (waiting for the model response). Default ``180``.
    - ``LLM_HTTP_CONNECT_TIMEOUT_SECONDS``: connect timeout. Default ``30``.
    """
    connect_raw = (os.environ.get("LLM_HTTP_CONNECT_TIMEOUT_SECONDS") or "").strip()
    try:
        connect = float(connect_raw) if connect_raw else 30.0
    except ValueError:
        connect = 30.0
    read_raw = (
        os.environ.get("LLM_HTTP_READ_TIMEOUT_SECONDS")
        or os.environ.get("LLM_HTTP_TIMEOUT_SECONDS")
        or ""
    ).strip()
    try:
        read = float(read_raw) if read_raw else 180.0
    except ValueError:
        read = 180.0
    read = max(read, 10.0)
    connect = max(min(connect, read), 1.0)
    return (connect, read)


class CopilotExecutor:
    def __init__(self, api_url: str = LLM_API_URL, model: str = LLM_MODEL):
        self.api_url = api_url
        self.model = model

    def ask_ai(self, prompt: str) -> str:
        timeout = llm_request_timeout()
        log.info(
            "Calling LLM API: url=%s model=%s prompt_len=%d timeout=%s",
            self.api_url,
            self.model,
            len(prompt),
            timeout,
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=_llm_request_headers(),
                proxies=_llm_proxies_for_url(self.api_url),
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            log.info("LLM response received: result_len=%d", len(result))
            return result
        except requests.exceptions.ConnectionError as e:
            log.warning("LLM connection error: %s", e)
            return (
                f"ERROR: Cannot connect to LLM service ({self.api_url}). "
                "Check network reachability and service status. "
                "For public APIs (e.g. DashScope) on a corporate network, set HTTPS_PROXY "
                "(and HTTP_PROXY) in the environment; use LLM_BYPASS_PROXY=1 only for intranet LLMs."
            )
        except requests.exceptions.Timeout as e:
            log.warning("LLM timeout: %s", e)
            return (
                "ERROR: LLM request timed out. Retry later. "
                "Large prompts (e.g. Gerrit patches) may need a higher "
                "LLM_HTTP_READ_TIMEOUT_SECONDS (or LLM_HTTP_TIMEOUT_SECONDS)."
            )
        except requests.exceptions.HTTPError as e:
            log.warning("LLM HTTP error: status=%s", e.response.status_code)
            return f"ERROR: LLM returned HTTP {e.response.status_code}: {e.response.text}"
        except (KeyError, IndexError, ValueError) as e:
            log.warning("LLM response parse error: %s", e)
            return f"ERROR: Failed to parse LLM response: {str(e)}"
