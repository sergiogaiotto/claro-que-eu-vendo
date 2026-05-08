# Claro que Eu vendo!

Assistente de inteligência de vendas B2B para PMEs. Pesquisa empresas, analisa interlocutores, monta briefings, recomenda produtos do catálogo via NBO (Next Best Offer), gera pitches estruturados, exporta guias em PDF e oferece **Botão de Pânico** para suporte ao vivo durante a negociação.

---

## Sumário

- [Visão funcional](#visão-funcional)
- [Arquitetura técnica](#arquitetura-técnica)
- [Stack](#stack)
- [Estrutura de diretórios](#estrutura-de-diretórios)
- [Quickstart](#quickstart)
- [Configuração — variáveis de ambiente](#configuração--variáveis-de-ambiente)
- [API REST — referência completa](#api-rest--referência-completa)
- [Modelo de dados](#modelo-de-dados)
- [Skills (SKILL.md) — como o agente raciocina](#skills-skillmd--como-o-agente-raciocina)
- [Catálogo Text-to-SQL + motor NBO](#catálogo-text-to-sql--motor-nbo)
- [Geração de PDF — Guia de Bolso do Vendedor](#geração-de-pdf--guia-de-bolso-do-vendedor)
- [Observabilidade](#observabilidade)
- [Segurança da Informação (SI / Cybersec)](#segurança-da-informação-si--cybersec)
- [Operação e deploy](#operação-e-deploy)
- [Base conceitual](#base-conceitual)
- [Licença](#licença)

---

## Visão funcional

O sistema apoia o vendedor em **três momentos** do ciclo comercial:

| Momento | O que o app faz | Skills envolvidos |
|---------|-----------------|-------------------|
| **Pré-reunião** | Briefing da empresa, perfil do interlocutor, tendências do setor, recomendação de produtos do catálogo, montagem de pitch e exportação em PDF | `briefing-empresa`, `perfil-interlocutor`, `tendencias-mercado`, `catalogo-match`, `nbo-engine`, `pitch-builder` |
| **Durante a reunião** | Botão de Pânico — respostas curtas (3-4 frases), focadas em ação imediata para defender preço, lidar com objeções e desbloquear a conversa | `botao-panico`, `objecao-preco` |
| **Pós-reunião** | Mensagem de follow-up personalizada para manter o relacionamento aquecido e avançar o ciclo | `follow-up` |

### Fluxo do vendedor

1. **Login** (cria root automaticamente no primeiro acesso).
2. **Cria um Pitch** — vincula a empresa-alvo a uma sessão persistente.
3. **Conversa com o agente** via chat — o agente identifica o skill correto, pesquisa na web, consulta o catálogo, e devolve a resposta formatada.
4. **Marca trechos com 👍** (Liked) e adiciona **anotações** em qualquer interação.
5. **Exporta o Guia de Bolso em PDF** — capa, índice, seções classificadas (Empresa, Interlocutor, Dores, Abordagem, Pitch, Produtos com cards NBO coloridos por tier), destaques, anotações e checklist pré-reunião.
6. **Importa CSV do catálogo** — colunas viram campos SQL automaticamente; o agente passa a recomendar produtos via NBO.

### Botões clicáveis ([[action: ...]])

O agente embute marcadores `[[action: texto]]` na resposta. O frontend converte em **botões clicáveis** que enviam o texto de volta como nova mensagem — usado para desambiguação (escolher entre múltiplas empresas/contatos), navegação ("Montar pitch", "Analisar interlocutor") e urgências durante a negociação.

### Desambiguação obrigatória

Regra inviolável do prompt do orquestrador: **toda busca que retornar mais de um resultado** (empresa homônima, perfis com mesmo nome, múltiplos contatos numa empresa, vários produtos no catálogo) faz o agente **parar, listar todos** e aguardar a seleção do vendedor. Isso elimina a classe de erros "briefing da empresa errada".

---

## Arquitetura técnica

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vanilla JS + Tailwind, single-file index.html)   │
│  Tabs: Chat · Pitches · Catálogo · Skills · Usuários        │
└──────────────────┬──────────────────────────────────────────┘
                   │  REST + JWT
┌──────────────────▼──────────────────────────────────────────┐
│  FastAPI (main.py)                                          │
│  Routers: /auth · /chat · /pitches · /catalog · /skills     │
│  Middleware: CORS · Pydantic validation                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
       ┌───────────┼───────────┬──────────────┐
       │           │           │              │
┌──────▼─────┐ ┌──▼──────┐ ┌──▼─────────┐ ┌──▼─────────────┐
│ LangGraph  │ │ SQLite  │ │ SQLite     │ │ ReportLab      │
│ ReAct      │ │ app.db  │ │ catalog.db │ │ PDF builder    │
│ Agent      │ │ (users, │ │ (Text-to-  │ │ (Guia de       │
│ + 6 tools  │ │ pitches)│ │  SQL)      │ │  Bolso)        │
└──────┬─────┘ └─────────┘ └────────────┘ └────────────────┘
       │
       ├── tavily_search (web search)
       ├── think_tool (reflexão estratégica)
       ├── catalog_list_tables / get_schema / query / nbo_analyze
       │
       ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ OpenAI (gpt-4o-mini)     │    │ LangFuse (opcional)      │
│ via langchain-openai     │    │ traces, sessions, costs  │
└──────────────────────────┘    └──────────────────────────┘
```

### Padrão ReAct via LangGraph

O agente usa o padrão **Reasoning + Acting** implementado como grafo de estados em [graph.py](app/agent/graph.py):

```
START → agent_node ─┐
         │          │ tool_calls?
         ▼          │
       END ◄─── _should_continue ─── tools (ToolNode)
                                         │
                                         └──► loop de volta a agent_node
```

- O `system_prompt` é montado dinamicamente: data atual + bloco `<Skills disponíveis>` (todos os SKILL.md concatenados) injetado em cada turn.
- `recursion_limit=30` no LangGraph evita loops infinitos.
- Streaming habilitado no `ChatOpenAI` (preparado para SSE futuro).

---

## Stack

**Backend:**
- Python 3.11+
- [FastAPI](https://fastapi.tiangolo.com/) ≥0.115 + [uvicorn](https://www.uvicorn.org/)
- [LangChain](https://www.langchain.com/) ≥0.3 + [LangGraph](https://langchain-ai.github.io/langgraph/) ≥0.4
- [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 (ORM) + SQLite
- [PyJWT](https://pyjwt.readthedocs.io/) (auth)
- [Pydantic](https://docs.pydantic.dev/) v2 + pydantic-settings (config & validação)
- [ReportLab](https://www.reportlab.com/) (PDF)
- [Tavily](https://www.tavily.com/) (web search) + [markdownify](https://github.com/matthewwithanm/python-markdownify) + httpx
- [LangFuse](https://langfuse.com/) (observabilidade — opcional)

**Frontend:** HTML único com Tailwind via CDN + JS vanilla. Zero build step.

**Modelos:** `gpt-4o-mini` (default, configurável via `OPENAI_MODEL`).

---

## Estrutura de diretórios

```
claro-que-eu-vendo/
├── main.py                          # FastAPI entry point + bootstrap
├── Dockerfile                       # Imagem Python 3.11-slim
├── requirements.txt
├── .env                             # Chaves (não commitar em prod)
├── data/
│   ├── app.db                       # users, pitches, pitch_interactions
│   └── catalog.db                   # produtos (schema dinâmico via CSV)
└── app/
    ├── config.py                    # Settings centralizadas (pydantic-settings)
    ├── database.py                  # Models SQLAlchemy + factory de session
    ├── catalog_engine.py            # Text-to-SQL + ferramentas LangChain do catálogo
    ├── skill_loader.py              # Carrega SKILL.md e injeta no system prompt
    ├── api/
    │   ├── routes.py                # POST /chat (orquestrador principal)
    │   ├── auth.py                  # /auth/login, users CRUD, JWT
    │   ├── pitch.py                 # /pitches CRUD + interactions + PDF builder
    │   ├── catalog.py               # /catalog import/export/sql/schema
    │   ├── skills.py                # /skills CRUD (edição em runtime)
    │   └── schemas.py               # Pydantic contracts
    ├── agent/
    │   ├── graph.py                 # LangGraph ReAct StateGraph
    │   ├── prompts.py               # SALES_ORCHESTRATOR_PROMPT + outros
    │   └── tools.py                 # tavily_search + think_tool (+ catalog tools)
    ├── observability/
    │   └── __init__.py              # LangFuse callback handler factory
    ├── skills/                      # 9 skills versionados como SKILL.md
    │   ├── briefing-empresa/SKILL.md
    │   ├── perfil-interlocutor/SKILL.md
    │   ├── tendencias-mercado/SKILL.md
    │   ├── catalogo-match/SKILL.md
    │   ├── nbo-engine/SKILL.md
    │   ├── pitch-builder/SKILL.md
    │   ├── botao-panico/SKILL.md
    │   ├── objecao-preco/SKILL.md
    │   └── follow-up/SKILL.md
    └── static/
        └── index.html               # SPA single-file (1.2k linhas)
```

---

## Quickstart

### 1. Clone e configure

```bash
git clone https://github.com/sergiogaiotto/claro-que-eu-vendo.git
cd claro-que-eu-vendo
cp .env .env.local             # ou edite o .env diretamente
# Edite com suas chaves reais — veja seção "Configuração"
```

### 2. Ambiente virtual + dependências

```bash
python -m venv .venv
# Linux/Mac:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (Git Bash):
source .venv/Scripts/activate

pip install -r requirements.txt
```

### 3. Execute

```bash
python main.py
# ou diretamente:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Abra `http://localhost:8000`. No primeiro login, qualquer username/senha cria automaticamente o usuário **root**.

### 4. Docker

```bash
docker build -t claro-que-eu-vendo .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data claro-que-eu-vendo
```

---

## Configuração — variáveis de ambiente

| Variável | Default | Obrigatório | Descrição |
|----------|---------|:-----------:|-----------|
| `OPENAI_API_KEY` | — | ✅ | Chave da OpenAI ([platform.openai.com](https://platform.openai.com)) |
| `OPENAI_MODEL` | `gpt-4o-mini` | | Modelo OpenAI |
| `TAVILY_API_KEY` | — | ✅ | Chave Tavily ([tavily.com](https://www.tavily.com)) |
| `LANGFUSE_PUBLIC_KEY` | — | | Observabilidade — desativada se vazia |
| `LANGFUSE_SECRET_KEY` | — | | |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | | Self-host suportado |
| `LANGSMITH_API_KEY` | — | | Reservado |
| `JWT_SECRET` | `change-me-in-production-...` | ⚠️ prod | Segredo do JWT — **trocar em produção** |
| `JWT_ALGORITHM` | `HS256` | | |
| `JWT_EXPIRE_MINUTES` | `480` (8h) | | |
| `DATABASE_URL` | `sqlite:///./data/app.db` | | Postgres/MySQL via SQLAlchemy URL |
| `APP_HOST` | `0.0.0.0` | | |
| `APP_PORT` | `8000` | | |
| `APP_ENV` | `development` | | |

O `_check_required_keys` em [main.py](main.py:17) **falha o startup** se `OPENAI_API_KEY` ou `TAVILY_API_KEY` estiverem vazias ou contiverem placeholders (`sk-your...`, `tvly-your...`). Mensagem clara apontando onde obter cada chave.

---

## API REST — referência completa

Todos os endpoints estão sob o prefixo `/api/v1`. CORS aberto (`allow_origins=["*"]` — restringir em produção).

### Autenticação — `/auth`

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/auth/has-users` | `{has_users: bool}` — frontend usa para decidir tela inicial |
| `POST` | `/auth/login` | Body: `{username, password}` → `{token, user_id, username, role, display_name}`. **Bootstrap**: se não há usuários, cria root automaticamente. |
| `POST` | `/auth/users` | Cria usuário (`role`: `root`, `admin`, `user`) |
| `GET` | `/auth/users` | Lista usuários |
| `PUT` | `/auth/users/{id}` | Atualiza display_name, role, profile, password |
| `DELETE` | `/auth/users/{id}` | Remove (proteção: não pode remover último root) |

### Chat — `/chat`

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/health` | `{status, version, agent}` |
| `POST` | `/chat` | Endpoint principal do agente |

**ChatRequest:**
```json
{
  "message": "Pesquise a empresa XYZ e prepare briefing",
  "history": [{"role": "user|assistant", "content": "..."}],
  "session_id": "uuid (opcional — gerado se ausente)",
  "user_id": "string (vai para LangFuse)",
  "pitch_id": 42,
  "company_name": "ACME Ltda",
  "company_city": "São Paulo"
}
```

Se `pitch_id` + `user_id` informados, a interação é persistida em `pitch_interactions` (user + assistant). Se `company_name` ou `company_city` informados, a mensagem é prefixada com `[Contexto: Empresa: X, Cidade: Y]` antes de ir ao LLM — usado pelo orquestrador como filtro primário de desambiguação.

**ChatResponse:** `{response: "markdown da resposta", session_id: "uuid"}`

**Tradução de erros** ([routes.py:50](app/api/routes.py:50)): erros da OpenAI são traduzidos em mensagens legíveis (chave inválida, rate limit, timeout) sem vazar stack traces.

### Pitches — `/pitches`

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/pitches/?user_id=X&company=Y&liked_only=bool` | Lista pitches do usuário com filtros |
| `POST` | `/pitches/?user_id=X` | Cria pitch (`{company_name}`) |
| `POST` | `/pitches/interactions` | Adiciona interação manual (`{pitch_id, role, content}`) |
| `PATCH` | `/pitches/interactions/{id}/like` | `{liked: true/false/null}` — marca trecho como destaque |
| `PATCH` | `/pitches/interactions/{id}/note` | `{note: "anotação"}` |
| `DELETE` | `/pitches/{id}` | Remove pitch + cascade interactions |
| `GET` | `/pitches/{id}/pdf` | Gera **Guia de Bolso do Vendedor** em PDF |

### Catálogo — `/catalog`

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/catalog/schema` | Colunas + amostra de 3 registros + total de linhas |
| `GET` | `/catalog/products?limit=50&offset=0` | Lista paginada |
| `POST` | `/catalog/sql` | Body: `{sql: "SELECT ..."}` — **SELECT-only** |
| `POST` | `/catalog/import` | multipart `file` (.csv) — drop & recreate |
| `GET` | `/catalog/export` | Download CSV |
| `DELETE` | `/catalog/` | Drop table |

### Skills — `/skills`

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/skills/` | Lista resumida (slug, name, objetivo, quando usar) |
| `GET` | `/skills/{slug}` | Conteúdo completo do SKILL.md |
| `POST` | `/skills/` | Cria skill — `slug` valida regex `^[a-z0-9\-]+$` |
| `PUT` | `/skills/{slug}` | Edita skill em runtime (próxima request usa o novo) |
| `DELETE` | `/skills/{slug}` | Remove skill |

### Documentação automática

FastAPI expõe Swagger e ReDoc:
- `http://localhost:8000/docs` (Swagger UI)
- `http://localhost:8000/redoc` (ReDoc)

---

## Modelo de dados

### `app.db` (SQLite — autenticação + pitches)

```
users
├── id (PK)
├── username (UNIQUE, INDEXED)
├── password_hash (SHA-256 hex)
├── role (root | admin | user)
├── display_name
├── profile_description
└── created_at

pitches
├── id (PK)
├── user_id → users.id
├── company_name (INDEXED)
└── created_at

pitch_interactions
├── id (PK)
├── pitch_id → pitches.id (CASCADE DELETE)
├── role (user | assistant)
├── content (TEXT)
├── liked (Boolean | NULL)  -- destaque do vendedor
├── note (TEXT)              -- anotação livre
└── created_at
```

### `catalog.db` (SQLite — schema dinâmico)

Tabela `produtos` é **criada em runtime** a partir do CSV importado. Cada coluna do CSV vira uma coluna `TEXT` (nome sanitizado por `_sanitize_col`). Índices são criados automaticamente em colunas que casam com `nome|name|produto|product|titulo|title|descricao` ([catalog_engine.py:74](app/catalog_engine.py:74)).

---

## Skills (SKILL.md) — como o agente raciocina

Cada skill é um arquivo markdown em `app/skills/<slug>/SKILL.md` contendo:
- **Objetivo** — quando o skill se aplica
- **Quando usar** — gatilhos do vendedor
- **Workflow** — passos numerados
- **Formato de saída** — template de resposta
- **Regras** — limites e obrigações

Em **cada turn do chat**, [skill_loader.py](app/skill_loader.py:56) lê todos os SKILL.md, concatena dentro de um bloco `<Skills disponíveis>`, e injeta no `SALES_ORCHESTRATOR_PROMPT`. O orquestrador identifica qual skill se aplica e segue o workflow declarado.

**Editar um skill via UI** (tab Skills) altera o comportamento do agente na próxima request — sem deploy.

### Os 9 skills disponíveis

| Skill | Quando dispara |
|-------|----------------|
| `briefing-empresa` | Vendedor pede dossiê de uma empresa-alvo |
| `perfil-interlocutor` | Análise de uma pessoa (cargo, comunicação, gatilhos) |
| `tendencias-mercado` | Panorama setorial atualizado |
| `catalogo-match` | Cruza dores da empresa com produtos do catálogo |
| `nbo-engine` | Monta proposta com Âncora + Acelerador + Expansão |
| `pitch-builder` | Script de vendas estruturado |
| `botao-panico` | Suporte rápido durante reunião — respostas de 3-4 frases |
| `objecao-preco` | Reposicionamento de "está caro" para valor |
| `follow-up` | Mensagem pós-reunião |

---

## Catálogo Text-to-SQL + motor NBO

### Importação de CSV

[catalog_engine.py:42](app/catalog_engine.py:42) recebe CSV (delimitador detectado automaticamente: `,` ou `;`), sanitiza nomes de coluna e faz **drop & recreate** da tabela `produtos`. Cada coluna vira `TEXT`, com `id INTEGER PRIMARY KEY AUTOINCREMENT` adicionado.

### Ferramentas do agente (LangChain Tools)

| Tool | Função |
|------|--------|
| `catalog_list_tables` | Descobrir tabelas existentes |
| `catalog_get_schema(table_name)` | Schema + amostra de dados — agente consulta antes de montar query |
| `catalog_query(sql)` | Executa SELECT — bloqueia INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE |
| `catalog_nbo_analyze(pain_points, max=5)` | Motor NBO — score por keyword match em todas as colunas de texto |

### Algoritmo NBO

1. Extrai keywords ≥4 chars dos pontos de dor (até 15 distintas).
2. Para cada produto, calcula `score = Σ (keyword in qualquer_coluna ? 1 : 0)`.
3. Ordena `score DESC`, retorna top-N.
4. Renderiza em markdown com aderência em estrelas (★★★★☆) e ações sugeridas (`[[action: ...]]`).

Query parametrizada com `?` placeholders — sem concatenação de string com input do usuário.

---

## Geração de PDF — Guia de Bolso do Vendedor

[pitch.py:166](app/api/pitch.py:166) gera o PDF via ReportLab com:

- **Capa** com nome da empresa, data, branding.
- **Sumário** dinâmico (só seções com conteúdo).
- **Classificação automática** das mensagens do agente em 6 grupos por keyword matching:
  - `1. A Empresa` · `2. O Interlocutor` · `3. Pontos de Dor` · `4. Estratégia de Abordagem` · `5. Roteiro do Pitch` · `6. Produtos Recomendados (NBO)`
- **Cards de produtos NBO** com borda colorida por tier:
  - 🟧 Âncora · 🟦 Acelerador · 🟩 Expansão
- **Tabela-resumo da proposta** com header, alternância de linhas, total destacado.
- **Destaques do Vendedor** — trechos marcados com 👍.
- **Anotações** do vendedor.
- **Checklist Pré-Reunião** (8 itens).
- Sanitização do nome do arquivo: regex `[^a-zA-Z0-9_\-]`, normalização Unicode `NFKD`.
- Markdown→ReportLab com escape HTML (`<`, `>`, `&`).

---

## Observabilidade

Cada chamada `/chat` cria um trace no LangFuse com:
- `session_id` — agrupamento de turns da mesma conversa
- `user_id` — para auditoria por vendedor
- `trace_name="chat"`
- Custos OpenAI por request (token in/out)
- Latência por nó do grafo
- Retries e erros

Se as chaves do LangFuse não estiverem configuradas, o `create_langfuse_handler` retorna `None` silenciosamente e o agente roda normalmente. O `handler.flush()` é chamado no `finally` do endpoint para garantir que traces não sejam perdidos em caso de erro.

---

## Segurança da Informação (SI / Cybersec)

Esta é uma aplicação **com dados sensíveis** (pesquisas comerciais, perfis de pessoas, catálogos privados). As proteções abaixo estão implementadas; **leia os "alertas para produção"** antes de expor o app em rede pública.

### 🔐 Autenticação & Autorização

| Mecanismo | Implementação | Local |
|-----------|---------------|-------|
| JWT (HS256) | PyJWT, expiração 480 min, payload com `sub`, `username`, `role`, `exp` | [auth.py:23](app/api/auth.py:23) |
| RBAC | 3 níveis: `root`, `admin`, `user` | [database.py:25](app/database.py:25) |
| Bootstrap seguro | Primeiro login de qualquer username cria automaticamente o root | [auth.py:99](app/api/auth.py:99) |
| Lockout prevention | Não permite remover o último usuário root | [auth.py:212](app/api/auth.py:212) |
| Tratamento de token | `ExpiredSignatureError` e `InvalidTokenError` capturados explicitamente | [auth.py:41](app/api/auth.py:41) |

### 🛡️ Proteção contra SQL Injection

| Vetor | Mitigação | Local |
|-------|-----------|-------|
| `/catalog/sql` | **Whitelist SELECT-only** — bloqueia INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE | [catalog_engine.py:135](app/catalog_engine.py:135) |
| NBO query builder | **Placeholders `?`** parametrizados — sem string concat com input | [catalog_engine.py:280](app/catalog_engine.py:280) |
| Nomes de coluna do CSV | `_sanitize_col` — regex `[^\w]→_`, prefixo se começa com dígito | [catalog_engine.py:29](app/catalog_engine.py:29) |
| Filtros ORM | SQLAlchemy parametriza queries por padrão | [pitch.py:84](app/api/pitch.py:84) |

### 🚧 Validação de entrada

- **Pydantic v2** em todos os endpoints — `Field(min_length=1, ...)`, type coercion, validação de schema.
- Slug de skill com regex `^[a-z0-9\-]+$` — previne **path traversal** via `/skills/../etc/passwd` ([skills.py:28](app/api/skills.py:28)).
- Validação de extensão `.csv` no upload ([catalog.py:66](app/api/catalog.py:66)).
- Decode com `utf-8-sig` (remove BOM) — evita parse-confusion em CSVs do Excel ([catalog.py:70](app/api/catalog.py:70)).
- Limite hard-coded `LIMIT 500` no `/catalog/products` (Query `le=500`).

### 🧱 Hardening da camada LLM

| Risco | Mitigação |
|-------|-----------|
| Loop infinito de tool calls | `recursion_limit=30` no LangGraph ([graph.py:101](app/agent/graph.py:101)) |
| Conteúdo HTML malicioso retornado por scrape | `markdownify` converte para markdown e trunca em **8000 chars** ([tools.py:36](app/agent/tools.py:36)) |
| Abuse de busca | `max_results=3` no Tavily |
| Vazamento de stack trace | Erros traduzidos para mensagens genéricas (chave inválida, rate limit, timeout) sem expor `str(exc)` em casos sensíveis ([routes.py:50](app/api/routes.py:50)) |
| Prompt injection via dados pesquisados | Resposta passa pelo formato estruturado dos skills antes de chegar ao usuário (defesa parcial — leia abaixo) |

### 📄 Hardening do gerador de PDF

- **HTML escaping** em `md_to_rl` — `&`, `<`, `>` substituídos antes de virar tag ReportLab ([pitch.py:266](app/api/pitch.py:266)).
- Sanitização do filename: `unicodedata.NFKD` + regex `[^a-zA-Z0-9_\-]` + colapso de underscores duplicados ([pitch.py:887](app/api/pitch.py:887)).
- Action tags `[[action: ...]]` removidas antes do render — não vazam para o documento exportado.

### 🕵️ Privacidade & Auditoria

- **Sem logs de conteúdo de chat** no servidor — só metadados (session_id, user_id) vão para LangFuse.
- User-Agent forjado nas buscas web (`Mozilla/5.0 ... Chrome/131`) — não revela User-Agent do servidor ([tools.py:17](app/agent/tools.py:17)).
- Histórico de pitches isolado por `user_id` — query sempre filtra `Pitch.user_id == user_id`.
- Cascade delete em `pitch_interactions` — ao remover pitch, todas as interações são apagadas atomicamente.

### ⚠️ Alertas para produção (hardening recomendado)

A aplicação está **pronta para uso interno / desenvolvimento**, mas os pontos abaixo precisam ser tratados antes de exposição pública:

| Risco | Status atual | Ação recomendada |
|-------|--------------|------------------|
| **Hash de senha SHA-256 sem salt** | `hashlib.sha256(password.encode()).hexdigest()` ([auth.py:19](app/api/auth.py:19)) | Migrar para **bcrypt** ou **argon2-cffi** (`pip install bcrypt`) — SHA-256 é vulnerável a rainbow tables |
| **CORS totalmente aberto** | `allow_origins=["*"]` ([main.py:42](main.py:42)) | Restringir a domínios específicos: `["https://app.suaempresa.com.br"]` |
| **JWT_SECRET default fraco** | String literal `"change-me-in-production-..."` ([config.py:27](app/config.py:27)) | **Obrigatoriamente** definir `JWT_SECRET` ≥32 bytes random em produção (`openssl rand -hex 32`) |
| **Sem rate limiting** | Endpoints `/auth/login`, `/chat`, `/catalog/sql` aceitam tráfego ilimitado | Adicionar [`slowapi`](https://github.com/laurentS/slowapi) ou nginx/Cloudflare |
| **Sem CSRF token** | API stateless via JWT — aceitável se token for armazenado em `Authorization` header (não em cookie) | Garantir que frontend NUNCA persista JWT em cookie sem `SameSite=Strict` + `HttpOnly` |
| **Token via query string** em [auth.py:34](app/api/auth.py:34) | `get_current_user(token: str = "")` aceita token em query | Migrar para `Depends(HTTPBearer())` — token só em header `Authorization: Bearer` |
| **Sem validação de tamanho de upload** | `/catalog/import` aceita CSV de qualquer tamanho | Adicionar `Content-Length` check e `MAX_UPLOAD_SIZE` |
| **`check_same_thread=False` no SQLite** | Necessário para FastAPI async, mas requer cuidado | Em produção, migrar para Postgres (`DATABASE_URL=postgresql://...`) |
| **HTTPS** | Servido via uvicorn HTTP plain | Coloque atrás de nginx/Caddy/Traefik com TLS terminator |
| **Logs de auditoria** | Apenas LangFuse (chat) | Adicionar log estruturado de eventos de auth (login success/fail, criação de usuário, edição de skill) |
| **Edição de Skills sem audit log** | `PUT /skills/{slug}` reescreve o arquivo sem trilha | Versionar `SKILL.md` em git ou registrar `who+when` em tabela |
| **Prompt injection via dados pesquisados** | Tavily retorna conteúdo de páginas externas que entra no contexto do LLM | Considerar sandbox de tool outputs (XML wrappers, instruction reinforcement) |
| **Dados em repouso não criptografados** | SQLite arquivo `.db` em disco | Em servidor compartilhado, criptografar volume (LUKS, BitLocker) ou usar Postgres com TDE |

### 🔬 Threat model resumido

| Ameaça | Vetor | Status |
|--------|-------|:------:|
| SQL Injection no `/catalog/sql` | User envia `DROP TABLE` | ✅ bloqueado |
| Path traversal em skills | `/skills/../../etc/passwd` | ✅ regex slug |
| XSS no PDF exportado | Markdown malicioso vira HTML no ReportLab | ✅ escape `&`, `<`, `>` |
| Brute force de senha | Login repetido | ⚠️ sem rate limit |
| Rainbow table de hash | DB exfiltrado, senhas crackadas | ⚠️ SHA-256 sem salt |
| Token sniffing | Token em query string aparece em logs do servidor | ⚠️ aceito via query |
| Lockout administrativo | Remoção de todos os roots | ✅ guarda explícita |
| Prompt injection | Conteúdo malicioso em página pesquisada | ⚠️ defesa parcial |

---

## Operação e deploy

### Backup

- **Volume `data/`** contém `app.db` + `catalog.db`. Backup periódico recomendado (cron + `sqlite3 .backup`).
- Em produção, prefira **Postgres** com replica + WAL archiving.

### Logs

- uvicorn em stdout/stderr — capturar via systemd, Docker logging driver, ou agregador (Loki, CloudWatch).
- Erros 5xx do FastAPI vêm com `detail` legível — útil para debugging sem expor stack trace ao cliente.

### Health checks

`GET /api/v1/health` retorna `{"status": "ok", "version": "1.0.0", "agent": "Claro que Eu vendo!"}`. Use em probes de Kubernetes/load balancer.

### Custos LLM

- gpt-4o-mini é o default (≈$0.15 / 1M input, ≈$0.60 / 1M output em maio/2026).
- Tavily oferece tier free de 1k buscas/mês.
- Monitore custos via LangFuse dashboard.

---

## Base conceitual

Inspirado em:
- [LangChain deepagents/deep_research](https://github.com/langchain-ai/deepagents) — adaptado para inteligência de vendas B2B com padrão **ReAct** (Reasoning + Acting) via LangGraph.
- Estratégia **NBO (Next Best Offer)** — combinação Âncora + Acelerador + Expansão.
- Padrão **Skills as Code** — comportamento do agente versionado em SKILL.md, editável em runtime sem deploy.

---

## Licença

MIT

---

*Projeto criado por [Sergio Gaiotto](https://www.falagaiotto.com.br)*
