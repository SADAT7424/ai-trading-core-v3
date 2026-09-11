"""
Application configuration.

All configuration is read from environment variables (via .env in local
development). Never hard-code secrets, connection strings, or credentials
here — see AGENTS.md, section 7.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GO OS API"
    environment: str = "development"  # development | testing | paper | shadow | production
    debug: bool = True

    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://go_os:go_os@localhost:5432/go_os"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = ["http://localhost:3000"]

    log_level: str = "INFO"
    log_json: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
