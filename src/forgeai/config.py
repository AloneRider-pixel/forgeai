from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str | None = None
    risk_gate_threshold: int = 60
    http_timeout_seconds: float = 15.0
    context_max_files: int = 5
    context_max_chars: int = 12000
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 30.0
    database_url: str = "sqlite+aiosqlite:///./forgeai.db"
    redis_url: str | None = None
    allowed_github_workflows: list[str] = Field(default_factory=lambda: ["ci.yml"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
