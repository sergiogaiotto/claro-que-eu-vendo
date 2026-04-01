"""Configuração centralizada da aplicação."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import field_validator

class Settings(BaseSettings):
    # ... campos existentes ...

    @field_validator('openai_api_key')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        if not v or v.startswith('sk-your'):
            raise ValueError(
                "OPENAI_API_KEY não configurada. "
                "Edite o arquivo .env com sua chave real de platform.openai.com"
            )
        return v

    @field_validator('tavily_api_key')
    @classmethod
    def validate_tavily_key(cls, v: str) -> str:
        if not v or v.startswith('tvly-your'):
            raise ValueError(
                "TAVILY_API_KEY não configurada. "
                "Edite o arquivo .env com sua chave real de tavily.com"
            )
        return v

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Web Search
    tavily_api_key: str = ""

    # Observabilidade
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # LangSmith (opcional)
    langsmith_api_key: str = ""

    # Auth / JWT
    jwt_secret: str = "change-me-in-production-claro-que-eu-vendo-2025"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
