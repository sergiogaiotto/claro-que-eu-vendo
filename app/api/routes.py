"""Rotas da API do agente de vendas."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agent import run_agent
from app.api.auth import get_current_user
from app.api.schemas import ChatRequest, ChatResponse, HealthResponse
from app.audit import audit_log
from app.config import get_settings
from app.database import Pitch, PitchInteraction, User, get_db
from app.observability import create_langfuse_handler
from app.ratelimit import rate_limiter
from app.security import PromptInjectionError, check_user_input, mask_pii, wrap_untrusted

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rl=Depends(rate_limiter("chat", get_settings().rate_limit_chat, get_settings().rate_limit_window_seconds)),
):
    cfg = get_settings()
    ip = http_request.client.host if http_request.client else None

    # Guardrail de entrada — bloqueia prompt injection (VULN-04 / LLM01).
    # Inclui o histórico enviado pelo cliente (role user), que também vai ao LLM.
    history_user_msgs = [m.content for m in request.history if m.role == "user"]
    try:
        check_user_input(request.message, request.company_name, request.company_city, *history_user_msgs)
    except PromptInjectionError as exc:
        audit_log("chat_blocked", user_id=user.id, message=request.message, ip=ip)
        raise HTTPException(status_code=400, detail=str(exc))

    audit_log("chat", user_id=user.id, message=request.message, ip=ip)

    session_id = request.session_id or str(uuid.uuid4())
    callbacks = []
    handler = create_langfuse_handler(
        session_id=session_id,
        user_id=str(user.id),
        trace_name="chat",
    )
    if handler:
        callbacks.append(handler)

    try:
        history = [{"role": m.role, "content": m.content} for m in request.history]
        message = request.message
        if request.company_name or request.company_city:
            ctx_parts = []
            if request.company_name:
                ctx_parts.append(f"Empresa: {request.company_name}")
            if request.company_city:
                ctx_parts.append(f"Cidade: {request.company_city}")
            # Contexto vem do usuário — trata como dado não confiável (Vetor 1).
            context_block = wrap_untrusted("contexto_usuario", ", ".join(ctx_parts))
            message = f"{context_block}\n\n{message}"

        response = await run_agent(
            message=message,
            history=history,
            callbacks=callbacks,
        )
    except Exception as exc:
        # Traduz erros comuns para mensagens legíveis
        err_str = str(exc)
        if "api_key" in err_str.lower() or "authentication" in err_str.lower():
            detail = "Chave de API inválida ou ausente. Verifique OPENAI_API_KEY no arquivo .env"
        elif "rate limit" in err_str.lower():
            detail = "Limite de requisições da API atingido. Aguarde alguns segundos."
        elif "connection" in err_str.lower() or "timeout" in err_str.lower():
            detail = "Timeout na conexão com a API OpenAI. Verifique sua conexão."
        else:
            detail = err_str
        raise HTTPException(status_code=500, detail=detail)
    finally:
        if handler:
            handler.flush()

    # Mascaramento de PII na saída (AUS-02 / LLM02).
    if cfg.pii_masking:
        response = mask_pii(response)

    # Persiste a interação apenas se o pitch pertencer ao usuário autenticado.
    if request.pitch_id:
        pitch = db.query(Pitch).filter(
            Pitch.id == request.pitch_id, Pitch.user_id == user.id
        ).first()
        if pitch:
            db.add(PitchInteraction(
                pitch_id=pitch.id, role="user", content=request.message,
            ))
            db.add(PitchInteraction(
                pitch_id=pitch.id, role="assistant", content=response,
            ))
            db.commit()

    return ChatResponse(response=response, session_id=session_id)
