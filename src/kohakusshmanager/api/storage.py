"""Storage mount configuration and usage endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kohakusshmanager import audit, remote, services
from kohakusshmanager.auth import Principal, require_admin, require_user
from kohakusshmanager.db import db_write, to_iso_z
from kohakusshmanager.models import (
    LocalAccount,
    Machine,
    StorageMount,
    UsageRecord,
)

router = APIRouter(prefix="/storage", tags=["storage"])


class MountCreate(BaseModel):
    name: str
    machine_id: int
    path: str
    subdirs: list[str] = []
    preferred: bool = False
    notes: str = ""
    enabled: bool = True


class MountUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    subdirs: list[str] | None = None
    preferred: bool | None = None
    notes: str | None = None
    enabled: bool | None = None


def serialize_mount(mount: StorageMount) -> dict:
    return {
        "id": mount.id,
        "name": mount.name,
        "machine_id": mount.machine_id,
        "machine_name": mount.machine.name if mount.machine else None,
        "path": mount.path,
        "subdirs": mount.subdirs or [],
        "preferred": mount.preferred,
        "notes": mount.notes,
        "enabled": mount.enabled,
    }


def _get_mount(mount_id: int) -> StorageMount:
    mount = StorageMount.get_or_none(StorageMount.id == mount_id)
    if mount is None:
        raise HTTPException(status_code=404, detail="mount not found")
    return mount


def _uid_to_user(machine: Machine) -> dict[int, dict]:
    mapping: dict[int, dict] = {}
    for account in LocalAccount.select().where(
        (LocalAccount.machine == machine) & (LocalAccount.uid.is_null(False))
    ):
        owner = account.user
        mapping[account.uid] = {
            "local_username": account.username,
            "panel_user_id": account.user_id,
            "panel_user": owner.username if owner else None,
        }
    return mapping


@router.get("/mounts")
def list_mounts(principal: Principal = Depends(require_user)):
    query = StorageMount.select().order_by(StorageMount.name)
    if principal.is_admin:
        return [serialize_mount(m) for m in query]
    return [
        {
            "id": m.id,
            "name": m.name,
            "machine_name": m.machine.name if m.machine else None,
            "path": m.path,
        }
        for m in query.where(StorageMount.enabled == True)  # noqa: E712
    ]


@router.post("/mounts", status_code=201)
def create_mount(body: MountCreate, principal: Principal = Depends(require_admin)):
    machine = Machine.get_or_none(Machine.id == body.machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="machine not found")
    if not remote.valid_path(body.path):
        raise HTTPException(status_code=400, detail="invalid mount path")
    for subdir in body.subdirs:
        if not remote.valid_path(subdir):
            raise HTTPException(
                status_code=400, detail=f"invalid subdir path: {subdir}"
            )
    mount = db_write(
        lambda: StorageMount.create(
            name=body.name,
            machine=machine,
            path=body.path,
            subdirs=body.subdirs,
            preferred=body.preferred,
            notes=body.notes,
            enabled=body.enabled,
        )
    )
    audit.record(principal.name, "mount_created", target=mount.name)
    return serialize_mount(mount)


@router.patch("/mounts/{mount_id}")
def update_mount(
    mount_id: int, body: MountUpdate, principal: Principal = Depends(require_admin)
):
    mount = _get_mount(mount_id)
    if body.path is not None:
        if not remote.valid_path(body.path):
            raise HTTPException(status_code=400, detail="invalid mount path")
        mount.path = body.path
    if body.subdirs is not None:
        for subdir in body.subdirs:
            if not remote.valid_path(subdir):
                raise HTTPException(status_code=400, detail=f"invalid subdir: {subdir}")
        mount.subdirs = body.subdirs
    if body.name is not None:
        mount.name = body.name
    if body.preferred is not None:
        mount.preferred = body.preferred
    if body.notes is not None:
        mount.notes = body.notes
    if body.enabled is not None:
        mount.enabled = body.enabled
    db_write(mount.save)
    return serialize_mount(mount)


@router.delete("/mounts/{mount_id}", status_code=204)
def delete_mount(mount_id: int, principal: Principal = Depends(require_admin)):
    mount = _get_mount(mount_id)
    name = mount.name
    db_write(lambda: mount.delete_instance(recursive=True))
    audit.record(principal.name, "mount_deleted", target=name)


@router.post("/mounts/{mount_id}/scan")
def scan_mount(mount_id: int, principal: Principal = Depends(require_admin)):
    mount = _get_mount(mount_id)
    action = services.scan_mount(mount, principal.name)
    return {"action_id": action.id}


@router.get("/mounts/{mount_id}/usage")
def mount_usage(mount_id: int, principal: Principal = Depends(require_admin)):
    # Full per-owner usage (every uid + resolved name) is admin-only; members
    # see their own rows through GET /storage/usage/mine.
    mount = _get_mount(mount_id)
    records = list(UsageRecord.select().where(UsageRecord.mount == mount))
    uid_map = _uid_to_user(mount.machine)

    total = None
    by_owner = []
    by_directory = []
    scanned_at = None
    status = "never"
    for rec in records:
        scanned_at = scanned_at or rec.scanned_at
        if rec.scope == "total":
            status = rec.status
            total = {
                "bytes": rec.bytes,
                "file_count": rec.file_count,
                "status": rec.status,
                "error": rec.error,
            }
        elif rec.scope == "owner":
            link = uid_map.get(rec.uid, {})
            by_owner.append(
                {
                    "uid": rec.uid,
                    "owner_name": rec.owner_name,
                    "local_username": link.get("local_username"),
                    "panel_user_id": link.get("panel_user_id"),
                    "panel_user": link.get("panel_user"),
                    "bytes": rec.bytes,
                    "file_count": rec.file_count,
                }
            )
        elif rec.scope == "directory":
            by_directory.append(
                {"path": rec.path, "bytes": rec.bytes, "file_count": rec.file_count}
            )

    by_owner.sort(key=lambda r: r["bytes"], reverse=True)
    return {
        "mount": serialize_mount(mount),
        "total": total,
        "by_owner": by_owner,
        "by_directory": by_directory,
        "scanned_at": to_iso_z(scanned_at),
        "status": status,
    }


@router.get("/usage/mine")
def usage_mine(principal: Principal = Depends(require_user)):
    if principal.user is None:
        return []
    rows = []
    mounts = StorageMount.select().where(StorageMount.enabled == True)  # noqa: E712
    for mount in mounts:
        my_uids = {
            a.uid
            for a in LocalAccount.select().where(
                (LocalAccount.machine == mount.machine)
                & (LocalAccount.user == principal.user_id)
                & (LocalAccount.uid.is_null(False))
            )
        }
        if not my_uids:
            continue
        for rec in UsageRecord.select().where(
            (UsageRecord.mount == mount) & (UsageRecord.scope == "owner")
        ):
            if rec.uid in my_uids:
                rows.append(
                    {
                        "mount_name": mount.name,
                        "machine_name": mount.machine.name if mount.machine else None,
                        "path": mount.path,
                        "uid": rec.uid,
                        "bytes": rec.bytes,
                        "file_count": rec.file_count,
                        "scanned_at": to_iso_z(rec.scanned_at),
                        "status": rec.status,
                    }
                )
    return rows
