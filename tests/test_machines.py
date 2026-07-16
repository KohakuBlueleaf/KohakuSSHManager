"""Machine registration, enrollment, and refresh via FakeSSH."""

from kohakusshmanager.models import LocalAccount

from .conftest import (
    enroll_machine,
    login_admin,
    make_pubkey,
    register_machine,
)


def _setup_enrolled(client, fake, address="10.0.0.1", name="node1"):
    login_admin(client)
    fm = fake.add(address)
    fm.add_account("mgr", 1000)
    fm.add_account("alice", 2001, keys=[make_pubkey("alice@old")])
    client.get("/api/machines/management-key")
    machine = register_machine(client, name, address, mgmt_user="mgr")
    enroll_machine(client, machine["id"], fm.host_fingerprint)
    return fm, machine


def test_register_enroll_refresh_lands_accounts_and_keys(client, fake):
    fm, machine = _setup_enrolled(client, fake)
    detail = client.get(f"/api/machines/{machine['id']}").json()
    assert detail["status"] == "online"
    assert detail["enrolled"] is True

    accounts = client.get(f"/api/machines/{machine['id']}/accounts").json()
    names = {a["username"] for a in accounts}
    assert {"mgr", "alice"} <= names

    alice = next(a for a in accounts if a["username"] == "alice")
    assert alice["uid"] == 2001
    assert len(alice["keys"]) == 1
    assert alice["keys"][0]["observed"] is True
    # Discovered key with unknown fingerprint is imported as no_owner.
    assert alice["keys"][0]["state"] == "no_owner"


def test_enroll_mismatch_returns_409(client, fake):
    login_admin(client)
    fake.add("10.0.0.9")
    client.get("/api/machines/management-key")
    machine = register_machine(client, "node9", "10.0.0.9", mgmt_user="mgr")
    client.post(f"/api/machines/{machine['id']}/enroll")
    resp = client.post(
        f"/api/machines/{machine['id']}/enroll/confirm",
        json={"fingerprint": "SHA256:WRONGFINGERPRINT"},
    )
    assert resp.status_code == 409


def test_refresh_marks_absent_accounts(client, fake):
    fm, machine = _setup_enrolled(client, fake)
    # alice disappears from the machine.
    del fm.accounts["alice"]
    fm.authorized.pop("alice", None)
    resp = client.post(f"/api/machines/{machine['id']}/refresh")
    assert resp.status_code == 200

    account = LocalAccount.get(
        (LocalAccount.machine == machine["id"]) & (LocalAccount.username == "alice")
    )
    assert account.present is False
    # History preserved, not deleted.
    assert (
        LocalAccount.select().where(LocalAccount.machine == machine["id"]).count() >= 2
    )


def test_machine_facts_shape(client, fake):
    fm, machine = _setup_enrolled(client, fake)
    facts = client.get(f"/api/machines/{machine['id']}").json()["facts"]
    for field in ("os", "hostname", "kernel", "cpu_model", "cpu_count", "mem_bytes"):
        assert field in facts
    assert isinstance(facts["mounts"], list)
    assert facts["mounts"][0].keys() >= {"target", "source", "fstype"}


def test_delete_account_requires_confirm_body(client, fake):
    fm, machine = _setup_enrolled(client, fake)
    accounts = client.get(f"/api/machines/{machine['id']}/accounts").json()
    alice = next(a for a in accounts if a["username"] == "alice")

    # Wrong confirm string -> 400.
    bad = client.request(
        "DELETE", f"/api/accounts/{alice['id']}", json={"confirm": "nope"}
    )
    assert bad.status_code == 400

    # Correct confirm + delete_home query -> action dispatched, removed on machine.
    ok = client.request(
        "DELETE",
        f"/api/accounts/{alice['id']}?delete_home=false",
        json={"confirm": "alice"},
    )
    assert ok.status_code == 200
    assert "action_id" in ok.json()
    assert "alice" not in fm.accounts


def test_delete_machine_requires_no_enabled_mounts(client, fake):
    fm, machine = _setup_enrolled(client, fake)
    client.post(
        "/api/storage/mounts",
        json={"name": "nas1", "machine_id": machine["id"], "path": "/data"},
    )
    blocked = client.request("DELETE", f"/api/machines/{machine['id']}")
    assert blocked.status_code == 409
