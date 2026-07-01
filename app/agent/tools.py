"""Ferramentas do agente de vendas.

Adaptado do framework deep_research para o contexto de vendas B2B.
"""

import asyncio

import httpx
from langchain_core.tools import tool
from markdownify import markdownify
from tavily import TavilyClient

from app.config import get_settings
from app.security import wrap_untrusted

_tavily_client: TavilyClient | None = None

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0 Safari/537.36"
)


def _get_tavily() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        cfg = get_settings()
        _tavily_client = TavilyClient(api_key=cfg.tavily_api_key)
    return _tavily_client


async def _fetch_page_async(client: httpx.AsyncClient, url: str, max_chars: int) -> str:
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        # markdownify é CPU-bound; rodar no event loop bloqueava o servidor
        # inteiro (causa do timeout). Offload para thread.
        md = await asyncio.to_thread(markdownify, resp.text)
        return md[:max_chars]
    except Exception as exc:
        return f"Erro ao acessar {url}: {exc}"


@tool
async def tavily_search(query: str) -> str:
    """Busca informações na web sobre empresas, pessoas ou mercados.

    Use para coletar dados sobre empresas-alvo, interlocutores,
    tendências de mercado e notícias relevantes para vendas.

    Args:
        query: Consulta de busca — seja específico para melhores resultados.
    """
    cfg = get_settings()
    query = (query or "").strip()[:512]
    if not query:
        return "Consulta vazia."

    client = _get_tavily()
    try:
        results = await asyncio.to_thread(
            client.search, query, max_results=cfg.tavily_max_results, topic="general"
        )
    except Exception as exc:
        return f"Erro na busca web: {exc}"

    items = results.get("results", [])
    if not items:
        return f"Nenhum resultado encontrado para '{query}'."

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT}, timeout=cfg.tavily_fetch_timeout
    ) as http:
        contents = await asyncio.gather(
            *(_fetch_page_async(http, item["url"], cfg.web_content_max_chars) for item in items)
        )

    parts = [
        f"## {item['title']}\n**URL:** {item['url']}\n\n{content}\n\n---"
        for item, content in zip(items, contents)
    ]
    body = f"Encontrados {len(parts)} resultado(s) para '{query}':\n\n" + "\n".join(parts)
    # Conteúdo web é não confiável — envolve para mitigar injeção indireta (Vetor 3).
    return wrap_untrusted("web", body)


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
