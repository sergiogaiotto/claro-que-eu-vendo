"""Autenticação — login, JWT em cookie HttpOnly, gestão de usuários."""

import hmac
import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import audit_log
from app.config import get_settings
from app.database import User, get_db
from app.ratelimit import rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------- password hashing (VULN-02 — salted, PBKDF2, sem SHA-256 puro) ----------

_PBKDF2_ROUNDS = 240_000
_SALT_BYTES = 16


def _hash_pw(password: str) -> str:
    """Gera hash salgado PBKDF2-HMAC-SHA256 (stdlib, sem dependência externa).

    Formato: pbkdf2_sha256$<rounds>$<salt_hex>$<hash_hex>
    """
    salt = os.urandom(_SALT_BYTES)
    dk = _pbkdf2(password, salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def _pbkdf2(password: str, salt: bytes, rounds: int) -> bytes:
    from hashlib import pbkdf2_hmac

    return pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)


def _verify_pw(password: str, stored: str) -> bool:
    """Verifica a senha; suporta o formato legado SHA-256 sem salt para migração."""
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, rounds_s, salt_hex, hash_hex = stored.split("$", 3)
            expected = bytes.fromhex(hash_hex)
            dk = _pbkdf2(password, bytes.fromhex(salt_hex), int(rounds_s))
            return hmac.compare_digest(dk, expected)
        except (ValueError, TypeError):
            return False
    # Legado: SHA-256 puro (será re-hasheado no próximo login bem-sucedido).
    legacy = sha256(password.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)


def _needs_rehash(stored: str) -> bool:
    return not stored.startswith("pbkdf2_sha256$")


# ---------- JWT / cookie ----------

def _create_token(user: User) -> str:
    cfg = get_settings()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=cfg.jwt_expire_minutes),
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def _set_auth_cookie(response: Response, token: str) -> None:
    cfg = get_settings()
    response.set_cookie(
        key=cfg.cookie_name,
        value=token,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite=cfg.cookie_samesite,
        max_age=cfg.jwt_expire_minutes * 60,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    cfg = get_settings()
    response.delete_cookie(key=cfg.cookie_name, path="/")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependência FastAPI — extrai o usuário do cookie HttpOnly (ou header Bearer)."""
    cfg = get_settings()
    token = request.cookies.get(cfg.cookie_name)
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Sessão inválida")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Sessão inválida")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Sessão inválida")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Exige papel root ou admin."""
    if user.role not in ("root", "admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user


def _guard_role_assignment(actor: User, target_role: str) -> None:
    """Impede escalonamento admin→root: apenas root cria/atribui o papel root."""
    if target_role == "root" and actor.role != "root":
        raise HTTPException(status_code=403, detail="Apenas root pode conceder o papel root")


def _guard_target_privilege(actor: User, target: User) -> None:
    """Impede que um admin modifique/exclua um usuário root."""
    if target.role == "root" and actor.role != "root":
        raise HTTPException(status_code=403, detail="Apenas root pode gerenciar usuários root")


# ---------- bootstrap de root (VULN-03) ----------

def bootstrap_root_from_env() -> None:
    """Cria o usuário root a partir de variáveis de ambiente, se não houver usuários.

    Executado no startup. Substitui a criação insegura de root no /login.
    """
    cfg = get_settings()
    if not cfg.root_username or not cfg.root_password:
        return
    from app.database import get_session_factory

    db = get_session_factory()()
    try:
        if db.query(User).count() > 0:
            return
        db.add(User(
            username=cfg.root_username,
            password_hash=_hash_pw(cfg.root_password),
            role="root",
            display_name="Super Usuário",
            profile_description="Usuário root criado via variável de ambiente no startup.",
        ))
        db.commit()
        audit_log("bootstrap_root", extra=f"username={cfg.root_username}")
    finally:
        db.close()


# ---------- schemas ----------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=1024)


class SetupRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=1024)
    setup_token: str = Field(..., min_length=1)


class UserPublic(BaseModel):
    user_id: int
    username: str
    role: str
    display_name: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=1024)
    role: str = Field(default="user")
    display_name: str = Field(default="")
    profile_description: str = Field(default="")


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    profile_description: str


class HasUsersResponse(BaseModel):
    has_users: bool
    setup_enabled: bool


_VALID_ROLES = {"root", "admin", "user"}


# ---------- routes ----------

@router.get("/has-users", response_model=HasUsersResponse)
def has_users(db: Session = Depends(get_db)):
    """Informa se há usuários e se o setup via web está habilitado."""
    cfg = get_settings()
    count = db.query(User).count()
    return HasUsersResponse(has_users=count > 0, setup_enabled=bool(cfg.setup_token))


@router.post("/setup", response_model=UserPublic)
def setup(
    req: SetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rl=Depends(rate_limiter("login", get_settings().rate_limit_login, get_settings().rate_limit_window_seconds)),
):
    """Cria o primeiro usuário root — apenas quando não há usuários E o
    setup_token confere (VULN-03). Sem SETUP_TOKEN configurado, fica desativado.
    """
    cfg = get_settings()
    if not cfg.setup_token:
        raise HTTPException(status_code=403, detail="Setup via web desativado. Use ROOT_USERNAME/ROOT_PASSWORD.")
    if db.query(User).count() > 0:
        raise HTTPException(status_code=409, detail="Sistema já inicializado")
    if not hmac.compare_digest(req.setup_token, cfg.setup_token):
        audit_log("setup_denied", ip=request.client.host if request.client else None)
        raise HTTPException(status_code=403, detail="Token de setup inválido")

    user = User(
        username=req.username,
        password_hash=_hash_pw(req.password),
        role="root",
        display_name="Super Usuário",
        profile_description="Usuário root criado no setup inicial.",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _create_token(user)
    _set_auth_cookie(response, token)
    audit_log("setup", user_id=user.id)
    return UserPublic(user_id=user.id, username=user.username, role=user.role, display_name=user.display_name)


@router.post("/login", response_model=UserPublic)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rl=Depends(rate_limiter("login", get_settings().rate_limit_login, get_settings().rate_limit_window_seconds)),
):
    """Login — autentica e emite o JWT em cookie HttpOnly.

    Não cria mais usuários automaticamente (VULN-03 corrigido).
    """
    ip = request.client.host if request.client else None
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not _verify_pw(req.password, user.password_hash):
        audit_log("login_failed", user_id=req.username, ip=ip)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    # Migração transparente de hash legado.
    if _needs_rehash(user.password_hash):
        user.password_hash = _hash_pw(req.password)
        db.commit()

    token = _create_token(user)
    _set_auth_cookie(response, token)
    audit_log("login", user_id=user.id, ip=ip)
    return UserPublic(user_id=user.id, username=user.username, role=user.role, display_name=user.display_name)


@router.post("/logout")
def logout(response: Response):
    _clear_auth_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    """Retorna o usuário autenticado (a partir do cookie)."""
    return UserPublic(user_id=user.id, username=user.username, role=user.role, display_name=user.display_name)


@router.post("/users", response_model=UserOut)
def create_user(
    req: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Cria novo usuário (requer admin/root)."""
    if req.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail="Papel inválido")
    _guard_role_assignment(_admin, req.role)
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Usuário já existe")

    user = User(
        username=req.username,
        password_hash=_hash_pw(req.password),
        role=req.role,
        display_name=req.display_name or req.username,
        profile_description=req.profile_description,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_log("user_create", user_id=_admin.id, extra=f"new={user.username}:{user.role}")
    return UserOut(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name,
        profile_description=user.profile_description,
    )


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """Lista todos os usuários (requer admin/root)."""
    users = db.query(User).order_by(User.id).all()
    return [
        UserOut(
            id=u.id, username=u.username, role=u.role,
            display_name=u.display_name,
            profile_description=u.profile_description,
        )
        for u in users
    ]


class UserUpdate(BaseModel):
    display_name: str = Field(default="")
    role: str = Field(default="")
    profile_description: str = Field(default="")
    password: str = Field(default="")


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Atualiza dados de um usuário (requer admin/root)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")

    # Um admin não pode modificar um root nem promover ninguém a root.
    _guard_target_privilege(_admin, user)

    if req.display_name:
        user.display_name = req.display_name
    if req.role:
        if req.role not in _VALID_ROLES:
            raise HTTPException(status_code=400, detail="Papel inválido")
        _guard_role_assignment(_admin, req.role)
        user.role = req.role
    if req.profile_description is not None:
        user.profile_description = req.profile_description
    if req.password:
        if len(req.password) < 8:
            raise HTTPException(status_code=400, detail="Senha muito curta (mín. 8)")
        user.password_hash = _hash_pw(req.password)

    db.commit()
    db.refresh(user)
    audit_log("user_update", user_id=_admin.id, extra=f"target={user.id}")
    return UserOut(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name,
        profile_description=user.profile_description,
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Remove um usuário (não pode remover o último root)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")

    if user.id == _admin.id:
        raise HTTPException(400, "Não é possível excluir a si mesmo")

    # Um admin não pode excluir um usuário root.
    _guard_target_privilege(_admin, user)

    if user.role == "root":
        root_count = db.query(User).filter(User.role == "root").count()
        if root_count <= 1:
            raise HTTPException(400, "Não é possível excluir o último usuário root")

    db.delete(user)
    db.commit()
    audit_log("user_delete", user_id=_admin.id, extra=f"target={user_id}")
    return {"deleted": user_id}
