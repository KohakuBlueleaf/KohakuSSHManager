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


def _count_by(model, field) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in model.select():
        value = getattr(row, field)
        counts[value] = counts.get(value, 0) + 1
    return counts


@router.get("/overview")
def overview(principal: Principal = Depends(require_admin)):
    machines_by_status = _count_by(Machine, "status")
    keys_by_state = _count_by(SSHKey, "state")

    users = list(User.select())
    users_by_role: dict[str, int] = {}
    users_disabled = 0
    for user in users:
        users_by_role[user.role] = users_by_role.get(user.role, 0) + 1
        if not user.enabled:
            users_disabled += 1

    requests_by_state = _count_by(AccessRequest, "state")

    since = utcnow() - timedelta(hours=24)
    failed_actions = (
        RemoteAction.select()
        .where((RemoteAction.state == "failed") & (RemoteAction.created_at >= since))
        .count()
    )
    return {
        "machines_by_status": machines_by_status,
        "machines_total": len(list(Machine.select())),
        "machines_enrolled": Machine.select()
        .where(Machine.enrolled == True)
        .count(),  # noqa: E712
        "keys_by_state": keys_by_state,
        "keys_total": sum(keys_by_state.values()),
        "no_owner_keys": keys_by_state.get("no_owner", 0),
        "users_total": len(users),
        "users_by_role": users_by_role,
        "users_disabled": users_disabled,
        "requests_by_state": requests_by_state,
        "pending_requests": requests_by_state.get("pending", 0),
        "failed_actions_24h": failed_actions,
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
