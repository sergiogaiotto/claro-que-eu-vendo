"""Claro que Eu vendo! — Entry point da aplicação FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router as chat_router
from app.api.auth import router as auth_router
from app.api.pitch import router as pitch_router
from app.api.catalog import router as catalog_router
from app.api.skills import router as skills_router
from app.config import get_settings
from app.database import init_db


def _check_required_keys(cfg) -> None:
    """Falha com mensagem clara se chaves obrigatórias não estiverem configuradas."""
    errors = []
    if not cfg.openai_api_key or cfg.openai_api_key.startswith("sk-your"):
        errors.append("OPENAI_API_KEY ausente ou com valor placeholder — configure em platform.openai.com")
    if not cfg.tavily_api_key or cfg.tavily_api_key.startswith("tvly-your"):
        errors.append("TAVILY_API_KEY ausente ou com valor placeholder — configure em tavily.com")
    if errors:
        raise RuntimeError(
            "Configuração incompleta:\n" + "\n".join(f"  • {e}" for e in errors)
        )


def create_app() -> FastAPI:
    cfg = get_settings()
    _check_required_keys(cfg)

    app = FastAPI(
        title="Claro que Eu vendo!",
        description="Assistente de vendas com IA para PMEs",
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()

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
