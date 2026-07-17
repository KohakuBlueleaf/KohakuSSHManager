"""Group and membership/assignment endpoints (admin only)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kohakusshmanager import audit
from kohakusshmanager.auth import Principal, require_admin
from kohakusshmanager.db import db_write
from kohakusshmanager.models import (
    Group,
    GroupMachine,
    GroupMember,
    Machine,
    User,
)

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


def serialize_group(group: Group) -> dict:
    members = [
        {
            "id": gm.user_id,
            "username": gm.user.username,
            "display_name": gm.user.display_name,
        }
        for gm in GroupMember.select().where(GroupMember.group == group)
    ]
    machines = [
        {"id": gm.machine_id, "name": gm.machine.name}
        for gm in GroupMachine.select().where(GroupMachine.group == group)
    ]
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "members": members,
        "machines": machines,
    }


def _get_group(group_id: int) -> Group:
    group = Group.get_or_none(Group.id == group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    return group


@router.get("")
def list_groups(principal: Principal = Depends(require_admin)):
    return [serialize_group(g) for g in Group.select().order_by(Group.name)]


@router.post("", status_code=201)
def create_group(body: GroupCreate, principal: Principal = Depends(require_admin)):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="group name required")
    if Group.get_or_none(Group.name == body.name) is not None:
        raise HTTPException(status_code=409, detail="group name already exists")
    group = db_write(lambda: Group.create(name=body.name, description=body.description))
    audit.record(principal.name, "group_created", target=group.name)
    return serialize_group(group)


@router.patch("/{group_id}")
def update_group(
    group_id: int, body: GroupUpdate, principal: Principal = Depends(require_admin)
):
    group = _get_group(group_id)
    if body.name is not None and body.name != group.name:
        if Group.get_or_none(Group.name == body.name) is not None:
            raise HTTPException(status_code=409, detail="group name already exists")
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    db_write(group.save)
    return serialize_group(group)


@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: int, principal: Principal = Depends(require_admin)):
    group = _get_group(group_id)
    name = group.name
    db_write(lambda: group.delete_instance(recursive=True))
    audit.record(principal.name, "group_deleted", target=name)


@router.post("/{group_id}/members/{user_id}", status_code=201)
def add_member(
    group_id: int, user_id: int, principal: Principal = Depends(require_admin)
):
    group = _get_group(group_id)
    user = User.get_or_none(User.id == user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    db_write(lambda: GroupMember.get_or_create(group=group, user=user))
    return serialize_group(group)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(
    group_id: int, user_id: int, principal: Principal = Depends(require_admin)
):
    group = _get_group(group_id)
    db_write(
        lambda: GroupMember.delete()
        .where((GroupMember.group == group) & (GroupMember.user == user_id))
        .execute()
    )


@router.post("/{group_id}/machines/{machine_id}", status_code=201)
def add_machine(
    group_id: int, machine_id: int, principal: Principal = Depends(require_admin)
):
    group = _get_group(group_id)
    machine = Machine.get_or_none(Machine.id == machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="machine not found")
    db_write(lambda: GroupMachine.get_or_create(group=group, machine=machine))
    return serialize_group(group)


@router.delete("/{group_id}/machines/{machine_id}", status_code=204)
def remove_machine(
    group_id: int, machine_id: int, principal: Principal = Depends(require_admin)
):
    group = _get_group(group_id)
    db_write(
        lambda: GroupMachine.delete()
        .where((GroupMachine.group == group) & (GroupMachine.machine == machine_id))
        .execute()
    )
