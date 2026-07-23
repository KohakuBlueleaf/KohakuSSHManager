"""Zero-config first-run secret provisioning, .env loading, startup webhook."""

import os

from kohakusshmanager import __version__, webhook
from kohakusshmanager import app as app_module
from kohakusshmanager.config import (
    _load_dotenv,
    _parse_env_file,
    cfg,
    ensure_secrets,
)


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


# --- .env parsing ----------------------------------------------------------


def test_parse_env_strips_quotes_and_ignores_comments():
    text = (
        "# a full-line comment\n"
        "\n"
        "KSM_HOST=example.com\n"
        "export KSM_PORT=9000\n"
        'KSM_WEBHOOK_URL="https://hook.example/abc"\n'
        "KSM_SECRET='quoted secret'\n"
        "  KSM_LOG_LEVEL = DEBUG \n"
        "MALFORMED LINE WITHOUT EQUALS\n"
        "=missingkey\n"
    )
    parsed = _parse_env_file(text)
    assert parsed["KSM_HOST"] == "example.com"
    assert parsed["KSM_PORT"] == "9000"  # leading `export ` tolerated
    assert parsed["KSM_WEBHOOK_URL"] == "https://hook.example/abc"  # dquotes stripped
    assert parsed["KSM_SECRET"] == "quoted secret"  # squotes stripped
    assert parsed["KSM_LOG_LEVEL"] == "DEBUG"  # surrounding whitespace stripped
    assert "MALFORMED LINE WITHOUT EQUALS" not in parsed
    assert "" not in parsed  # empty key skipped


def test_load_dotenv_real_env_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KSM_TEST_FROM_FILE=file-value\nKSM_TEST_OVERRIDDEN=file-value\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KSM_ENV_FILE", str(env_file))
    monkeypatch.setenv("KSM_TEST_OVERRIDDEN", "real-env-value")
    monkeypatch.delenv("KSM_TEST_FROM_FILE", raising=False)
    try:
        _load_dotenv()
        # File value fills in an unset variable...
        assert os.environ["KSM_TEST_FROM_FILE"] == "file-value"
        # ...but a real environment variable is never overwritten.
        assert os.environ["KSM_TEST_OVERRIDDEN"] == "real-env-value"
    finally:
        os.environ.pop("KSM_TEST_FROM_FILE", None)


def test_load_dotenv_missing_file_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("KSM_ENV_FILE", str(tmp_path / "does-not-exist.env"))
    _load_dotenv()  # must not raise


# --- startup webhook -------------------------------------------------------


def test_announce_startup_sends_when_configured(monkeypatch):
    sent = []

    def fake_send(event, message, data=None):
        sent.append((event, message, data))
        return {"delivered": True}

    monkeypatch.setattr(app_module.webhook, "send", fake_send)
    monkeypatch.setattr(cfg.webhook, "url", "https://hook.example/x")
    monkeypatch.setattr(cfg.app, "host", "0.0.0.0")
    monkeypatch.setattr(cfg.app, "port", 8123)

    app_module._announce_startup()

    assert len(sent) == 1
    event, message, data = sent[0]
    assert event == "app.startup"
    assert event in webhook.EVENTS
    assert __version__ in message
    assert "0.0.0.0:8123" in message
    assert data["version"] == __version__
    assert data["host"] == "0.0.0.0"
    assert data["port"] == 8123


def test_announce_startup_skips_when_no_url(monkeypatch):
    sent = []
    monkeypatch.setattr(app_module.webhook, "send", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(cfg.webhook, "url", "")

    app_module._announce_startup()

    assert sent == []
