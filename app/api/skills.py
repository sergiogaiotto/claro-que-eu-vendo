"""Módulo Skills — gestão dos SKILL.md que direcionam o raciocínio do agente."""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user, require_admin
from app.audit import audit_log
from app.database import User
from app.security import is_safe_slug, resolve_within
from app.skill_loader import SKILLS_DIR, load_skill, get_skills_summary

router = APIRouter(prefix="/skills", tags=["skills"])


def _validate_slug(slug: str) -> str:
    """Valida o slug e confirma que resolve dentro de SKILLS_DIR (VULN-13)."""
    if not is_safe_slug(slug):
        raise HTTPException(400, "Slug inválido")
    try:
        resolve_within(SKILLS_DIR, slug)
    except ValueError:
        raise HTTPException(400, "Slug inválido")
    return slug


class SkillSummary(BaseModel):
    slug: str
    name: str
    objetivo: str
    quando: str


class SkillDetail(BaseModel):
    slug: str
    name: str
    content: str


class SkillCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9\-]+$")
    content: str = Field(..., min_length=10, max_length=50_000)


class SkillUpdate(BaseModel):
    content: str = Field(..., min_length=10, max_length=50_000)


@router.get("/", response_model=list[SkillSummary])
def list_skills(_user: User = Depends(get_current_user)):
    """Lista todos os skills disponíveis (requer login — VULN-16)."""
    return [SkillSummary(**s) for s in get_skills_summary()]


@router.get("/{slug}", response_model=SkillDetail)
def get_skill(slug: str, _user: User = Depends(get_current_user)):
    """Retorna conteúdo completo de um skill (requer login — VULN-16)."""
    slug = _validate_slug(slug)
    skill = load_skill(slug)
    if not skill:
        raise HTTPException(404, "Skill não encontrado")
    return SkillDetail(slug=skill.slug, name=skill.name, content=skill.content)


@router.post("/", response_model=SkillDetail)
def create_skill(req: SkillCreate, admin: User = Depends(require_admin)):
    """Cria um novo skill personalizado (requer admin — VULN-09/04)."""
    _validate_slug(req.slug)
    skill_dir = os.path.join(SKILLS_DIR, req.slug)
    if os.path.exists(skill_dir):
        raise HTTPException(409, "Skill já existe")

    os.makedirs(skill_dir, exist_ok=True)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(req.content)

    audit_log("skill_create", user_id=admin.id, extra=f"slug={req.slug}")
    skill = load_skill(req.slug)
    return SkillDetail(slug=skill.slug, name=skill.name, content=skill.content)


@router.put("/{slug}", response_model=SkillDetail)
def update_skill(slug: str, req: SkillUpdate, admin: User = Depends(require_admin)):
    """Atualiza o conteúdo de um skill existente (requer admin — VULN-09/13)."""
    slug = _validate_slug(slug)
    skill_file = os.path.join(SKILLS_DIR, slug, "SKILL.md")
    if not os.path.isfile(skill_file):
        raise HTTPException(404, "Skill não encontrado")

    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(req.content)

    audit_log("skill_update", user_id=admin.id, extra=f"slug={slug}")
    skill = load_skill(slug)
    return SkillDetail(slug=skill.slug, name=skill.name, content=skill.content)


@router.delete("/{slug}")
def delete_skill(slug: str, admin: User = Depends(require_admin)):
    """Remove um skill (requer admin — VULN-09/13)."""
    slug = _validate_slug(slug)
    skill_dir = os.path.join(SKILLS_DIR, slug)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_file):
        raise HTTPException(404, "Skill não encontrado")

    os.remove(skill_file)
    try:
        os.rmdir(skill_dir)
    except OSError:
        pass
    audit_log("skill_delete", user_id=admin.id, extra=f"slug={slug}")
    return {"deleted": slug}
