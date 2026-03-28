"""Schemas da API — contratos de entrada e saída."""

from pydantic import BaseModel, Field


class MessageInput(BaseModel):
    role: str = Field(default="user", description="Papel: user ou assistant")
    content: str = Field(..., description="Conteúdo da mensagem")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Mensagem do vendedor", min_length=1)
    history: list[MessageInput] = Field(default_factory=list, description="Histórico")
    session_id: str | None = Field(default=None, description="ID da sessão")
    user_id: str | None = Field(default=None, description="ID do vendedor")
    pitch_id: int | None = Field(default=None, description="ID do pitch ativo")
    company_name: str = Field(default="", description="CNPJ ou nome da empresa")
    company_city: str = Field(default="", description="Cidade da empresa")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Resposta do agente")
    session_id: str | None = Field(default=None)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    agent: str = "Claro que Eu vendo!"
