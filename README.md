# Claro que Eu vendo!

Assistente de vendas com IA para PMEs — pesquisa empresas, analisa interlocutores, monta briefings e dá suporte em tempo real durante negociações.

## Arquitetura

```
claro-que-eu-vendo/
├── main.py                          # FastAPI entry point
├── requirements.txt
├── .env.example
├── app/
│   ├── config.py                    # Settings (pydantic-settings)
│   ├── api/
│   │   ├── routes.py                # Endpoints REST
│   │   └── schemas.py               # Contratos Pydantic
│   ├── agent/
│   │   ├── graph.py                 # LangGraph ReAct agent
│   │   ├── prompts.py               # System prompts
│   │   └── tools.py                 # Tavily search + think tool
│   ├── observability/
│   │   └── __init__.py              # LangFuse callback handler
│   └── static/
│       └── index.html               # Frontend (Tailwind + vanilla JS)
```

**Stack:** Python 3.11+ · FastAPI · LangGraph · LangChain · OpenAI · Tavily · LangFuse

## Quickstart

### 1. Clone e configure

```bash
git clone https://github.com/sergiogaiotto/claro-que-eu-vendo.git
cd claro-que-eu-vendo
cp .env.example .env
# Edite .env com suas chaves reais
```

### 2. Instale dependências

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Execute

```bash
python main.py
```

Acesse `http://localhost:8000` no navegador.

## API

### `POST /api/v1/chat`

```json
{
  "message": "Pesquise a empresa XYZ e prepare um briefing",
  "history": [],
  "session_id": "opcional",
  "user_id": "opcional"
}
```

Resposta:

```json
{
  "response": "## Perfil da Empresa XYZ\n...",
  "session_id": "uuid"
}
```

### `GET /api/v1/health`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "agent": "Claro que Eu vendo!"
}
```

## Chaves necessárias

| Variável | Onde obter | Obrigatório |
|----------|-----------|-------------|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | Sim |
| `TAVILY_API_KEY` | [tavily.com](https://www.tavily.com) | Sim |
| `LANGFUSE_PUBLIC_KEY` | [cloud.langfuse.com](https://cloud.langfuse.com) | Não* |
| `LANGFUSE_SECRET_KEY` | [cloud.langfuse.com](https://cloud.langfuse.com) | Não* |

*Observabilidade desativada sem LangFuse — o agente funciona normalmente.

## Funcionalidades

- **Briefing de Empresa**: pesquisa web, perfil, pontos de dor, recomendações
- **Perfil de Interlocutor**: análise de presença digital, estilo de comunicação
- **Tendências de Mercado**: análise setorial com dados atualizados
- **Botão de Pânico**: suporte rápido durante negociação ao vivo
- **Observabilidade**: traces completos no LangFuse
- **API REST**: integração com qualquer sistema via HTTP

## Base Conceitual

Inspirado no framework [deepagents/deep_research](https://github.com/langchain-ai/deepagents) da LangChain, adaptado para inteligência de vendas B2B com padrão ReAct (Reasoning + Acting) via LangGraph.

## Licença

MIT

---

*Projeto criado por [Sergio Gaiotto](https://www.falagaiotto.com.br)*
