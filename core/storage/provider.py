"""Storage abstraction layer for EvidenceOS.

Provides LocalStorageProvider for development/self-hosted deployments and
an ObjectStorageProvider interface for S3/GCS production environments.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from core.config import get_settings


class StorageProvider(ABC):
    """Abstract interface for preserving immutable original evidence artifacts."""

    @abstractmethod
    def save(self, case_id: str, evidence_id: str, safe_filename: str, content: bytes) -> str:
        """Store raw evidence bytes and return a canonical storage_key."""

    @abstractmethod
    def read(self, storage_key: str) -> bytes:
        """Retrieve raw evidence bytes by storage_key."""

    @abstractmethod
    def resolve_path(self, storage_key: str) -> Optional[Path]:
        """Return local filesystem Path if backed by local storage, else None."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Check if evidence exists in storage."""


class LocalFilesystemStorage(StorageProvider):
    """Stores original evidence files under a structured local directory hierarchy."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self.base_dir = (base_dir or settings.storage_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, storage_key: str) -> Path:
        candidate = (self.base_dir / storage_key).resolve()
        if not str(candidate).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal attempt blocked for storage_key: {storage_key}")
        return candidate

    def save(self, case_id: str, evidence_id: str, safe_filename: str, content: bytes) -> str:
        rel_key = f"{case_id}/{evidence_id}_{safe_filename}"
        target_path = self._safe_resolve(rel_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return rel_key

    def read(self, storage_key: str) -> bytes:
        target_path = self._safe_resolve(storage_key)
        if not target_path.exists():
            raise FileNotFoundError(f"Evidence artifact not found: {storage_key}")
        return target_path.read_bytes()

    def resolve_path(self, storage_key: str) -> Optional[Path]:
        return self._safe_resolve(storage_key)

    def exists(self, storage_key: str) -> bool:
        try:
            return self._safe_resolve(storage_key).exists()
        except ValueError:
            return False


def get_storage_provider() -> StorageProvider:
    return LocalFilesystemStorage()
