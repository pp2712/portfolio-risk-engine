"""Application configuration, loaded from environment variables / .env.

Never hardcode credentials -- see CLAUDE.md "Security rules".
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    test_database_url: str = ""
    api_key: str
    mc_default_seed: int = 42
    data_source: str = "yfinance"
    log_level: str = "INFO"
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
