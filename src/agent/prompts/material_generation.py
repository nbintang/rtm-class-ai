from __future__ import annotations

from src.agent.types import GenerateType


def _build_schema_lines(generate_types: list[GenerateType]) -> list[str]:
    lines: list[str] = []
    if "mcq" in generate_types:
        lines.append(
            '  "mcq_quiz": {"questions": [{"question": "...", "options": ["...", "...", "...", "..."], "correct_answer": "...", "explanation": "..."}]}'
        )
    if "essay" in generate_types:
        lines.append(
            '  "essay_quiz": {"questions": [{"question": "...", "expected_points": "..."}]}'
        )
    if "summary" in generate_types:
        lines.append(
            '  "summary": {"title": "...", "overview": "...", "key_points": ["...", "..."]}'
        )
    return lines


def build_material_generation_prompt(
    *,
    material_text: str,
    generate_types: list[GenerateType],
    mcq_count: int,
    essay_count: int,
    summary_max_words: int,
    context: str,
) -> str:
    if not generate_types:
        raise ValueError("generate_types must contain at least one item.")

    context_block = f"\n\nUser context:\n{context}" if context.strip() else ""
    schema_lines = _build_schema_lines(generate_types)
    schema_body = ",\n".join(schema_lines)

    requirements: list[str] = []
    if "mcq" in generate_types:
        requirements.append(f"Buat tepat {mcq_count} soal pilihan ganda.")
    if "essay" in generate_types:
        requirements.append(f"Buat tepat {essay_count} soal essay.")
    if "summary" in generate_types:
        requirements.append(f"Ringkasan overview maksimal {summary_max_words} kata.")

    requested_blocks = ", ".join(generate_types)
    requirement_block = "\n".join(requirements)
    return (
        "Kamu adalah asisten pendidikan. Baca materi dan hasilkan JSON valid saja.\n"
        "Jangan gunakan markdown, jangan gunakan kode blok.\n"
        f"Generate hanya blok berikut: {requested_blocks}.\n"
        "Schema output HARUS:\n"
        "{\n"
        f"{schema_body}\n"
        "}\n"
        f"{requirement_block}\n"
        "Semua keluaran harus Bahasa Indonesia.\n"
        f"{context_block}\n\n"
        "Materi:\n"
        f"{material_text}"
    )
