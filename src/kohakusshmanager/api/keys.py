"""SSH public-key endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kohakusshmanager import audit, services
from kohakusshmanager.auth import Principal, require_user
from kohakusshmanager.db import to_iso_z
from kohakusshmanager.errors import ValidationError
from kohakusshmanager.models import AccountKey, SSHKey, User
from kohakusshmanager.sshkeys import parse_ssh_public_key

router = APIRouter(prefix="/keys", tags=["keys"])


class KeyCreate(BaseModel):
    public_key: str
    comment: str | None = None
    install: bool = False
    user_id: int | None = None  # admin only


class AssignRequest(BaseModel):
    user_id: int


def serialize_key(key: SSHKey) -> dict:
    return {
        "id": key.id,
        "user_id": key.user_id,
        "public_key": key.public_key,
        "fingerprint": key.fingerprint,
        "comment": key.comment,
        "state": key.state,
        "created_at": to_iso_z(key.created_at),
    }


@router.get("")
def list_keys(
    user_id: int | None = None,
    state: str | None = None,
    principal: Principal = Depends(require_user),
):
    query = SSHKey.select()
    if principal.is_admin:
        if user_id is not None:
            query = query.where(SSHKey.user == user_id)
        if state is not None:
            query = query.where(SSHKey.state == state)
    else:
        query = query.where(SSHKey.user == principal.user_id)
    return [serialize_key(k) for k in query.order_by(SSHKey.id)]


@router.post("", status_code=201)
def add_key(body: KeyCreate, principal: Principal = Depends(require_user)):
    try:
        parsed = parse_ssh_public_key(body.public_key)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if SSHKey.get_or_none(SSHKey.fingerprint == parsed.fingerprint) is not None:
        raise HTTPException(status_code=409, detail="key already exists")

    owner: User | None
    if principal.is_admin:
        owner = None
        if body.user_id is not None:
            owner = User.get_or_none(User.id == body.user_id)
            if owner is None:
                raise HTTPException(status_code=404, detail="user not found")
        state = "active" if owner is not None else "no_owner"
    else:
        owner = principal.user
        state = "active"

    key = SSHKey.create(
        user=owner,
        public_key=parsed.normalized,
        fingerprint=parsed.fingerprint,
        comment=body.comment or parsed.comment,
        state=state,
    )
    audit.record(principal.name, "key_added", target=parsed.fingerprint)

    action_ids: list[int] = []
    if body.install and owner is not None:
        actions = services.install_user_key_everywhere(owner, key, principal.name)
        action_ids = [a.id for a in actions]

    return {"key": serialize_key(key), "action_ids": action_ids}


@router.post("/{key_id}/revoke")
def revoke_key(key_id: int, principal: Principal = Depends(require_user)):
    key = SSHKey.get_or_none(SSHKey.id == key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="key not found")
    if not principal.is_admin and key.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="not your key")
    actions = services.revoke_user_key(key, principal.name)
    audit.record(principal.name, "key_revoked", target=key.fingerprint)
    return {"action_ids": [a.id for a in actions]}


@router.post("/{key_id}/assign")
def assign_key(
    key_id: int, body: AssignRequest, principal: Principal = Depends(require_user)
):
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="admin privileges required")
    key = SSHKey.get_or_none(SSHKey.id == key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="key not found")
    if key.state != "no_owner":
        raise HTTPException(status_code=409, detail="key already has an owner")
    user = User.get_or_none(User.id == body.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    key.user = user
    key.state = "active"
    key.save()
    audit.record(
        principal.name, "key_assigned", target=key.fingerprint, detail=user.username
    )
    return serialize_key(key)


@router.delete("/{key_id}", status_code=204)
def delete_key(key_id: int, principal: Principal = Depends(require_user)):
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="admin privileges required")
    key = SSHKey.get_or_none(SSHKey.id == key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="key not found")
    if key.state not in ("revoked", "no_owner"):
        raise HTTPException(
            status_code=409, detail="only revoked or no-owner keys can be deleted"
        )
    observed = (
        AccountKey.select()
        .where((AccountKey.key == key) & (AccountKey.observed == True))  # noqa: E712
        .count()
    )
    if observed:
        raise HTTPException(
            status_code=409, detail="key is still observed on a machine; revoke first"
        )
    key.delete_instance(recursive=True)
    audit.record(principal.name, "key_deleted", target=key.fingerprint)
