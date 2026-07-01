"""Claro que Eu vendo! — Entry point da aplicação FastAPI."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router as chat_router
from app.api.auth import router as auth_router, bootstrap_root_from_env
from app.api.pitch import router as pitch_router
from app.api.catalog import router as catalog_router
from app.api.skills import router as skills_router
from app.config import get_settings
from app.database import init_db
from app.middleware import SecurityHeadersMiddleware

logger = logging.getLogger("cqv")


def _check_required_keys(cfg) -> None:
    """Avisa (sem derrubar a app) se chaves de LLM não estiverem configuradas.

    O endpoint /chat degrada com mensagem clara quando a chave falta; demais
    módulos (auth, catálogo, skills, pitch) funcionam normalmente.
    """
    warnings = []
    if not cfg.openai_api_key or cfg.openai_api_key.startswith("sk-your"):
        warnings.append("OPENAI_API_KEY ausente/placeholder — o chat ficará indisponível até configurar.")
    if not cfg.tavily_api_key or cfg.tavily_api_key.startswith("tvly-your"):
        warnings.append("TAVILY_API_KEY ausente/placeholder — a busca web ficará indisponível.")
    for w in warnings:
        logger.warning(w)


def create_app() -> FastAPI:
    cfg = get_settings()
    _check_required_keys(cfg)

    app = FastAPI(
        title="Claro que Eu vendo!",
        description="Assistente de vendas com IA para PMEs",
        version="2.0.0",
    )

    # CORS restrito por variável de ambiente (VULN-05 — sem wildcard+credentials).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Cabeçalhos de segurança (AUS-05). HSTS apenas quando servido via HTTPS.
    app.add_middleware(SecurityHeadersMiddleware, hsts=cfg.cookie_secure)

    init_db()
    bootstrap_root_from_env()

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(pitch_router, prefix="/api/v1")
    app.include_router(catalog_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api/v1")

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/")
    async def root():
        return FileResponse("app/static/index.html")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    cfg = get_settings()
    uvicorn.run("main:app", host=cfg.app_host, port=cfg.app_port, reload=True)
