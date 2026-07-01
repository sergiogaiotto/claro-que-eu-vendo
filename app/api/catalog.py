"""Módulo Catálogo v2 — Text-to-SQL com SQLite + motor NBO."""

from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.auth import get_current_user, require_admin
from app.catalog_engine import (
    _get_conn,
    clear_catalog,
    execute_catalog_sql,
    export_catalog_csv,
    get_catalog_schema,
    import_csv_to_catalog,
)
from app.database import User
from app.ratelimit import rate_limiter

router = APIRouter(prefix="/catalog", tags=["catalog"])

# Tamanho máximo de upload de CSV (5 MB) — evita esgotamento de memória.
_MAX_CSV_BYTES = 5 * 1024 * 1024


class SqlQuery(BaseModel):
    sql: str = Field(..., min_length=1)


class NlQuery(BaseModel):
    question: str = Field(..., min_length=1)


# ============================================================
# Endpoints
# ============================================================

@router.get("/schema")
def schema(_user: User = Depends(get_current_user)):
    """Retorna schema do catálogo com amostra de dados."""
    info = get_catalog_schema()
    return info


@router.get("/products")
def list_products(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(get_current_user),
):
    """Lista produtos com paginação (parâmetros parametrizados)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM produtos LIMIT ? OFFSET ?", (limit, offset))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as total FROM produtos")
        total = cur.fetchone()["total"]
        return {"products": rows, "total": total, "limit": limit, "offset": offset}
    except Exception:
        return {"products": [], "total": 0, "limit": limit, "offset": offset}
    finally:
        conn.close()


@router.post("/sql")
def run_sql(
    req: SqlQuery,
    _user: User = Depends(get_current_user),
    _rl=Depends(rate_limiter("catalog_sql", 60, 60)),
):
    """Executa query SQL SELECT (somente leitura) no catálogo."""
    try:
        results = execute_catalog_sql(req.sql)
        return {"results": results, "count": len(results)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Erro SQL: {e}")


@router.post("/import")
async def import_csv(
    file: UploadFile = File(...),
    _admin: User = Depends(require_admin),
):
    """Importa CSV — colunas viram campos da tabela SQLite (requer admin)."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Arquivo deve ser .csv")

    content = await file.read()
    if len(content) > _MAX_CSV_BYTES:
        raise HTTPException(413, "Arquivo excede o limite de 5 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV deve estar em UTF-8")
    result = import_csv_to_catalog(text)

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.get("/export")
def export_csv(_user: User = Depends(get_current_user)):
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
def clear(_admin: User = Depends(require_admin)):
    """Limpa o catálogo (drop table) — requer admin."""
    clear_catalog()
    return {"deleted": True}
