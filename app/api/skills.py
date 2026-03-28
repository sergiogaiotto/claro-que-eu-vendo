"""Módulo Skills — gestão dos SKILL.md que direcionam o raciocínio do agente."""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.skill_loader import SKILLS_DIR, load_all_skills, load_skill, get_skills_summary

router = APIRouter(prefix="/skills", tags=["skills"])


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
    slug: str = Field(..., min_length=1, pattern=r"^[a-z0-9\-]+$")
    content: str = Field(..., min_length=10)


class SkillUpdate(BaseModel):
    content: str = Field(..., min_length=10)


@router.get("/", response_model=list[SkillSummary])
def list_skills():
    """Lista todos os skills disponíveis."""
    return [SkillSummary(**s) for s in get_skills_summary()]


@router.get("/{slug}", response_model=SkillDetail)
def get_skill(slug: str):
    """Retorna conteúdo completo de um skill."""
    skill = load_skill(slug)
    if not skill:
        raise HTTPException(404, "Skill não encontrado")
    return SkillDetail(slug=skill.slug, name=skill.name, content=skill.content)


@router.post("/", response_model=SkillDetail)
def create_skill(req: SkillCreate):
    """Cria um novo skill personalizado."""
    skill_dir = os.path.join(SKILLS_DIR, req.slug)
    if os.path.exists(skill_dir):
        raise HTTPException(409, "Skill já existe")

    os.makedirs(skill_dir, exist_ok=True)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(req.content)

    skill = load_skill(req.slug)
    return SkillDetail(slug=skill.slug, name=skill.name, content=skill.content)


@router.put("/{slug}", response_model=SkillDetail)
def update_skill(slug: str, req: SkillUpdate):
    """Atualiza o conteúdo de um skill existente."""
    skill_file = os.path.join(SKILLS_DIR, slug, "SKILL.md")
    if not os.path.isfile(skill_file):
        raise HTTPException(404, "Skill não encontrado")

    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(req.content)

    skill = load_skill(slug)
    return SkillDetail(slug=skill.slug, name=skill.name, content=skill.content)


@router.delete("/{slug}")
def delete_skill(slug: str):
    """Remove um skill."""
    skill_dir = os.path.join(SKILLS_DIR, slug)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_file):
        raise HTTPException(404, "Skill não encontrado")

    os.remove(skill_file)
    try:
        os.rmdir(skill_dir)
    except OSError:
        pass
    return {"deleted": slug}
