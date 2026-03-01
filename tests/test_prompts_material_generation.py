from __future__ import annotations

import unittest

from src.agent.prompts import build_material_generation_prompt


class BuildMaterialGenerationPromptTests(unittest.TestCase):
    def test_prompt_for_mcq_and_summary(self) -> None:
        prompt = build_material_generation_prompt(
            material_text="Materi tentang ekosistem.",
            generate_types=["mcq", "summary"],
            mcq_count=10,
            essay_count=3,
            summary_max_words=200,
            context="User suka contoh konkret.",
        )

        self.assertIn("Buat tepat 10 soal pilihan ganda.", prompt)
        self.assertIn("Ringkasan overview maksimal 200 kata.", prompt)
        self.assertNotIn("Buat tepat 3 soal essay.", prompt)
        self.assertIn('"mcq_quiz"', prompt)
        self.assertIn('"summary"', prompt)
        self.assertNotIn('"essay_quiz"', prompt)
        self.assertIn("User context:", prompt)
        self.assertIn("Materi:\nMateri tentang ekosistem.", prompt)

    def test_prompt_raises_for_empty_generate_types(self) -> None:
        with self.assertRaises(ValueError):
            build_material_generation_prompt(
                material_text="Materi tentang ekosistem.",
                generate_types=[],
                mcq_count=10,
                essay_count=3,
                summary_max_words=200,
                context="",
            )


if __name__ == "__main__":
    unittest.main()
