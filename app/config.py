"""Configuração centralizada da aplicação."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Limites do agente / consumo (LLM10 Unbounded Consumption · VULN-10/15 · AUS-03)
    llm_max_tokens: int = 4096
    llm_request_timeout: float = 60.0          # timeout por chamada LLM
    agent_timeout_seconds: float = 90.0        # wall-clock do agente inteiro
    agent_recursion_limit: int = 12            # nº máx. de ciclos ReAct
    history_max_messages: int = 20             # histórico truncado
    tavily_max_results: int = 3
    tavily_fetch_timeout: float = 6.0          # timeout por página buscada
    web_content_max_chars: int = 6000          # corte de conteúdo por página

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

    # Cookie de sessão (VULN-08 — JWT em HttpOnly cookie, não localStorage)
    cookie_name: str = "cqv_session"
    cookie_secure: bool = False        # True em produção (HTTPS)
    cookie_samesite: str = "strict"    # strict mitiga CSRF

    # Bootstrap de root (VULN-03 — sem auto-criação no login)
    root_username: str = ""
    root_password: str = ""
    setup_token: str = ""              # exigido para setup via web; vazio = setup web desativado

    # CORS (VULN-05 — sem wildcard + credentials)
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Rate limiting (AUS-01)
    rate_limit_chat: int = 20          # requisições por janela
    rate_limit_login: int = 10
    rate_limit_window_seconds: int = 60

    # Segurança de saída (AUS-02 — PII masking)
    pii_masking: bool = True

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"

    # Valor de fábrica do segredo JWT — se permanecer, tokens são forjáveis.
    _DEFAULT_JWT_SECRET = "change-me-in-production-claro-que-eu-vendo-2025"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def jwt_secret_is_weak(self) -> bool:
        return (not self.jwt_secret) or self.jwt_secret == self._DEFAULT_JWT_SECRET or len(self.jwt_secret) < 16

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()
