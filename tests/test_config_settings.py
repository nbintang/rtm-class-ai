from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config import _parse_hex_color, get_settings


class ConfigColorParsingTests(unittest.TestCase):
    def test_parse_hex_color_accepts_valid_6_digit(self) -> None:
        self.assertEqual(_parse_hex_color("#1f4e79", "#1F4E79"), "#1F4E79")

    def test_parse_hex_color_accepts_valid_3_digit(self) -> None:
        self.assertEqual(_parse_hex_color("ABC", "#1F4E79"), "#ABC")

    def test_parse_hex_color_fallback_on_invalid(self) -> None:
        self.assertEqual(_parse_hex_color("invalid", "#1F4E79"), "#1F4E79")

    def test_lkpd_header_title_defaults(self) -> None:
        with patch("src.config.load_dotenv", return_value=True):
            with patch.dict(os.environ, {}, clear=True):
                settings = get_settings()

        self.assertEqual(settings.lkpd_header_title_line1, "LEMBAR KERJA PESERTA DIDIK (LKPD)")
        self.assertEqual(settings.lkpd_header_title_line2, "SMARTER AI")
        self.assertEqual(settings.lkpd_header_title_line3, "")

    def test_lkpd_header_title_override(self) -> None:
        with patch("src.config.load_dotenv", return_value=True):
            with patch.dict(
                os.environ,
                {
                    "LKPD_HEADER_TITLE_LINE1": "BARIS 1",
                    "LKPD_HEADER_TITLE_LINE2": "BARIS 2",
                    "LKPD_HEADER_TITLE_LINE3": "BARIS 3",
                },
                clear=True,
            ):
                settings = get_settings()

        self.assertEqual(settings.lkpd_header_title_line1, "BARIS 1")
        self.assertEqual(settings.lkpd_header_title_line2, "BARIS 2")
        self.assertEqual(settings.lkpd_header_title_line3, "BARIS 3")


if __name__ == "__main__":
    unittest.main()
