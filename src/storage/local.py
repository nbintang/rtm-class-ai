from pathlib import Path

from src.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upload_bytes(self, key: str, content: bytes) -> str:
        destination = self.base_path / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return str(destination)

    def download_bytes(self, key: str) -> bytes:
        source = self.base_path / key
        return source.read_bytes()

