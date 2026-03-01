from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agent.lkpd_storage import LkpdFileStorage


class LkpdFileStorageTests(unittest.TestCase):
    def test_save_pdf_writes_pdf_and_metadata(self) -> None:
        with patch("src.agent.lkpd_storage.Path.mkdir", return_value=None):
            storage = LkpdFileStorage()
        storage._base_dir = Mock()
        storage._base_dir.mkdir = Mock()

        pdf_path = Mock()
        meta_path = Mock()
        storage._pdf_path = Mock(return_value=pdf_path)  # type: ignore[method-assign]
        storage._meta_path = Mock(return_value=meta_path)  # type: ignore[method-assign]

        stored = storage.save_pdf(b"%PDF-1.4 test")

        self.assertTrue(stored.file_id.startswith("lkpd-"))
        pdf_path.write_bytes.assert_called_once()
        meta_path.write_text.assert_called_once()

    def test_get_pdf_path_returns_none_when_expired(self) -> None:
        with patch("src.agent.lkpd_storage.Path.mkdir", return_value=None):
            storage = LkpdFileStorage()

        storage._load_meta = Mock(  # type: ignore[method-assign]
            return_value={"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
        )
        pdf_path = Mock()
        pdf_path.exists.return_value = True
        storage._pdf_path = Mock(return_value=pdf_path)  # type: ignore[method-assign]
        storage._delete_pair = Mock()  # type: ignore[method-assign]

        path = storage.get_pdf_path("lkpd-1")

        self.assertIsNone(path)
        storage._delete_pair.assert_called_once_with("lkpd-1")

    def test_get_pdf_path_returns_path_when_valid(self) -> None:
        with patch("src.agent.lkpd_storage.Path.mkdir", return_value=None):
            storage = LkpdFileStorage()

        storage._load_meta = Mock(  # type: ignore[method-assign]
            return_value={"expires_at": (datetime.now(UTC) + timedelta(seconds=60)).isoformat()}
        )
        pdf_path = Mock()
        pdf_path.exists.return_value = True
        storage._pdf_path = Mock(return_value=pdf_path)  # type: ignore[method-assign]

        path = storage.get_pdf_path("lkpd-1")

        self.assertEqual(path, pdf_path)

    def test_cleanup_expired_files_removes_only_expired_items(self) -> None:
        with patch("src.agent.lkpd_storage.Path.mkdir", return_value=None):
            storage = LkpdFileStorage()

        storage._base_dir = SimpleNamespace(
            glob=lambda _: [SimpleNamespace(stem="expired"), SimpleNamespace(stem="active")]
        )
        storage._load_meta = Mock(  # type: ignore[method-assign]
            side_effect=[
                {"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()},
                {"expires_at": (datetime.now(UTC) + timedelta(seconds=60)).isoformat()},
            ]
        )
        storage._delete_pair = Mock()  # type: ignore[method-assign]

        removed = storage.cleanup_expired_files()

        self.assertEqual(removed, 1)
        storage._delete_pair.assert_called_once_with("expired")


if __name__ == "__main__":
    unittest.main()
