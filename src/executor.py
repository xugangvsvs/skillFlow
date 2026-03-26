import os
import requests

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
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            return f"ERROR: 无法连接到 LLM 服务 ({self.api_url})，请确认网络或服务状态。"
        except requests.exceptions.Timeout:
            return "ERROR: LLM 服务响应超时，请稍后重试。"
        except requests.exceptions.HTTPError as e:
            return f"ERROR: LLM 服务返回错误 {e.response.status_code}: {e.response.text}"
        except (KeyError, IndexError, ValueError) as e:
            return f"ERROR: 解析 LLM 响应失败: {str(e)}"
