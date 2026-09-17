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
    github_webhook_secret: str | None = None
    risk_gate_threshold: int = 60
    http_timeout_seconds: float = 15.0
    context_max_files: int = 5
    context_max_chars: int = 12000
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 30.0
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    retrieval_max_files: int = Field(default=200, ge=10, le=1000)
    retrieval_top_k: int = Field(default=8, ge=1, le=50)
    database_url: str = "sqlite+aiosqlite:///./forgeai.db"
    auto_create_schema: bool = True
    redis_url: str | None = None
    allowed_github_workflows: list[str] = Field(default_factory=lambda: ["ci.yml"])
    webhook_dispatch_interval_seconds: float = 2.0
    webhook_dispatch_max_attempts: int = Field(default=5, ge=1, le=20)
    auth_required: bool = False
    api_key_roles: dict[str, list[str]] = Field(default_factory=dict)
    otel_exporter_otlp_endpoint: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
