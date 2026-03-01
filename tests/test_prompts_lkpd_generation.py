from __future__ import annotations

import unittest

from src.agent.prompts import build_lkpd_generation_prompt


class BuildLkpdGenerationPromptTests(unittest.TestCase):
    def test_prompt_contains_activity_count_and_schema(self) -> None:
        prompt = build_lkpd_generation_prompt(
            material_text="Materi ekosistem dan rantai makanan.",
            activity_count=5,
            context="Kelas 8 SMP",
        )

        self.assertIn("Buat tepat 5 aktivitas", prompt)
        self.assertIn('"lkpd"', prompt)
        self.assertIn('"activities"', prompt)
        self.assertIn('"assessment_rubric"', prompt)
        self.assertIn("User context:", prompt)


if __name__ == "__main__":
    unittest.main()
