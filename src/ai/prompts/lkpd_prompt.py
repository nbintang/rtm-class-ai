def build_lkpd_prompt(source_text: str) -> str:
    return (
        "Create an LKPD (Lembar Kerja Peserta Didik) from the source text. "
        "Include goals, instructions, and student exercises.\n\n"
        f"Source Text:\n{source_text}"
    )

