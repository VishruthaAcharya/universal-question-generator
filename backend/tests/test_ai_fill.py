from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ai_fill_fields_empty():
    response = client.post("/api/ai-fill-fields", json={"questions": [], "fields": []})
    assert response.status_code == 200
    assert response.json() == {"suggestions": []}

def test_ai_fill_fields_mocked_success():
    mock_suggestions = [
        {
            "question_id": "q1",
            "fields": {
                "Topic": {
                    "value": "Quadratic Equations",
                    "status": "AI_INFERRED",
                    "confidence": 0.96,
                    "reason": "Derived from question stem"
                },
                "Difficulty": {
                    "value": "Medium",
                    "status": "AI_INFERRED",
                    "confidence": 0.91
                }
            }
        }
    ]
    with patch("app.services.azure_openai.fill_missing_fields_for_questions", return_value=mock_suggestions):
        response = client.post(
            "/api/ai-fill-fields",
            json={
                "questions": [{"id": "q1", "question": "Solve x^2 - 4 = 0"}],
                "fields": ["Topic", "Difficulty"],
                "context": {"subject": "Mathematics"}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["fields"]["Topic"]["value"] == "Quadratic Equations"
