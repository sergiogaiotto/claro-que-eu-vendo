"""Autenticação — login, JWT, gestão de usuários."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import User, get_db

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------- helpers ----------

def _hash_pw(password: str) -> str:
    return sha256(password.encode()).hexdigest()


def _create_token(user: User) -> str:
    cfg = get_settings()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=cfg.jwt_expire_minutes),
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def get_current_user(token: str = "", db: Session = Depends(get_db)) -> User:
    """Dependência FastAPI — extrai usuário do token."""
    cfg = get_settings()
    if not token:
        raise HTTPException(status_code=401, detail="Token ausente")
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


# ---------- schemas ----------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    role: str
    display_name: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
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


# ---------- routes ----------

@router.get("/has-users", response_model=HasUsersResponse)
def has_users(db: Session = Depends(get_db)):
    """Verifica se existe algum usuário cadastrado."""
    count = db.query(User).count()
    return HasUsersResponse(has_users=count > 0)


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login — se não existir nenhum usuário, cria root automaticamente."""
    user_count = db.query(User).count()

    if user_count == 0:
        new_user = User(
            username=req.username,
            password_hash=_hash_pw(req.password),
            role="root",
            display_name="Super Usuário",
            profile_description="Usuário root criado automaticamente no primeiro acesso.",
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        token = _create_token(new_user)
        return LoginResponse(
            token=token,
            user_id=new_user.id,
            username=new_user.username,
            role=new_user.role,
            display_name=new_user.display_name,
        )

    user = db.query(User).filter(User.username == req.username).first()
    if not user or user.password_hash != _hash_pw(req.password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = _create_token(user)
    return LoginResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
    )


@router.post("/users", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db)):
    """Cria novo usuário (requer admin/root via frontend)."""
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
    return UserOut(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name,
        profile_description=user.profile_description,
    )


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    """Lista todos os usuários."""
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
def update_user(user_id: int, req: UserUpdate, db: Session = Depends(get_db)):
    """Atualiza dados de um usuário."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")

    if req.display_name:
        user.display_name = req.display_name
    if req.role:
        user.role = req.role
    if req.profile_description is not None:
        user.profile_description = req.profile_description
    if req.password:
        user.password_hash = _hash_pw(req.password)

    db.commit()
    db.refresh(user)
    return UserOut(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name,
        profile_description=user.profile_description,
    )


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Remove um usuário (não pode remover a si mesmo ou último root)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")

    if user.role == "root":
        root_count = db.query(User).filter(User.role == "root").count()
        if root_count <= 1:
            raise HTTPException(400, "Não é possível excluir o último usuário root")

    db.delete(user)
    db.commit()
    return {"deleted": user_id}
