"""Admin overview, audit log, and webhook test endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends

from kohakusshmanager import webhook
from kohakusshmanager.auth import Principal, require_admin
from kohakusshmanager.db import to_iso_z, utcnow
from kohakusshmanager.models import (
    AccessRequest,
    AuditLog,
    Machine,
    RemoteAction,
    SSHKey,
    User,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def overview(principal: Principal = Depends(require_admin)):
    machines_by_status: dict[str, int] = {}
    for machine in Machine.select():
        machines_by_status[machine.status] = (
            machines_by_status.get(machine.status, 0) + 1
        )
    since = utcnow() - timedelta(hours=24)
    failed_actions = (
        RemoteAction.select()
        .where((RemoteAction.state == "failed") & (RemoteAction.created_at >= since))
        .count()
    )
    return {
        "machines_by_status": machines_by_status,
        "machines_total": Machine.select().count(),
        "pending_requests": AccessRequest.select()
        .where(AccessRequest.state == "pending")
        .count(),
        "failed_actions_24h": failed_actions,
        "users_total": User.select().count(),
        "no_owner_keys": SSHKey.select().where(SSHKey.state == "no_owner").count(),
    }


@router.get("/audit")
def audit_log(
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    principal: Principal = Depends(require_admin),
):
    query = AuditLog.select().order_by(AuditLog.id.desc())
    if action is not None:
        query = query.where(AuditLog.action == action)
    limit = max(1, min(limit, 500))
    rows = query.limit(limit).offset(max(0, offset))
    return [
        {
            "id": row.id,
            "actor": row.actor,
            "action": row.action,
            "target": row.target,
            "detail": row.detail,
            "created_at": to_iso_z(row.created_at),
        }
        for row in rows
    ]


@router.post("/webhook/test")
def webhook_test(principal: Principal = Depends(require_admin)):
    result = webhook.send(
        "test",
        "KohakuSSHManager webhook test",
        {"actor": principal.name},
    )
    return result
