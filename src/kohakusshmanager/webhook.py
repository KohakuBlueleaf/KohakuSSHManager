"""Best-effort webhook notifications (one URL, one attempt, logged result).

The payload shape adapts to the configured URL: Discord and Slack incoming
webhooks reject foreign JSON, so those get their native format; every other
URL receives the generic ``{event, message, data, timestamp}`` document.
"""

from datetime import datetime, timezone

import httpx

from kohakusshmanager.config import cfg
from kohakusshmanager.crypto import redact
from kohakusshmanager.logger import get_logger

logger = get_logger("WEBHOOK")

EVENTS = {
    "app.startup",
    "access_request.pending",
    "access_request.approved",
    "access_request.revoked",
    "machine.unreachable",
    "action.failed",
    "init.failed",
    "scan.failed",
    "test",
}

# Discord caps `content` at 2000 characters.
_DISCORD_LIMIT = 2000


def _format_text(event: str, message: str, data: dict) -> str:
    """One human-readable chat line: event tag, message, compact data."""
    text = f"[{event}] {message}"
    details = ", ".join(f"{k}={v}" for k, v in data.items())
    if details:
        text += f"\n{details}"
    return text


def build_payload(url: str, event: str, message: str, data: dict) -> dict:
    """Shape the payload for the webhook provider the URL points at."""
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return {"content": _format_text(event, message, data)[:_DISCORD_LIMIT]}
    if "hooks.slack.com/" in url:
        return {"text": _format_text(event, message, data)}
    return {
        "event": event,
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def send(event: str, message: str, data: dict | None = None) -> dict:
    """POST to the configured webhook URL, if any."""
    if not cfg.webhook.url:
        return {"delivered": False, "reason": "webhook disabled"}
    payload = build_payload(cfg.webhook.url, event, redact(message), data or {})
    try:
        response = httpx.post(cfg.webhook.url, json=payload, timeout=5.0)
        logger.info("Webhook {} -> {}", event, response.status_code)
        return {"delivered": True, "status_code": response.status_code}
    except Exception as exc:  # best-effort: never propagate delivery failures
        logger.warning("Webhook {} delivery failed: {}", event, exc)
        return {"delivered": False, "error": str(exc)}
