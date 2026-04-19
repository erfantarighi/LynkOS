import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_JWT_SECRETS = {
    "change-me-in-production-please-set-LYNKOS_JWT_SECRET",
    "dev-secret",
    "dev",
    "",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LYNKOS_", env_file=".env", extra="ignore")

    admin_username: str = "admin"
    # bcrypt hash of the admin password. Default is the hash of "admin" — change before deploying.
    admin_password_hash: str = (
        "$2b$12$LnnT0KhmCCNkPB7fA9wo5ehiTLhokl0V7u0vHqqRuRBnXZ7FqJGd2"
    )
    jwt_secret: str = "change-me-in-production-please-set-LYNKOS_JWT_SECRET"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    cors_origins: list[str] = ["http://localhost:5173"]

    # Interface naming conventions
    wan_interface: str = "eth0"
    lan_interface: str = "wlan0"

    # Fake-it mode returns canned data instead of shelling out to nmcli — for dev on non-Pi hosts.
    mock_mode: bool = False

    # Where the snapshot (routes/hotspot/pppoe config) is stored. Default is
    # <install_dir>/data/snapshot.json. Override with LYNKOS_SNAPSHOT_PATH.
    snapshot_path: str = ""

    # AI feature flags / provider selection.
    ai_enabled: bool = False
    ai_provider: str = "mock"
    ai_model: str = "gpt-4.1-mini"
    ai_api_key: str = ""
    ai_max_input_bytes: int = 32_768
    ai_allow_action_execution: bool = False
    ai_state_cache_seconds: int = 5


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.mock_mode and s.jwt_secret in INSECURE_JWT_SECRETS:
        # Fail fast — a default JWT secret in production lets anyone forge tokens.
        raise RuntimeError(
            "LYNKOS_JWT_SECRET is missing or set to an insecure default. "
            "Generate a real one with `openssl rand -hex 32` and put it in /etc/default/lynkos."
        )
    if not s.mock_mode and s.cors_origins == ["*"]:
        # A wildcard CORS + credentials won't actually work in browsers, and it's
        # a sloppy default for a privileged admin UI. Warn, don't fail.
        logging.getLogger("lynkos").warning(
            "LYNKOS_CORS_ORIGINS is '*' — set it to your actual origin(s) in production."
        )
    return s
