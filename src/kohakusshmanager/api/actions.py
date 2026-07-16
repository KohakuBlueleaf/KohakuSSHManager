"""RemoteAction listing, polling, and retry endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from kohakusshmanager import audit, services
from kohakusshmanager.auth import Principal, require_admin, require_user
from kohakusshmanager.db import to_iso_z
from kohakusshmanager.models import RemoteAction

router = APIRouter(prefix="/actions", tags=["actions"])


def serialize_action(action: RemoteAction) -> dict:
    return {
        "id": action.id,
        "action": action.action,
        "actor": action.actor,
        "state": action.state,
        "input_summary": action.input_summary,
        "result": action.result,
        "error": action.error,
        "machine": (
            {"id": action.machine_id, "name": action.machine.name}
            if action.machine
            else None
        ),
        "account_id": action.account_id,
        "key_id": action.key_id,
        "request_id": action.request_id,
        "started_at": to_iso_z(action.started_at),
        "finished_at": to_iso_z(action.finished_at),
        "created_at": to_iso_z(action.created_at),
    }


@router.get("")
def list_actions(
    machine_id: int | None = None,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
    principal: Principal = Depends(require_user),
):
    query = RemoteAction.select().order_by(RemoteAction.id.desc())
    if machine_id is not None:
        query = query.where(RemoteAction.machine == machine_id)
    if state is not None:
        query = query.where(RemoteAction.state == state)
    if not (principal.is_admin or principal.role == "leader"):
        query = query.where(RemoteAction.actor == principal.name)
    limit = max(1, min(limit, 200))
    rows = query.limit(limit).offset(max(0, offset))
    return [serialize_action(a) for a in rows]


@router.get("/{action_id}")
def get_action(action_id: int, principal: Principal = Depends(require_user)):
    action = RemoteAction.get_or_none(RemoteAction.id == action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="action not found")
    if not (principal.is_admin or principal.role == "leader"):
        if action.actor != principal.name:
            raise HTTPException(status_code=403, detail="not permitted")
    return serialize_action(action)


@router.post("/{action_id}/retry")
def retry_action(action_id: int, principal: Principal = Depends(require_admin)):
    action = RemoteAction.get_or_none(RemoteAction.id == action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="action not found")
    if action.state not in ("failed", "interrupted"):
        raise HTTPException(
            status_code=409, detail="only failed or interrupted actions can be retried"
        )
    new_action = services.retry_action(action, principal.name)
    audit.record(principal.name, "action_retried", target=str(action_id))
    return {"action_id": new_action.id}
