import logging
import os
import requests

log = logging.getLogger("skillflow.executor")

LLM_API_URL = os.environ.get(
    "LLM_API_URL",
    "http://hzllmapi.dyn.nesc.nokia.net:8080/v1/chat/completions"
)
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3-32b")


class CopilotExecutor:
    def __init__(self, api_url: str = LLM_API_URL, model: str = LLM_MODEL):
        self.api_url = api_url
        self.model = model

    def ask_ai(self, prompt: str) -> str:
        log.info("Calling LLM API: url=%s model=%s prompt_len=%d", self.api_url, self.model, len(prompt))
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                proxies={"http": "", "https": ""},  # bypass system proxy for intranet
                timeout=60,
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
                "Check network reachability and service status."
            )
        except requests.exceptions.Timeout as e:
            log.warning("LLM timeout: %s", e)
            return "ERROR: LLM request timed out. Retry later."
        except requests.exceptions.HTTPError as e:
            log.warning("LLM HTTP error: status=%s", e.response.status_code)
            return f"ERROR: LLM returned HTTP {e.response.status_code}: {e.response.text}"
        except (KeyError, IndexError, ValueError) as e:
            log.warning("LLM response parse error: %s", e)
            return f"ERROR: Failed to parse LLM response: {str(e)}"
