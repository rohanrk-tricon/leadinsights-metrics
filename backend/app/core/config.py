import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _repo_root = Path(__file__).resolve().parents[3]

    api_title: str = "LeadDB Assistant API"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "postgres"
    pg_password: str = "Test@123"
    pg_database: str = "leaddb"

    model_provider: Literal["groq", "gemini", "bedrock"] = "groq"
    model_temperature: float = 0.0
    groq_model: str = "llama-3.3-70b-versatile"
    groq_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    google_api_key: str | None = None
    bedrock_model_id: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None

    freshdesk_domain: str | None = None
    freshdesk_api_key: str | None = None
    ticket_schema: str = "leadinsights"
    ticket_support_email: str = "informacomleadinsights@leadinsights.freshdesk.com"

    schema_cache_ttl_seconds: int = 300
    query_row_limit: int = 200

    model_config = SettingsConfigDict(
        env_file=(_repo_root / ".env", _repo_root / ".env.local"),
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def postgres_dsn(self) -> str:
        password = quote_plus(self.pg_password)
        return (
            f"postgresql://{self.pg_user}:{password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        )

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def backend_root(self) -> Path:
        return self.repo_root / "backend"

    @property
    def mcp_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.backend_root)
        env["PG_HOST"] = self.pg_host
        env["PG_PORT"] = str(self.pg_port)
        env["PG_USER"] = self.pg_user
        env["PG_PASSWORD"] = self.pg_password
        env["PG_DATABASE"] = self.pg_database
        return env


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
