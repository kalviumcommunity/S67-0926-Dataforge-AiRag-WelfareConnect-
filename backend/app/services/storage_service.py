"""
Storage Service abstraction.
Handles saving and retrieving raw document files from local disk or cloud object storage.
"""

import os
from pathlib import Path
from typing import Optional
from backend.app.config import settings


class StorageService:
    @staticmethod
    def _resolve_local_path(storage_key: str) -> Path:
        """Resolve storage key to a secure local file path."""
        # Sanitize storage key
        clean_key = storage_key.strip().replace("\\", "/").lstrip("/")
        base_dir = Path(settings.LOCAL_STORAGE_PATH).resolve()
        target_path = (base_dir / clean_key).resolve()

        # Prevent directory traversal attacks
        if not str(target_path).startswith(str(base_dir)):
            raise ValueError(f"Invalid storage key path: {storage_key}")

        return target_path

    @classmethod
    def save_file(cls, storage_key: str, content: bytes) -> str:
        """
        Save binary document content to storage.
        Returns the confirmed storage key.
        """
        target_path = cls._resolve_local_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(content)
        return storage_key

    @classmethod
    def download_file(cls, storage_key: str) -> bytes:
        """
        Download/retrieve binary content for a given storage key.
        Raises FileNotFoundError if file is missing.
        """
        target_path = cls._resolve_local_path(storage_key)
        if not target_path.exists():
            raise FileNotFoundError(f"Storage file not found: {storage_key} at {target_path}")
        with open(target_path, "rb") as f:
            return f.read()

    @classmethod
    def get_file_path(cls, storage_key: str) -> str:
        """Get absolute filesystem path for local storage."""
        target_path = cls._resolve_local_path(storage_key)
        return str(target_path)

    @classmethod
    def file_exists(cls, storage_key: str) -> bool:
        """Check if file exists in storage."""
        try:
            target_path = cls._resolve_local_path(storage_key)
            return target_path.exists()
        except Exception:
            return False

    @classmethod
    def delete_file(cls, storage_key: str) -> bool:
        """Remove file from storage."""
        try:
            target_path = cls._resolve_local_path(storage_key)
            if target_path.exists():
                target_path.unlink()
                return True
            return False
        except Exception:
            return False


storage_service = StorageService()
