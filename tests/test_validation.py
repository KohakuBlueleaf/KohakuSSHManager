"""Username, group, and path validation."""

from kohakusshmanager import remote


def test_valid_usernames():
    assert remote.valid_username("alice")
    assert remote.valid_username("_svc")
    assert remote.valid_username("user-01")
    assert remote.valid_username("a" * 32)


def test_invalid_usernames():
    assert not remote.valid_username("")
    assert not remote.valid_username("1alice")  # cannot start with digit
    assert not remote.valid_username("Alice")  # uppercase
    assert not remote.valid_username("a b")  # space
    assert not remote.valid_username("a;rm")  # metachar
    assert not remote.valid_username("a" * 33)  # too long


def test_valid_groups():
    assert remote.valid_group("docker")
    assert remote.valid_group("sudo")
    assert not remote.valid_group("bad group")


def test_valid_paths():
    assert remote.valid_path("/data")
    assert remote.valid_path("/mnt/nas1/share")


def test_invalid_paths():
    assert not remote.valid_path("relative/path")
    assert not remote.valid_path("/etc/../secret")
    assert not remote.valid_path("/data; rm -rf /")
    assert not remote.valid_path("/data with space")
    assert not remote.valid_path("/data$(whoami)")
    assert not remote.valid_path("")


def test_require_helpers_raise():
    import pytest

    from kohakusshmanager.errors import ValidationError

    with pytest.raises(ValidationError):
        remote.require_username("1bad")
    with pytest.raises(ValidationError):
        remote.require_path("../x")
