import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret-for-unit-tests")

from app.credentials import current_admin_hash, set_admin_hash  # noqa: E402


def test_file_overrides_env(tmp_path: Path) -> None:
    hash_path = tmp_path / "admin_hash"
    with patch("app.credentials._hash_path", return_value=hash_path):
        # No file → falls back to settings.admin_password_hash (from env/config defaults)
        env_hash = current_admin_hash()
        assert env_hash  # non-empty

        # Write a file → that overrides
        set_admin_hash("$2b$12$customHashFromFile")
        assert current_admin_hash() == "$2b$12$customHashFromFile"


def test_file_mode_is_0600(tmp_path: Path) -> None:
    hash_path = tmp_path / "admin_hash"
    with patch("app.credentials._hash_path", return_value=hash_path):
        set_admin_hash("$2b$12$someHash")
        assert oct(hash_path.stat().st_mode)[-3:] == "600"


def test_empty_file_falls_back(tmp_path: Path) -> None:
    hash_path = tmp_path / "admin_hash"
    hash_path.write_text("")
    hash_path.chmod(0o600)
    with patch("app.credentials._hash_path", return_value=hash_path):
        result = current_admin_hash()
        # Empty file → fall back to env default (non-empty)
        assert result and result != ""
