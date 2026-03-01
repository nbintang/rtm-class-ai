from __future__ import annotations

from io import BytesIO

from src.agent.types import LkpdContent, MaterialInfo


def render_lkpd_pdf(
    *,
    lkpd: LkpdContent,
    material: MaterialInfo,
    document_id: str,
) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("reportlab package is required for LKPD PDF rendering.") from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    elements = [
        Paragraph(lkpd.title, styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"Document ID: {document_id}", styles["Normal"]),
        Paragraph(f"Sumber: {material.filename} ({material.file_type})", styles["Normal"]),
        Spacer(1, 12),
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
