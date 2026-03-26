def test_executor_logic_with_mock(mocker):
    # 模拟 subprocess.run 的行为，不真的去调那个报错的 Node.js
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = "AI: Suggested fix for log error."
    mock_run.return_value.returncode = 0

    from src.executor import CopilotExecutor
    exe = CopilotExecutor()
    response = exe.ask_ai("Explain error")

    assert "AI:" in response
    # 验证是否按照预期拼装了命令
    args, kwargs = mock_run.call_args
    assert "explain" in args[0]

def test_executor_new_cli_call(mocker):
    """验证是否调用了正确的新版 CLI 命令"""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "This command analyzes IMS2 snapshots..."

    from src.executor import CopilotExecutor
    exe = CopilotExecutor()
    res = exe.ask_ai("Explain ims2")

    # 验证调用的命令是否包含 explain
    args, kwargs = mock_run.call_args
    assert "explain" in args[0]
    assert res == "This command analyzes IMS2 snapshots..."
