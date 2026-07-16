"""Authentication, roles, and session expiry."""

from datetime import timedelta

from kohakusshmanager.db import utcnow
from kohakusshmanager.models import Session

from .conftest import ADMIN_TOKEN, create_user, login_admin


def test_admin_login_ok(client):
    resp = client.post(
        "/api/auth/login", json={"username": "__token__", "password": ADMIN_TOKEN}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    assert body["role"] == "admin"


def test_admin_login_bad_token(client):
    resp = client.post(
        "/api/auth/login", json={"username": "__token__", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_user_login_and_me(client):
    login_admin(client)
    create_user(client, "alice", "pw123", role="member")
    client.post("/api/auth/logout")
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "pw123"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"
    me = client.get("/api/auth/me")
    assert me.json()["name"] == "alice"


def test_disabled_user_blocked(client):
    login_admin(client)
    user = create_user(client, "bob", "pw123")
    client.patch(f"/api/users/{user['id']}", json={"enabled": False})
    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "pw123"})
    assert resp.status_code == 401


def test_role_blocks_member_from_admin_routes(client):
    login_admin(client)
    create_user(client, "carol", "pw123", role="member")
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "carol", "password": "pw123"})
    # Members cannot list users.
    assert client.get("/api/users").status_code == 403
    # Members cannot create machines.
    assert (
        client.post(
            "/api/machines",
            json={"name": "m", "address": "1.2.3.4", "management_user": "mgr"},
        ).status_code
        == 403
    )


def test_unauthenticated_blocked(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/users").status_code == 401


def test_session_expiry(client):
    login_admin(client)
    assert client.get("/api/auth/me").status_code == 200
    # Force-expire the session in the DB.
    Session.update(expires_at=utcnow() - timedelta(hours=1)).execute()
    assert client.get("/api/auth/me").status_code == 401


def test_password_change(client):
    login_admin(client)
    create_user(client, "dave", "oldpw")
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "dave", "password": "oldpw"})
    resp = client.post(
        "/api/auth/password",
        json={"old_password": "oldpw", "new_password": "newpw"},
    )
    assert resp.status_code == 200
    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/login", json={"username": "dave", "password": "newpw"}
        ).status_code
        == 200
    )
