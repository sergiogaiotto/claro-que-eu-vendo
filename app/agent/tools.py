"""Ferramentas do agente de vendas.

Adaptado do framework deep_research para o contexto de vendas B2B.
"""

import httpx
from langchain_core.tools import tool
from markdownify import markdownify
from tavily import TavilyClient

from app.config import get_settings

_tavily_client: TavilyClient | None = None


def _get_tavily() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        cfg = get_settings()
        _tavily_client = TavilyClient(api_key=cfg.tavily_api_key)
    return _tavily_client


def _fetch_page(url: str, timeout: float = 10.0) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0 Safari/537.36"
        )
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return markdownify(resp.text)[:8000]
    except Exception as exc:
        return f"Erro ao acessar {url}: {exc}"


@tool
def tavily_search(query: str) -> str:
    """Busca informações na web sobre empresas, pessoas ou mercados.

    Use para coletar dados sobre empresas-alvo, interlocutores,
    tendências de mercado e notícias relevantes para vendas.

    Args:
        query: Consulta de busca — seja específico para melhores resultados.
    """
    client = _get_tavily()
    results = client.search(query, max_results=3, topic="general")

    parts: list[str] = []
    for item in results.get("results", []):
        url = item["url"]
        title = item["title"]
        content = _fetch_page(url)
        parts.append(f"## {title}\n**URL:** {url}\n\n{content}\n\n---")

    return f"Encontrados {len(parts)} resultado(s) para '{query}':\n\n" + "\n".join(parts)


@tool
def think_tool(reflection: str) -> str:
    """Ferramenta de reflexão estratégica durante a pesquisa.

    Use após cada busca para analisar resultados e planejar próximos passos.
    Avalie: O que encontrei? O que falta? Devo continuar buscando?

    Args:
        reflection: Sua análise do progresso da pesquisa.
    """
    return f"Reflexão registrada: {reflection}"


TOOLS = [tavily_search, think_tool]

# Catalog SQL tools — importados separadamente para evitar circular import
try:
    from app.catalog_engine import CATALOG_TOOLS
    TOOLS = TOOLS + CATALOG_TOOLS
except ImportError:
    pass
