from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from src.config import settings


@dataclass(slots=True)
class StoredLkpdPdf:
    file_id: str
    path: Path
    expires_at: datetime


class LkpdFileStorage:
    def __init__(self) -> None:
        self._base_dir = Path(settings.lkpd_pdf_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save_pdf(self, payload: bytes) -> StoredLkpdPdf:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_id = f"lkpd-{uuid4().hex}"
        pdf_path = self._pdf_path(file_id)
        meta_path = self._meta_path(file_id)
        expires_at = datetime.now(UTC) + timedelta(seconds=settings.lkpd_pdf_ttl_seconds)

        pdf_path.write_bytes(payload)
        meta_path.write_text(
            json.dumps({"file_id": file_id, "expires_at": expires_at.isoformat()}),
            encoding="utf-8",
        )
        return StoredLkpdPdf(file_id=file_id, path=pdf_path, expires_at=expires_at)

    def get_pdf_path(self, file_id: str) -> Path | None:
        meta = self._load_meta(file_id)
        if meta is None:
            return None

        expires_at = datetime.fromisoformat(str(meta["expires_at"]))
        if datetime.now(UTC) >= expires_at:
            self._delete_pair(file_id)
            return None

        pdf_path = self._pdf_path(file_id)
        if not pdf_path.exists():
            self._delete_pair(file_id)
            return None
        return pdf_path

    def cleanup_expired_files(self) -> int:
        removed = 0
        now = datetime.now(UTC)
        for meta_file in self._base_dir.glob("*.json"):
            file_id = meta_file.stem
            meta = self._load_meta(file_id)
            if not meta:
                self._delete_pair(file_id)
                removed += 1
                continue

            expires_at = datetime.fromisoformat(str(meta["expires_at"]))
            if now >= expires_at:
                self._delete_pair(file_id)
                removed += 1
        return removed

    def _load_meta(self, file_id: str) -> dict[str, str] | None:
        meta_path = self._meta_path(file_id)
        if not meta_path.exists():
            return None
        try:
            raw = meta_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return None
            if "expires_at" not in payload:
                return None
            return {"expires_at": str(payload["expires_at"])}
        except Exception:
            return None

    def _delete_pair(self, file_id: str) -> None:
        pdf_path = self._pdf_path(file_id)
        meta_path = self._meta_path(file_id)
        if pdf_path.exists():
            pdf_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

    def _pdf_path(self, file_id: str) -> Path:
        return self._base_dir / f"{file_id}.pdf"

    def _meta_path(self, file_id: str) -> Path:
        return self._base_dir / f"{file_id}.json"
