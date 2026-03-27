import pytest
import json
from unittest.mock import patch
from src.app import create_app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


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


def test_analyze_with_valid_skill(client):
    """Test POST /api/analyze with a valid skill and user input."""
    with patch("src.app.CopilotExecutor") as mock_executor_class:
        mock_executor_class.return_value.ask_ai.return_value = "Mocked AI analysis result."
        response = client.post(
            "/api/analyze",
            data=json.dumps({"skill_name": "analyze-ims2", "user_input": "ims2"}),
            content_type="application/json"
        )
    assert response.status_code == 200
    data = response.get_json()
    assert "result" in data


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
    payload = {"user_input": "test"}  # Missing skill_name
    response = client.post(
        "/api/analyze",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 400
