"""Webhook payload shaping per provider URL."""

from kohakusshmanager.webhook import _DISCORD_LIMIT, build_payload


def test_discord_url_gets_content_payload():
    payload = build_payload(
        "https://discord.com/api/webhooks/123/token",
        "app.startup",
        "KohakuSSHManager 0.1.0 started",
        {"version": "0.1.0"},
    )
    assert set(payload) == {"content"}
    assert "[app.startup]" in payload["content"]
    assert "KohakuSSHManager 0.1.0 started" in payload["content"]
    assert "version=0.1.0" in payload["content"]


def test_discord_content_is_truncated():
    payload = build_payload(
        "https://discordapp.com/api/webhooks/123/token",
        "test",
        "x" * 5000,
        {},
    )
    assert len(payload["content"]) <= _DISCORD_LIMIT


def test_slack_url_gets_text_payload():
    payload = build_payload(
        "https://hooks.slack.com/services/T0/B0/token",
        "test",
        "hello",
        {},
    )
    assert set(payload) == {"text"}
    assert "[test] hello" in payload["text"]


def test_other_url_gets_generic_payload():
    payload = build_payload("https://example.com/hook", "test", "hello", {"a": 1})
    assert set(payload) == {"event", "message", "data", "timestamp"}
    assert payload["event"] == "test"
    assert payload["data"] == {"a": 1}
    assert payload["timestamp"].endswith("Z")
