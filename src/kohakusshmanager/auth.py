"""Panel authentication: password/token hashing, sessions, role dependencies."""

import secrets
from datetime import timedelta

import bcrypt
from fastapi import HTTPException, Request, Response

from kohakusshmanager.config import cfg
from kohakusshmanager.db import db_write, utcnow
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import Session, User

logger = get_logger("AUTH")

COOKIE_NAME = "ksm_session"
ADMIN_PRINCIPAL = "__token__"

_admin_token_hash: bytes | None = None


# --- Password / token hashing ---------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def init_admin_token() -> None:
    """Compute the admin-token bcrypt hash once (called from lifespan)."""
    global _admin_token_hash
    if _admin_token_hash is not None:
        return
    if cfg.auth.admin_token:
        _admin_token_hash = bcrypt.hashpw(
            cfg.auth.admin_token.encode("utf-8"), bcrypt.gensalt()
        )


def verify_admin_token(token: str) -> bool:
    if _admin_token_hash is None:
        init_admin_token()
    if _admin_token_hash is None:
        return False
    try:
        return bcrypt.checkpw(token.encode("utf-8"), _admin_token_hash)
    except (ValueError, TypeError):
        return False


# --- Sessions --------------------------------------------------------------


def create_session(user: User | None, is_admin: bool) -> Session:
    token = secrets.token_urlsafe(32)  # 43-char urlsafe token
    expires_at = utcnow() + timedelta(hours=cfg.auth.session_ttl_hours)
    return db_write(
        lambda: Session.create(
            token=token, user=user, is_admin=is_admin, expires_at=expires_at
        )
    )


def set_session_cookie(response: Response, session: Session) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=session.token,
        httponly=True,
        samesite="lax",
        max_age=cfg.auth.session_ttl_hours * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


# --- Principal / dependencies ---------------------------------------------


class Principal:
    """The authenticated actor for a request."""

    def __init__(self, user: User | None, is_admin: bool):
        self.user = user
        self.is_admin = is_admin
        if is_admin:
            self.role = "admin"
            self.name = ADMIN_PRINCIPAL
        else:
            self.role = user.role if user else "member"
            self.name = user.username if user else "anonymous"

    @property
    def is_leader(self) -> bool:
        return self.role in ("admin", "leader")

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None


def get_principal(request: Request) -> Principal | None:
    """Resolve the current session cookie to a Principal, or None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    session = Session.get_or_none(Session.token == token)
    if session is None:
        return None
    if session.expires_at <= utcnow():
        db_write(session.delete_instance)
        return None
    if session.is_admin:
        return Principal(user=None, is_admin=True)
    user = session.user
    if user is None or not user.enabled:
        return None
    return Principal(user=user, is_admin=False)


def require_user(request: Request) -> Principal:
    principal = get_principal(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return principal


def require_leader(request: Request) -> Principal:
    principal = require_user(request)
    if not principal.is_leader:
        raise HTTPException(status_code=403, detail="leader or admin role required")
    return principal


def require_admin(request: Request) -> Principal:
    principal = require_user(request)
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="admin privileges required")
    return principal
