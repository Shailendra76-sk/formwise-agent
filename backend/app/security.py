from __future__ import annotations

import hashlib
from pathlib import Path

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_upload(filename: str, content_type: str, size_bytes: int, max_size: int) -> None:
    if not filename or Path(filename).name != filename:
        raise ValueError("invalid filename")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("unsupported document type")
    if size_bytes <= 0 or size_bytes > max_size:
        raise ValueError("document size is outside the allowed range")
