"""Loader de Skills — lê arquivos SKILL.md e injeta no contexto do agente."""

import os
from dataclasses import dataclass

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")


@dataclass
class Skill:
    slug: str
    name: str
    content: str
    path: str


def _extract_name(content: str, slug: str) -> str:
    """Extrai o título do skill da primeira linha H1 do markdown."""
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return slug.replace("-", " ").title()


def load_all_skills() -> list[Skill]:
    """Carrega todos os skills do diretório app/skills/."""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        skill_file = os.path.join(skill_dir, "SKILL.md")
        if os.path.isdir(skill_dir) and os.path.isfile(skill_file):
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()
            skills.append(Skill(
                slug=entry,
                name=_extract_name(content, entry),
                content=content,
                path=skill_file,
            ))
    return skills


def load_skill(slug: str) -> Skill | None:
    """Carrega um skill específico pelo slug."""
    skill_file = os.path.join(SKILLS_DIR, slug, "SKILL.md")
    if not os.path.isfile(skill_file):
        return None
    with open(skill_file, "r", encoding="utf-8") as f:
        content = f.read()
    return Skill(slug=slug, name=_extract_name(content, slug), content=content, path=skill_file)


def build_skills_context() -> str:
    """Monta o bloco de contexto com todos os skills para injetar no system prompt."""
    skills = load_all_skills()
    if not skills:
        return ""

    parts = ["<Skills disponíveis>"]
    parts.append("Você possui os seguintes skills especializados. "
                 "Identifique automaticamente qual skill usar com base no pedido do vendedor. "
                 "Siga o workflow e formato de saída definidos no skill correspondente.\n")

    for s in skills:
        parts.append(f"### Skill: {s.name} (slug: {s.slug})")
        parts.append(s.content)
        parts.append("---\n")

    parts.append("</Skills disponíveis>")
    return "\n".join(parts)


def get_skills_summary() -> list[dict]:
    """Retorna lista resumida dos skills para o frontend."""
    skills = load_all_skills()
    result = []
    for s in skills:
        lines = s.content.splitlines()
        objetivo = ""
        quando = ""
        for i, line in enumerate(lines):
            if line.startswith("## Objetivo"):
                if i + 1 < len(lines):
                    objetivo = lines[i + 1].strip()
            if line.startswith("## Quando usar"):
                if i + 1 < len(lines):
                    quando = lines[i + 1].strip().lstrip("- ")
        result.append({
            "slug": s.slug,
            "name": s.name,
            "objetivo": objetivo,
            "quando": quando,
        })
    return result
