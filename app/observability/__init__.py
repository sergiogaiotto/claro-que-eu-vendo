"""Integração com LangFuse para observabilidade do agente."""

from app.config import get_settings

_LangfuseHandler = None

try:
    from langfuse.callback import CallbackHandler
    _LangfuseHandler = CallbackHandler
except ImportError:
    try:
        from langfuse import CallbackHandler
        _LangfuseHandler = CallbackHandler
    except ImportError:
        pass


def create_langfuse_handler(
    session_id: str | None = None,
    user_id: str | None = None,
    trace_name: str = "claro-que-eu-vendo",
):
    """Cria um callback handler do LangFuse se disponível e configurado."""
    cfg = get_settings()

    if _LangfuseHandler is None:
        return None

    if not cfg.langfuse_public_key or not cfg.langfuse_secret_key:
        return None

    return _LangfuseHandler(
        public_key=cfg.langfuse_public_key,
        secret_key=cfg.langfuse_secret_key,
        host=cfg.langfuse_host,
        session_id=session_id,
        user_id=user_id,
        trace_name=trace_name,
    )