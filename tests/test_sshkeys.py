"""SSH public-key parsing, normalization, and fingerprinting."""

import pytest

from kohakusshmanager.errors import ValidationError
from kohakusshmanager.sshkeys import compute_fingerprint, parse_ssh_public_key

from .conftest import make_pubkey


def test_parse_valid_ed25519():
    key = make_pubkey("alice@laptop")
    parsed = parse_ssh_public_key(key)
    assert parsed.key_type == "ssh-ed25519"
    assert parsed.comment == "alice@laptop"
    assert parsed.fingerprint.startswith("SHA256:")
    assert "=" not in parsed.fingerprint  # padding stripped


def test_normalization_strips_and_preserves_comment():
    key = make_pubkey("kohaku")
    parsed = parse_ssh_public_key("   " + key + "   ")
    assert parsed.normalized.endswith(" kohaku")
    assert parsed.normalized.startswith("ssh-ed25519 ")


def test_fingerprint_stable():
    key = make_pubkey("x")
    a = parse_ssh_public_key(key)
    b = parse_ssh_public_key(key)
    assert a.fingerprint == b.fingerprint == compute_fingerprint(a.blob)


def test_reject_unknown_type():
    with pytest.raises(ValidationError):
        parse_ssh_public_key("ssh-magic AAAAB3Nz comment")


def test_reject_bad_base64():
    with pytest.raises(ValidationError):
        parse_ssh_public_key("ssh-ed25519 not_base64!!! comment")


def test_reject_empty():
    with pytest.raises(ValidationError):
        parse_ssh_public_key("")


def test_reject_type_mismatch():
    # Valid rsa blob announced as ed25519 -> internal type field mismatch.
    good = make_pubkey("c")
    b64 = good.split()[1]
    with pytest.raises(ValidationError):
        parse_ssh_public_key(f"ssh-rsa {b64} c")
