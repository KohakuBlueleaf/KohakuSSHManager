"""Access request lifecycle endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kohakusshmanager import audit, permissions, remote, services, webhook
from kohakusshmanager.auth import Principal, require_user
from kohakusshmanager.db import db_write, to_iso_z
from kohakusshmanager.models import AccessRequest, Machine, SSHKey, User

router = APIRouter(prefix="/access", tags=["access"])


class AccessRequestCreate(BaseModel):
    machine_id: int
    username: str | None = None
    user_id: int | None = None  # admin only: grant on behalf of this user


class RejectRequest(BaseModel):
    reason: str = ""


def serialize_request(req: AccessRequest) -> dict:
    return {
        "id": req.id,
        "user_id": req.user_id,
        "machine_id": req.machine_id,
        "machine_name": req.machine.name if req.machine else None,
        "username": req.username,
        "account_id": req.account_id,
        "state": req.state,
        "reason": req.reason,
        "requested_by": req.requested_by,
        "decided_by": req.decided_by,
        "decided_at": to_iso_z(req.decided_at),
        "valid_until": to_iso_z(req.valid_until),
        "last_error": req.last_error,
        "created_at": to_iso_z(req.created_at),
    }


def _leader_scope(principal: Principal, machine: Machine) -> bool:
    if principal.is_admin:
        return True
    if principal.role == "leader" and principal.user is not None:
        return permissions.machine_in_leader_scope(principal.user, machine)
    return False


@router.post("/requests", status_code=201)
def create_request(
    body: AccessRequestCreate, principal: Principal = Depends(require_user)
):
    machine = Machine.get_or_none(Machine.id == body.machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="machine not found")

    # Admins may grant on behalf of another panel user: the request then belongs
    # to that user, so approval installs *their* active keys.
    target_user = principal.user
    if body.user_id is not None:
        if not principal.is_admin:
            raise HTTPException(
                status_code=403,
                detail="only admins may create requests for another user",
            )
        target_user = User.get_or_none(User.id == body.user_id)
        if target_user is None:
            raise HTTPException(status_code=404, detail="user not found")
        if not target_user.enabled:
            raise HTTPException(status_code=400, detail="user is disabled")

    # Non-admins may only request access under their configured default account
    # (or their panel username if unset); a body-supplied target could otherwise
    # name root, another user, or the management account. Admins may target a
    # specific existing account.
    if principal.is_admin:
        if target_user is not None:
            username = (
                body.username or target_user.default_account or target_user.username
            )
        else:
            username = body.username
    elif principal.user is not None:
        username = principal.user.default_account or principal.user.username
    else:
        username = None
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if not remote.valid_username(username):
        raise HTTPException(status_code=400, detail="invalid unix username")
    if username == machine.management_user:
        raise HTTPException(
            status_code=403,
            detail="cannot request access as the machine's management account",
        )

    if target_user is not None:
        existing = AccessRequest.get_or_none(
            (AccessRequest.user == target_user)
            & (AccessRequest.machine == machine)
            & (AccessRequest.username == username)
            & (AccessRequest.state.in_(["pending", "approved", "active"]))
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"an equivalent request is already {existing.state}",
            )

    decision, reason = permissions.decide_access(principal, machine)
    if decision == "reject":
        raise HTTPException(status_code=403, detail=reason)

    req = db_write(
        lambda: AccessRequest.create(
            user=target_user,
            machine=machine,
            username=username,
            requested_by=principal.name,
            reason=reason,
            state="pending",
        )
    )

    if decision == "auto":
        actions = services.approve_request(req, principal.name)
        audit.record(
            principal.name, "request_auto_approved", target=machine.name, detail=reason
        )
        req = AccessRequest.get_by_id(req.id)
        return {**serialize_request(req), "action_ids": [a.id for a in actions]}

    webhook.send(
        "access_request.pending",
        f"{principal.name} requests access to '{machine.name}' as '{username}'.",
        {"machine": machine.name, "username": username, "request_id": req.id},
    )
    audit.record(principal.name, "request_created", target=machine.name)
    return {**serialize_request(req), "action_ids": []}


@router.get("/requests")
def list_requests(
    state: str | None = None,
    mine: bool = False,
    principal: Principal = Depends(require_user),
):
    query = AccessRequest.select().order_by(AccessRequest.id.desc())
    if state is not None:
        query = query.where(AccessRequest.state == state)

    if principal.is_admin and not mine:
        rows = list(query)
    elif principal.role == "leader" and not mine and principal.user is not None:
        scope = permissions.leader_machine_ids(principal.user)
        rows = [
            r for r in query if r.user_id == principal.user_id or r.machine_id in scope
        ]
    else:
        rows = list(query.where(AccessRequest.user == principal.user_id))
    return [serialize_request(r) for r in rows]


def _get_request(request_id: int) -> AccessRequest:
    req = AccessRequest.get_or_none(AccessRequest.id == request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="request not found")
    return req


@router.post("/requests/{request_id}/approve")
def approve(request_id: int, principal: Principal = Depends(require_user)):
    req = _get_request(request_id)
    if not _leader_scope(principal, req.machine):
        raise HTTPException(status_code=403, detail="not permitted to approve")
    if req.state not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail=f"request is {req.state}")
    actions = services.approve_request(req, principal.name)
    audit.record(principal.name, "request_approved", target=req.machine.name)
    return {"action_ids": [a.id for a in actions]}


@router.post("/requests/{request_id}/reject")
def reject(
    request_id: int, body: RejectRequest, principal: Principal = Depends(require_user)
):
    req = _get_request(request_id)
    if not _leader_scope(principal, req.machine):
        raise HTTPException(status_code=403, detail="not permitted to reject")
    if req.state not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail=f"request is {req.state}")
    req.state = "rejected"
    req.reason = body.reason or req.reason
    req.decided_by = principal.name
    req.decided_at = services.utcnow()
    db_write(req.save)
    audit.record(
        principal.name, "request_rejected", target=req.machine.name, detail=body.reason
    )
    return serialize_request(req)


@router.post("/requests/{request_id}/revoke")
def revoke(request_id: int, principal: Principal = Depends(require_user)):
    req = _get_request(request_id)
    is_owner = req.user_id is not None and req.user_id == principal.user_id
    if not (principal.is_admin or (is_owner and req.state == "active")):
        raise HTTPException(status_code=403, detail="not permitted to revoke")
    actions = services.revoke_request(req, principal.name)
    audit.record(principal.name, "request_revoked", target=req.machine.name)
    return {"action_ids": [a.id for a in actions]}


@router.get("/overview")
def overview(principal: Principal = Depends(require_user)):
    if principal.user is None:
        return {"access": [], "keys": []}
    requests = AccessRequest.select().where(AccessRequest.user == principal.user_id)
    access = []
    for req in requests:
        access.append(
            {
                "request_id": req.id,
                "machine_id": req.machine_id,
                "machine_name": req.machine.name if req.machine else None,
                "username": req.username,
                "state": req.state,
                "account_id": req.account_id,
                "last_result": req.state,
                "last_error": req.last_error,
                "updated_at": to_iso_z(req.decided_at or req.created_at),
            }
        )
    keys = [
        {
            "id": k.id,
            "fingerprint": k.fingerprint,
            "comment": k.comment,
            "state": k.state,
        }
        for k in SSHKey.select().where(SSHKey.user == principal.user_id)
    ]
    return {"access": access, "keys": keys}
