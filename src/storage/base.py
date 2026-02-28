from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def upload_bytes(self, key: str, content: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        raise NotImplementedError

