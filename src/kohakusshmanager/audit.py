"""Immutable audit log helper + retention cleanup."""

from datetime import timedelta

from kohakusshmanager.config import cfg
from kohakusshmanager.crypto import redact
from kohakusshmanager.db import utcnow
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import AuditLog

logger = get_logger("AUDIT")


def record(actor: str, action: str, target: str = "", detail: str = "") -> AuditLog:
    """Write a short, immutable audit row (details are redacted for safety)."""
    return AuditLog.create(
        actor=actor,
        action=action,
        target=str(target)[:200],
        detail=redact(str(detail))[:500],
    )


def cleanup_audit() -> int:
    """Delete audit rows older than the configured retention. 0 = keep forever."""
    days = cfg.audit.retention_days
    if days <= 0:
        return 0
    cutoff = utcnow() - timedelta(days=days)
    deleted = AuditLog.delete().where(AuditLog.created_at < cutoff).execute()
    if deleted:
        logger.info("Audit cleanup removed {} rows older than {} days", deleted, days)
    return deleted
