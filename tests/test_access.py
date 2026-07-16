"""Access decision matrix and request -> approve -> install -> revoke flow."""

from kohakusshmanager.auth import Principal
from kohakusshmanager.models import (
    Group,
    GroupMachine,
    GroupMember,
    Machine,
    User,
)
from kohakusshmanager.permissions import decide_access

from .conftest import (
    create_user,
    enroll_machine,
    login_admin,
    login_user,
    make_pubkey,
    register_machine,
)


def test_decide_access_matrix(dbfile):
    machine = Machine.create(name="m", address="a", management_user="mgr")
    admin = Principal(user=None, is_admin=True)
    assert decide_access(admin, machine)[0] == "auto"

    member = User.create(username="mem", password_hash="x", role="member")
    assert decide_access(Principal(member, False), machine)[0] == "review"

    leader = User.create(username="lead", password_hash="x", role="leader")
    assert decide_access(Principal(leader, False), machine)[0] == "review"

    group = Group.create(name="g")
    GroupMember.create(group=group, user=leader)
    GroupMachine.create(group=group, machine=machine)
    assert decide_access(Principal(leader, False), machine)[0] == "auto"

    disabled = User.create(
        username="dis", password_hash="x", role="member", enabled=False
    )
    assert decide_access(Principal(disabled, False), machine)[0] == "reject"


def _setup(client, fake, address="10.0.1.1", name="anode"):
    login_admin(client)
    fm = fake.add(address)
    fm.add_account("mgr", 1000)
    client.get("/api/machines/management-key")
    machine = register_machine(client, name, address, mgmt_user="mgr")
    enroll_machine(client, machine["id"], fm.host_fingerprint)
    return fm, machine


def test_full_request_approve_install_revoke(client, fake):
    fm, machine = _setup(client, fake)
    user = create_user(client, "alice", "pw")
    key = make_pubkey("alice@laptop")
    client.post("/api/keys", json={"public_key": key, "user_id": user["id"]})

    # Alice (member) requests -> review -> pending.
    client.post("/api/auth/logout")
    login_user(client, "alice", "pw")
    created = client.post("/api/access/requests", json={"machine_id": machine["id"]})
    assert created.status_code == 201
    req = created.json()
    assert req["state"] == "pending"

    # Admin approves -> synchronous install -> active.
    client.post("/api/auth/logout")
    login_admin(client)
    approved = client.post(f"/api/access/requests/{req['id']}/approve")
    assert approved.status_code == 200

    reqs = {r["id"]: r for r in client.get("/api/access/requests").json()}
    assert reqs[req["id"]]["state"] == "active"
    # Key physically installed on the (fake) machine.
    assert "alice" in fm.accounts
    assert fm.authorized.get("alice", "").strip() != ""

    # Revoke removes the key but leaves the account/home.
    revoked = client.post(f"/api/access/requests/{req['id']}/revoke")
    assert revoked.status_code == 200
    assert "alice" in fm.accounts  # account preserved
    assert fm.authorized.get("alice", "").strip() == ""  # key removed
    reqs = {r["id"]: r for r in client.get("/api/access/requests").json()}
    assert reqs[req["id"]]["state"] == "revoked"


def test_admin_request_auto_approves(client, fake):
    fm, machine = _setup(client, fake, address="10.0.1.2", name="anode2")
    # Admin creating a request for a target username -> auto -> active.
    resp = client.post(
        "/api/access/requests",
        json={"machine_id": machine["id"], "username": "svcbot"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["state"] == "active"
    assert "svcbot" in fm.accounts


def test_member_request_forced_to_own_username(client, fake):
    # A member cannot request a Unix account other than their own panel name;
    # a body-supplied "root" is ignored in favor of the panel username.
    _setup(client, fake, address="10.0.2.1", name="pnode1")
    create_user(client, "alice", "pw")
    client.post("/api/auth/logout")
    login_user(client, "alice", "pw")
    created = client.post(
        "/api/access/requests",
        json={"machine_id": 1, "username": "root"},
    )
    assert created.status_code == 201
    assert created.json()["username"] == "alice"


def test_request_management_account_blocked(client, fake):
    # Nobody (member or admin) may request access as the management account.
    _setup(client, fake, address="10.0.2.2", name="pnode2")
    resp = client.post(
        "/api/access/requests",
        json={"machine_id": 1, "username": "mgr"},
    )
    assert resp.status_code == 403


def test_approve_privileged_account_refused(client, fake):
    # Even if a request names a pre-existing privileged account (uid < 1000),
    # approval must refuse to install keys into it.
    fm, machine = _setup(client, fake, address="10.0.2.3", name="pnode3")
    fm.add_account("root", 0)
    resp = client.post(
        "/api/access/requests",
        json={"machine_id": machine["id"], "username": "root"},
    )
    assert resp.status_code == 201
    # Admin request auto-approves, but the install worker refuses -> failed.
    reqs = {r["id"]: r for r in client.get("/api/access/requests").json()}
    assert reqs[resp.json()["id"]]["state"] == "failed"
    assert fm.authorized.get("root", "").strip() == ""


def test_management_account_is_flagged_and_protected(client, fake):
    # After refresh the management account appears in the list, flagged as
    # management, and its delete/group operations are rejected.
    fm, machine = _setup(client, fake, address="10.0.2.4", name="pnode4")
    client.post(f"/api/machines/{machine['id']}/refresh")
    accounts = client.get(f"/api/machines/{machine['id']}/accounts").json()
    mgmt = next(a for a in accounts if a["username"] == "mgr")
    assert mgmt["is_management"] is True

    # Delete and group-change are blocked (409); adopt/unlink are not.
    deleted = client.request(
        "DELETE",
        f"/api/accounts/{mgmt['id']}",
        json={"confirm": "mgr", "delete_home": False},
    )
    assert deleted.status_code == 409
    grouped = client.post(
        f"/api/accounts/{mgmt['id']}/groups", json={"add": ["docker"]}
    )
    assert grouped.status_code == 409
    assert "mgr" in fm.accounts  # untouched


def test_member_cannot_see_others_data(client, fake):
    _setup(client, fake, address="10.0.1.3", name="anode3")
    alice = create_user(client, "alice", "pw")
    create_user(client, "bob", "pw")
    client.post(
        "/api/keys", json={"public_key": make_pubkey("a"), "user_id": alice["id"]}
    )

    client.post("/api/auth/logout")
    login_user(client, "bob", "pw")
    # Bob only sees his own (empty) key list.
    assert client.get("/api/keys").json() == []
    # Bob cannot enumerate all requests as admin would.
    assert client.get("/api/access/requests").json() == []
