"""Grafo do agente de vendas com LangGraph.

Implementa o padrão ReAct (Reasoning + Acting) usando LangGraph,
inspirado na arquitetura do deep_research framework.
"""

from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.prompts import SALES_ORCHESTRATOR_PROMPT
from app.agent.tools import TOOLS
from app.config import get_settings
from app.skill_loader import build_skills_context


def _build_llm() -> ChatOpenAI:
    cfg = get_settings()
    return ChatOpenAI(
        model=cfg.openai_model,
        api_key=cfg.openai_api_key,
        temperature=0.3,
        streaming=True,
    )


def _should_continue(state: MessagesState) -> str:
    """Decide se o agente deve chamar ferramentas ou encerrar."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _agent_node(state: MessagesState) -> dict[str, Any]:
    """Nó principal do agente — raciocina e decide ações."""
    llm = _build_llm().bind_tools(TOOLS)

    system_prompt = SALES_ORCHESTRATOR_PROMPT.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        skills_context=build_skills_context(),
    )

    messages = state["messages"]
    has_system = any(isinstance(m, SystemMessage) for m in messages)

    if not has_system:
        messages = [SystemMessage(content=system_prompt)] + list(messages)

    response = llm.invoke(messages)
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


async def run_agent(
    message: str,
    history: list[dict[str, str]] | None = None,
    callbacks: list | None = None,
) -> str:
    """Executa o agente e retorna a resposta final.

    Args:
        message: Mensagem do usuário.
        history: Histórico de mensagens anteriores.
        callbacks: Callbacks do LangFuse ou outros.

    Returns:
        Texto da resposta do agente.
    """
    agent = create_sales_agent()

    messages: list = []
    if history:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=message))

    config: dict[str, Any] = {"recursion_limit": 30}
    if callbacks:
        config["callbacks"] = callbacks

    result = await agent.ainvoke({"messages": messages}, config=config)

    final_messages = result["messages"]
    for msg in reversed(final_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content

    return "Não consegui processar sua solicitação. Tente reformular."
