from __future__ import annotations

import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CredentialDecryptionError(RuntimeError):
    """Raised when an encrypted admin credential cannot be decrypted safely."""


def decrypt_admin_api_key(ciphertext: Any) -> Any:
    """Decrypt an application-layer encrypted admin_api_keys value.

    FORMwise stores provider credentials as Fernet ciphertext. The key is supplied only
    through the process environment and is never persisted in the database.
    JSON credential payloads are intentionally left to the caller because this helper
    returns the decrypted string exactly as stored.
    """
    if ciphertext is None or ciphertext == "":
        raise CredentialDecryptionError("encrypted credential is empty")
    key = os.getenv("FORMWISE_CREDENTIAL_ENCRYPTION_KEY", "").strip()
    if not key:
        raise CredentialDecryptionError("FORMWISE_CREDENTIAL_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode("utf-8")).decrypt(str(ciphertext).encode("utf-8")).decode("utf-8")
    except (ValueError, InvalidToken) as exc:
        raise CredentialDecryptionError("admin credential decryption failed") from exc
