import pytest
from src.executor import CopilotExecutor, llm_request_timeout


def _mock_response(mocker, content="AI: Suggested fix for log error.", status_code=200):
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    mock_resp.raise_for_status = mocker.MagicMock()
    return mock_resp


def test_executor_returns_ai_content(mocker):
    """Happy path: return choices[0].message.content."""
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker))

    exe = CopilotExecutor()
    response = exe.ask_ai("Explain error")

    assert response == "AI: Suggested fix for log error."
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["messages"][0]["content"] == "Explain error"
    # Default URL is intranet-style: bypass env proxy
    assert kwargs["proxies"] == {"http": "", "https": ""}
    assert kwargs["timeout"] == llm_request_timeout()


def test_executor_uses_configured_model(mocker):
    """Configured model is sent in the JSON payload."""
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker, "analysis result"))

    exe = CopilotExecutor(model="qwen/qwen3-32b")
    exe.ask_ai("Explain ims2")

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "qwen/qwen3-32b"


def test_executor_sends_bearer_when_dashscope_key_set(mocker, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-ds-test")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker))

    CopilotExecutor().ask_ai("hi")

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer sk-ds-test"


def test_executor_no_authorization_without_api_key(mocker, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker))

    CopilotExecutor().ask_ai("hi")

    _, kwargs = mock_post.call_args
    assert "Authorization" not in kwargs["headers"]


def test_executor_llm_api_key_takes_precedence(mocker, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-first")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-second")
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker))

    CopilotExecutor().ask_ai("hi")

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer sk-first"


def test_executor_public_llm_uses_system_proxy(mocker, monkeypatch):
    """DashScope and other public URLs must not force empty proxies (so HTTPS_PROXY works)."""
    monkeypatch.delenv("LLM_BYPASS_PROXY", raising=False)
    ds = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker))

    CopilotExecutor(api_url=ds).ask_ai("hi")

    _, kwargs = mock_post.call_args
    assert kwargs["proxies"] is None


def test_executor_llm_bypass_proxy_forces_no_proxy(mocker, monkeypatch):
    monkeypatch.setenv("LLM_BYPASS_PROXY", "1")
    ds = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker))

    CopilotExecutor(api_url=ds).ask_ai("hi")

    _, kwargs = mock_post.call_args
    assert kwargs["proxies"] == {"http": "", "https": ""}


def test_executor_connection_error(mocker):
    """Connection errors return a readable English message."""
    import requests as req
    mocker.patch("requests.post", side_effect=req.exceptions.ConnectionError())

    exe = CopilotExecutor()
    result = exe.ask_ai("any prompt")

    assert result.startswith("ERROR: Cannot connect to LLM service")


def test_executor_timeout(mocker):
    """Timeouts return a readable English message."""
    import requests as req
    mocker.patch("requests.post", side_effect=req.exceptions.Timeout())

    exe = CopilotExecutor()
    result = exe.ask_ai("any prompt")

    assert "timed out" in result.lower()
    assert "LLM_HTTP_READ_TIMEOUT_SECONDS" in result


def test_llm_request_timeout_defaults(monkeypatch):
    monkeypatch.delenv("LLM_HTTP_CONNECT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_HTTP_READ_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_HTTP_TIMEOUT_SECONDS", raising=False)
    assert llm_request_timeout() == (30.0, 180.0)


def test_llm_request_timeout_from_env(monkeypatch):
    monkeypatch.setenv("LLM_HTTP_CONNECT_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("LLM_HTTP_TIMEOUT_SECONDS", "400")
    assert llm_request_timeout() == (15.0, 400.0)
