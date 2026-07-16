"""Zero-config first-run secret provisioning."""

from kohakusshmanager.config import cfg, ensure_secrets


def test_env_secrets_take_precedence_and_write_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg.app, "db_path", str(tmp_path / "ksm.db"))
    info = ensure_secrets()
    assert info["secret_source"] == "env"
    assert info["admin_token_source"] == "env"
    # Nothing persisted when env provides both.
    assert not (tmp_path / "secret.key").exists()
    assert not (tmp_path / "admin_token.txt").exists()


def test_generates_and_persists_then_reuses(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg.app, "db_path", str(tmp_path / "ksm.db"))
    monkeypatch.setattr(cfg.auth, "secret", None)
    monkeypatch.setattr(cfg.auth, "admin_token", None)

    info = ensure_secrets()
    assert info["secret_source"] == "generated"
    assert info["admin_token_source"] == "generated"
    secret_file = tmp_path / "secret.key"
    token_file = tmp_path / "admin_token.txt"
    assert secret_file.is_file() and token_file.is_file()
    generated_secret = cfg.auth.secret
    generated_token = cfg.auth.admin_token
    assert generated_secret and generated_token
    assert generated_secret != generated_token

    # Reuse: a second run (fresh None values) reads the same files back.
    monkeypatch.setattr(cfg.auth, "secret", None)
    monkeypatch.setattr(cfg.auth, "admin_token", None)
    info2 = ensure_secrets()
    assert info2["secret_source"] == "file"
    assert info2["admin_token_source"] == "file"
    assert cfg.auth.secret == generated_secret
    assert cfg.auth.admin_token == generated_token
