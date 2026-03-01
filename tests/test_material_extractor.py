from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agent.material_extractor import extract_material_text


class MaterialExtractorTests(unittest.TestCase):
    def test_txt_extract_success(self) -> None:
        text, file_type, warnings = extract_material_text(
            filename="materi.txt",
            content_type="text/plain",
            payload=b"Halo siswa kelas 8",
        )
        self.assertEqual(file_type, "txt")
        self.assertEqual(text, "Halo siswa kelas 8")
        self.assertEqual(warnings, [])

    def test_unsupported_extension_raises(self) -> None:
        with self.assertRaises(ValueError):
            extract_material_text(
                filename="materi.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                payload=b"x",
            )

    @patch("src.agent.material_extractor.extract_text_from_pdf")
    def test_pdf_path_is_used(self, mock_extract_pdf) -> None:
        mock_extract_pdf.return_value = "konten pdf"
        text, file_type, warnings = extract_material_text(
            filename="materi.pdf",
            content_type="application/pdf",
            payload=b"%PDF",
        )
        self.assertEqual(file_type, "pdf")
        self.assertEqual(text, "konten pdf")
        self.assertEqual(warnings, [])

    @patch("src.agent.material_extractor.extract_text_from_pptx")
    def test_pptx_path_is_used(self, mock_extract_pptx) -> None:
        mock_extract_pptx.return_value = "konten pptx"
        text, file_type, warnings = extract_material_text(
            filename="materi.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            payload=b"PPTX",
        )
        self.assertEqual(file_type, "pptx")
        self.assertEqual(text, "konten pptx")
        self.assertEqual(warnings, [])

    def test_does_not_truncate_text(self) -> None:
        text, file_type, warnings = extract_material_text(
            filename="materi.txt",
            content_type="text/plain",
            payload=b"1234567890",
        )
        self.assertEqual(file_type, "txt")
        self.assertEqual(text, "1234567890")
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
