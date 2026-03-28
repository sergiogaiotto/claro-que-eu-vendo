"""Catalog SQL Engine — motor Text-to-SQL para o catálogo de produtos.

Cria tabelas SQLite dinamicamente a partir de CSVs importados,
fornece ferramentas de consulta em linguagem natural e motor NBO.
"""

import csv
import os
import re
import sqlite3
from io import StringIO
from typing import Any

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.config import get_settings

CATALOG_DB_PATH = os.path.join("data", "catalog.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(CATALOG_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CATALOG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _sanitize_col(name: str) -> str:
    """Transforma nome de coluna CSV em nome SQL seguro."""
    clean = re.sub(r"[^\w]", "_", name.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean or clean[0].isdigit():
        clean = "col_" + clean
    return clean


# ============================================================
# Import / Export / Schema
# ============================================================

def import_csv_to_catalog(content: str, table_name: str = "produtos") -> dict:
    """Importa CSV para tabela SQLite. Colunas criadas automaticamente."""
    reader = csv.DictReader(StringIO(content), delimiter=",")
    if not reader.fieldnames:
        reader = csv.DictReader(StringIO(content), delimiter=";")
    if not reader.fieldnames:
        return {"error": "CSV sem cabeçalhos detectados", "imported": 0}

    original_fields = [f.strip() for f in reader.fieldnames if f.strip()]
    sql_fields = [_sanitize_col(f) for f in original_fields]
    field_map = dict(zip(original_fields, sql_fields))

    conn = _get_conn()
    cur = conn.cursor()

    # Drop e recria a tabela (fresh import)
    cur.execute(f"DROP TABLE IF EXISTS {table_name}")
    cols_def = ", ".join(f'"{c}" TEXT' for c in sql_fields)
    cur.execute(f'CREATE TABLE {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols_def})')

    # Insere dados
    placeholders = ", ".join(["?"] * len(sql_fields))
    cols_insert = ", ".join(f'"{c}"' for c in sql_fields)
    count = 0
    for row in reader:
        values = [row.get(orig, "").strip() for orig in original_fields]
        cur.execute(f"INSERT INTO {table_name} ({cols_insert}) VALUES ({placeholders})", values)
        count += 1

    conn.commit()

    # Cria índice nos campos que parecem nome/produto
    for col in sql_fields:
        if any(kw in col for kw in ["nome", "name", "produto", "product", "titulo", "title", "descricao"]):
            try:
                cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_{col} ON {table_name}("{col}")')
            except Exception:
                pass

    conn.commit()
    conn.close()

    return {
        "imported": count,
        "table": table_name,
        "columns": sql_fields,
        "column_mapping": field_map,
    }


def export_catalog_csv(table_name: str = "produtos") -> str:
    """Exporta tabela do catálogo como CSV."""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        if not rows:
            return ""
        cols = [desc[0] for desc in cur.description if desc[0] != "id"]
        buf = StringIO()
        writer = csv.DictWriter(buf, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row[c] for c in cols})
        return buf.getvalue()
    except Exception:
        return ""
    finally:
        conn.close()


def get_catalog_schema(table_name: str = "produtos") -> dict:
    """Retorna schema da tabela do catálogo."""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]

        # Amostra de 3 registros
        cur.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample_rows = [dict(r) for r in cur.fetchall()]

        return {"table": table_name, "columns": columns, "row_count": count, "sample": sample_rows}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


def execute_catalog_sql(query: str) -> list[dict]:
    """Executa query SQL read-only no catálogo."""
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    upper = query.upper().strip()
    for kw in forbidden:
        if kw in upper and kw != "CREATE":  # permite CREATE INDEX internamente
            raise ValueError(f"Operação {kw} não permitida. Apenas SELECT.")

    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(query)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def clear_catalog(table_name: str = "produtos"):
    conn = _get_conn()
    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.commit()
    conn.close()


# ============================================================
# LangChain Tools para o Agente
# ============================================================

@tool
def catalog_list_tables() -> str:
    """Lista todas as tabelas disponíveis no catálogo de produtos.

    Use para descobrir quais tabelas existem no banco de dados do catálogo.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    if not tables:
        return "Catálogo vazio. Nenhuma tabela encontrada. O vendedor precisa importar um CSV na aba Catálogo."
    return f"Tabelas disponíveis: {', '.join(tables)}"


@tool
def catalog_get_schema(table_name: str = "produtos") -> str:
    """Retorna o schema completo de uma tabela do catálogo com exemplos de dados.

    Use para entender as colunas disponíveis antes de montar queries.

    Args:
        table_name: Nome da tabela (padrão: produtos)
    """
    info = get_catalog_schema(table_name)
    if "error" in info:
        return f"Erro: {info['error']}"

    cols = "\n".join(f"  - {c['name']} ({c['type']})" for c in info["columns"])
    sample = ""
    if info["sample"]:
        sample = "\n\nAmostra de dados:\n"
        for row in info["sample"]:
            sample += "  " + " | ".join(f"{k}={v}" for k, v in row.items() if k != "id") + "\n"

    return f"""Tabela: {info['table']}
Registros: {info['row_count']}

Colunas:
{cols}
{sample}"""


@tool
def catalog_query(sql: str) -> str:
    """Executa uma query SQL SELECT no catálogo de produtos e retorna os resultados.

    APENAS queries SELECT são permitidas. Use para buscar, filtrar,
    agregar e analisar produtos do catálogo.

    Args:
        sql: Query SQL SELECT a executar.
    """
    try:
        results = execute_catalog_sql(sql)
        if not results:
            return "Nenhum resultado encontrado."
        header = " | ".join(results[0].keys())
        rows = "\n".join(" | ".join(str(v) for v in r.values()) for r in results[:20])
        total_note = f"\n\n({len(results)} resultado(s) total)" if len(results) > 20 else f"\n\n({len(results)} resultado(s))"
        return f"{header}\n{'─' * len(header)}\n{rows}{total_note}"
    except Exception as e:
        return f"Erro na query: {e}"


@tool
def catalog_nbo_analyze(company_pain_points: str, max_recommendations: int = 5) -> str:
    """Motor NBO (Next Best Offer) — analisa dores da empresa e recomenda produtos do catálogo.

    Cruza os pontos de dor identificados com os produtos disponíveis no catálogo
    usando busca semântica por similaridade textual no SQLite.

    Args:
        company_pain_points: Descrição dos pontos de dor/necessidades da empresa-alvo.
        max_recommendations: Número máximo de recomendações (padrão: 5).
    """
    info = get_catalog_schema("produtos")
    if "error" in info or info.get("row_count", 0) == 0:
        return "Catálogo vazio. Importe produtos na aba Catálogo antes de usar o NBO."

    # Identifica colunas de texto que podem conter descrições de produto
    text_cols = []
    for col in info["columns"]:
        if col["name"] != "id":
            text_cols.append(col["name"])

    # Monta query LIKE com palavras-chave das dores
    keywords = re.findall(r'\b\w{4,}\b', company_pain_points.lower())
    keywords = list(set(keywords))[:15]

    if not keywords or not text_cols:
        # Fallback: retorna todos os produtos
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM produtos LIMIT {max_recommendations}")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        if not rows:
            return "Nenhum produto encontrado."
        result = "Produtos disponíveis (sem filtro de relevância):\n\n"
        for i, r in enumerate(rows, 1):
            result += f"{i}. " + " | ".join(f"{k}={v}" for k, v in r.items() if k != "id") + "\n"
        return result

    # Scoring: cada produto recebe pontos por matches de keyword
    like_clauses = []
    for kw in keywords:
        col_likes = " OR ".join(f'LOWER("{c}") LIKE ?' for c in text_cols)
        like_clauses.append(f"({col_likes})")

    # Monta a query com score de relevância
    score_parts = []
    all_params = []
    for kw in keywords:
        col_cases = " + ".join(
            f'(CASE WHEN LOWER("{c}") LIKE ? THEN 1 ELSE 0 END)' for c in text_cols
        )
        score_parts.append(f"({col_cases})")
        for _ in text_cols:
            all_params.append(f"%{kw}%")

    score_expr = " + ".join(score_parts)
    cols_select = ", ".join(f'"{c}"' for c in text_cols)

    query = f"""
        SELECT {cols_select}, ({score_expr}) as nbo_score
        FROM produtos
        WHERE ({score_expr}) > 0
        ORDER BY nbo_score DESC
        LIMIT {max_recommendations}
    """
    # Params duplicados (uma vez para WHERE, uma vez para SELECT)
    full_params = all_params + all_params

    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(query, full_params)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        conn.close()
        return f"Erro no NBO: {e}. Tente reformular os pontos de dor."
    conn.close()

    if not rows:
        return "Nenhum produto do catálogo apresentou correspondência com os pontos de dor informados."

    # Formata resultado NBO
    result = f"## Recomendação NBO — {len(rows)} produto(s) com maior aderência\n\n"
    result += f"Palavras-chave usadas: {', '.join(keywords[:10])}\n\n"

    for i, r in enumerate(rows, 1):
        score = r.pop("nbo_score", 0)
        stars = "★" * min(int(score), 5) + "☆" * max(0, 5 - int(score))
        result += f"### Recomendação #{i} — Aderência: {stars} ({score} pontos)\n"
        for k, v in r.items():
            if v:
                result += f"- **{k}:** {v}\n"
        result += "\n"

    result += "---\n"
    result += "Próximos passos: [[action: Montar pitch com estes produtos]] "
    result += "[[action: Refinar busca com mais detalhes]] "
    result += "[[action: Ver todos os produtos do catálogo]]"

    return result


CATALOG_TOOLS = [catalog_list_tables, catalog_get_schema, catalog_query, catalog_nbo_analyze]
