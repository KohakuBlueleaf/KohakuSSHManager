"""Leader/group scope: auto-approve in scope, review out of scope."""

from .conftest import (
    create_user,
    enroll_machine,
    login_admin,
    login_user,
    register_machine,
)


def _enrolled(client, fake, address, name):
    fm = fake.add(address)
    fm.add_account("mgr", 1000)
    machine = register_machine(client, name, address, mgmt_user="mgr")
    enroll_machine(client, machine["id"], fm.host_fingerprint)
    return fm, machine


def test_leader_auto_approves_in_scope_reviews_out_of_scope(client, fake):
    login_admin(client)
    client.get("/api/machines/management-key")
    fm_in, m_in = _enrolled(client, fake, "10.0.5.1", "in-scope")
    fm_out, m_out = _enrolled(client, fake, "10.0.5.2", "out-scope")

    leader = create_user(client, "lead", "pw", role="leader")

    # Group grants the leader scope over m_in only.
    group = client.post("/api/groups", json={"name": "team"}).json()
    client.post(f"/api/groups/{group['id']}/members/{leader['id']}")
    client.post(f"/api/groups/{group['id']}/machines/{m_in['id']}")

    client.post("/api/auth/logout")
    login_user(client, "lead", "pw")

    # In scope -> auto -> active.
    in_scope = client.post(
        "/api/access/requests",
        json={"machine_id": m_in["id"], "username": "lead"},
    )
    assert in_scope.status_code == 201
    assert in_scope.json()["state"] == "active"
    assert "lead" in fm_in.accounts

    # Out of scope -> review -> pending, and nothing provisioned.
    out_scope = client.post(
        "/api/access/requests",
        json={"machine_id": m_out["id"], "username": "lead"},
    )
    assert out_scope.status_code == 201
    assert out_scope.json()["state"] == "pending"
    assert "lead" not in fm_out.accounts


def test_leader_sees_scoped_requests(client, fake):
    login_admin(client)
    client.get("/api/machines/management-key")
    fm, machine = _enrolled(client, fake, "10.0.5.3", "shared")
    leader = create_user(client, "lead", "pw", role="leader")
    create_user(client, "mem", "pw", role="member")

    group = client.post("/api/groups", json={"name": "team"}).json()
    client.post(f"/api/groups/{group['id']}/members/{leader['id']}")
    client.post(f"/api/groups/{group['id']}/machines/{machine['id']}")

    # Member files a request for the shared machine.
    client.post("/api/auth/logout")
    login_user(client, "mem", "pw")
    client.post(
        "/api/access/requests",
        json={"machine_id": machine["id"], "username": "mem"},
    )

    # Leader sees the request targeting an in-scope machine.
    client.post("/api/auth/logout")
    login_user(client, "lead", "pw")
    visible = client.get("/api/access/requests").json()
    assert any(r["username"] == "mem" for r in visible)
