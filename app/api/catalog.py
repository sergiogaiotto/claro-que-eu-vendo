"""Módulo Catálogo v2 — Text-to-SQL com SQLite + motor NBO."""

from io import BytesIO

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.catalog_engine import (
    clear_catalog,
    execute_catalog_sql,
    export_catalog_csv,
    get_catalog_schema,
    import_csv_to_catalog,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


class SqlQuery(BaseModel):
    sql: str = Field(..., min_length=1)


class NlQuery(BaseModel):
    question: str = Field(..., min_length=1)


# ============================================================
# Endpoints
# ============================================================

@router.get("/schema")
def schema():
    """Retorna schema do catálogo com amostra de dados."""
    info = get_catalog_schema()
    return info


@router.get("/products")
def list_products(limit: int = Query(default=50, le=500), offset: int = Query(default=0)):
    """Lista produtos com paginação."""
    try:
        rows = execute_catalog_sql(f"SELECT * FROM produtos LIMIT {limit} OFFSET {offset}")
        count_result = execute_catalog_sql("SELECT COUNT(*) as total FROM produtos")
        total = count_result[0]["total"] if count_result else 0
        return {"products": rows, "total": total, "limit": limit, "offset": offset}
    except Exception:
        return {"products": [], "total": 0, "limit": limit, "offset": offset}


@router.post("/sql")
def run_sql(req: SqlQuery):
    """Executa query SQL SELECT no catálogo."""
    try:
        results = execute_catalog_sql(req.sql)
        return {"results": results, "count": len(results)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Erro SQL: {e}")


@router.post("/import")
async def import_csv(file: UploadFile = File(...)):
    """Importa CSV — colunas viram campos da tabela SQLite."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Arquivo deve ser .csv")

    content = await file.read()
    text = content.decode("utf-8-sig")
    result = import_csv_to_catalog(text)

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.get("/export")
def export_csv():
    """Exporta catálogo como CSV."""
    csv_content = export_catalog_csv()
    if not csv_content:
        raise HTTPException(404, "Catálogo vazio")

    output = BytesIO(csv_content.encode("utf-8-sig"))
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="catalogo.csv"'},
    )


@router.delete("/")
def clear():
    """Limpa o catálogo (drop table)."""
    clear_catalog()
    return {"deleted": True}
