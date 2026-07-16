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


def test_profile_update(client):
    login_admin(client)
    create_user(client, "erin", "pw123")
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "erin", "password": "pw123"})

    resp = client.patch(
        "/api/auth/profile",
        json={
            "display_name": "Erin R",
            "default_account": "erin_r",
            "username": "erinr",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "erinr"
    assert body["display_name"] == "Erin R"
    assert body["default_account"] == "erin_r"
    # /me reflects the change (session survives the rename).
    assert client.get("/api/auth/me").json()["name"] == "erinr"


def test_profile_rejects_bad_values(client):
    login_admin(client)
    create_user(client, "frank", "pw123")
    create_user(client, "grace", "pw123")
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "frank", "password": "pw123"})

    # Duplicate username.
    assert (
        client.patch("/api/auth/profile", json={"username": "grace"}).status_code == 409
    )
    # Reserved admin principal name.
    assert (
        client.patch("/api/auth/profile", json={"username": "__token__"}).status_code
        == 400
    )
    # Invalid Unix account name.
    assert (
        client.patch(
            "/api/auth/profile", json={"default_account": "Bad Name!"}
        ).status_code
        == 400
    )


def test_default_account_drives_request_target(client, fake):
    from .conftest import enroll_machine, login_user, register_machine

    login_admin(client)
    fm = fake.add("10.0.9.1")
    fm.add_account("mgr", 1000)
    client.get("/api/machines/management-key")
    machine = register_machine(client, "dnode", "10.0.9.1", mgmt_user="mgr")
    enroll_machine(client, machine["id"], fm.host_fingerprint)
    create_user(client, "heidi", "pw123")

    client.post("/api/auth/logout")
    login_user(client, "heidi", "pw123")
    client.patch("/api/auth/profile", json={"default_account": "heidi_lab"})
    created = client.post("/api/access/requests", json={"machine_id": machine["id"]})
    assert created.status_code == 201
    # Target defaults to the configured account, not the panel username.
    assert created.json()["username"] == "heidi_lab"


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
