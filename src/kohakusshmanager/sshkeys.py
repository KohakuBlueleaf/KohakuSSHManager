"""SSH public-key parsing, normalization, and fingerprinting.

Fingerprint format matches OpenSSH: ``SHA256:`` + base64(sha256(raw key bytes))
with trailing ``=`` padding stripped.
"""

import base64
import binascii
from dataclasses import dataclass
from hashlib import sha256

from cryptography.hazmat.primitives.serialization import load_ssh_public_key

from kohakusshmanager.errors import ValidationError

VALID_KEY_TYPES = {
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
}


@dataclass(frozen=True)
class ParsedKey:
    key_type: str
    blob: bytes
    comment: str
    normalized: str
    fingerprint: str


def compute_fingerprint(blob: bytes) -> str:
    digest = sha256(blob).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _first_field(blob: bytes) -> bytes:
    if len(blob) < 4:
        raise ValidationError("invalid public key: truncated key blob")
    length = int.from_bytes(blob[:4], "big")
    if len(blob) < 4 + length:
        raise ValidationError("invalid public key: bad length prefix")
    return blob[4 : 4 + length]


def parse_ssh_public_key(text: str) -> ParsedKey:
    """Parse and validate a single-line OpenSSH public key."""
    text = (text or "").strip()
    if not text:
        raise ValidationError("public key is empty")
    parts = text.split()
    if len(parts) < 2:
        raise ValidationError(
            "invalid public key: expected '<type> <base64> [comment]'"
        )
    key_type = parts[0]
    b64 = parts[1]
    comment = " ".join(parts[2:]) if len(parts) > 2 else ""

    if key_type not in VALID_KEY_TYPES:
        raise ValidationError(f"unsupported key type: {key_type}")

    try:
        blob = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("invalid base64 in public key") from exc

    inner = _first_field(blob)
    if inner.decode("ascii", "replace") != key_type:
        raise ValidationError("public key type does not match key data")

    # Soft cryptographic validation (sk-* keys may be unsupported by the lib).
    if not key_type.startswith("sk-"):
        try:
            load_ssh_public_key(f"{key_type} {b64}".encode("ascii"))
        except Exception as exc:  # soft-validate: reject anything the lib rejects
            raise ValidationError("public key failed cryptographic validation") from exc

    normalized = f"{key_type} {b64}" + (f" {comment}" if comment else "")
    return ParsedKey(
        key_type=key_type,
        blob=blob,
        comment=comment,
        normalized=normalized,
        fingerprint=compute_fingerprint(blob),
    )
