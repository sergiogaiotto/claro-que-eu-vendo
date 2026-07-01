"""Rate limiting leve em memória (AUS-01 / LLM10 Unbounded Consumption).

Implementação sem dependências externas — janela deslizante por chave
(IP + rota). Suficiente para uma instância única; para deploy multi-réplica,
trocar por Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)
_ops = 0
_SWEEP_EVERY = 500  # varre chaves ociosas periodicamente (evita leak de memória)


def _sweep(now: float, window: int) -> None:
    """Remove chaves cuja janela expirou por completo (chamada sob _lock)."""
    stale = [k for k, dq in _hits.items() if not dq or dq[-1] < now - window]
    for k in stale:
        del _hits[k]


def _client_ip(request: Request) -> str:
    # Respeita X-Forwarded-For quando atrás de proxy confiável.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check(key: str, limit: int, window: int) -> None:
    global _ops
    now = time.monotonic()
    with _lock:
        _ops += 1
        if _ops % _SWEEP_EVERY == 0:
            _sweep(now, window)
        dq = _hits[key]
        cutoff = now - window
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            retry = int(dq[0] + window - now) + 1
            raise HTTPException(
                status_code=429,
                detail="Muitas requisições. Aguarde alguns segundos.",
                headers={"Retry-After": str(max(retry, 1))},
            )
        dq.append(now)


def rate_limiter(bucket: str, limit: int, window: int):
    """Cria uma dependência FastAPI que aplica rate limit por IP para `bucket`."""

    async def _dep(request: Request) -> None:
        _check(f"{bucket}:{_client_ip(request)}", limit, window)

    return _dep
