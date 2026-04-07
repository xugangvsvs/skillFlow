import pytest
from src.executor import CopilotExecutor


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


def test_executor_uses_configured_model(mocker):
    """Configured model is sent in the JSON payload."""
    mock_post = mocker.patch("requests.post", return_value=_mock_response(mocker, "analysis result"))

    exe = CopilotExecutor(model="qwen/qwen3-32b")
    exe.ask_ai("Explain ims2")

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "qwen/qwen3-32b"


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
