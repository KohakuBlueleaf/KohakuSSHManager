"""Best-effort webhook notifications (one URL, one attempt, logged result)."""

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


def send(event: str, message: str, data: dict | None = None) -> dict:
    """POST a small JSON payload to the configured webhook URL, if any."""
    if not cfg.webhook.url:
        return {"delivered": False, "reason": "webhook disabled"}
    payload = {
        "event": event,
        "message": redact(message),
        "data": data or {},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        response = httpx.post(cfg.webhook.url, json=payload, timeout=5.0)
        logger.info("Webhook {} -> {}", event, response.status_code)
        return {"delivered": True, "status_code": response.status_code}
    except Exception as exc:  # best-effort: never propagate delivery failures
        logger.warning("Webhook {} delivery failed: {}", event, exc)
        return {"delivered": False, "error": str(exc)}
