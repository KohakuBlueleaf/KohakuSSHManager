"""Initialization: preview excludes mgmt, apply archives once, rerun skips."""

from kohakusshmanager.models import AccountKey, LocalAccount, SSHKey

from .conftest import (
    enroll_machine,
    login_admin,
    make_pubkey,
    register_machine,
)


def _setup(client, fake):
    login_admin(client)
    fm = fake.add("10.0.3.1")
    fm.add_account("mgr", 1000, keys=[make_pubkey("mgmt@key")])
    fm.add_account("alice", 2001, keys=[make_pubkey("alice@old")])
    fm.add_account("bob", 2002, keys=[make_pubkey("bob@old")])
    client.get("/api/machines/management-key")
    machine = register_machine(client, "inode", "10.0.3.1", mgmt_user="mgr")
    enroll_machine(client, machine["id"], fm.host_fingerprint)
    return fm, machine


def test_preview_excludes_management_account(client, fake):
    fm, machine = _setup(client, fake)
    preview = client.post(f"/api/machines/{machine['id']}/init/preview").json()
    usernames = {a["username"] for a in preview["accounts"]}
    assert "mgr" not in usernames
    assert {"alice", "bob"} <= usernames


def test_apply_archives_records_no_owner_and_reruns_skip(client, fake):
    fm, machine = _setup(client, fake)
    apply = client.post(
        f"/api/machines/{machine['id']}/init/apply",
        json={"usernames": ["alice", "bob"]},
    ).json()
    results = {r["username"]: r for r in apply["results"]}
    assert results["alice"]["archived"] is True
    assert results["alice"]["keys"]  # discovered fingerprints recorded

    # A backup exists on the fake machine and the live file is now empty.
    assert fm.backups.get("alice")
    assert fm.authorized.get("alice", "").strip() == ""

    # Discovered keys are recorded as no_owner with archive origin.
    account = LocalAccount.get(
        (LocalAccount.machine == machine["id"]) & (LocalAccount.username == "alice")
    )
    assert account.key_file_archived is True
    archive_links = AccountKey.select().where(
        (AccountKey.account == account) & (AccountKey.origin == "archive")
    )
    assert archive_links.count() == 1
    assert SSHKey.get(SSHKey.id == archive_links[0].key_id).state == "no_owner"

    # Management account never processed.
    assert "mgr" not in fm.backups

    # Rerun is safe: already-archived accounts are skipped.
    rerun = client.post(
        f"/api/machines/{machine['id']}/init/apply",
        json={"usernames": ["alice"]},
    ).json()
    rr = {r["username"]: r for r in rerun["results"]}
    assert rr["alice"].get("skipped") is True
    # Still exactly one backup (never overwritten).
    assert len(fm.backups["alice"]) == 1
