from __future__ import annotations

import importlib.util
import unittest

from src.agent.lkpd_pdf import render_lkpd_pdf
from src.agent.types import LkpdActivity, LkpdContent, LkpdRubricItem, MaterialInfo


class LkpdPdfTests(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec("reportlab") is not None,
        "reportlab is not installed",
    )
    def test_render_lkpd_pdf_returns_pdf_bytes(self) -> None:
        payload = render_lkpd_pdf(
            lkpd=LkpdContent(
                title="LKPD Ekosistem",
                learning_objectives=["Memahami ekosistem"],
                instructions=["Baca materi", "Kerjakan aktivitas"],
                activities=[
                    LkpdActivity(
                        activity_no=1,
                        task="Identifikasi komponen biotik",
                        expected_output="Daftar komponen biotik",
                        assessment_hint="Akurasi klasifikasi",
                    )
                ],
                worksheet_template="Nama/Kelas/Jawaban",
                assessment_rubric=[
                    LkpdRubricItem(
                        aspect="Konsep",
                        criteria="Ketepatan",
                        score_range="1-4",
                    )
                ],
            ),
            material=MaterialInfo(
                filename="materi.txt",
                file_type="txt",
                extracted_chars=120,
            ),
            document_id="doc-1",
        )

        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 100)


if __name__ == "__main__":
    unittest.main()
