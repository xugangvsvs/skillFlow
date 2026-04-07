import pytest
import json
import io
from pathlib import Path
from unittest.mock import patch
from src.app import create_app

USE_CASES_EXAMPLE_YAML = Path(__file__).resolve().parent.parent / "config" / "use_cases.example.yaml"
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client_example_uc_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Stable use-case catalog; avoid GitLab sync if GITLAB_REPO_URL is set on the host."""
    cfg = tmp_path / "skillflow-test.yaml"
    cfg.write_text("log_level: INFO\n", encoding="utf-8")
    monkeypatch.setenv("SKILLFLOW_CONFIG", str(cfg))
    monkeypatch.delenv("GITLAB_REPO_URL", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    app = create_app(
        skill_path=str(REPO_ROOT / "dev-skills"),
        use_cases_path=str(USE_CASES_EXAMPLE_YAML),
    )
    app.config["TESTING"] = True
    with app.test_client() as tc:
        yield tc


def test_get_skills(client):
    """Test that /api/skills returns a list of available skills."""
    response = client.get("/api/skills")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    # Should have at least one skill (analyze-ims2)
    assert len(data) >= 1
    # Each skill should have expected fields
    if data:
        assert "name" in data[0]
        assert "description" in data[0]
        assert "inputs" in data[0]


def test_get_skills_exposes_inputs_metadata_from_front_matter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    sf = tmp_path / "skillflow-test.yaml"
    sf.write_text("log_level: INFO\n", encoding="utf-8")
    monkeypatch.setenv("SKILLFLOW_CONFIG", str(sf))
    monkeypatch.delenv("GITLAB_REPO_URL", raising=False)

    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "id: demo\n"
        "name: demo-skill\n"
        "description: demo description\n"
        "inputs:\n"
        "  - name: analysis_mode\n"
        "    type: select\n"
        "    label: Analysis mode\n"
        "    options: [topology, state]\n"
        "    default: topology\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    app = create_app(skill_path=str(tmp_path))
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/skills")

    assert response.status_code == 200
    skills = response.get_json()
    assert isinstance(skills, list)
    assert len(skills) == 1
    assert skills[0]["name"] == "demo-skill"
    assert isinstance(skills[0]["inputs"], list)
    assert skills[0]["inputs"][0]["name"] == "analysis_mode"


def test_analyze_with_valid_skill(client):
    """Test POST /api/analyze with a valid skill and user input."""
    with patch("src.app.CopilotExecutor") as mock_executor_class, patch("src.app.SkillRunner.run_tool_if_configured") as mock_run:
        mock_executor_class.return_value.ask_ai.return_value = "Mocked AI analysis result."
        mock_run.return_value = {
            "mode": "fallback",
            "tool_output": "",
            "note": "No adapter configured",
        }
        response = client.post(
            "/api/analyze",
            data=json.dumps({"skill_name": "analyze-ims2", "user_input": "ims2"}),
            content_type="application/json"
        )
    assert response.status_code == 200
    data = response.get_json()
    assert "result" in data
    assert "mode" in data
    assert "execution_note" in data


def test_analyze_with_invalid_skill(client):
    """Test POST /api/analyze with a non-existent skill."""
    payload = {
        "skill_name": "nonexistent-skill",
        "user_input": "test input"
    }
    response = client.post(
        "/api/analyze",
        data=json.dumps(payload),
        content_type="application/json"
    )
    # Should either 404 or return error status
    assert response.status_code in [404, 400]


def test_analyze_missing_payload(client):
    """Test POST /api/analyze with missing required fields."""
    payload = {"user_input": "test"}  # Missing skill_name and use_case_id
    response = client.post(
        "/api/analyze",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 400
    err = response.get_json().get("error", "")
    assert "use_case_id" in err and "skill_name" in err


def test_web_home_page_available(client):
    """Test that web home page route is available and returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.content_type


def test_web_home_page_contains_core_sections(client):
    """Test that web home page includes core UI sections for Phase 2."""
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert "SkillFlow Web Assistant" in html
    assert "id=\"skill-list\"" in html
    assert "id=\"analysis-input\"" in html
    assert "id=\"terminal-output\"" in html
    assert "id=\"tab-usecases\"" in html


def test_web_home_page_contains_search_and_file_upload(client):
    """Test that web home page includes phase-2 controls: search and file upload."""
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert "id=\"skill-search\"" in html
    assert "id=\"log-file\"" in html
    assert "id=\"dynamic-inputs\"" in html


def test_analyze_accepts_multipart_with_uploaded_file(client):
    """Test POST /api/analyze accepts multipart form data with a log file."""
    with patch("src.app.CopilotExecutor.ask_ai", return_value="Mocked multipart analysis") as mock_ask_ai, \
         patch("src.app.SkillRunner.run_tool_if_configured", return_value={
             "mode": "fallback",
             "tool_output": "",
             "note": "No adapter configured",
         }):
        response = client.post(
            "/api/analyze",
            data={
                "skill_name": "analyze-ims2",
                "user_input": "check call flow",
                "log_file": (io.BytesIO(b"line1\nline2"), "sample.log"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["result"] == "Mocked multipart analysis"
    sent_prompt = mock_ask_ai.call_args[0][0]
    assert "Attached log content" in sent_prompt


def test_analyze_uses_tool_output_when_tool_first_mode(client):
    """Test analyze endpoint uses tool output when adapter runner returns tool-first mode."""
    with patch("src.app.CopilotExecutor.ask_ai", return_value="Tool-first summary") as mock_ask_ai, \
         patch("src.app.SkillRunner.run_tool_if_configured", return_value={
             "mode": "tool-first",
             "tool_output": "parsed object count: 42",
             "note": "Tool executed",
         }):
        response = client.post(
            "/api/analyze",
            data={
                "skill_name": "analyze-ims2",
                "user_input": "inspect snapshot",
                "log_file": (io.BytesIO(b"raw ims2 binary-like content"), "sample.ims2"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "tool-first"
    assert payload["execution_note"] == "Tool executed"

    sent_prompt = mock_ask_ai.call_args[0][0]
    assert "Tool output (tool-first mode)" in sent_prompt
    assert "parsed object count: 42" in sent_prompt


def test_analyze_rejects_empty_uploaded_file(client):
    """Test POST /api/analyze rejects an empty uploaded file."""
    response = client.post(
        "/api/analyze",
        data={
            "skill_name": "analyze-ims2",
            "user_input": "check call flow",
            "log_file": (io.BytesIO(b""), "empty.log"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_analyze_tool_error_excludes_binary_content_and_warns_llm(client):
    """When tool-first fails (tool_error reason), binary file content must NOT be included
    in the LLM prompt, and the prompt must explicitly warn against fabricating data."""
    with patch("src.app.CopilotExecutor.ask_ai", return_value="Error explanation") as mock_ask_ai, \
         patch("src.app.SkillRunner.run_tool_if_configured", return_value={
             "mode": "fallback",
             "reason": "tool_error",
             "tool_output": "",
             "note": "thread 'main' panicked at 'assertion failed'",
         }):
        response = client.post(
            "/api/analyze",
            data={
                "skill_name": "analyze-ims2",
                "user_input": "analyze this",
                "log_file": (io.BytesIO(b"\x00\x01\x02binary content"), "snapshot.ims2"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    sent_prompt = mock_ask_ai.call_args[0][0]
    # Must include the tool error
    assert "panicked" in sent_prompt
    # Must warn LLM not to fabricate
    assert "Do NOT fabricate" in sent_prompt
    # Must NOT include raw binary file content
    assert "Attached log content" not in sent_prompt
    assert "binary content" not in sent_prompt


def test_analyze_truncates_huge_uploaded_log_in_fallback_prompt(client):
    """Huge uploaded logs should be truncated in fallback prompt path to avoid oversized LLM payloads."""
    huge_text = ("X" * 350000).encode("utf-8")
    with patch("src.app.CopilotExecutor.ask_ai", return_value="Mocked huge-log analysis") as mock_ask_ai, \
         patch("src.app.SkillRunner.run_tool_if_configured", return_value={
             "mode": "fallback",
             "tool_output": "",
             "note": "Tool failed",
         }):
        response = client.post(
            "/api/analyze",
            data={
                "skill_name": "analyze-ims2",
                "user_input": "inspect huge file",
                "log_file": (io.BytesIO(huge_text), "huge.ims2"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    sent_prompt = mock_ask_ai.call_args[0][0]
    assert "truncated" in sent_prompt.lower()
    assert len(sent_prompt) < 200000


def test_analyze_includes_dynamic_input_params_in_prompt(client):
    with patch("src.app.CopilotExecutor.ask_ai", return_value="ok") as mock_ask_ai, \
         patch("src.app.SkillRunner.run_tool_if_configured", return_value={
             "mode": "fallback",
             "reason": "no_adapter",
             "tool_output": "",
             "note": "No adapter configured",
         }):
        response = client.post(
            "/api/analyze",
            data={
                "skill_name": "analyze-ims2",
                "user_input": "check this",
                "input_params": json.dumps(
                    {
                        "analysis_mode": "topology",
                        "focus_object": "RMOD_L-1",
                    }
                ),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    sent_prompt = mock_ask_ai.call_args[0][0]
    assert "Input parameters" in sent_prompt
    assert "analysis_mode: topology" in sent_prompt
    assert "focus_object: RMOD_L-1" in sent_prompt


def test_analyze_passes_input_params_to_skill_runner(client):
    """Tool-first path must receive form/json input_params for adapter arg templates."""
    with patch("src.app.CopilotExecutor.ask_ai", return_value="ok"), patch(
        "src.app.SkillRunner.run_tool_if_configured",
        return_value={
            "mode": "fallback",
            "reason": "no_adapter",
            "tool_output": "",
            "note": "No adapter configured",
        },
    ) as mock_run:
        client.post(
            "/api/analyze",
            json={
                "skill_name": "analyze-ims2",
                "user_input": "inspect",
                "input_params": {"analysis_mode": "state", "focus_object": "RMOD-1"},
            },
            content_type="application/json",
        )
    mock_run.assert_called_once_with(
        skill_name="analyze-ims2",
        file_name="",
        file_bytes=b"",
        input_params={"analysis_mode": "state", "focus_object": "RMOD-1"},
    )


def test_get_use_cases(client_example_uc_yaml):
    """GET /api/use-cases returns catalog from use_cases.example.yaml by default."""
    response = client_example_uc_yaml.get("/api/use-cases")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    entry = next((x for x in data if x.get("id") == "analyze-ims2-snapshot"), None)
    assert entry is not None
    assert entry.get("available") is True
    assert isinstance(entry.get("inputs"), list)
    assert "title" in entry


def test_analyze_with_use_case_id(client_example_uc_yaml):
    with patch("src.app.CopilotExecutor.ask_ai", return_value="ok") as mock_ask, patch(
        "src.app.SkillRunner.run_tool_if_configured",
        return_value={
            "mode": "fallback",
            "reason": "no_adapter",
            "tool_output": "",
            "note": "No adapter configured",
        },
    ) as mock_run:
        response = client_example_uc_yaml.post(
            "/api/analyze",
            json={
                "use_case_id": "analyze-ims2-snapshot",
                "user_input": "check snapshot",
            },
            content_type="application/json",
        )
    assert response.status_code == 200
    mock_run.assert_called_once()
    _args, kwargs = mock_run.call_args
    assert kwargs["skill_name"] == "analyze-ims2"
    mock_ask.assert_called_once()


def test_analyze_use_case_id_and_skill_name_rejected(client_example_uc_yaml):
    response = client_example_uc_yaml.post(
        "/api/analyze",
        json={
            "use_case_id": "analyze-ims2-snapshot",
            "skill_name": "analyze-ims2",
            "user_input": "x",
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "not both" in response.get_json().get("error", "").lower()


def test_analyze_unknown_use_case_id(client_example_uc_yaml):
    response = client_example_uc_yaml.post(
        "/api/analyze",
        json={"use_case_id": "does-not-exist", "user_input": "x"},
        content_type="application/json",
    )
    assert response.status_code == 404


def test_analyze_use_case_prompt_prefix_in_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sf = tmp_path / "skillflow-test.yaml"
    sf.write_text("log_level: INFO\n", encoding="utf-8")
    monkeypatch.setenv("SKILLFLOW_CONFIG", str(sf))
    monkeypatch.delenv("GITLAB_REPO_URL", raising=False)
    uc_file = tmp_path / "uc.yaml"
    uc_file.write_text(
        "use_cases:\n"
        "  - id: prefixed-uc\n"
        "    title: Prefixed\n"
        "    skill_name: analyze-ims2\n"
        "    prompt_prefix: 'LINE_FROM_USE_CASE_CONFIG'\n",
        encoding="utf-8",
    )
    app = create_app(skill_path=str(REPO_ROOT / "dev-skills"), use_cases_path=str(uc_file))
    app.config["TESTING"] = True
    with app.test_client() as client, patch(
        "src.app.CopilotExecutor.ask_ai", return_value="ok"
    ) as mock_ask, patch(
        "src.app.SkillRunner.run_tool_if_configured",
        return_value={
            "mode": "fallback",
            "reason": "no_adapter",
            "tool_output": "",
            "note": "No adapter configured",
        },
    ):
        response = client.post(
            "/api/analyze",
            json={"use_case_id": "prefixed-uc", "user_input": "user line"},
            content_type="application/json",
        )
    assert response.status_code == 200
    sent = mock_ask.call_args[0][0]
    assert "LINE_FROM_USE_CASE_CONFIG" in sent
    assert "user line" in sent


def test_analyze_stream_emits_single_sse_data_event(client):
    """Contract: one SSE data line with full LLM text (not token streaming)."""
    with patch("src.app.CopilotExecutor.ask_ai", return_value="complete answer"), patch(
        "src.app.SkillRunner.run_tool_if_configured",
        return_value={
            "mode": "fallback",
            "reason": "no_adapter",
            "tool_output": "",
            "note": "No adapter configured",
        },
    ):
        response = client.post(
            "/api/analyze/stream",
            json={"skill_name": "analyze-ims2", "user_input": "q"},
            content_type="application/json",
        )
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    data_lines = [ln for ln in text.split("\n") if ln.startswith("data: ")]
    assert len(data_lines) == 1
    payload = json.loads(data_lines[0][6:])
    assert payload["chunk"] == "complete answer"


def test_analyze_stream_accepts_use_case_id(client_example_uc_yaml):
    with patch("src.app.CopilotExecutor.ask_ai", return_value="streamed via uc"), patch(
        "src.app.SkillRunner.run_tool_if_configured",
        return_value={
            "mode": "fallback",
            "reason": "no_adapter",
            "tool_output": "",
            "note": "No adapter configured",
        },
    ):
        response = client_example_uc_yaml.post(
            "/api/analyze/stream",
            json={"use_case_id": "analyze-ims2-snapshot", "user_input": "q"},
            content_type="application/json",
        )
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    data_lines = [ln for ln in text.split("\n") if ln.startswith("data: ")]
    assert len(data_lines) == 1
    payload = json.loads(data_lines[0][6:])
    assert payload["chunk"] == "streamed via uc"
