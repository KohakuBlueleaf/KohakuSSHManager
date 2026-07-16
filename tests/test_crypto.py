"""Crypto roundtrip, wrong-secret failure, and redaction."""

import pytest

from kohakusshmanager import crypto


def test_encrypt_decrypt_roundtrip():
    plaintext = b"-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n-----END OPENSSH PRIVATE KEY-----"
    nonce, ciphertext = crypto.encrypt(plaintext)
    assert crypto.decrypt(nonce, ciphertext) == plaintext


def test_decrypt_wrong_secret_fails():
    nonce, ciphertext = crypto.encrypt(b"payload", secret="secret-a")
    with pytest.raises(ValueError):
        crypto.decrypt(nonce, ciphertext, secret="secret-b")


def test_derive_key_is_stable_and_32_bytes():
    key1 = crypto.derive_key("same-secret")
    key2 = crypto.derive_key("same-secret")
    assert key1 == key2
    assert len(key1) == 32
    assert crypto.derive_key("other") != key1


def test_redact_strips_private_key_blocks():
    text = (
        "before\n-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "AAAAsecretmaterial\n-----END OPENSSH PRIVATE KEY-----\nafter"
    )
    redacted = crypto.redact(text)
    assert "secretmaterial" not in redacted
    assert "REDACTED PRIVATE KEY" in redacted
    assert redacted.startswith("before")
    assert redacted.endswith("after")


def test_missing_secret_raises():
    with pytest.raises(crypto.SecretUnavailable):
        crypto.encrypt(b"x", secret="")
