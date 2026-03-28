# Perfil do Interlocutor

## Objetivo
Construir perfil detalhado da pessoa com quem o vendedor vai negociar, incluindo estilo de comunicação e estratégia de abordagem.

## Quando usar
- Vendedor menciona nome de pessoa, cargo, ou pede "perfil do interlocutor", "analisar contato"
- Preparação para reunião onde o foco é a pessoa, não a empresa

## Workflow

### Passo 0 — Desambiguação (OBRIGATÓRIO)
Antes de qualquer análise, buscar o nome/cargo/empresa nas fontes disponíveis.
Se encontrar **mais de um perfil possível**, PARAR e listar TODOS para o vendedor escolher:

```
Encontrei X perfis possíveis para [NOME] na empresa [EMPRESA]. Qual é o correto?

1. **Nome Completo** — Cargo (Cidade)
   LinkedIn: [link]
   [[action: Selecionar Nome Completo — Cargo]]

2. **Nome Completo** — Cargo (Cidade)
   LinkedIn: [link]
   [[action: Selecionar Nome Completo — Cargo]]

[[action: Nenhum destes — buscar com outros dados]]
```

SÓ prosseguir para o Passo 1 após confirmação do vendedor.
Se encontrar apenas 1 resultado com alta confiança, confirmar brevemente e seguir.

### Passo 1 — Dados profissionais
Nome, cargo atual, empresa, tempo no cargo

### Passo 2 — Trajetória
Empresas anteriores, formação acadêmica, especializações

### Passo 3 — Presença digital
LinkedIn (publicações, artigos, interesses), Twitter/X, palestras.
Se encontrar perfis em múltiplas redes, listar todos com links.

### Passo 4 — Estilo de comunicação
Inferir se é técnico/executivo, formal/informal, data-driven/relacional

### Passo 5 — Interesses profissionais
Temas que publica, comenta, compartilha

### Passo 6 — Recomendação de abordagem
Como abrir a conversa, tom adequado, o que evitar

## Formato de saída

```
## Perfil — [NOME]

**Cargo:** ...
**Empresa:** ...
**Tempo no cargo:** ...

### Trajetória
Resumo de 2-3 linhas sobre carreira.

### Estilo de Comunicação
- Tipo: [Técnico | Executivo | Híbrido]
- Tom: [Formal | Informal | Adaptável]
- Foco: [Dados/ROI | Relacionamento | Inovação]

### Interesses Profissionais
- Tema A (evidência: publicou sobre X)
- Tema B (evidência: comentou sobre Y)

### Estratégia de Abordagem
- **Abra com:** sugestão de tema para quebra-gelo
- **Argumente com:** tipo de argumento que ressoa com este perfil
- **Evite:** comportamentos que podem afastar
- **Tom recomendado:** descrição do tom ideal

### Fontes
[1] URL
```

## Regras
- Distinguir claramente dados confirmados vs. inferências.
- Marcar inferências com "(inferido)" ou "(provável)".
- Não fazer julgamentos de personalidade — focar em comportamento profissional observável.
- Se não encontrar informações suficientes, sugerir perguntas para o vendedor coletar na própria reunião.
