from __future__ import annotations

from pathlib import Path


class PrivateStorage:
    """Minimal storage boundary; public URLs are deliberately unsupported."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def key_path(self, user_id: str, storage_key: str) -> Path:
        candidate = (self.root / user_id / storage_key).resolve()
        user_root = (self.root / user_id).resolve()
        if candidate != user_root and user_root not in candidate.parents:
            raise ValueError("invalid storage key")
        return candidate

    def save(self, user_id: str, storage_key: str, data: bytes) -> Path:
        path = self.key_path(user_id, storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def read(self, user_id: str, storage_key: str) -> bytes:
        return self.key_path(user_id, storage_key).read_bytes()

    def delete(self, user_id: str, storage_key: str) -> None:
        path = self.key_path(user_id, storage_key)
        if path.exists():
            path.unlink()
