"""User management endpoints (admin only)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kohakusshmanager import audit, services
from kohakusshmanager.auth import Principal, hash_password, require_admin
from kohakusshmanager.db import db_write, to_iso_z
from kohakusshmanager.models import AccessRequest, SSHKey, User

router = APIRouter(prefix="/users", tags=["users"])

_ROLES = {"member", "leader"}


class UserCreate(BaseModel):
    username: str
    display_name: str = ""
    password: str
    role: str = "member"


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    enabled: bool | None = None
    password: str | None = None


def serialize_user(user: User) -> dict:
    key_count = (
        SSHKey.select()
        .where((SSHKey.user == user) & (SSHKey.state == "active"))
        .count()
    )
    access_count = (
        AccessRequest.select()
        .where((AccessRequest.user == user) & (AccessRequest.state == "active"))
        .count()
    )
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "enabled": user.enabled,
        "key_count": key_count,
        "active_access_count": access_count,
        "created_at": to_iso_z(user.created_at),
    }


@router.get("")
def list_users(principal: Principal = Depends(require_admin)):
    return [serialize_user(u) for u in User.select().order_by(User.username)]


@router.post("", status_code=201)
def create_user(body: UserCreate, principal: Principal = Depends(require_admin)):
    username = body.username.strip()
    if not username or " " in username:
        raise HTTPException(status_code=400, detail="invalid username")
    if body.role not in _ROLES:
        raise HTTPException(status_code=400, detail="role must be member or leader")
    if not body.password:
        raise HTTPException(status_code=400, detail="password must not be empty")
    if User.get_or_none(User.username == username) is not None:
        raise HTTPException(status_code=409, detail="username already exists")
    user = db_write(
        lambda: User.create(
            username=username,
            display_name=body.display_name or username,
            password_hash=hash_password(body.password),
            role=body.role,
        )
    )
    audit.record(principal.name, "user_created", target=username)
    return serialize_user(user)


@router.patch("/{user_id}")
def update_user(
    user_id: int, body: UserUpdate, principal: Principal = Depends(require_admin)
):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if body.role is not None:
        if body.role not in _ROLES:
            raise HTTPException(status_code=400, detail="role must be member or leader")
        user.role = body.role
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.enabled is not None:
        user.enabled = body.enabled
    if body.password:
        user.password_hash = hash_password(body.password)
    db_write(user.save)
    audit.record(principal.name, "user_updated", target=user.username)
    return serialize_user(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, principal: Principal = Depends(require_admin)):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    username = user.username
    services.delete_panel_user(user)
    audit.record(
        principal.name,
        "user_deleted",
        target=username,
        detail="panel user only; machine accounts untouched",
    )
