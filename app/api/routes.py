"""Rotas da API do agente de vendas."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent import run_agent
from app.api.schemas import ChatRequest, ChatResponse, HealthResponse
from app.database import Pitch, PitchInteraction, get_db
from app.observability import create_langfuse_handler

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Endpoint principal de chat com o agente de vendas."""
    session_id = request.session_id or str(uuid.uuid4())

    callbacks = []
    handler = create_langfuse_handler(
        session_id=session_id,
        user_id=request.user_id,
        trace_name="chat",
    )
    if handler:
        callbacks.append(handler)

    try:
        history = [{"role": m.role, "content": m.content} for m in request.history]

        # Injeta contexto da empresa na mensagem se disponível
        message = request.message
        if request.company_name or request.company_city:
            ctx_parts = []
            if request.company_name:
                ctx_parts.append(f"Empresa: {request.company_name}")
            if request.company_city:
                ctx_parts.append(f"Cidade: {request.company_city}")
            message = f"[Contexto: {', '.join(ctx_parts)}]\n\n{message}"

        response = await run_agent(
            message=message,
            history=history,
            callbacks=callbacks,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if handler:
            handler.flush()

    # Salva interações no pitch se pitch_id foi informado
    if request.pitch_id and request.user_id:
        pitch = db.query(Pitch).filter(Pitch.id == request.pitch_id).first()
        if pitch:
            db.add(PitchInteraction(
                pitch_id=pitch.id, role="user", content=request.message,
            ))
            db.add(PitchInteraction(
                pitch_id=pitch.id, role="assistant", content=response,
            ))
            db.commit()

    return ChatResponse(response=response, session_id=session_id)
