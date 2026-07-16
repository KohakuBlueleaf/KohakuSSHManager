"""Machine, account, and initialization endpoints.

This router uses explicit full paths (no prefix) so that ``/accounts/...``
endpoints can live alongside ``/machines/...``.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kohakusshmanager import audit, permissions, services
from kohakusshmanager.auth import Principal, require_admin, require_user
from kohakusshmanager.config import cfg
from kohakusshmanager.crypto import SecretUnavailable
from kohakusshmanager.db import to_iso_z
from kohakusshmanager.models import (
    AccountKey,
    LocalAccount,
    Machine,
    RemoteAction,
    StorageMount,
    User,
)

router = APIRouter(tags=["machines"])


class MachineCreate(BaseModel):
    name: str
    address: str
    port: int = 22
    management_user: str
    tags: list[str] = []
    notes: str = ""


class MachineUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    port: int | None = None
    management_user: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class EnrollConfirm(BaseModel):
    fingerprint: str


class AdoptRequest(BaseModel):
    user_id: int


class GroupsRequest(BaseModel):
    add: list[str] = []
    remove: list[str] = []


class DeleteAccountRequest(BaseModel):
    confirm: str
    delete_home: bool = False


class InitApply(BaseModel):
    usernames: list[str]


# --- Serialization ---------------------------------------------------------


def _leader_in_scope(principal: Principal, machine: Machine) -> bool:
    if principal.is_admin:
        return True
    if principal.role == "leader" and principal.user is not None:
        return permissions.machine_in_leader_scope(principal.user, machine)
    return False


def serialize_machine_member(machine: Machine) -> dict:
    facts = machine.facts or {}
    return {
        "id": machine.id,
        "name": machine.name,
        "tags": machine.tags or [],
        "status": machine.status,
        "facts": {"os": facts.get("os")},
        "last_check_at": to_iso_z(machine.last_check_at),
    }


def serialize_machine_summary(machine: Machine) -> dict:
    return {
        "id": machine.id,
        "name": machine.name,
        "address": machine.address,
        "port": machine.port,
        "management_user": machine.management_user,
        "host_key_fingerprint": machine.host_key_fingerprint,
        "enrolled": machine.enrolled,
        "tags": machine.tags or [],
        "notes": machine.notes,
        "facts": machine.facts,
        "status": machine.status,
        "last_check_at": to_iso_z(machine.last_check_at),
        "last_error": machine.last_error,
        "created_at": to_iso_z(machine.created_at),
    }


def serialize_account(account: LocalAccount) -> dict:
    keys = []
    for ak in AccountKey.select().where(AccountKey.account == account):
        key = ak.key
        owner = key.user
        keys.append(
            {
                "fingerprint": key.fingerprint,
                "comment": key.comment,
                "state": key.state,
                "observed": ak.observed,
                "managed": ak.managed,
                "origin": ak.origin,
                "owner_name": owner.username if owner else None,
            }
        )
    linked = account.user
    return {
        "id": account.id,
        "machine_id": account.machine_id,
        "username": account.username,
        "uid": account.uid,
        "gid": account.gid,
        "home": account.home,
        "shell": account.shell,
        "user_id": account.user_id,
        "user": (
            {
                "id": linked.id,
                "username": linked.username,
                "display_name": linked.display_name,
            }
            if linked
            else None
        ),
        "state": account.state,
        "locked": account.locked,
        "groups": account.groups or [],
        "present": account.present,
        "key_file_archived": account.key_file_archived,
        "last_seen_at": to_iso_z(account.last_seen_at),
        "keys": keys,
    }


def _serialize_action_brief(action: RemoteAction) -> dict:
    return {
        "id": action.id,
        "action": action.action,
        "state": action.state,
        "actor": action.actor,
        "error": action.error,
        "created_at": to_iso_z(action.created_at),
        "finished_at": to_iso_z(action.finished_at),
    }


def _get_machine(machine_id: int) -> Machine:
    machine = Machine.get_or_none(Machine.id == machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="machine not found")
    return machine


def _get_account(account_id: int) -> LocalAccount:
    account = LocalAccount.get_or_none(LocalAccount.id == account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return account


# --- Machine CRUD ----------------------------------------------------------


@router.get("/machines")
def list_machines(principal: Principal = Depends(require_user)):
    machines = Machine.select().order_by(Machine.name)
    if principal.is_admin or principal.role == "leader":
        return [serialize_machine_summary(m) for m in machines]
    return [serialize_machine_member(m) for m in machines]


@router.post("/machines", status_code=201)
def create_machine(body: MachineCreate, principal: Principal = Depends(require_admin)):
    if Machine.get_or_none(Machine.name == body.name) is not None:
        raise HTTPException(status_code=409, detail="machine name already exists")
    machine = Machine.create(
        name=body.name,
        address=body.address,
        port=body.port,
        management_user=body.management_user,
        tags=body.tags,
        notes=body.notes,
    )
    audit.record(principal.name, "machine_created", target=machine.name)
    return serialize_machine_summary(machine)


@router.get("/machines/management-key")
def management_key(principal: Principal = Depends(require_admin)):
    if not cfg.auth.secret:
        raise HTTPException(status_code=503, detail="KSM_SECRET is not configured")
    try:
        mk = services.generate_management_key()
    except SecretUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"public_key": mk.public_key}


@router.get("/machines/{machine_id}")
def get_machine(machine_id: int, principal: Principal = Depends(require_user)):
    machine = _get_machine(machine_id)
    if not (principal.is_admin or principal.role == "leader"):
        return serialize_machine_member(machine)
    data = serialize_machine_summary(machine)
    data["accounts"] = [
        serialize_account(a)
        for a in LocalAccount.select().where(LocalAccount.machine == machine)
    ]
    data["mounts"] = [
        {"id": m.id, "name": m.name, "path": m.path, "enabled": m.enabled}
        for m in StorageMount.select().where(StorageMount.machine == machine)
    ]
    data["recent_actions"] = [
        _serialize_action_brief(a)
        for a in RemoteAction.select()
        .where(RemoteAction.machine == machine)
        .order_by(RemoteAction.id.desc())
        .limit(20)
    ]
    return data


@router.patch("/machines/{machine_id}")
def update_machine(
    machine_id: int, body: MachineUpdate, principal: Principal = Depends(require_admin)
):
    machine = _get_machine(machine_id)
    if body.name is not None and body.name != machine.name:
        if Machine.get_or_none(Machine.name == body.name) is not None:
            raise HTTPException(status_code=409, detail="machine name already exists")
        machine.name = body.name
    for field in ("address", "management_user", "notes"):
        value = getattr(body, field)
        if value is not None:
            setattr(machine, field, value)
    if body.port is not None:
        machine.port = body.port
    if body.tags is not None:
        machine.tags = body.tags
    machine.save()
    audit.record(principal.name, "machine_updated", target=machine.name)
    return serialize_machine_summary(machine)


@router.delete("/machines/{machine_id}", status_code=204)
def delete_machine(machine_id: int, principal: Principal = Depends(require_admin)):
    machine = _get_machine(machine_id)
    enabled_mounts = (
        StorageMount.select()
        .where(
            (StorageMount.machine == machine) & (StorageMount.enabled == True)
        )  # noqa: E712
        .count()
    )
    if enabled_mounts:
        raise HTTPException(
            status_code=409, detail="disable this machine's storage mounts first"
        )
    name = machine.name
    machine.delete_instance(recursive=True)
    audit.record(principal.name, "machine_deleted", target=name)


# --- Enrollment -----------------------------------------------------------


@router.post("/machines/{machine_id}/enroll")
async def enroll(machine_id: int, principal: Principal = Depends(require_admin)):
    machine = _get_machine(machine_id)
    result = await asyncio.to_thread(services.enroll_probe, machine, principal.name)
    return result


@router.post("/machines/{machine_id}/enroll/confirm")
async def enroll_confirm(
    machine_id: int, body: EnrollConfirm, principal: Principal = Depends(require_admin)
):
    _get_machine(machine_id)
    result = await asyncio.to_thread(
        services.enroll_confirm, machine_id, body.fingerprint, principal.name
    )
    audit.record(principal.name, "machine_enrolled", target=str(machine_id))
    return result


@router.post("/machines/{machine_id}/refresh")
def refresh(machine_id: int, principal: Principal = Depends(require_user)):
    machine = _get_machine(machine_id)
    if not _leader_in_scope(principal, machine):
        raise HTTPException(status_code=403, detail="not permitted for this machine")
    action = services.refresh_machine(machine, principal.name)
    return {"action_id": action.id}


@router.get("/machines/{machine_id}/accounts")
def machine_accounts(machine_id: int, principal: Principal = Depends(require_user)):
    machine = _get_machine(machine_id)
    if not (principal.is_admin or principal.role == "leader"):
        raise HTTPException(status_code=403, detail="not permitted")
    return [
        serialize_account(a)
        for a in LocalAccount.select().where(LocalAccount.machine == machine)
    ]


# --- Account operations ----------------------------------------------------


@router.post("/accounts/{account_id}/adopt")
def adopt_account(
    account_id: int, body: AdoptRequest, principal: Principal = Depends(require_admin)
):
    account = _get_account(account_id)
    user = User.get_or_none(User.id == body.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    account.user = user
    account.state = "adopted"
    account.save()
    audit.record(
        principal.name, "account_adopted", target=account.username, detail=user.username
    )
    return serialize_account(account)


@router.post("/accounts/{account_id}/unlink")
def unlink_account(account_id: int, principal: Principal = Depends(require_admin)):
    account = _get_account(account_id)
    account.user = None
    account.state = "unmanaged"
    account.save()
    audit.record(principal.name, "account_unlinked", target=account.username)
    return serialize_account(account)


@router.post("/accounts/{account_id}/groups")
def account_groups(
    account_id: int, body: GroupsRequest, principal: Principal = Depends(require_admin)
):
    account = _get_account(account_id)
    action = services.set_account_groups(account, body.add, body.remove, principal.name)
    return {"action_id": action.id}


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: int,
    body: DeleteAccountRequest,
    principal: Principal = Depends(require_admin),
):
    account = _get_account(account_id)
    if body.confirm != account.username:
        raise HTTPException(
            status_code=400, detail="confirm must equal the account username"
        )
    action = services.delete_local_account(account, body.delete_home, principal.name)
    audit.record(
        principal.name,
        "account_deleted",
        target=account.username,
        detail=f"delete_home={body.delete_home}",
    )
    return {"action_id": action.id}


# --- Initialization --------------------------------------------------------


@router.post("/machines/{machine_id}/init/preview")
async def init_preview(machine_id: int, principal: Principal = Depends(require_admin)):
    machine = _get_machine(machine_id)
    return await asyncio.to_thread(
        services.initialize_machine_preview, machine, principal.name
    )


@router.post("/machines/{machine_id}/init/apply")
async def init_apply(
    machine_id: int, body: InitApply, principal: Principal = Depends(require_admin)
):
    machine = _get_machine(machine_id)
    result = await asyncio.to_thread(
        services.initialize_machine_apply, machine, body.usernames, principal.name
    )
    audit.record(
        principal.name,
        "init_apply",
        target=machine.name,
        detail=f"{len(body.usernames)} accounts",
    )
    return result
