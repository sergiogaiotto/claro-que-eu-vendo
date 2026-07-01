# Claro que Eu vendo!

Assistente de inteligência de vendas B2B para PMEs. Pesquisa empresas, analisa interlocutores, monta briefings, recomenda produtos do catálogo via NBO (Next Best Offer), gera pitches estruturados, exporta guias em PDF e oferece **Botão de Pânico** para suporte ao vivo durante a negociação.

> **Estado de segurança:** a aplicação passou por uma auditoria AppSec (OWASP LLM Top 10 2025 · OWASP ASVS · CWE · LGPD) com 22 achados e **todos foram remediados** — veja a seção [Segurança da Informação](#segurança-da-informação-si--cybersec). O playbook reutilizável que consolida essa metodologia está em [`.claude/skills/seguranca-appsec/SKILL.md`](.claude/skills/seguranca-appsec/SKILL.md).

---

## Sumário

- [Visão funcional](#visão-funcional)
- [Arquitetura técnica](#arquitetura-técnica)
- [Stack](#stack)
- [Estrutura de diretórios](#estrutura-de-diretórios)
- [Quickstart](#quickstart)
- [Configuração — variáveis de ambiente](#configuração--variáveis-de-ambiente)
- [Provisionamento do primeiro usuário (bootstrap)](#provisionamento-do-primeiro-usuário-bootstrap)
- [API REST — referência completa](#api-rest--referência-completa)
- [Modelo de dados](#modelo-de-dados)
- [Skills (SKILL.md) — como o agente raciocina](#skills-skillmd--como-o-agente-raciocina)
- [Catálogo Text-to-SQL + motor NBO](#catálogo-text-to-sql--motor-nbo)
- [Geração de PDF — Guia de Bolso do Vendedor](#geração-de-pdf--guia-de-bolso-do-vendedor)
- [Observabilidade e auditoria](#observabilidade-e-auditoria)
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

1. **Login** com credenciais (o primeiro usuário root é provisionado pelo operador — ver [bootstrap](#provisionamento-do-primeiro-usuário-bootstrap)). A sessão vive em um **cookie HttpOnly**.
2. **Cria um Pitch** — vincula a empresa-alvo a uma sessão persistente, isolada por usuário.
3. **Conversa com o agente** via chat — o agente identifica o skill correto, pesquisa na web, consulta o catálogo, e devolve a resposta formatada.
4. **Marca trechos com 👍** (Liked) e adiciona **anotações** em qualquer interação.
5. **Exporta o Guia de Bolso em PDF** — capa, índice, seções classificadas (Empresa, Interlocutor, Dores, Abordagem, Pitch, Produtos com cards NBO coloridos por tier), destaques, anotações e checklist pré-reunião.
6. **Importa CSV do catálogo** — colunas viram campos SQL automaticamente; o agente passa a recomendar produtos via NBO.

### Botões clicáveis ([[action: ...]])

O agente embute marcadores `[[action: texto]]` na resposta. O frontend converte em **botões clicáveis** que enviam o texto de volta como nova mensagem — usado para desambiguação (escolher entre múltiplas empresas/contatos), navegação ("Montar pitch", "Analisar interlocutor") e urgências durante a negociação. Os botões são renderizados com `data-action` + delegação de evento (sem `onclick` inline) e o HTML passa por sanitização — ver [XSS](#-saída-e-xss-vuln-07).

### Desambiguação obrigatória

Regra inviolável do prompt do orquestrador: **toda busca que retornar mais de um resultado** (empresa homônima, perfis com mesmo nome, múltiplos contatos numa empresa, vários produtos no catálogo) faz o agente **parar, listar todos** e aguardar a seleção do vendedor. Isso elimina a classe de erros "briefing da empresa errada".

---

## Arquitetura técnica

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vanilla JS + Tailwind, single-file index.html)   │
│  Tabs: Chat · Pitches · Catálogo · Skills · Usuários        │
│  Auth: cookie HttpOnly · DOMPurify · sanitização de URL      │
└──────────────────┬──────────────────────────────────────────┘
                   │  REST + cookie de sessão (same-origin)
┌──────────────────▼──────────────────────────────────────────┐
│  FastAPI (main.py)                                          │
│  Routers: /auth · /chat · /pitches · /catalog · /skills     │
│  Middleware: CORS (allowlist) · Security Headers (CSP/HSTS)  │
│  Por rota: Auth (get_current_user) · Rate limit · Pydantic  │
│  Módulos SI: security · audit · ratelimit · middleware       │
└──────────────────┬──────────────────────────────────────────┘
                   │
       ┌───────────┼───────────┬──────────────┐
       │           │           │              │
┌──────▼─────┐ ┌──▼──────┐ ┌──▼─────────┐ ┌──▼─────────────┐
│ LangGraph  │ │ SQLite  │ │ SQLite     │ │ ReportLab      │
│ ReAct      │ │ app.db  │ │ catalog.db │ │ PDF builder    │
│ Agent      │ │ (users, │ │ (Text-to-  │ │ (Guia de       │
│ + 6 tools  │ │ pitches)│ │  SQL RO)   │ │  Bolso)        │
└──────┬─────┘ └─────────┘ └────────────┘ └────────────────┘
       │
       ├── tavily_search (web search — conteúdo tratado como não confiável)
       ├── think_tool (reflexão estratégica)
       ├── catalog_list_tables / get_schema / query / nbo_analyze
       │
       ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ OpenAI (gpt-4o-mini)     │    │ LangFuse (opcional)      │
│ max_tokens + timeout     │    │ traces, sessions, costs  │
└──────────────────────────┘    └──────────────────────────┘
```

### Padrão ReAct via LangGraph

O agente usa o padrão **Reasoning + Acting** implementado como grafo de estados em [`app/agent/graph.py`](app/agent/graph.py):

```
START → agent_node ─┐
         │          │ tool_calls?
         ▼          │
       END ◄─── _should_continue ─── tools (ToolNode)
                                         │
                                         └──► loop de volta a agent_node
```

Características (com foco em latência e custo previsíveis):

- O nó do agente é **assíncrono** (`await llm.ainvoke`), o grafo e o LLM base ficam em cache (`lru_cache`), e o `system_prompt` (data + bloco `<Skills disponíveis>`) é montado **uma vez por requisição** — não a cada iteração do ReAct.
- **Timeout wall-clock** de `AGENT_TIMEOUT_SECONDS` (default 90s) em torno do agente inteiro via `asyncio.wait_for` → em vez de pendurar, retorna uma mensagem amigável.
- `ChatOpenAI` com **`max_tokens`** e **`request_timeout`** por chamada; **`AGENT_RECURSION_LIMIT`** (default 12) limita os ciclos ReAct; o histórico é truncado a `HISTORY_MAX_MESSAGES`.
- A ferramenta de busca faz o parsing HTML→markdown (`markdownify`, CPU-bound) **fora do event loop** (em thread) e limita conteúdo/resultados — isso eliminou o *timeout recorrente da primeira consulta pesada*.

---

## Stack

**Backend:**
- Python 3.11+
- [FastAPI](https://fastapi.tiangolo.com/) ≥0.115 + [uvicorn](https://www.uvicorn.org/)
- [LangChain](https://www.langchain.com/) ≥0.3 + [LangGraph](https://langchain-ai.github.io/langgraph/) ≥0.4
- [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 (ORM) + SQLite
- [PyJWT](https://pyjwt.readthedocs.io/) (assinatura da sessão) — hashing de senha com **PBKDF2-HMAC-SHA256** (stdlib, salgado)
- [Pydantic](https://docs.pydantic.dev/) v2 + pydantic-settings (config & validação)
- [ReportLab](https://www.reportlab.com/) (PDF)
- [Tavily](https://www.tavily.com/) (web search) + [markdownify](https://github.com/matthewwithanm/python-markdownify) + httpx
- [LangFuse](https://langfuse.com/) (observabilidade — opcional)

**Frontend:** HTML único com Tailwind via CDN + JS vanilla + [DOMPurify](https://github.com/cure53/DOMPurify) (sanitização). Zero build step.

**Modelos:** `gpt-4o-mini` (default, configurável via `OPENAI_MODEL`).

Dependências pinadas com **limite superior** em [`requirements.txt`](requirements.txt) (mitiga supply-chain risk).

---

## Estrutura de diretórios

```
claro-que-eu-vendo/
├── main.py                          # FastAPI entry point + middlewares + bootstrap
├── Dockerfile                       # Imagem endurecida (non-root, healthcheck)
├── .dockerignore                    # Exclui .env, data/, .git da imagem
├── .gitignore                       # Ignora .env, *.db, __pycache__…
├── requirements.txt                 # Deps pinadas com upper bound
├── .env.example                     # Modelo de configuração (copie para .env)
├── data/                            # (ignorado no git) bancos SQLite em runtime
│   ├── app.db                       # users, pitches, pitch_interactions
│   └── catalog.db                   # produtos (schema dinâmico via CSV)
├── .claude/skills/
│   └── seguranca-appsec/SKILL.md    # Playbook reutilizável de AppSec + LLM
└── app/
    ├── config.py                    # Settings centralizadas (pydantic-settings)
    ├── database.py                  # Models SQLAlchemy + factory de session
    ├── security.py                  # Guardrails de prompt injection · PII masking · validação SQL/slug
    ├── audit.py                     # Audit log com hash de conteúdo (LGPD)
    ├── ratelimit.py                 # Rate limiting em memória (janela deslizante)
    ├── middleware.py                # Security headers (CSP, HSTS, X-Frame-Options…)
    ├── catalog_engine.py            # Text-to-SQL (read-only) + ferramentas LangChain do catálogo
    ├── skill_loader.py              # Carrega SKILL.md e injeta no system prompt
    ├── api/
    │   ├── routes.py                # POST /chat (orquestrador + guardrails + PII masking)
    │   ├── auth.py                  # /auth login/setup/me/logout, users CRUD, JWT em cookie
    │   ├── pitch.py                 # /pitches CRUD + interactions + PDF builder (ownership)
    │   ├── catalog.py               # /catalog import/export/sql/schema (auth)
    │   ├── skills.py                # /skills CRUD (auth + anti path traversal)
    │   └── schemas.py               # Pydantic contracts
    ├── agent/
    │   ├── graph.py                 # LangGraph ReAct StateGraph (timeout, max_tokens)
    │   ├── prompts.py               # SALES_ORCHESTRATOR_PROMPT (+ seção de segurança)
    │   └── tools.py                 # tavily_search + think_tool (+ catalog tools)
    ├── observability/
    │   └── __init__.py              # LangFuse callback handler factory
    ├── skills/                      # 9 skills de VENDAS versionados como SKILL.md
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
        └── index.html               # SPA single-file (~1.2k linhas)
```

> **Nota:** `.env` e `data/*.db` **não são versionados** (foram removidos do histórico e cobertos pelo `.gitignore`). Os skills em `app/skills/` são de domínio de vendas e **são injetados no prompt do agente**; o skill de segurança fica em `.claude/skills/` justamente para **não** contaminar o contexto do agente.

---

## Quickstart

### 1. Clone e configure

```bash
git clone https://github.com/sergiogaiotto/claro-que-eu-vendo.git
cd claro-que-eu-vendo
cp .env.example .env
# Edite o .env com suas chaves e segredos — veja "Configuração"
```

Gere um segredo JWT forte:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Ambiente virtual + dependências

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\Activate.ps1        # Windows PowerShell

pip install -r requirements.txt
```

### 3. Provisione o root e execute

```bash
# Bootstrap do primeiro usuário via env (ver seção dedicada):
export ROOT_USERNAME=admin
export ROOT_PASSWORD='uma-senha-forte'

python main.py
# ou: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Abra `http://localhost:8000` e faça login com `ROOT_USERNAME` / `ROOT_PASSWORD`.

### 4. Docker

```bash
docker build -t claro-que-eu-vendo .
docker run -p 8000:8000 --env-file .env \
  -e ROOT_USERNAME=admin -e ROOT_PASSWORD='uma-senha-forte' \
  -v $(pwd)/data:/app/data claro-que-eu-vendo
```

A imagem roda como usuário **não-root**, inclui `HEALTHCHECK` e usa `.dockerignore` para não copiar `.env`/`data`.

---

## Configuração — variáveis de ambiente

Todas as variáveis têm defaults seguros para desenvolvimento. Em produção, defina no mínimo `JWT_SECRET`, o bootstrap do root, as chaves de API e `COOKIE_SECURE=true`.

### LLM e limites do agente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `OPENAI_API_KEY` | — | Chave da OpenAI (necessária para o chat) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo OpenAI |
| `TAVILY_API_KEY` | — | Chave Tavily (necessária para busca web) |
| `LLM_MAX_TOKENS` | `4096` | Teto de tokens por resposta (custo/latência) |
| `LLM_REQUEST_TIMEOUT` | `60` | Timeout (s) por chamada ao LLM |
| `AGENT_TIMEOUT_SECONDS` | `90` | Timeout wall-clock do agente inteiro |
| `AGENT_RECURSION_LIMIT` | `12` | Máximo de ciclos ReAct |
| `HISTORY_MAX_MESSAGES` | `20` | Truncamento do histórico |
| `TAVILY_MAX_RESULTS` | `3` | Resultados por busca |
| `TAVILY_FETCH_TIMEOUT` | `6` | Timeout (s) por página buscada |
| `WEB_CONTENT_MAX_CHARS` | `6000` | Corte de conteúdo por página |

### Autenticação, sessão e bootstrap

| Variável | Default | Descrição |
|----------|---------|-----------|
| `JWT_SECRET` | `change-me-...` | **Segredo de assinatura da sessão.** Em `APP_ENV=production` a app **recusa subir** com o default/curto |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_EXPIRE_MINUTES` | `480` (8h) | Expiração do token |
| `COOKIE_NAME` | `cqv_session` | Nome do cookie de sessão |
| `COOKIE_SECURE` | `false` | **`true` em produção** (HTTPS) — marca o cookie como Secure |
| `COOKIE_SAMESITE` | `strict` | Mitiga CSRF |
| `ROOT_USERNAME` | — | Cria o root no startup (com `ROOT_PASSWORD`) se não houver usuários |
| `ROOT_PASSWORD` | — | Senha do root de bootstrap |
| `SETUP_TOKEN` | — | Alternativa: habilita o setup via web exigindo este token secreto |

### Rede, segurança e privacidade

| Variável | Default | Descrição |
|----------|---------|-----------|
| `ALLOWED_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Allowlist de origens CORS (separadas por vírgula) |
| `RATE_LIMIT_CHAT` | `20` | Requisições de chat por janela/IP |
| `RATE_LIMIT_LOGIN` | `10` | Tentativas de login/setup por janela/IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Tamanho da janela do rate limit |
| `PII_MASKING` | `true` | Mascara CPF/e-mail/telefone na saída do agente |

### Observabilidade e infra

| Variável | Default | Descrição |
|----------|---------|-----------|
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | — | Observabilidade — desativada se vazias |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Self-host suportado |
| `DATABASE_URL` | `sqlite:///./data/app.db` | Postgres/MySQL via SQLAlchemy URL |
| `APP_HOST` / `APP_PORT` | `0.0.0.0` / `8000` | |
| `APP_ENV` | `development` | `production` ativa o fail-fast do `JWT_SECRET` e o HSTS quando `COOKIE_SECURE=true` |

Se `OPENAI_API_KEY`/`TAVILY_API_KEY` estiverem ausentes/placeholder, a app **sobe mesmo assim** (log de aviso) — os módulos de auth/catálogo/skills/pitch funcionam e o `/chat` degrada com mensagem clara.

---

## Provisionamento do primeiro usuário (bootstrap)

Por segurança, **o login não cria mais usuários automaticamente** (fecha o sequestro de instância — VULN-03). O primeiro root é provisionado de uma destas formas:

- **Opção A — via ambiente (recomendada):** defina `ROOT_USERNAME` e `ROOT_PASSWORD`. No startup, se não houver usuários, o root é criado com hash salgado. Faça login com essas credenciais.
- **Opção B — setup via web com token:** defina `SETUP_TOKEN=<segredo>`. A tela de login exibe um campo **"Token de setup"**; informe usuário, senha e o token para criar o root (só funciona enquanto não há usuários e o token confere).

Sem nenhuma das duas, a tela de login informa que é preciso configurar o servidor — este é o comportamento seguro esperado, não um bug.

---

## API REST — referência completa

Todos os endpoints estão sob o prefixo `/api/v1`. **CORS é restrito por `ALLOWED_ORIGINS`** (sem wildcard). A sessão é um **cookie HttpOnly**; o frontend é servido pela própria app (same-origin), então o cookie acompanha as requisições automaticamente. Para clientes de API, também é aceito `Authorization: Bearer <token>`.

### Autenticação — `/auth`

| Método | Path | Auth | Descrição |
|--------|------|:----:|-----------|
| `GET` | `/auth/has-users` | — | `{has_users, setup_enabled}` — o frontend decide login vs. setup |
| `POST` | `/auth/setup` | token | Cria o primeiro root; exige `SETUP_TOKEN` e `count==0`. Emite o cookie de sessão |
| `POST` | `/auth/login` | — | `{username, password}` → dados públicos do usuário + **cookie HttpOnly**. Rate-limited; **não** cria usuários |
| `POST` | `/auth/logout` | — | Limpa o cookie de sessão |
| `GET` | `/auth/me` | sessão | Retorna o usuário autenticado (restaura sessão no reload) |
| `POST` | `/auth/users` | admin | Cria usuário (`role`: `root`/`admin`/`user`) — **só root concede root** |
| `GET` | `/auth/users` | admin | Lista usuários |
| `PUT` | `/auth/users/{id}` | admin | Atualiza display/role/profile/senha — admin não modifica root nem promove a root |
| `DELETE` | `/auth/users/{id}` | admin | Remove (não pode remover a si mesmo, o último root, e admin não remove root) |

Senhas: **PBKDF2-HMAC-SHA256 salgado** (240k rounds), verificação timing-safe e re-hash transparente de hashes legados no login.

### Chat — `/chat`

| Método | Path | Auth | Descrição |
|--------|------|:----:|-----------|
| `GET` | `/health` | — | `{status, version, agent}` |
| `POST` | `/chat` | sessão | Endpoint principal do agente — rate-limited |

**ChatRequest:**
```json
{
  "message": "Pesquise a empresa XYZ e prepare briefing",
  "history": [{"role": "user|assistant", "content": "..."}],
  "session_id": "uuid (opcional — gerado se ausente)",
  "pitch_id": 42,
  "company_name": "ACME Ltda",
  "company_city": "São Paulo"
}
```

Fluxo de segurança do `/chat`:

- O usuário vem **do cookie de sessão** (não de `user_id` no corpo).
- `message`, `company_name`, `company_city` e as mensagens `user` do `history` passam por um **guardrail de prompt injection**; entrada suspeita retorna `400`.
- O contexto empresa/cidade e o conteúdo web são envolvidos em um bloco **`<<DADOS_NAO_CONFIAVEIS>>`** (separando dados de instruções).
- A interação só é persistida se `pitch_id` pertencer ao usuário autenticado.
- A resposta passa por **mascaramento de PII** (se `PII_MASKING=true`) antes de retornar.

**ChatResponse:** `{response: "markdown da resposta", session_id: "uuid"}`

### Pitches — `/pitches`  (todos exigem sessão; ownership por token)

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/pitches/?company=Y&liked_only=bool` | Lista pitches **do usuário logado** (sem `user_id` no cliente) |
| `POST` | `/pitches/` | Cria pitch (`{company_name}`) vinculado ao usuário |
| `POST` | `/pitches/interactions` | Adiciona interação (valida que o pitch é do usuário) |
| `PATCH` | `/pitches/interactions/{id}/like` | `{liked}` — só em interação própria |
| `PATCH` | `/pitches/interactions/{id}/note` | `{note}` — só em interação própria |
| `DELETE` | `/pitches/{id}` | Remove pitch próprio + cascade |
| `GET` | `/pitches/{id}/pdf` | Gera **Guia de Bolso** do pitch próprio |

Acesso a recurso de outro usuário retorna **404** (não vaza existência).

### Catálogo — `/catalog`

| Método | Path | Auth | Descrição |
|--------|------|:----:|-----------|
| `GET` | `/catalog/schema` | sessão | Colunas + amostra + total |
| `GET` | `/catalog/products?limit=50&offset=0` | sessão | Lista paginada (parametrizada) |
| `POST` | `/catalog/sql` | sessão | `{sql}` — **read-only real** (ver abaixo), rate-limited |
| `POST` | `/catalog/import` | **admin** | multipart `.csv` (limite 5 MB) — drop & recreate |
| `GET` | `/catalog/export` | sessão | Download CSV |
| `DELETE` | `/catalog/` | **admin** | Drop table |

### Skills — `/skills`

| Método | Path | Auth | Descrição |
|--------|------|:----:|-----------|
| `GET` | `/skills/` | sessão | Lista resumida |
| `GET` | `/skills/{slug}` | sessão | Conteúdo do SKILL.md (não é mais público — VULN-16) |
| `POST` | `/skills/` | **admin** | Cria skill — slug `^[a-z0-9\-]+$` |
| `PUT` | `/skills/{slug}` | **admin** | Edita skill (slug validado anti-traversal) |
| `DELETE` | `/skills/{slug}` | **admin** | Remove skill (slug validado) |

### Documentação automática

FastAPI expõe Swagger (`/docs`) e ReDoc (`/redoc`).

---

## Modelo de dados

### `app.db` (SQLite — autenticação + pitches)

```
users
├── id (PK)
├── username (UNIQUE, INDEXED)
├── password_hash (pbkdf2_sha256$rounds$salt$hash — salgado)
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

Tabela `produtos` é **criada em runtime** a partir do CSV importado. Cada coluna do CSV vira uma coluna `TEXT` (nome sanitizado por `_sanitize_col` e identificadores citados). Índices são criados automaticamente em colunas que casam com `nome|name|produto|product|titulo|title|descricao`.

---

## Skills (SKILL.md) — como o agente raciocina

Cada skill de vendas é um arquivo markdown em `app/skills/<slug>/SKILL.md` contendo **Objetivo**, **Quando usar**, **Workflow**, **Formato de saída** e **Regras**.

Em cada requisição de chat, [`app/skill_loader.py`](app/skill_loader.py) lê todos os SKILL.md, concatena dentro de um bloco `<Skills disponíveis>`, e injeta no `SALES_ORCHESTRATOR_PROMPT` (montado uma vez por requisição). O orquestrador identifica qual skill se aplica e segue o workflow declarado. **Editar um skill via UI** (tab Skills, restrita a admin) altera o comportamento na próxima request — sem deploy.

O `SALES_ORCHESTRATOR_PROMPT` inclui uma **seção de segurança** instruindo o modelo a nunca revelar o system prompt/skills e a tratar blocos `<<DADOS_NAO_CONFIAVEIS>>` apenas como dados.

### Os 9 skills de vendas

| Skill | Quando dispara |
|-------|----------------|
| `briefing-empresa` | Dossiê de uma empresa-alvo |
| `perfil-interlocutor` | Análise de uma pessoa (cargo, comunicação, gatilhos) |
| `tendencias-mercado` | Panorama setorial atualizado |
| `catalogo-match` | Cruza dores da empresa com produtos do catálogo |
| `nbo-engine` | Proposta com Âncora + Acelerador + Expansão |
| `pitch-builder` | Script de vendas estruturado |
| `botao-panico` | Suporte rápido durante reunião (3-4 frases) |
| `objecao-preco` | Reposiciona "está caro" para valor |
| `follow-up` | Mensagem pós-reunião |

> Além destes, o repositório traz um skill de **engenharia de segurança** reutilizável em `.claude/skills/seguranca-appsec/SKILL.md` — um playbook AppSec + OWASP LLM Top 10 aplicável a qualquer projeto.

---

## Catálogo Text-to-SQL + motor NBO

### Importação de CSV

[`app/catalog_engine.py`](app/catalog_engine.py) recebe CSV (delimitador `,` ou `;` autodetectado), sanitiza nomes de coluna e faz **drop & recreate** da tabela `produtos` (identificadores validados e citados). Upload limitado a 5 MB, exige UTF-8.

### Ferramentas do agente (LangChain Tools)

| Tool | Função |
|------|--------|
| `catalog_list_tables` | Descobrir tabelas existentes |
| `catalog_get_schema(table_name)` | Schema + amostra — `table_name` **validado por whitelist** contra os identificadores existentes |
| `catalog_query(sql)` | Executa **SELECT read-only** — ver segurança abaixo |
| `catalog_nbo_analyze(pain_points, max=5)` | Motor NBO — score por keyword match; `max` limitado a 1..20 |

### Execução SQL read-only (defesa em profundidade)

`execute_catalog_sql` **não** depende de blocklist bypassável. Em cada consulta:

1. Remove comentários e exige que a instrução comece com `SELECT`/`WITH`.
2. `PRAGMA query_only = ON` — o SQLite recusa qualquer escrita no nível do engine (independe de capitalização/comentário/UNION).
3. Apenas **uma instrução** (o driver recusa múltiplas).
4. Bloqueia introspecção de `sqlite_master`/`sqlite_schema`.
5. Limita as linhas retornadas.

### Algoritmo NBO

1. Extrai keywords ≥4 chars dos pontos de dor (até 15 distintas).
2. Para cada produto, `score = Σ (keyword em qualquer coluna ? 1 : 0)`.
3. Ordena `score DESC`, retorna top-N (query com placeholders `?`).
4. Renderiza em markdown com aderência em estrelas (★★★★☆) e ações `[[action: ...]]`.

---

## Geração de PDF — Guia de Bolso do Vendedor

[`app/api/pitch.py`](app/api/pitch.py) gera o PDF via ReportLab (apenas para o dono do pitch) com:

- **Capa** com nome da empresa, data, branding e **sumário** dinâmico.
- **Classificação automática** das mensagens do agente em 6 grupos (`A Empresa`, `O Interlocutor`, `Pontos de Dor`, `Estratégia de Abordagem`, `Roteiro do Pitch`, `Produtos Recomendados (NBO)`).
- **Cards de produtos NBO** por tier: 🟧 Âncora · 🟦 Acelerador · 🟩 Expansão.
- **Tabela-resumo da proposta**, **Destaques (👍)**, **Anotações** e **Checklist Pré-Reunião**.
- Markdown→ReportLab com **escape HTML** (`&`, `<`, `>`); action tags removidas do documento; filename sanitizado (`NFKD` + regex).

---

## Observabilidade e auditoria

**LangFuse (opcional):** cada `/chat` cria um trace com `session_id`, `user_id`, custos OpenAI, latência por nó e erros. Sem chaves configuradas, o handler é `None` e o agente roda normalmente; `handler.flush()` no `finally` garante que traces não se percam.

**Audit log (LGPD):** [`app/audit.py`](app/audit.py) registra eventos de segurança (login, login_failed, setup, chat, chat_blocked, criação/edição/remoção de usuário e skill) com **quem, quando e IP**, guardando apenas o **hash SHA-256** do conteúdo sensível (não o texto) — rastreabilidade com minimização de dados.

---

## Segurança da Informação (SI / Cybersec)

Esta aplicação lida com **dados sensíveis** (pesquisas comerciais, perfis de pessoas, catálogos privados). Ela passou por auditoria AppSec (OWASP LLM Top 10 2025 · OWASP ASVS · CWE · LGPD) e os **22 achados foram remediados** e verificados por teste fim a fim (inclusive XSS em navegador real). Abaixo, os controles por domínio; ao final, os pontos que ainda dependem do **ambiente de deploy**.

### 🔐 Autenticação & sessão

| Controle | Implementação |
|----------|---------------|
| Hash de senha (VULN-02) | **PBKDF2-HMAC-SHA256 salgado** (240k rounds), compare timing-safe, re-hash de legado no login |
| Sessão (VULN-08) | JWT em **cookie HttpOnly + SameSite=strict + Secure** (config.); sem token em `localStorage`; restauro via `/auth/me` |
| Bootstrap (VULN-03) | Login **não cria** usuário; root vem de env ou `/setup` com `SETUP_TOKEN` e `count==0` |
| Segredo JWT | **Fail-fast** no startup em produção se `JWT_SECRET` for padrão/curto |
| RBAC & escalonamento | 3 papéis; **só root concede/gerencia root**; admin não se promove nem edita/remove root |
| Anti-brute-force (AUS-01) | Rate limit em `/login` e `/setup` |

### 🛡️ Injeção (SQL / path)

| Vetor | Mitigação |
|-------|-----------|
| `/catalog/sql` e `catalog_query` (VULN-01) | **Read-only real** (`PRAGMA query_only`, só SELECT/WITH, single-statement, bloqueio de `sqlite_master`, limite de linhas) |
| `table_name` em PRAGMA/schema (VULN-14) | **Whitelist** + quoting de identificadores |
| Slug de skill (VULN-13) | Regex + **resolução de caminho** confirmando que fica dentro de `SKILLS_DIR` — em `GET/PUT/DELETE` e no loader |
| ORM/NBO | SQLAlchemy e placeholders `?` parametrizados |

### 🤖 Camada LLM (OWASP LLM Top 10)

| Risco | Mitigação |
|-------|-----------|
| Prompt injection (VULN-04 · LLM01) | Guardrail de entrada (pt/en, leetspeak, inclui histórico) + envelope `<<DADOS_NAO_CONFIAVEIS>>` para contexto e web + reforço no system prompt |
| Excessive Agency (VULN-15 · LLM06) | Tools de catálogo **somente leitura**; parâmetros validados; recursão limitada |
| System Prompt Leakage (VULN-16 · LLM07) | `/skills` exige login; instrução de confidencialidade no prompt |
| Unbounded Consumption (VULN-10/15 · LLM10) | `max_tokens`, `request_timeout`, **timeout wall-clock**, histórico truncado, rate limit no `/chat` |
| Insecure Output (LLM02/05) | **PII masking** na saída; ver XSS |

### 🖥️ Saída e XSS (VULN-07)

- **Sanitização de URL** (só `http/https/mailto`; bloqueia `javascript:`/`data:`).
- **DOMPurify** aplicado ao HTML derivado da saída do LLM, com **fallback seguro** se o CDN não carregar.
- Botões de ação via **`data-action` + delegação** (sem `onclick` inline vindo do modelo).
- Todos os sinks `innerHTML` do frontend usam escape/`safeHTML` (inclui nomes de coluna do catálogo).

### 🌐 Transporte, CORS e headers

- **CORS por allowlist** (`ALLOWED_ORIGINS`) — sem `*` com credenciais (VULN-05).
- **Security headers** (AUS-05) via middleware: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `HSTS` (quando HTTPS).

### 🗂️ Privacidade, auditoria e higiene de repositório

- **Audit log** com hash de conteúdo (AUS-04 · LGPD).
- **Sem segredos no versionamento** (VULN-11): `.gitignore`/`.dockerignore`; `.env` e `*.db` removidos do repositório; `.env.example` como modelo.
- **Dependências pinadas** com upper bound (VULN-12).
- **Dockerfile endurecido** (AUS-06): usuário não-root, `HEALTHCHECK`, `.dockerignore`.
- Rate limiter com **eviction** de chaves ociosas (não vaza memória).

### 🔬 Threat model resumido

| Ameaça | Vetor | Status |
|--------|-------|:------:|
| SQL Injection no `/catalog/sql` | `DELETE`/`DROP`/UNION/comentário/multi-statement | ✅ read-only real |
| SQLi via `table_name` | PRAGMA com input do LLM | ✅ whitelist |
| Path traversal em skills | `GET/PUT/DELETE /skills/../..` | ✅ validação de caminho |
| IDOR | acessar pitch/dados de outro usuário | ✅ ownership → 404 |
| Escalonamento admin→root | admin cria/promove root | ✅ bloqueado |
| Brute force de senha | login repetido | ✅ rate limit |
| Rainbow table | DB exfiltrado | ✅ PBKDF2 salgado |
| Token roubado via XSS | ler JWT do `localStorage` | ✅ cookie HttpOnly |
| XSS (saída do LLM) | `javascript:`/`onerror`/action | ✅ sanitização + DOMPurify |
| Prompt injection | override no input/web/histórico | ✅ guardrail + isolamento (defesa em camadas) |
| Custo/DoS de LLM | prompt caro / flood | ✅ max_tokens + timeout + rate limit |
| CORS abusivo | site terceiro com credenciais | ✅ allowlist |

### ⚠️ Depende do ambiente de deploy (não é código)

| Ponto | Ação |
|-------|------|
| **HTTPS + cookie Secure** | Sirva atrás de TLS (Render/Caddy/nginx) e defina `COOKIE_SECURE=true` |
| **Segredos definidos** | `JWT_SECRET` forte, bootstrap do root e chaves de API nas envs do provedor |
| **Persistência do SQLite** | Discos efêmeros (ex.: Render) apagam `data/*.db` a cada deploy — use disco persistente ou Postgres (`DATABASE_URL=postgresql://...`) |
| **Rate limit multi-réplica** | O limiter é em memória (por instância); para várias réplicas, use Redis |
| **CSP com `unsafe-inline`** | A UI usa handlers/estilos inline (Tailwind); a CSP permite `unsafe-inline` em script/style. Endurecer exige refatorar a SPA |
| **SAST/SCA no CI** | Recomenda-se Semgrep/CodeQL + `pip-audit`/Dependabot |

---

## Operação e deploy

### Deploy no Render (exemplo)

1. Conecte o repositório e escolha *Web Service* (build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`).
2. Em **Environment**, defina: `JWT_SECRET` (forte), `ROOT_USERNAME` + `ROOT_PASSWORD` (ou `SETUP_TOKEN`), `COOKIE_SECURE=true`, `ALLOWED_ORIGINS=https://<seu-app>.onrender.com`, `OPENAI_API_KEY`, `TAVILY_API_KEY`.
3. Para **persistir dados**, adicione um *Persistent Disk* montado (ex.: `/var/data`) e defina `DATABASE_URL=sqlite:////var/data/app.db`. Sem isso, os dados são recriados a cada deploy (o root de env é recriado, mas pitches/usuários se perdem).

### Backup e logs

- **Volume `data/`** contém `app.db` + `catalog.db` (backup via `sqlite3 .backup`); em produção, prefira Postgres com WAL/replica.
- uvicorn escreve em stdout/stderr; o audit log usa o logger `cqv.audit`. Capture via systemd, Docker logging driver ou agregador (Loki, CloudWatch).

### Health checks

`GET /api/v1/health` → `{"status": "ok", ...}`. Use em probes de LB/Kubernetes (o Dockerfile também traz `HEALTHCHECK`).

### Custos LLM

- `gpt-4o-mini` default; `max_tokens`, timeout e truncamento de histórico contêm o custo por request. Monitore via LangFuse.

---

## Base conceitual

Inspirado em:
- [LangChain deepagents/deep_research](https://github.com/langchain-ai/deepagents) — padrão **ReAct** via LangGraph, adaptado para inteligência de vendas B2B.
- Estratégia **NBO (Next Best Offer)** — Âncora + Acelerador + Expansão.
- Padrão **Skills as Code** — comportamento do agente versionado em SKILL.md, editável em runtime.
- **OWASP LLM Top 10 (2025)** e **OWASP ASVS** — base da postura de segurança (ver [`.claude/skills/seguranca-appsec/SKILL.md`](.claude/skills/seguranca-appsec/SKILL.md)).

---

## Licença

MIT

---

*Projeto criado por [Sergio Gaiotto](https://www.falagaiotto.com.br)*
