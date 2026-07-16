"""Storage scan aggregation, duplicate-source handling, and mine-filter."""

from kohakusshmanager.models import LocalAccount, UsageRecord

from .conftest import (
    create_user,
    enroll_machine,
    login_admin,
    login_user,
    register_machine,
)


def _setup(client, fake, address="10.0.4.1", name="snode"):
    login_admin(client)
    fm = fake.add(address)
    fm.add_account("mgr", 1000)
    fm.add_account("alice", 2001)
    fm.usage_owners = [(2001, 5000, 10), (3000, 999, 1)]
    client.get("/api/machines/management-key")
    machine = register_machine(client, name, address, mgmt_user="mgr")
    enroll_machine(client, machine["id"], fm.host_fingerprint)
    return fm, machine


def test_scan_aggregates_owner_and_directory(client, fake):
    fm, machine = _setup(client, fake)
    created = client.post(
        "/api/storage/mounts",
        json={
            "name": "nas1",
            "machine_id": machine["id"],
            "path": "/data",
            "subdirs": ["/data/projects"],
        },
    )
    mount_id = created.json()["id"]
    scan = client.post(f"/api/storage/mounts/{mount_id}/scan")
    assert scan.status_code == 200

    usage = client.get(f"/api/storage/mounts/{mount_id}/usage").json()
    assert usage["status"] == "ok"
    owners = {o["uid"]: o for o in usage["by_owner"]}
    assert owners[2001]["bytes"] == 5000
    assert owners[2001]["file_count"] == 10
    # by_owner sorted descending by bytes.
    assert usage["by_owner"][0]["uid"] == 2001
    assert any(d["path"] == "/data/projects" for d in usage["by_directory"])


def test_scan_replaces_previous_records(client, fake):
    fm, machine = _setup(client, fake, address="10.0.4.2", name="snode2")
    created = client.post(
        "/api/storage/mounts",
        json={"name": "nas1", "machine_id": machine["id"], "path": "/data"},
    )
    mount_id = created.json()["id"]
    client.post(f"/api/storage/mounts/{mount_id}/scan")
    first = UsageRecord.select().where(UsageRecord.mount == mount_id).count()
    client.post(f"/api/storage/mounts/{mount_id}/scan")
    second = UsageRecord.select().where(UsageRecord.mount == mount_id).count()
    # Latest-only: rescanning does not accumulate duplicate rows.
    assert first == second


def test_usage_mine_filters_to_linked_uid(client, fake):
    fm, machine = _setup(client, fake, address="10.0.4.3", name="snode3")
    user = create_user(client, "alice", "pw")
    # Link alice's panel user to her local account (uid 2001).
    account = LocalAccount.get(
        (LocalAccount.machine == machine["id"]) & (LocalAccount.username == "alice")
    )
    client.post(f"/api/accounts/{account.id}/adopt", json={"user_id": user["id"]})

    created = client.post(
        "/api/storage/mounts",
        json={"name": "nas1", "machine_id": machine["id"], "path": "/data"},
    )
    mount_id = created.json()["id"]
    client.post(f"/api/storage/mounts/{mount_id}/scan")

    client.post("/api/auth/logout")
    login_user(client, "alice", "pw")
    mine = client.get("/api/storage/usage/mine").json()
    assert len(mine) == 1
    assert mine[0]["uid"] == 2001
    assert mine[0]["bytes"] == 5000


def test_duplicate_logical_name_not_summed(client, fake):
    # Two machines expose the same logical source "nas1"; usage is per-mount,
    # never summed into one figure.
    fm1, m1 = _setup(client, fake, address="10.0.4.4", name="dup1")
    fm2, m2 = _setup(client, fake, address="10.0.4.5", name="dup2")
    mount1 = client.post(
        "/api/storage/mounts",
        json={"name": "nas1", "machine_id": m1["id"], "path": "/data"},
    ).json()
    mount2 = client.post(
        "/api/storage/mounts",
        json={"name": "nas1", "machine_id": m2["id"], "path": "/data"},
    ).json()
    client.post(f"/api/storage/mounts/{mount1['id']}/scan")
    client.post(f"/api/storage/mounts/{mount2['id']}/scan")

    u1 = client.get(f"/api/storage/mounts/{mount1['id']}/usage").json()
    u2 = client.get(f"/api/storage/mounts/{mount2['id']}/usage").json()
    # Each mount keeps its own records under the same logical name.
    assert u1["mount"]["name"] == u2["mount"]["name"] == "nas1"
    assert u1["mount"]["machine_id"] != u2["mount"]["machine_id"]
