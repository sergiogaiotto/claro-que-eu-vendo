# Briefing de Empresa

## Objetivo
Construir um dossiê completo sobre uma empresa-alvo para preparar o vendedor antes de uma reunião comercial.

## Quando usar
- Vendedor informa nome de empresa e pede "briefing", "pesquisar empresa", "preparar reunião"
- Qualquer pedido que envolva entender uma empresa antes de abordar

## Workflow

### Passo 0 — Desambiguação (OBRIGATÓRIO)
Antes de montar o briefing, verificar se o nome/CNPJ da empresa retorna um resultado único.
Se encontrar **mais de uma empresa possível** (homônimas, filiais, grupo empresarial), PARAR e listar:

```
Encontrei X resultados para "[EMPRESA]" em [CIDADE]. Qual é a correta?

1. **Razão Social** — Setor, Porte (Cidade/UF)
   Site: [link]
   [[action: Selecionar Razão Social — Setor]]

2. **Razão Social** — Setor, Porte (Cidade/UF)
   Site: [link]
   [[action: Selecionar Razão Social — Setor]]

[[action: Nenhuma — refinar a busca]]
```

SÓ prosseguir após confirmação do vendedor.

### Passo 1 — Dados básicos
Nome oficial, CNPJ (se disponível), setor, porte, localização, site

### Passo 2 — Presença digital
Site, redes sociais, nota no Reclame Aqui, avaliações Google

### Passo 3 — Contatos-chave encontrados
Ao pesquisar a empresa, identificar pessoas relevantes (diretoria, C-level, gestores).
Se encontrar **múltiplos contatos**, listar TODOS com cargo e fonte:

```
### Contatos identificados na empresa
Encontrei os seguintes contatos. Deseja analisar o perfil de algum deles?

1. **Nome** — Cargo
   [[action: Analisar perfil de Nome — Cargo]]

2. **Nome** — Cargo
   [[action: Analisar perfil de Nome — Cargo]]
```

### Passo 4 — Notícias recentes
Últimos 6 meses — expansão, contratações, problemas, lançamentos

### Passo 5 — Concorrentes diretos
2-3 concorrentes principais e como se posicionam

### Passo 6 — Pontos de dor inferidos
Com base no setor + porte + notícias, quais problemas provavelmente enfrentam

## Formato de saída

```
## Perfil da Empresa — [NOME]

**Setor:** ...
**Porte:** ...
**Localização:** ...
**Site:** ...

### Sobre
Parágrafo com visão geral da empresa.

### Notícias Recentes
- [data] título e contexto
- [data] título e contexto

### Concorrentes
- Concorrente A — diferencial
- Concorrente B — diferencial

### Pontos de Dor Identificados
1. Ponto de dor + evidência
2. Ponto de dor + evidência

### Fontes
[1] URL
[2] URL
```

## Regras
- Nunca inventar dados. Se não encontrar, dizer explicitamente.
- Priorizar fontes primárias (site da empresa, LinkedIn, releases oficiais).
- Notícias devem ter data. Não usar informações desatualizadas (>12 meses) sem avisar.
- Pontos de dor devem ser baseados em evidências, não genéricos.
