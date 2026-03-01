from __future__ import annotations


def build_lkpd_generation_prompt(
    *,
    material_text: str,
    activity_count: int,
    context: str,
) -> str:
    context_block = f"\n\nUser context:\n{context}" if context.strip() else ""
    return (
        "Kamu adalah asisten pendidikan. Baca materi dan hasilkan JSON valid saja.\n"
        "Jangan gunakan markdown, jangan gunakan kode blok.\n"
        "Schema output HARUS:\n"
        "{\n"
        '  "lkpd": {\n'
        '    "title": "...",\n'
        '    "learning_objectives": ["...", "..."],\n'
        '    "instructions": ["...", "..."],\n'
        '    "activities": [\n'
        '      {"activity_no": 1, "task": "...", "expected_output": "...", "assessment_hint": "..."}\n'
        "    ],\n"
        '    "worksheet_template": "...",\n'
        '    "assessment_rubric": [\n'
        '      {"aspect": "...", "criteria": "...", "score_range": "1-4"}\n'
        "    ]\n"
        "  }\n"
        "}\n"
        f"Buat tepat {activity_count} aktivitas pada field activities.\n"
        "Semua keluaran harus Bahasa Indonesia.\n"
        f"{context_block}\n\n"
        "Materi:\n"
        f"{material_text}"
    )
