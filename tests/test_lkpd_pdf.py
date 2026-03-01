from __future__ import annotations

import importlib.util
from io import BytesIO
import unittest
from unittest.mock import patch

from src.agent.lkpd_pdf import render_lkpd_pdf
from src.agent.types import LkpdActivity, LkpdContent, LkpdRubricItem, MaterialInfo


class LkpdPdfTests(unittest.TestCase):
    _HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None
    _HAS_PYPDF = importlib.util.find_spec("pypdf") is not None

    @staticmethod
    def _sample_lkpd(*, activity_count: int = 1) -> LkpdContent:
        return LkpdContent(
            title="LKPD Ekosistem",
            learning_objectives=["Memahami ekosistem"],
            instructions=["Baca materi", "Kerjakan aktivitas"],
            activities=[
                LkpdActivity(
                    activity_no=idx,
                    task=f"Aktivitas {idx}",
                    expected_output=f"Output {idx}",
                    assessment_hint=f"Hint {idx}",
                )
                for idx in range(1, activity_count + 1)
            ],
            worksheet_template="Nama/Kelas/Jawaban",
            assessment_rubric=[
                LkpdRubricItem(
                    aspect="Konsep",
                    criteria="Ketepatan",
                    score_range="1-4",
                )
            ],
        )

    @staticmethod
    def _sample_material() -> MaterialInfo:
        return MaterialInfo(
            filename="materi.txt",
            file_type="txt",
            extracted_chars=120,
        )

    @staticmethod
    def _extract_pages_text(payload: bytes) -> list[str]:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(payload))
        return [(page.extract_text() or "") for page in reader.pages]

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab is not installed")
    def test_render_lkpd_pdf_returns_pdf_bytes(self) -> None:
        payload = render_lkpd_pdf(
            lkpd=self._sample_lkpd(activity_count=1),
            material=self._sample_material(),
            document_id="doc-1",
        )

        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 100)

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab is not installed")
    def test_render_lkpd_pdf_fallback_without_logo(self) -> None:
        with patch("src.agent.lkpd_pdf.settings.lkpd_header_logo_path", ".assets/lkpd/not-found.png"):
            payload = render_lkpd_pdf(
                lkpd=self._sample_lkpd(activity_count=2),
                material=self._sample_material(),
                document_id="doc-2",
            )

        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 100)

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab is not installed")
    def test_render_lkpd_pdf_invalid_accent_color_fallback(self) -> None:
        with patch("src.agent.lkpd_pdf.settings.lkpd_header_accent_hex", "NOT-A-HEX"):
            payload = render_lkpd_pdf(
                lkpd=self._sample_lkpd(activity_count=2),
                material=self._sample_material(),
                document_id="doc-3",
            )

        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 100)

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab is not installed")
    def test_render_lkpd_pdf_multi_page_with_header_callback(self) -> None:
        payload = render_lkpd_pdf(
            lkpd=self._sample_lkpd(activity_count=20),
            material=self._sample_material(),
            document_id="doc-4",
        )

        self.assertTrue(payload.startswith(b"%PDF"))
        self.assertGreater(len(payload), 2000)

    @unittest.skipUnless(_HAS_REPORTLAB and _HAS_PYPDF, "reportlab/pypdf is not installed")
    def test_first_page_has_identity_and_metadata_later_pages_do_not(self) -> None:
        payload = render_lkpd_pdf(
            lkpd=self._sample_lkpd(activity_count=60),
            material=self._sample_material(),
            document_id="doc-5",
        )
        pages = self._extract_pages_text(payload)

        self.assertGreaterEqual(len(pages), 2)
        first_page = pages[0]
        second_page = pages[1]

        self.assertIn("Document ID: doc-5", first_page)
        self.assertIn("Sumber: materi.txt (txt)", first_page)
        self.assertIn("Nama:", first_page)
        self.assertIn("NIS:", first_page)
        self.assertIn("Kelas:", first_page)
        self.assertIn("Tanggal:", first_page)

        self.assertIn("LEMBAR KERJA PESERTA DIDIK (LKPD)", second_page)
        self.assertIn("SMARTER AI", second_page)
        self.assertNotIn("Document ID:", second_page)
        self.assertNotIn("Sumber:", second_page)
        self.assertNotIn("Nama:", second_page)
        self.assertNotIn("NIS:", second_page)
        self.assertNotIn("Kelas:", second_page)
        self.assertNotIn("Tanggal:", second_page)

    @unittest.skipUnless(_HAS_REPORTLAB, "reportlab is not installed")
    def test_render_lkpd_pdf_with_empty_title_line3(self) -> None:
        with patch("src.agent.lkpd_pdf.settings.lkpd_header_title_line3", ""):
            payload = render_lkpd_pdf(
                lkpd=self._sample_lkpd(activity_count=3),
                material=self._sample_material(),
                document_id="doc-6",
            )

        self.assertTrue(payload.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
