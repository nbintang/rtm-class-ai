from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from src.agent.types import LkpdContent, MaterialInfo
from src.config import settings

_HEADER_HEIGHT = 74
_FIRST_PAGE_EXTRAS_HEIGHT = 106


def _resolve_logo_path() -> str | None:
    raw = settings.lkpd_header_logo_path.strip()
    if not raw:
        return None

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.exists() and candidate.is_file():
        return str(candidate)
    return None


def _draw_student_identity_block(canvas: Any, doc: Any, y_top: float) -> None:
    from reportlab.lib import colors

    box_x = doc.leftMargin
    box_w = doc.pagesize[0] - doc.leftMargin - doc.rightMargin
    box_h = 44
    box_y = y_top - box_h
    mid_x = box_x + (box_w / 2)
    row_y = box_y + (box_h / 2)

    canvas.setStrokeColor(colors.HexColor("#7A869A"))
    canvas.setLineWidth(0.8)
    canvas.roundRect(box_x, box_y, box_w, box_h, 4, stroke=1, fill=0)
    canvas.line(mid_x, box_y, mid_x, box_y + box_h)
    canvas.line(box_x, row_y, box_x + box_w, row_y)

    canvas.setFillColor(colors.HexColor("#2B2D42"))
    canvas.setFont("Helvetica", 9)
    canvas.drawString(box_x + 8, row_y + 5, "Nama:")
    canvas.drawString(mid_x + 8, row_y + 5, "NIS:")
    canvas.drawString(box_x + 8, box_y + 5, "Kelas:")
    canvas.drawString(mid_x + 8, box_y + 5, "Tanggal:")


def _draw_header_brand(
    canvas: Any,
    doc: Any,
    *,
    logo_path: str | None,
    accent_color: Any,
    title_line1: str,
    title_line2: str,
    title_line3: str,
) -> None:
    from reportlab.lib import colors

    page_w, page_h = doc.pagesize
    header_y = page_h - _HEADER_HEIGHT

    canvas.saveState()

    canvas.setFillColor(accent_color)
    canvas.rect(0, header_y, page_w, _HEADER_HEIGHT, stroke=0, fill=1)
    canvas.setStrokeColor(colors.HexColor("#D1D5DB"))
    canvas.setLineWidth(0.5)
    canvas.line(0, header_y, page_w, header_y)

    logo_x = doc.leftMargin
    logo_y = header_y + 12
    logo_size = _HEADER_HEIGHT - 24
    if logo_path:
        try:
            canvas.drawImage(
                logo_path,
                logo_x,
                logo_y,
                width=logo_size,
                height=logo_size,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    title_lines = [title_line1.strip(), title_line2.strip()]
    third_line = title_line3.strip()
    if third_line:
        title_lines.append(third_line)

    y_start = page_h - 24
    for idx, line in enumerate(title_lines):
        if idx == 0:
            canvas.setFont("Helvetica-Bold", 12)
        elif idx == 1:
            canvas.setFont("Helvetica-Bold", 11)
        else:
            canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(colors.white)
        canvas.drawCentredString(page_w / 2, y_start - (idx * 15), line)

    canvas.restoreState()


def _draw_first_page_extras(
    canvas: Any,
    doc: Any,
    *,
    material: MaterialInfo,
    document_id: str,
) -> None:
    from reportlab.lib import colors

    page_h = doc.pagesize[1]
    extras_top = page_h - _HEADER_HEIGHT - 10

    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#374151"))
    canvas.setFont("Helvetica", 9)
    canvas.drawString(doc.leftMargin, extras_top - 12, f"Document ID: {document_id}")
    canvas.drawString(
        doc.leftMargin,
        extras_top - 25,
        f"Sumber: {material.filename} ({material.file_type})",
    )
    _draw_student_identity_block(canvas, doc, y_top=extras_top - 34)
    canvas.restoreState()


def _draw_first_page(
    canvas: Any,
    doc: Any,
    *,
    material: MaterialInfo,
    document_id: str,
    logo_path: str | None,
    accent_color: Any,
    title_line1: str,
    title_line2: str,
    title_line3: str,
) -> None:
    _draw_header_brand(
        canvas,
        doc,
        logo_path=logo_path,
        accent_color=accent_color,
        title_line1=title_line1,
        title_line2=title_line2,
        title_line3=title_line3,
    )
    _draw_first_page_extras(canvas, doc, material=material, document_id=document_id)


def _draw_later_page(
    canvas: Any,
    doc: Any,
    *,
    logo_path: str | None,
    accent_color: Any,
    title_line1: str,
    title_line2: str,
    title_line3: str,
) -> None:
    _draw_header_brand(
        canvas,
        doc,
        logo_path=logo_path,
        accent_color=accent_color,
        title_line1=title_line1,
        title_line2=title_line2,
        title_line3=title_line3,
    )


def render_lkpd_pdf(
    *,
    lkpd: LkpdContent,
    material: MaterialInfo,
    document_id: str,
) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer
    except ImportError as exc:
        raise RuntimeError("reportlab package is required for LKPD PDF rendering.") from exc

    try:
        accent_color = colors.HexColor(settings.lkpd_header_accent_hex)
    except Exception:
        accent_color = colors.HexColor("#1F4E79")
    logo_path = _resolve_logo_path()
    title_line1 = settings.lkpd_header_title_line1.strip() or "LEMBAR KERJA PESERTA DIDIK (LKPD)"
    title_line2 = settings.lkpd_header_title_line2.strip() or "SMARTER AI"
    title_line3 = settings.lkpd_header_title_line3.strip()

    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    page_w, page_h = A4
    frame_width = page_w - doc.leftMargin - doc.rightMargin

    first_frame_top = page_h - _HEADER_HEIGHT - _FIRST_PAGE_EXTRAS_HEIGHT - 12
    first_frame_height = first_frame_top - doc.bottomMargin
    first_frame = Frame(
        x1=doc.leftMargin,
        y1=doc.bottomMargin,
        width=frame_width,
        height=first_frame_height,
        id="lkpd-first-frame",
        showBoundary=0,
    )

    later_frame_top = page_h - _HEADER_HEIGHT - 12
    later_frame_height = later_frame_top - doc.bottomMargin
    later_frame = Frame(
        x1=doc.leftMargin,
        y1=doc.bottomMargin,
        width=frame_width,
        height=later_frame_height,
        id="lkpd-later-frame",
        showBoundary=0,
    )

    first_template = PageTemplate(
        id="lkpd-first-page",
        frames=[first_frame],
        autoNextPageTemplate="lkpd-later-page",
        onPage=lambda canvas, page_doc: _draw_first_page(
            canvas,
            page_doc,
            material=material,
            document_id=document_id,
            logo_path=logo_path,
            accent_color=accent_color,
            title_line1=title_line1,
            title_line2=title_line2,
            title_line3=title_line3,
        ),
    )
    later_template = PageTemplate(
        id="lkpd-later-page",
        frames=[later_frame],
        onPage=lambda canvas, page_doc: _draw_later_page(
            canvas,
            page_doc,
            logo_path=logo_path,
            accent_color=accent_color,
            title_line1=title_line1,
            title_line2=title_line2,
            title_line3=title_line3,
        ),
    )
    doc.addPageTemplates([first_template, later_template])

    styles = getSampleStyleSheet()

    elements = [
        Paragraph(lkpd.title, styles["Title"]),
        Spacer(1, 8),
        Paragraph("Tujuan Pembelajaran", styles["Heading2"]),
    ]
    for idx, item in enumerate(lkpd.learning_objectives, start=1):
        elements.append(Paragraph(f"{idx}. {item}", styles["Normal"]))

    elements.extend([Spacer(1, 12), Paragraph("Petunjuk", styles["Heading2"])])
    for idx, item in enumerate(lkpd.instructions, start=1):
        elements.append(Paragraph(f"{idx}. {item}", styles["Normal"]))

    elements.extend([Spacer(1, 12), Paragraph("Aktivitas", styles["Heading2"])])
    for activity in lkpd.activities:
        elements.append(
            Paragraph(
                f"{activity.activity_no}. {activity.task}",
                styles["Heading3"],
            )
        )
        elements.append(Paragraph(f"Output: {activity.expected_output}", styles["Normal"]))
        elements.append(Paragraph(f"Hint Penilaian: {activity.assessment_hint}", styles["Normal"]))
        elements.append(Spacer(1, 6))

    elements.extend([Spacer(1, 12), Paragraph("Template Lembar Jawaban", styles["Heading2"])])
    elements.append(Paragraph(lkpd.worksheet_template, styles["Normal"]))

    elements.extend([Spacer(1, 12), Paragraph("Rubrik Penilaian", styles["Heading2"])])
    for idx, rubric in enumerate(lkpd.assessment_rubric, start=1):
        elements.append(
            Paragraph(
                f"{idx}. {rubric.aspect} - {rubric.criteria} (Skor: {rubric.score_range})",
                styles["Normal"],
            )
        )

    doc.build(elements)
    return buffer.getvalue()
