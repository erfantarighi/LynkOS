import os

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret-for-ai")

from fastapi.testclient import TestClient

from app.ai.history import AIHistoryStore
from app.ai.service import service
from app.auth import hash_password
from app.config import get_settings
from app.main import app


def _client(tmp_path) -> TestClient:
    settings = get_settings()
    settings.admin_username = "admin"
    settings.admin_password_hash = hash_password("hunter2")
    settings.ai_enabled = True
    settings.ai_provider = "mock"
    settings.ai_allow_action_execution = False
    settings.snapshot_path = str(tmp_path / "snapshot.json")
    service._history = AIHistoryStore(tmp_path)
    service._cached_state = None
    service._provider = None
    return TestClient(app)


def _token(client: TestClient) -> str:
    res = client.post("/api/auth/login", data={"username": "admin", "password": "hunter2"})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_ai_routes_expose_mvp_surface(tmp_path) -> None:
    client = _client(tmp_path)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    status = client.get("/api/ai/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["enabled"] is True
    assert status.json()["provider"] == "mock"

    insights = client.post("/api/ai/insights", headers=headers)
    assert insights.status_code == 200
    assert "summary" in insights.json()
    assert "generated_at" in insights.json()

    recommendations = client.get("/api/ai/recommendations", headers=headers)
    assert recommendations.status_code == 200
    assert "items" in recommendations.json()

    anomalies = client.get("/api/ai/anomalies", headers=headers)
    assert anomalies.status_code == 200
    assert "items" in anomalies.json()

    parsed = client.post(
        "/api/ai/intent/parse",
        headers=headers,
        json={"text": "Disable SSH"},
    )
    assert parsed.status_code == 200
    assert parsed.json()["intent"] == "disable_ssh"
    assert parsed.json()["actions"][0]["type"] == "disable_ssh"

    review = client.post(
        "/api/ai/intent/review",
        headers=headers,
        json={"text": "Disable SSH", "plan": parsed.json(), "approved": True},
    )
    assert review.status_code == 200
    assert review.json()["ok"] is True


def test_ai_parse_surfaces_provider_errors(tmp_path) -> None:
    client = _client(tmp_path)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    settings = get_settings()
    settings.ai_provider = "openai"
    settings.ai_api_key = ""
    service._provider = None

    parsed = client.post(
        "/api/ai/intent/parse",
        headers=headers,
        json={"text": "Disable SSH"},
    )
    assert parsed.status_code == 502
    assert "AI provider error" in parsed.text
