"""
Application configuration — all secrets and tunables are read from
environment variables with sensible defaults for local development.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ────────────────────────────────────────────────────────────
    # Swap to PostgreSQL with a single env-var:
    #   DATABASE_URL=postgresql+asyncpg://user:pass@host/db
    DATABASE_URL: str = "sqlite+aiosqlite:///./mhm.db"

    # ── JWT ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── App ─────────────────────────────────────────────────────────────────
    APP_TITLE: str = "MHM – Mental Health Monitoring API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False


settings = Settings()
