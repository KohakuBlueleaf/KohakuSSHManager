"""Key add-installs, revoke-removes, and no-owner assignment."""

from kohakusshmanager.models import AccountKey, SSHKey

from .conftest import (
    create_user,
    enroll_machine,
    login_admin,
    login_user,
    make_pubkey,
    register_machine,
)


def _active_access(client, fake):
    """Create an enrolled machine, a user, and an active access grant."""
    login_admin(client)
    fm = fake.add("10.0.2.1")
    fm.add_account("mgr", 1000)
    client.get("/api/machines/management-key")
    machine = register_machine(client, "knode", "10.0.2.1", mgmt_user="mgr")
    enroll_machine(client, machine["id"], fm.host_fingerprint)
    user = create_user(client, "alice", "pw")
    client.post(
        "/api/keys", json={"public_key": make_pubkey("first"), "user_id": user["id"]}
    )
    # Alice (member) files the request so it is linked to her panel user,
    # then the admin approves it (member-initiated is the real flow).
    client.post("/api/auth/logout")
    login_user(client, "alice", "pw")
    req = client.post("/api/access/requests", json={"machine_id": machine["id"]}).json()
    client.post("/api/auth/logout")
    login_admin(client)
    client.post(f"/api/access/requests/{req['id']}/approve")
    active = {r["id"]: r for r in client.get("/api/access/requests").json()}
    assert active[req["id"]]["state"] == "active"
    return fm, machine, user


def test_add_key_installs_to_active_links(client, fake):
    fm, machine, user = _active_access(client, fake)
    installed_before = fm.authorized.get("alice", "")
    # Add a second key with install=True.
    second = make_pubkey("second")
    resp = client.post(
        "/api/keys",
        json={"public_key": second, "user_id": user["id"], "install": True},
    )
    assert resp.status_code == 201
    assert resp.json()["action_ids"]  # a per-machine install action ran
    after = fm.authorized.get("alice", "")
    assert after.count("ssh-ed25519") == installed_before.count("ssh-ed25519") + 1


def test_revoke_key_removes_from_links(client, fake):
    fm, machine, user = _active_access(client, fake)
    keys = client.get(f"/api/keys?user_id={user['id']}").json()
    key_id = keys[0]["id"]
    assert fm.authorized.get("alice", "").strip() != ""

    resp = client.post(f"/api/keys/{key_id}/revoke")
    assert resp.status_code == 200
    assert SSHKey.get_by_id(key_id).state == "revoked"
    # Removed from the machine.
    assert fm.authorized.get("alice", "").strip() == ""


def test_revoke_schedules_removal_even_when_unobserved(client, fake):
    # A managed key on a machine that was offline at the last refresh
    # (observed=False) must still schedule a removal action, not be skipped.
    fm, machine, user = _active_access(client, fake)
    key_id = client.get(f"/api/keys?user_id={user['id']}").json()[0]["id"]
    # Simulate the last refresh having missed this key.
    AccountKey.update(observed=False).where(AccountKey.key == key_id).execute()

    resp = client.post(f"/api/keys/{key_id}/revoke")
    assert resp.status_code == 200
    assert resp.json()["action_ids"]  # removal still scheduled
    assert SSHKey.get_by_id(key_id).state == "revoked"


def test_no_owner_import_and_assign(client, fake):
    login_admin(client)
    # Admin imports a key with no user -> no_owner.
    resp = client.post("/api/keys", json={"public_key": make_pubkey("orphan")})
    assert resp.status_code == 201
    key = resp.json()["key"]
    assert key["state"] == "no_owner"
    assert key["user_id"] is None

    user = create_user(client, "carol", "pw")
    assigned = client.post(
        f"/api/keys/{key['id']}/assign", json={"user_id": user["id"]}
    )
    assert assigned.status_code == 200
    assert assigned.json()["state"] == "active"
    assert assigned.json()["user_id"] == user["id"]


def test_delete_revoked_key(client, fake):
    login_admin(client)
    resp = client.post("/api/keys", json={"public_key": make_pubkey("z")})
    key_id = resp.json()["key"]["id"]
    # no_owner key, no observed links -> deletable.
    deleted = client.request("DELETE", f"/api/keys/{key_id}")
    assert deleted.status_code == 204
    assert SSHKey.get_or_none(SSHKey.id == key_id) is None
