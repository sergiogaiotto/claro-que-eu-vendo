# Catálogo Match + NBO

## Objetivo
Consultar o catálogo de produtos via SQL, cruzar com as necessidades da empresa-alvo, e aplicar Next Best Offer (NBO) para recomendar a combinação ideal de produtos/serviços.

## Quando usar
- Vendedor pede "qual produto oferecer", "o que combina com esta empresa", "recomendação de produto"
- Vendedor clica em "Ver produtos do catálogo que combinam"
- Após já ter identificado dores da empresa
- Quando existem produtos cadastrados no catálogo (tabela SQLite)

## Ferramentas disponíveis

1. **catalog_list_tables**: Lista tabelas disponíveis no catálogo
2. **catalog_get_schema**: Retorna colunas, tipos e amostra de dados
3. **catalog_query**: Executa queries SELECT no catálogo (Text-to-SQL)
4. **catalog_nbo_analyze**: Motor NBO automático — cruza dores com produtos por relevância

## Workflow

### Fase 1: Diagnóstico do catálogo
1. Use `catalog_list_tables` para verificar se existe catálogo
2. Use `catalog_get_schema` para entender colunas disponíveis
3. Se catálogo vazio, avise o vendedor para importar CSV

### Fase 2: Entender a demanda
1. Identifique os pontos de dor da empresa (do briefing ou conversa)
2. Identifique critérios de filtro: porte, setor, orçamento, urgência

### Fase 3: NBO (Next Best Offer)
1. Use `catalog_nbo_analyze` passando as dores como texto
2. O motor NBO faz scoring por relevância textual
3. Analise o ranking retornado

### Fase 4: Refinamento via SQL
1. Se o NBO não for preciso o suficiente, use `catalog_query` com queries específicas:
   - Filtrar por faixa de preço: `SELECT * FROM produtos WHERE CAST(preco AS REAL) BETWEEN X AND Y`
   - Buscar por categoria: `SELECT * FROM produtos WHERE LOWER(categoria) LIKE '%software%'`
   - Ordenar por relevância: `ORDER BY algum_campo DESC`
2. Combine múltiplas queries se necessário

### Fase 5: Montar a proposta NBO
Para cada produto recomendado, construir:
- **Por que este produto**: conexão direta com a dor
- **Argumento de venda**: frase pronta para a reunião
- **Combinação sugerida**: pacote com complementos
- **Valor estimado de ROI**: quanto o cliente pode ganhar/economizar

## Formato de saída

```
## Proposta NBO — [EMPRESA]

### Produto Principal
**[Nome]** — Aderência: ★★★★★
- Resolve: [dor principal]
- Argumento: "Com [produto], vocês podem [benefício] em [prazo]."
- Preço: [se disponível no catálogo]

### Complementos Sugeridos
1. **[Produto B]** — potencializa o resultado principal
2. **[Produto C]** — cobre uma necessidade secundária

### Pacote Recomendado
| Produto | Função | Preço |
|---------|--------|-------|
| Produto A | Resolve dor 1 | R$ X |
| Produto B | Complementa A | R$ Y |
| **Total** | | **R$ Z** |

### Produtos NÃO recomendados agora
- [Produto X]: motivo (pode ser oferecido em fase 2)

### Próximo passo
[[action: Montar pitch com esta proposta]] [[action: Ajustar pacote]] [[action: Ver mais opções]]
```

## Técnicas NBO aplicadas

### 1. Propensity Scoring
Cada produto recebe score baseado em quantas palavras-chave das dores aparecem em seus campos.

### 2. Cross-sell / Up-sell
Após identificar o produto principal, buscar complementos:
- Cross-sell: produto de categoria diferente que combina
- Up-sell: versão premium do produto recomendado

### 3. Bundle Optimization
Montar pacote que maximiza valor percebido:
- Produto principal (resolve a dor #1)
- Complemento (resolve dor #2 ou potencializa #1)
- Serviço agregado (implementação, treinamento, suporte)

### 4. Timing-based Offer
Considerar urgência do cliente:
- Alta urgência: propor pacote express com desconto
- Média: propor implementação faseada
- Baixa: propor POC/piloto

## Regras
- Se catálogo vazio, NÃO inventar produtos. Avisar para importar.
- Sempre justificar recomendações com dados do catálogo.
- Máximo 5 produtos na recomendação principal.
- Incluir produtos NÃO recomendados quando relevante.
- Se preço disponível no catálogo, sempre incluir na proposta.
- Sugerir pacotes, não produtos isolados.
