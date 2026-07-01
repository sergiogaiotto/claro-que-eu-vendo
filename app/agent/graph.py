"""Grafo do agente de vendas com LangGraph.

Implementa o padrão ReAct (Reasoning + Acting) usando LangGraph,
inspirado na arquitetura do deep_research framework.
"""

import asyncio
from datetime import datetime
from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.prompts import SALES_ORCHESTRATOR_PROMPT
from app.agent.tools import TOOLS
from app.config import get_settings
from app.skill_loader import build_skills_context


@lru_cache(maxsize=1)
def _base_llm() -> ChatOpenAI:
    """LLM base reutilizado entre requisições (cliente HTTP compartilhado).

    max_tokens + timeout limitam custo e latência por chamada
    (VULN-10 Unbounded Consumption). streaming=False para que o timeout
    delimite a chamada inteira de forma previsível.
    """
    cfg = get_settings()
    return ChatOpenAI(
        model=cfg.openai_model,
        api_key=cfg.openai_api_key,
        temperature=0.3,
        streaming=False,
        max_tokens=cfg.llm_max_tokens,
        timeout=cfg.llm_request_timeout,
        max_retries=1,
    )


def _should_continue(state: MessagesState) -> str:
    """Decide se o agente deve chamar ferramentas ou encerrar."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


async def _agent_node(state: MessagesState) -> dict[str, Any]:
    """Nó principal do agente — raciocina e decide ações (assíncrono e cancelável)."""
    llm = _base_llm().bind_tools(TOOLS)

    messages = list(state["messages"])
    # O system prompt (com skills) é montado uma única vez por requisição:
    # nas iterações seguintes a SystemMessage já está no estado.
    if not any(isinstance(m, SystemMessage) for m in messages):
        system_prompt = SALES_ORCHESTRATOR_PROMPT.format(
            date=datetime.now().strftime("%Y-%m-%d"),
            skills_context=build_skills_context(),
        )
        messages = [SystemMessage(content=system_prompt)] + messages

    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def create_sales_agent() -> StateGraph:
    """Cria o grafo do agente de vendas."""
    graph = StateGraph(MessagesState)

    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


@lru_cache(maxsize=1)
def _compiled_agent():
    """Grafo compilado reutilizado entre requisições (evita recompilar sempre)."""
    return create_sales_agent()


async def run_agent(
    message: str,
    history: list[dict[str, str]] | None = None,
    callbacks: list | None = None,
) -> str:
    """Executa o agente e retorna a resposta final.

    Aplica timeout wall-clock (AUS-03/VULN-15) e trunca o histórico
    (VULN-10) para conter latência e custo — origem do timeout recorrente
    na primeira consulta pesada de briefing.

    Args:
        message: Mensagem do usuário.
        history: Histórico de mensagens anteriores.
        callbacks: Callbacks do LangFuse ou outros.

    Returns:
        Texto da resposta do agente.
    """
    cfg = get_settings()
    agent = _compiled_agent()

    messages: list = []
    if history:
        # Trunca o histórico às últimas N mensagens para limitar o contexto.
        for msg in history[-cfg.history_max_messages:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=message))

    config: dict[str, Any] = {"recursion_limit": cfg.agent_recursion_limit}
    if callbacks:
        config["callbacks"] = callbacks

    try:
        result = await asyncio.wait_for(
            agent.ainvoke({"messages": messages}, config=config),
            timeout=cfg.agent_timeout_seconds,
        )
    except asyncio.TimeoutError:
        return (
            "A pesquisa está demorando mais do que o esperado e foi interrompida "
            "para não travar o atendimento. Tente uma pergunta mais específica "
            "(por exemplo, foque em um único aspecto da empresa ou interlocutor)."
        )

    final_messages = result["messages"]
    for msg in reversed(final_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content

    return "Não consegui processar sua solicitação. Tente reformular."
