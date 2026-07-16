"""Authentication endpoints: login, logout, me, profile, password change."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from kohakusshmanager import audit, remote
from kohakusshmanager.auth import (
    ADMIN_PRINCIPAL,
    COOKIE_NAME,
    Principal,
    clear_session_cookie,
    create_session,
    hash_password,
    require_user,
    set_session_cookie,
    verify_admin_token,
    verify_password,
)
from kohakusshmanager.models import Session, User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ProfileRequest(BaseModel):
    username: str | None = None
    display_name: str | None = None
    default_account: str | None = None


def principal_dict(principal: Principal) -> dict:
    if principal.is_admin:
        return {
            "name": ADMIN_PRINCIPAL,
            "role": "admin",
            "is_admin": True,
            "display_name": "Administrator",
            "default_account": "",
        }
    user = principal.user
    return {
        "name": user.username,
        "role": user.role,
        "is_admin": False,
        "display_name": user.display_name or user.username,
        "default_account": user.default_account or "",
    }


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response):
    if body.username == ADMIN_PRINCIPAL:
        if verify_admin_token(body.password):
            session = create_session(user=None, is_admin=True)
            set_session_cookie(response, session)
            audit.record(ADMIN_PRINCIPAL, "login", target="admin")
            return principal_dict(Principal(user=None, is_admin=True))
        audit.record(body.username, "login_failed", target="admin")
        raise HTTPException(status_code=401, detail="invalid credentials")

    user = User.get_or_none(User.username == body.username)
    if user and user.enabled and verify_password(body.password, user.password_hash):
        session = create_session(user=user, is_admin=False)
        set_session_cookie(response, session)
        audit.record(user.username, "login")
        return principal_dict(Principal(user=user, is_admin=False))

    audit.record(body.username, "login_failed", detail="bad password or disabled")
    raise HTTPException(status_code=401, detail="invalid credentials")


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session = Session.get_or_none(Session.token == token)
        if session is not None:
            session.delete_instance()
    clear_session_cookie(response)
    return Response(status_code=204)


@router.get("/me")
def me(principal: Principal = Depends(require_user)):
    return principal_dict(principal)


@router.patch("/profile")
def update_profile(body: ProfileRequest, principal: Principal = Depends(require_user)):
    if principal.is_admin or principal.user is None:
        raise HTTPException(
            status_code=400,
            detail="the admin principal has no editable profile",
        )
    user = principal.user

    if body.username is not None:
        new_name = body.username.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="username must not be empty")
        if new_name == ADMIN_PRINCIPAL:
            raise HTTPException(status_code=400, detail="username is reserved")
        if new_name != user.username:
            if User.get_or_none(User.username == new_name) is not None:
                raise HTTPException(status_code=409, detail="username already taken")
            user.username = new_name

    if body.display_name is not None:
        user.display_name = body.display_name.strip()

    if body.default_account is not None:
        acct = body.default_account.strip()
        if acct and not remote.valid_username(acct):
            raise HTTPException(
                status_code=400,
                detail="default account must be a valid Unix username",
            )
        user.default_account = acct

    user.save()
    audit.record(user.username, "profile_updated")
    return principal_dict(principal)


@router.post("/password")
def change_password(
    body: PasswordRequest, principal: Principal = Depends(require_user)
):
    if principal.is_admin or principal.user is None:
        raise HTTPException(
            status_code=400, detail="admin token password is managed via configuration"
        )
    user = principal.user
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    if not body.new_password:
        raise HTTPException(status_code=400, detail="new password must not be empty")
    user.password_hash = hash_password(body.new_password)
    user.save()
    audit.record(user.username, "password_changed")
    return {"success": True}
