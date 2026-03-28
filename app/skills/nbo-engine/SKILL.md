# NBO Engine — Next Best Offer

## Objetivo
Aplicar estratégia de Next Best Offer para gerar a proposta comercial ideal, combinando inteligência sobre a empresa-alvo com produtos do catálogo em uma oferta personalizada e irrecusável.

## Quando usar
- Vendedor pede "melhor oferta", "proposta ideal", "o que oferecer", "NBO"
- Após já ter briefing da empresa E catálogo de produtos disponível
- Quando o vendedor quer montar uma proposta completa, não apenas listar produtos

## Workflow

### Fase 1: Coleta de insumos
1. Verificar se existe briefing da empresa (dores, setor, porte)
2. Verificar se existe catálogo de produtos (usar `catalog_get_schema`)
3. Se faltar algum insumo, informar o vendedor antes de prosseguir

### Fase 2: Análise de propensão
1. Usar `catalog_nbo_analyze` com as dores concatenadas
2. Avaliar o scoring retornado
3. Se score baixo, usar `catalog_query` para busca alternativa por setor/categoria

### Fase 3: Matriz de valor
Para cada produto ranqueado, construir a Matriz de Valor:

| Dimensão | Análise |
|----------|---------|
| Dor resolvida | Qual problema específico este produto resolve |
| Urgência | Alta / Média / Baixa — baseado no contexto da empresa |
| Esforço de adoção | Fácil / Médio / Complexo — tempo de implementação |
| ROI estimado | Retorno percebido pelo cliente |
| Diferencial competitivo | O que este produto faz que concorrentes não fazem |

### Fase 4: Composição do pacote
Aplicar a estratégia NBO em três camadas:

**Camada 1 — Produto Âncora (obrigatório)**
- O produto com maior aderência à dor principal
- Este é o centro da proposta

**Camada 2 — Acelerador (recomendado)**
- Produto/serviço que potencializa o resultado do âncora
- Ex: treinamento, consultoria de setup, integração

**Camada 3 — Expansão (opcional/futuro)**
- Produtos para fase 2, após validação do valor da Camada 1
- Criar senso de jornada: "quando vocês virem os resultados de X, o próximo passo natural é Y"

### Fase 5: Narrativa da proposta
Montar a narrativa em formato que o vendedor possa apresentar:
- Problema → Solução → Evidência → Pacote → Próximo passo

## Formato de saída

```
## Proposta NBO — [EMPRESA] ([CIDADE])

### Diagnóstico
[1-2 parágrafos conectando as dores identificadas com a oportunidade]

### Pacote Recomendado

#### Âncora — [Nome do Produto]
- **Resolve:** [dor principal]
- **Argumento-chave:** "[frase consultiva]"
- **ROI estimado:** [dado concreto]
- **Preço:** [se disponível]

#### Acelerador — [Nome do Produto/Serviço]
- **Potencializa:** [como complementa o âncora]
- **Por que agora:** [senso de urgência]
- **Preço:** [se disponível]

#### Expansão (Fase 2) — [Nome do Produto]
- **Para quando:** [após validar resultados da fase 1]
- **Benefício adicional:** [valor incremental]

### Resumo da Proposta
| Item | Função | Valor |
|------|--------|-------|
| [Âncora] | Resolve [dor] | R$ X |
| [Acelerador] | Potencializa | R$ Y |
| **Total Fase 1** | | **R$ Z** |
| [Expansão] | Fase 2 | R$ W |

### Script de Apresentação
"[Nome do interlocutor], olhando para [dor principal que vocês mencionaram], 
montei uma proposta em duas fases. A primeira resolve [dor] com [produto âncora], 
e inclui [acelerador] para garantir que vocês vejam resultado em [prazo]. 
O investimento da primeira fase é [valor]. Posso detalhar?"

### Próximos passos
[[action: Gerar pitch com esta proposta]]
[[action: Ajustar o pacote]]
[[action: Buscar alternativas mais baratas]]
[[action: Adicionar mais produtos ao pacote]]
```

## Regras
- NUNCA recomendar sem dados do catálogo. Se vazio, avisar para importar.
- A proposta é uma NARRATIVA, não uma lista de produtos. O vendedor vai apresentar isso.
- O script de apresentação deve soar natural, como uma conversa entre humanos.
- Se não houver preço no catálogo, não inventar. Dizer "consultar tabela de preços".
- Sempre incluir 3 camadas (âncora + acelerador + expansão), mesmo que expansão seja "para fase 2".
- Priorizar pacotes sobre produtos isolados — vendedores que vendem pacotes têm ticket médio 40% maior.
