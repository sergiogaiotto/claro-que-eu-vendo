"""Log de auditoria com mascaramento (AUS-04 / LGPD Art. 46/48).

Registra QUEM fez QUE ação e QUANDO, sem persistir o conteúdo sensível da
mensagem — apenas um hash SHA-256, permitindo rastreabilidade sem violar a
minimização de dados exigida pela LGPD.
"""

from __future__ import annotations

import logging
from hashlib import sha256

_logger = logging.getLogger("cqv.audit")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [AUDIT] %(message)s")
    )
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def _hash(text: str) -> str:
    return sha256((text or "").encode("utf-8")).hexdigest()[:16]


def audit_log(
    action: str,
    user_id: str | int | None = None,
    message: str | None = None,
    ip: str | None = None,
    extra: str | None = None,
) -> None:
    """Registra um evento de auditoria.

    Args:
        action: nome da ação (ex.: "chat", "login", "skill_create").
        user_id: identificador do usuário (não sensível).
        message: conteúdo sensível — apenas o hash é registrado.
        ip: IP de origem.
        extra: metadados adicionais não sensíveis.
    """
    parts = [f"action={action}"]
    if user_id is not None:
        parts.append(f"user={user_id}")
    if ip:
        parts.append(f"ip={ip}")
    if message is not None:
        parts.append(f"msg_sha256={_hash(message)}")
        parts.append(f"msg_len={len(message)}")
    if extra:
        parts.append(f"extra={extra}")
    _logger.info(" ".join(parts))
