from pathlib import Path
from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

import os 

class Settings(BaseSettings):
    _repo_root = Path(__file__).resolve().parents[3]

    # API / Frontend
    api_title: str = "LeadDB Assistant API"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    # Postgres
    pg_host: str | None = Field(None, validation_alias=AliasChoices("PG_HOST", "DB_HOST"))
    pg_port: int | None = Field(None, validation_alias=AliasChoices("PG_PORT", "DB_PORT"))
    pg_user: str | None = Field(None, validation_alias=AliasChoices("PG_USER", "DB_USER"))
    pg_password: str | None = Field(None, validation_alias=AliasChoices("PG_PASSWORD", "DB_PASSWORD"))
    pg_database: str | None = Field(None, validation_alias=AliasChoices("PG_DATABASE", "DB_NAME"))

    # Model config
    model_provider: Literal["groq", "gemini", "bedrock"] = "bedrock"
    model_temperature: float = 0.0
    groq_model: str = "llama-3.3-70b-versatile"
    groq_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    google_api_key: str | None = None
    bedrock_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"
    aws_region: str | None = Field("us-east-1", validation_alias=AliasChoices("AWS_DEFAULT_REGION", "AWS_REGION"))
    aws_access_key_id: str | None = Field(None, validation_alias=AliasChoices("AWS_ACCESS_KEY_ID"))
    aws_secret_access_key: str | None = Field(None, validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY"))
    aws_session_token: str | None = Field(None, validation_alias=AliasChoices("AWS_SESSION_TOKEN"))

    # Freshdesk
    freshdesk_domain: str | None = Field(None, validation_alias=AliasChoices("FRESHDESK_DOMAIN"))
    freshdesk_api_key: str | None = Field(None, validation_alias=AliasChoices("FRESHDESK_API_KEY"))
    ticket_schema: str = "leadinsights"
    ticket_support_email: str = Field(
        "informacomleadinsights@leadinsights.freshdesk.com",
        validation_alias=AliasChoices("TICKET_SUPPORT_EMAIL"),
    )

    # Misc
    schema_cache_ttl_seconds: int = 300
    query_row_limit: int = 200

    model_config = SettingsConfigDict(
        env_file=(_repo_root / ".env", _repo_root / ".env.local"),
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def postgres_dsn(self) -> str | None:
        if not all([self.pg_user, self.pg_password, self.pg_host, self.pg_port, self.pg_database]):
            return None
        password = quote_plus(self.pg_password)
        return f"postgresql://{self.pg_user}:{password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def backend_root(self) -> Path:
        return self.repo_root / "backend"

    @property
    def mcp_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.backend_root)
        if self.pg_host: env["PG_HOST"] = self.pg_host
        if self.pg_port: env["PG_PORT"] = str(self.pg_port)
        if self.pg_user: env["PG_USER"] = self.pg_user
        if self.pg_password: env["PG_PASSWORD"] = self.pg_password
        if self.pg_database: env["PG_DATABASE"] = self.pg_database
        return env

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
