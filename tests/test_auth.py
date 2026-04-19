import os

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret-for-unit-tests")

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


def _client_with_admin(password: str = "hunter2") -> TestClient:
    settings = get_settings()
    settings.admin_username = "admin"
    settings.admin_password_hash = hash_password(password)
    return TestClient(app)


def test_health_is_public():
    client = _client_with_admin()
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_and_access_protected_route():
    client = _client_with_admin("hunter2")
    r = client.post("/api/auth/login", data={"username": "admin", "password": "hunter2"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"username": "admin"}


def test_login_rejects_bad_password():
    client = _client_with_admin("hunter2")
    r = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_protected_route_rejects_missing_token():
    client = _client_with_admin()
    r = client.get("/api/wifi/scan")
    assert r.status_code == 401
