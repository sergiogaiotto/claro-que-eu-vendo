"""Módulo Pitch — histórico de interações, anotações, PDF."""

import json
import re
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import Pitch, PitchInteraction, get_db

router = APIRouter(prefix="/pitches", tags=["pitches"])


# ---------- schemas ----------

class InteractionOut(BaseModel):
    id: int
    role: str
    content: str
    liked: bool | None
    note: str
    created_at: str


class PitchOut(BaseModel):
    id: int
    company_name: str
    created_at: str
    interactions: list[InteractionOut]


class PitchCreate(BaseModel):
    company_name: str = Field(..., min_length=1)


class SaveInteraction(BaseModel):
    pitch_id: int
    role: str
    content: str


class UpdateLike(BaseModel):
    liked: bool | None = None


class UpdateNote(BaseModel):
    note: str = ""


# ---------- helpers ----------

def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _pitch_to_out(p: Pitch) -> PitchOut:
    return PitchOut(
        id=p.id,
        company_name=p.company_name,
        created_at=_fmt(p.created_at),
        interactions=[
            InteractionOut(
                id=i.id, role=i.role, content=i.content,
                liked=i.liked, note=i.note, created_at=_fmt(i.created_at),
            )
            for i in p.interactions
        ],
    )


# ---------- routes ----------

@router.get("/", response_model=list[PitchOut])
def list_pitches(
    user_id: int = Query(...),
    company: str = Query(default=""),
    liked_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    q = db.query(Pitch).filter(Pitch.user_id == user_id)
    if company:
        q = q.filter(Pitch.company_name.ilike(f"%{company}%"))
    pitches = q.order_by(Pitch.created_at.desc()).all()

    results = []
    for p in pitches:
        out = _pitch_to_out(p)
        if liked_only:
            out.interactions = [i for i in out.interactions if i.liked is True]
            if not out.interactions:
                continue
        results.append(out)
    return results


@router.post("/", response_model=PitchOut)
def create_pitch(req: PitchCreate, user_id: int = Query(...), db: Session = Depends(get_db)):
    pitch = Pitch(user_id=user_id, company_name=req.company_name)
    db.add(pitch)
    db.commit()
    db.refresh(pitch)
    return _pitch_to_out(pitch)


@router.post("/interactions", response_model=InteractionOut)
def add_interaction(req: SaveInteraction, db: Session = Depends(get_db)):
    pitch = db.query(Pitch).filter(Pitch.id == req.pitch_id).first()
    if not pitch:
        raise HTTPException(404, "Pitch não encontrado")
    interaction = PitchInteraction(
        pitch_id=req.pitch_id, role=req.role, content=req.content,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return InteractionOut(
        id=interaction.id, role=interaction.role, content=interaction.content,
        liked=interaction.liked, note=interaction.note,
        created_at=_fmt(interaction.created_at),
    )


@router.patch("/interactions/{interaction_id}/like", response_model=InteractionOut)
def update_like(interaction_id: int, req: UpdateLike, db: Session = Depends(get_db)):
    i = db.query(PitchInteraction).filter(PitchInteraction.id == interaction_id).first()
    if not i:
        raise HTTPException(404, "Interação não encontrada")
    i.liked = req.liked
    db.commit()
    db.refresh(i)
    return InteractionOut(
        id=i.id, role=i.role, content=i.content,
        liked=i.liked, note=i.note, created_at=_fmt(i.created_at),
    )


@router.patch("/interactions/{interaction_id}/note", response_model=InteractionOut)
def update_note(interaction_id: int, req: UpdateNote, db: Session = Depends(get_db)):
    i = db.query(PitchInteraction).filter(PitchInteraction.id == interaction_id).first()
    if not i:
        raise HTTPException(404, "Interação não encontrada")
    i.note = req.note
    db.commit()
    db.refresh(i)
    return InteractionOut(
        id=i.id, role=i.role, content=i.content,
        liked=i.liked, note=i.note, created_at=_fmt(i.created_at),
    )


@router.delete("/{pitch_id}")
def delete_pitch(pitch_id: int, db: Session = Depends(get_db)):
    """Exclui um pitch e todas as suas interações."""
    pitch = db.query(Pitch).filter(Pitch.id == pitch_id).first()
    if not pitch:
        raise HTTPException(404, "Pitch não encontrado")
    db.delete(pitch)
    db.commit()
    return {"deleted": pitch_id}


@router.get("/{pitch_id}/pdf")
def generate_pdf(pitch_id: int, db: Session = Depends(get_db)):
    """Gera PDF Guia de Bolso do Vendedor — compilado estruturado do pitch."""
    pitch = db.query(Pitch).filter(Pitch.id == pitch_id).first()
    if not pitch:
        raise HTTPException(404, "Pitch não encontrado")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, Color
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether,
        )
    except ImportError:
        raise HTTPException(500, "reportlab não instalado. Execute: pip install reportlab")

    # --- Cores ---
    BRAND = HexColor("#ea580c")
    BRAND_DARK = HexColor("#9a3412")
    BRAND_LIGHT = HexColor("#fff7ed")
    GRAY = HexColor("#666666")
    GRAY_LIGHT = HexColor("#f5f5f5")
    DARK = HexColor("#1a1a1a")

    # --- Estilos ---
    styles = getSampleStyleSheet()

    s_cover_title = ParagraphStyle("CoverTitle", parent=styles["Title"],
        fontSize=28, textColor=BRAND, alignment=TA_CENTER, spaceAfter=8)
    s_cover_sub = ParagraphStyle("CoverSub", parent=styles["Normal"],
        fontSize=14, textColor=GRAY, alignment=TA_CENTER, spaceAfter=4)
    s_cover_meta = ParagraphStyle("CoverMeta", parent=styles["Normal"],
        fontSize=10, textColor=GRAY, alignment=TA_CENTER)

    s_section = ParagraphStyle("Section", parent=styles["Heading1"],
        fontSize=16, textColor=BRAND, spaceBefore=20, spaceAfter=8,
        borderPadding=(0, 0, 4, 0), borderWidth=0, borderColor=BRAND)
    s_subsection = ParagraphStyle("Subsection", parent=styles["Heading2"],
        fontSize=12, textColor=BRAND_DARK, spaceBefore=12, spaceAfter=4)

    s_body = ParagraphStyle("Body", parent=styles["Normal"],
        fontSize=10, leading=14, textColor=DARK, alignment=TA_JUSTIFY)
    s_body_bold = ParagraphStyle("BodyBold", parent=s_body, fontName="Helvetica-Bold")
    s_quote = ParagraphStyle("Quote", parent=s_body,
        leftIndent=16, rightIndent=16, fontSize=10, leading=14,
        textColor=BRAND_DARK, fontName="Helvetica-Oblique",
        borderPadding=(8, 8, 8, 8), backColor=BRAND_LIGHT)
    s_note = ParagraphStyle("Note", parent=s_body,
        fontSize=9, textColor=GRAY, leftIndent=12, fontName="Helvetica-Oblique")
    s_liked = ParagraphStyle("Liked", parent=s_body,
        fontSize=9, textColor=HexColor("#16a34a"), leftIndent=12)
    s_footer = ParagraphStyle("Footer", parent=styles["Normal"],
        fontSize=8, textColor=GRAY, alignment=TA_CENTER)

    # --- Extração de conteúdo ---
    assistant_contents = []
    user_questions = []
    liked_contents = []
    notes = []

    for inter in pitch.interactions:
        if inter.role == "assistant" and inter.content:
            assistant_contents.append(inter.content)
            if inter.liked is True:
                liked_contents.append(inter.content)
        elif inter.role == "user" and inter.content:
            user_questions.append(inter.content)
        if inter.note:
            notes.append(inter.note)

    full_text = "\n\n".join(assistant_contents)

    # --- Parsing inteligente de seções ---
    def extract_sections(text: str) -> list[tuple[str, str]]:
        """Extrai seções do markdown (## e ###) com conteúdo."""
        sections = []
        current_title = ""
        current_body = []

        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## ") or stripped.startswith("### "):
                if current_title or current_body:
                    sections.append((current_title, "\n".join(current_body).strip()))
                current_title = stripped.lstrip("#").strip()
                current_body = []
            else:
                current_body.append(line)

        if current_title or current_body:
            sections.append((current_title, "\n".join(current_body).strip()))

        return sections

    def md_to_rl(text: str) -> str:
        """Converte markdown básico para tags reportlab."""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        # Links — texto + url entre parênteses
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<b>\1</b>', text)
        # Bullets com indentação visual
        text = re.sub(r'^- (.+)$', r'  •  \1', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s+(.+)$', r'  •  \1', text, flags=re.MULTILINE)
        # Limpa separadores --- e ===
        text = re.sub(r'^[\-=]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Limpa linhas de tabela separadora |---|---|
        text = re.sub(r'^\|[\s\-:]+\|[\s\-:|]*$', '', text, flags=re.MULTILINE)
        # Limpa action tags
        text = re.sub(r'\[\[action:.+?\]\]', '', text)
        text = re.sub(r'\{action:.+?\}', '', text)
        # Limpa linhas vazias múltiplas
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Line breaks
        text = text.replace("\n", "<br/>")
        # Limpa br consecutivos
        text = re.sub(r'(<br/>){3,}', '<br/><br/>', text)
        return text.strip()

    def parse_md_table(text: str) -> list[list[str]] | None:
        """Detecta e parseia uma tabela markdown, retorna lista de linhas."""
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        table_lines = []
        for line in lines:
            if line.startswith("|") and line.endswith("|"):
                # Pula separador |---|---|
                if re.match(r'^\|[\s\-:]+(\|[\s\-:]+)+\|$', line):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                table_lines.append(cells)
            elif table_lines:
                break
        return table_lines if len(table_lines) >= 2 else None

    def build_table(rows: list[list[str]]) -> Table:
        """Cria tabela reportlab elegante a partir de linhas parseadas."""
        # Converte cada célula em Paragraph para suportar bold/wrap
        s_cell = ParagraphStyle("Cell", parent=s_body, fontSize=9, leading=12)
        s_cell_head = ParagraphStyle("CellH", parent=s_cell,
            fontName="Helvetica-Bold", textColor=BRAND_DARK)

        table_data = []
        for i, row in enumerate(rows):
            style = s_cell_head if i == 0 else s_cell
            table_data.append([
                Paragraph(md_to_rl(cell), style) for cell in row
            ])

        ncols = max(len(r) for r in table_data)
        col_width = min(480 / ncols, 180)

        t = Table(table_data, colWidths=[col_width] * ncols)
        t.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_LIGHT),
            ('TEXTCOLOR', (0, 0), (-1, 0), BRAND_DARK),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            # Corpo
            ('BACKGROUND', (0, 1), (-1, -1), HexColor("#fafafa")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#f9f9f9")]),
            # Bordas suaves
            ('LINEBELOW', (0, 0), (-1, 0), 1, BRAND),
            ('LINEBELOW', (0, 1), (-1, -2), 0.25, HexColor("#e5e5e5")),
            ('LINEBELOW', (0, -1), (-1, -1), 0.5, HexColor("#cccccc")),
            # Sem bordas laterais — visual limpo
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            # Arredondamento visual (linha superior mais grossa)
            ('LINEABOVE', (0, 0), (-1, 0), 0.5, HexColor("#e5e5e5")),
        ]))
        return t

    def render_body(body: str, elems: list):
        """Renderiza body de seção, separando tabelas de texto."""
        if not body:
            return

        # Divide em blocos: detecta tabelas markdown
        lines = body.split("\n")
        current_text = []
        in_table = False
        table_lines = []

        def flush_text():
            txt = "\n".join(current_text).strip()
            if txt:
                elems.append(Paragraph(md_to_rl(txt), s_body))

        def flush_table():
            parsed = parse_md_table("\n".join(table_lines))
            if parsed:
                elems.append(Spacer(1, 0.2 * cm))
                elems.append(build_table(parsed))
                elems.append(Spacer(1, 0.2 * cm))
            else:
                # Não era tabela válida, trata como texto
                txt = "\n".join(table_lines)
                if txt.strip():
                    elems.append(Paragraph(md_to_rl(txt), s_body))

        for line in lines:
            stripped = line.strip()
            is_table_line = stripped.startswith("|") and stripped.endswith("|")

            if is_table_line:
                if not in_table:
                    flush_text()
                    current_text = []
                    in_table = True
                    table_lines = []
                table_lines.append(stripped)
            else:
                if in_table:
                    flush_table()
                    table_lines = []
                    in_table = False
                current_text.append(line)

        # Flush final
        if in_table:
            flush_table()
        else:
            flush_text()

    # --- Renderers especiais para Produtos/NBO ---

    # Cores por camada NBO
    TIER_COLORS = {
        "ancora": {"bg": HexColor("#fff7ed"), "border": BRAND, "label": "ÂNCORA"},
        "acelerador": {"bg": HexColor("#eff6ff"), "border": HexColor("#3b82f6"), "label": "ACELERADOR"},
        "expansao": {"bg": HexColor("#f0fdf4"), "border": HexColor("#22c55e"), "label": "EXPANSÃO"},
        "default": {"bg": HexColor("#f9fafb"), "border": HexColor("#9ca3af"), "label": "PRODUTO"},
    }

    def detect_tier(title: str) -> dict:
        t = title.lower()
        if any(k in t for k in ["âncora", "ancora", "principal"]):
            return TIER_COLORS["ancora"]
        if any(k in t for k in ["acelerador", "complemento", "acelera"]):
            return TIER_COLORS["acelerador"]
        if any(k in t for k in ["expansão", "expansao", "fase 2", "futuro"]):
            return TIER_COLORS["expansao"]
        return TIER_COLORS["default"]

    s_card_title = ParagraphStyle("CardTitle", parent=s_body,
        fontSize=11, fontName="Helvetica-Bold", textColor=DARK,
        spaceBefore=0, spaceAfter=0)
    s_card_body = ParagraphStyle("CardBody", parent=s_body,
        fontSize=9, leading=13, textColor=HexColor("#374151"),
        spaceBefore=0, spaceAfter=0)
    s_card_label = ParagraphStyle("CardLabel", parent=s_body,
        fontSize=8, fontName="Helvetica-Bold", textColor=GRAY,
        spaceBefore=0, spaceAfter=0)
    s_card_value = ParagraphStyle("CardValue", parent=s_body,
        fontSize=9, textColor=DARK, spaceBefore=0, spaceAfter=0)
    s_summary_title = ParagraphStyle("SummTitle", parent=s_body,
        fontSize=11, fontName="Helvetica-Bold", textColor=BRAND_DARK,
        spaceBefore=12, spaceAfter=6)

    def render_product_card(title: str, body: str, elems: list):
        """Renderiza um produto como card multi-row com borda lateral colorida."""
        tier = detect_tier(title)

        # Monta rows: primeira row = badge+título, demais = campos
        rows = []

        # Row 0: badge de tier + título
        clean_title = re.sub(r'^(âncora|acelerador|expansão|fase\s*2)\s*[—\-:]\s*',
                             '', title, flags=re.IGNORECASE).strip()
        badge_text = f'<font color="#ffffff"><b>  {tier["label"]}  </b></font>'
        title_text = md_to_rl(clean_title) if clean_title else md_to_rl(title)
        rows.append([
            Paragraph(badge_text, ParagraphStyle("BadgeP", parent=s_body,
                fontSize=7, fontName="Helvetica-Bold",
                textColor=HexColor("#ffffff"))),
            Paragraph(title_text, s_card_title),
        ])

        # Parseia body em pares label:valor ou texto livre
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        for line in lines:
            clean = line.lstrip("-•* ").strip()
            # Pula separadores, action tags, linhas de tabela
            if re.match(r'^[\-=]{3,}$', clean):
                continue
            if re.match(r'^\|', clean):
                continue
            if '[[action:' in clean or '{action:' in clean:
                continue

            # Detecta **Label:** Valor
            m = re.match(r'\*\*(.+?)\*\*[:\s]*(.+)', clean)
            if m:
                label = m.group(1).strip().rstrip(":")
                value = m.group(2).strip()
                rows.append([
                    Paragraph(f'<b>{label}</b>', s_card_label),
                    Paragraph(md_to_rl(value), s_card_value),
                ])
            elif clean:
                # Texto livre ocupa as 2 colunas (será merged)
                rows.append([
                    Paragraph(md_to_rl(clean), s_card_body),
                    "",
                ])

        t = Table(rows, colWidths=[80, 400])

        style_cmds = [
            # Fundo do card
            ('BACKGROUND', (0, 0), (-1, -1), tier["bg"]),
            # Borda lateral esquerda grossa colorida
            ('LINEBEFORE', (0, 0), (0, -1), 3.5, tier["border"]),
            # Badge na primeira célula
            ('BACKGROUND', (0, 0), (0, 0), tier["border"]),
            # Padding
            ('LEFTPADDING', (0, 0), (0, -1), 8),
            ('LEFTPADDING', (1, 0), (1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            # Título: mais padding
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            # Alinhamento
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ]

        # SPAN para linhas de texto livre (coluna 0 sozinha se coluna 1 vazia)
        for i, row in enumerate(rows):
            if i > 0 and (row[1] == "" or row[1] is None):
                style_cmds.append(('SPAN', (0, i), (1, i)))

        t.setStyle(TableStyle(style_cmds))

        elems.append(KeepTogether([t]))
        elems.append(Spacer(1, 0.35 * cm))

    def render_summary_table(body: str, elems: list) -> bool:
        """Renderiza tabela-resumo do pacote como tabela elegante."""
        parsed = parse_md_table(body)
        if not parsed or len(parsed) < 2:
            return False

        ncols = max(len(r) for r in parsed)
        if ncols < 2:
            return False

        # Detecta linha de total
        has_total = any("total" in c.lower() for c in parsed[-1])

        # Styles por tipo de linha
        s_th = ParagraphStyle("TH", parent=s_body,
            fontSize=8, fontName="Helvetica-Bold", textColor=BRAND_DARK)
        s_td = ParagraphStyle("TD", parent=s_body,
            fontSize=9, textColor=DARK, leading=12)
        s_tt = ParagraphStyle("TT", parent=s_body,
            fontSize=10, fontName="Helvetica-Bold", textColor=BRAND_DARK)

        table_data = []
        for i, row in enumerate(parsed):
            if i == 0:
                style = s_th
            elif i == len(parsed) - 1 and has_total:
                style = s_tt
            else:
                style = s_td
            # Preenche colunas faltantes
            padded = row + [""] * (ncols - len(row))
            table_data.append([Paragraph(md_to_rl(c), style) for c in padded])

        # Larguras inteligentes
        if ncols == 4:
            col_widths = [170, 130, 90, 90]
        elif ncols == 3:
            col_widths = [220, 160, 100]
        elif ncols == 2:
            col_widths = [320, 160]
        else:
            w = 480 / ncols
            col_widths = [w] * ncols

        t = Table(table_data, colWidths=col_widths)

        style_cmds = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_LIGHT),
            ('LINEBELOW', (0, 0), (-1, 0), 1.2, BRAND),
            # Linhas do corpo
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#fafafa")]),
            ('LINEBELOW', (0, 1), (-1, -2), 0.3, HexColor("#e5e5e5")),
            # Padding generoso
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Última coluna à direita (valores)
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ]

        if has_total:
            style_cmds.extend([
                ('LINEABOVE', (0, -1), (-1, -1), 1.2, BRAND),
                ('BACKGROUND', (0, -1), (-1, -1), BRAND_LIGHT),
            ])

        # Borda externa sutil
        style_cmds.append(('BOX', (0, 0), (-1, -1), 0.5, HexColor("#e0e0e0")))

        t.setStyle(TableStyle(style_cmds))
        elems.append(Spacer(1, 0.2 * cm))
        elems.append(t)
        elems.append(Spacer(1, 0.3 * cm))
        return True

    def split_sub_sections(body: str) -> list[tuple[str, str]]:
        """Extrai sub-seções #### de dentro de um body."""
        subs = []
        current_title = ""
        current_lines = []

        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#### "):
                if current_title or current_lines:
                    subs.append((current_title, "\n".join(current_lines).strip()))
                current_title = stripped.lstrip("#").strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_title or current_lines:
            subs.append((current_title, "\n".join(current_lines).strip()))

        return subs

    def body_has_table(body: str) -> bool:
        """Verifica se o body contém uma tabela markdown."""
        table_lines = [l for l in body.split("\n")
                       if l.strip().startswith("|") and l.strip().endswith("|")]
        return len(table_lines) >= 3

    def extract_non_table_text(body: str) -> str:
        """Extrai texto fora de tabelas."""
        result = []
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                continue
            result.append(line)
        return "\n".join(result).strip()

    def render_produtos_section(group: list, elems: list):
        """Renderiza seção de produtos com cards + tabela-resumo."""
        elems.append(Paragraph("6. Produtos Recomendados (NBO)", s_section))
        elems.append(HRFlowable(width="100%", thickness=0.5, color=BRAND,
                                spaceAfter=12, spaceBefore=0))

        for title, body in group:
            title_lower = title.lower()

            # Detecta se é resumo/tabela-proposta
            is_summary = any(k in title_lower for k in [
                "resumo", "pacote recomendado", "proposta", "total",
                "investimento", "valores", "precificação", "matriz",
            ])

            if is_summary:
                elems.append(Paragraph(md_to_rl(title), s_summary_title))
                if body_has_table(body):
                    rendered = render_summary_table(body, elems)
                    # Renderiza texto fora da tabela também
                    extra = extract_non_table_text(body)
                    if extra:
                        render_body(extra, elems)
                    if not rendered:
                        render_body(body, elems)
                else:
                    render_body(body, elems)
                continue

            # Detecta se body contém #### (sub-produtos dentro de ### Pacote)
            subs = split_sub_sections(body)
            has_sub_products = any(s[0] for s in subs)

            if has_sub_products:
                # Título do bloco (ex: "Pacote Recomendado")
                if title:
                    elems.append(Paragraph(md_to_rl(title), s_subsection))
                    elems.append(Spacer(1, 0.2 * cm))

                for sub_title, sub_body in subs:
                    if not sub_title:
                        # Texto pré-sub-seção (diagnóstico, etc.)
                        if sub_body:
                            # Verifica se contém tabela
                            if body_has_table(sub_body):
                                render_summary_table(sub_body, elems)
                                extra = extract_non_table_text(sub_body)
                                if extra:
                                    render_body(extra, elems)
                            else:
                                render_body(sub_body, elems)
                                elems.append(Spacer(1, 0.2 * cm))
                        continue

                    # Detecta se sub-seção é resumo/tabela
                    sub_lower = sub_title.lower()
                    sub_is_summary = any(k in sub_lower for k in [
                        "resumo", "total", "investimento", "script",
                        "próximo", "proximo",
                    ])

                    if sub_is_summary or body_has_table(sub_body):
                        elems.append(Paragraph(md_to_rl(sub_title), s_summary_title))
                        if body_has_table(sub_body):
                            render_summary_table(sub_body, elems)
                            extra = extract_non_table_text(sub_body)
                            if extra:
                                render_body(extra, elems)
                        else:
                            render_body(sub_body, elems)
                    elif any(k in sub_lower for k in [
                        "âncora", "ancora", "acelerador", "expansão",
                        "expansao", "produto", "complemento",
                    ]):
                        # Card de produto
                        render_product_card(sub_title, sub_body, elems)
                    else:
                        # Sub-seção genérica (Script, Próximos passos...)
                        elems.append(Paragraph(md_to_rl(sub_title), s_subsection))
                        render_body(sub_body, elems)
                        elems.append(Spacer(1, 0.2 * cm))
            elif title:
                # Produto individual sem sub-seções
                is_product = any(k in title_lower for k in [
                    "âncora", "ancora", "acelerador", "expansão",
                    "expansao", "produto", "complemento",
                ])
                if is_product:
                    render_product_card(title, body, elems)
                else:
                    elems.append(Paragraph(md_to_rl(title), s_subsection))
                    render_body(body, elems)
                    elems.append(Spacer(1, 0.2 * cm))
            else:
                render_body(body, elems)

    sections = extract_sections(full_text)

    # --- Classificar seções por tipo ---
    section_groups = {
        "empresa": [],
        "interlocutor": [],
        "dores": [],
        "abordagem": [],
        "pitch": [],
        "produtos": [],
        "outros": [],
    }

    def classify(title: str) -> str:
        t = title.lower()
        if any(k in t for k in ["empresa", "perfil da emp", "sobre", "setor", "porte", "notícia", "concorr"]):
            return "empresa"
        if any(k in t for k in ["interlocutor", "perfil —", "trajetória", "comunicação", "contato"]):
            return "interlocutor"
        if any(k in t for k in ["dor", "ponto de dor", "desafio", "problema", "necessidade"]):
            return "dores"
        if any(k in t for k in ["abordagem", "estratégia", "tom ", "quebra-gelo", "evit", "argumen"]):
            return "abordagem"
        if any(k in t for k in ["pitch", "abertura", "diagnóstico", "fechamento", "objeção", "prova social", "script"]):
            return "pitch"
        if any(k in t for k in ["produto", "nbo", "recomend", "catálogo", "pacote", "proposta", "âncora"]):
            return "produtos"
        return "outros"

    for title, body in sections:
        cat = classify(title)
        section_groups[cat].append((title, body))

    # --- Montar PDF ---
    elements = []

    # ===== CAPA =====
    elements.append(Spacer(1, 4 * cm))
    elements.append(Paragraph("GUIA DE BOLSO", s_cover_sub))
    elements.append(Paragraph(pitch.company_name, s_cover_title))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="40%", thickness=2, color=BRAND,
                                spaceAfter=12, spaceBefore=0, hAlign="CENTER"))
    elements.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", s_cover_meta))
    elements.append(Paragraph("Claro que Eu vendo! — Assistente de Vendas com IA", s_cover_meta))
    elements.append(Spacer(1, 3 * cm))

    # Sumário rápido
    toc_items = []
    if section_groups["empresa"]: toc_items.append("1. Empresa")
    if section_groups["interlocutor"]: toc_items.append("2. Interlocutor")
    if section_groups["dores"]: toc_items.append("3. Pontos de dor")
    if section_groups["abordagem"]: toc_items.append("4. Estratégia de abordagem")
    if section_groups["pitch"]: toc_items.append("5. Roteiro do pitch")
    if section_groups["produtos"]: toc_items.append("6. Produtos recomendados")
    if liked_contents: toc_items.append("⭐ Destaques do vendedor")
    if notes: toc_items.append("📝 Anotações do vendedor")

    if toc_items:
        elements.append(Paragraph("Neste guia", s_subsection))
        elements.append(Paragraph("<br/>".join(toc_items), s_body))
        elements.append(Spacer(1, 1 * cm))

    # ===== SEÇÕES =====
    group_titles = {
        "empresa": "1. A Empresa",
        "interlocutor": "2. O Interlocutor",
        "dores": "3. Pontos de Dor",
        "abordagem": "4. Estratégia de Abordagem",
        "pitch": "5. Roteiro do Pitch",
        "produtos": "6. Produtos Recomendados (NBO)",
    }

    for group_key in ["empresa", "interlocutor", "dores", "abordagem", "pitch"]:
        group = section_groups[group_key]
        if not group:
            continue

        elements.append(Paragraph(group_titles[group_key], s_section))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND,
                                    spaceAfter=8, spaceBefore=0))

        for title, body in group:
            if title:
                elements.append(Paragraph(md_to_rl(title), s_subsection))
            render_body(body, elements)
            elements.append(Spacer(1, 0.3 * cm))

    # ===== PRODUTOS — renderer especial com cards =====
    if section_groups["produtos"]:
        render_produtos_section(section_groups["produtos"], elements)

    # ===== OUTROS (não classificados) =====
    if section_groups["outros"]:
        elements.append(Paragraph("Informações Complementares", s_section))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND,
                                    spaceAfter=8, spaceBefore=0))
        for title, body in section_groups["outros"]:
            if title:
                elements.append(Paragraph(md_to_rl(title), s_subsection))
            render_body(body, elements)
            elements.append(Spacer(1, 0.3 * cm))

    # ===== DESTAQUES DO VENDEDOR (liked) =====
    if liked_contents:
        elements.append(Paragraph("Destaques do Vendedor", s_section))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND,
                                    spaceAfter=8, spaceBefore=0))
        elements.append(Paragraph(
            "Trechos marcados com 'Gostei!' durante a preparação:", s_note))
        elements.append(Spacer(1, 0.3 * cm))

        for content in liked_contents:
            # Extrai só os primeiros 500 chars de cada liked
            short = content[:500] + ("..." if len(content) > 500 else "")
            elements.append(Paragraph(md_to_rl(short), s_quote))
            elements.append(Spacer(1, 0.3 * cm))

    # ===== ANOTAÇÕES =====
    if notes:
        elements.append(Paragraph("Anotações do Vendedor", s_section))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND,
                                    spaceAfter=8, spaceBefore=0))
        for note in notes:
            elements.append(Paragraph(f"• {md_to_rl(note)}", s_body))
        elements.append(Spacer(1, 0.3 * cm))

    # ===== CHECKLIST RÁPIDO =====
    elements.append(Paragraph("Checklist Pré-Reunião", s_section))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BRAND,
                                spaceAfter=8, spaceBefore=0))

    checklist = [
        "□ Li o perfil da empresa e entendo o setor",
        "□ Sei quem é o interlocutor e como se comunica",
        "□ Tenho os pontos de dor mapeados",
        "□ Preparei perguntas de diagnóstico",
        "□ Sei quais produtos oferecer e por quê",
        "□ Tenho respostas prontas para objeções prováveis",
        "□ Defini o próximo passo que vou propor",
        "□ Testei o app 'Botão de Pânico' no celular",
    ]
    elements.append(Paragraph("<br/>".join(checklist), s_body))
    elements.append(Spacer(1, 1 * cm))

    # ===== RODAPÉ =====
    elements.append(HRFlowable(width="60%", thickness=0.5, color=GRAY,
                                spaceAfter=8, spaceBefore=16, hAlign="CENTER"))
    elements.append(Paragraph(
        "Gerado por 'Claro que Eu vendo!' — falagaiotto.com.br", s_footer))
    elements.append(Paragraph(
        "Este guia é confidencial e de uso exclusivo do vendedor.", s_footer))

    # --- Build ---
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    doc.build(elements)
    buf.seek(0)

    import unicodedata
    ascii_name = unicodedata.normalize("NFKD", pitch.company_name)
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', ascii_name).strip('_')
    safe_name = re.sub(r'_{2,}', '_', safe_name) or "empresa"
    filename = f"guia_vendedor_{safe_name}_{pitch.id}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )