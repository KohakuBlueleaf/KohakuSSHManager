"""Authenticated encryption for the SSH management private key.

Key = HKDF-SHA256(deployment secret). Cipher = AES-256-GCM with a random
12-byte nonce. The plaintext private key is never logged, serialized, or
returned to clients; ``redact`` scrubs PEM private-key blocks from any text
that does flow to logs.
"""

import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from kohakusshmanager.config import cfg

_HKDF_SALT = b"kohakusshmanager"
_HKDF_INFO = b"management-key-v1"
_NONCE_LEN = 12

_PEM_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)


class SecretUnavailable(RuntimeError):
    """Raised when a management-key operation is attempted without KSM_SECRET."""


def derive_key(secret: str) -> bytes:
    """Derive a fixed 32-byte AES key from the deployment secret."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    )
    return hkdf.derive(secret.encode("utf-8"))


def _key(secret: str | None) -> bytes:
    secret = secret if secret is not None else cfg.auth.secret
    if not secret:
        raise SecretUnavailable(
            "deployment secret (KSM_SECRET) is not configured; "
            "management-key operations are unavailable"
        )
    return derive_key(secret)


def encrypt(plaintext: bytes, secret: str | None = None) -> tuple[bytes, bytes]:
    """Return (nonce, ciphertext) for ``plaintext`` under the deployment secret."""
    import os

    aes = AESGCM(_key(secret))
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = aes.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def decrypt(nonce: bytes, ciphertext: bytes, secret: str | None = None) -> bytes:
    """Decrypt ciphertext; raise a clear error if the secret changed."""
    aes = AESGCM(_key(secret))
    try:
        return aes.decrypt(bytes(nonce), bytes(ciphertext), None)
    except InvalidTag as exc:
        raise ValueError(
            "deployment secret changed or management key data corrupted"
        ) from exc


def redact(text: str) -> str:
    """Strip PEM private-key blocks from text destined for logs/errors."""
    if not text or "PRIVATE KEY" not in text:
        return text
    return _PEM_BLOCK.sub("[REDACTED PRIVATE KEY]", text)
