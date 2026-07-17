"""Service facade: refresh, enrollment, user deletion, retry + re-exports.

Read-only reads may run bare; multi-step writes are wrapped in ``db.atomic()``.
Long/mutating remote work is dispatched through the runner and returns a
RemoteAction; short sync flows (enroll confirm, init preview/apply) run inline
and finalize their own RemoteAction row. Flow implementations live in the
``services_access`` / ``services_init`` / ``services_storage`` modules and are
re-exported here so callers use a single ``services.X`` surface.
"""

from kohakusshmanager import remote, ssh, webhook
from kohakusshmanager.db import db_write, utcnow
from kohakusshmanager.errors import ConflictError
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import (
    AccessRequest,
    LocalAccount,
    Machine,
    RemoteAction,
    SSHKey,
    User,
)
from kohakusshmanager.services_access import (
    approve_request,
    delete_local_account,
    install_key_action,
    install_user_key_everywhere,
    remove_key_action,
    revoke_request,
    revoke_user_key,
    set_account_groups,
)
from kohakusshmanager.services_base import (
    complete_action,
    dispatch,
    generate_management_key,
    get_active_management_key,
    new_action,
    with_connection,
)
from kohakusshmanager.services_base import apply_account_keys as _apply_account_keys
from kohakusshmanager.services_init import (
    initialize_machine_apply,
    initialize_machine_preview,
)
from kohakusshmanager.services_storage import scan_mount
from kohakusshmanager.ssh import SSHTimeout, SSHUnreachable

logger = get_logger("SERVICES")

__all__ = [
    "utcnow",
    "get_active_management_key",
    "generate_management_key",
    "refresh_machine",
    "enroll_probe",
    "enroll_confirm",
    "approve_request",
    "revoke_request",
    "install_user_key_everywhere",
    "revoke_user_key",
    "set_account_groups",
    "delete_local_account",
    "initialize_machine_preview",
    "initialize_machine_apply",
    "scan_mount",
    "delete_panel_user",
    "retry_action",
]


# --- Refresh ---------------------------------------------------------------


def _refresh_machine_work(machine_id: int) -> dict:
    machine = Machine.get_by_id(machine_id)

    def work(client):
        facts = remote.inspect_machine(client)
        accounts = remote.inspect_accounts(client)
        keys_by_user = {
            acc["username"]: remote.inspect_authorized_keys(
                client, acc["username"], acc["home"]
            )
            for acc in accounts
        }
        return facts, accounts, keys_by_user

    try:
        facts, accounts, keys_by_user = with_connection(machine, work)
    except ssh.SSHError as exc:
        status = "offline" if isinstance(exc, (SSHUnreachable, SSHTimeout)) else "error"

        def _fail():
            m = Machine.get_by_id(machine_id)
            m.status = status
            m.last_error = str(exc)
            m.last_check_at = utcnow()
            m.save()

        db_write(_fail)
        if isinstance(exc, (SSHUnreachable, SSHTimeout)):
            webhook.send(
                "machine.unreachable",
                f"Machine '{machine.name}' is unreachable: {exc}",
                {"machine": machine.name},
            )
        raise

    def _persist():
        machine = Machine.get_by_id(machine_id)
        machine.facts = facts
        machine.status = "online"
        machine.last_error = None
        machine.last_check_at = utcnow()
        machine.save()
        seen = set()
        for acc in accounts:
            seen.add(acc["username"])
            account = LocalAccount.get_or_none(
                (LocalAccount.machine == machine)
                & (LocalAccount.username == acc["username"])
            )
            if account is None:
                account = LocalAccount(
                    machine=machine, username=acc["username"], state="unmanaged"
                )
            account.uid = acc["uid"]
            account.gid = acc["gid"]
            account.home = acc["home"] or ""
            account.shell = acc["shell"] or ""
            account.groups = acc["groups"]
            account.locked = acc["locked"]
            account.present = True
            account.last_seen_at = utcnow()
            account.save()
            _apply_account_keys(account, keys_by_user.get(acc["username"], []))
        for account in LocalAccount.select().where(LocalAccount.machine == machine):
            if account.present and account.username not in seen:
                account.present = False
                account.save()

    db_write(_persist)
    return {"status": "online", "accounts": len(accounts)}


def refresh_machine(machine: Machine, actor: str) -> RemoteAction:
    return dispatch(
        "refresh_machine",
        actor,
        lambda: _refresh_machine_work(machine.id),
        machine=machine,
        input_summary=f"refresh {machine.name}",
    )


# --- Enrollment ------------------------------------------------------------


def enroll_probe(machine: Machine, actor: str) -> dict:
    action = new_action("enroll", actor, machine=machine, state="running")
    try:
        fingerprint = ssh.probe_host_key(machine.address, machine.port)
        complete_action(action, {"host_key_fingerprint": fingerprint})
        return {"host_key_fingerprint": fingerprint, "action_id": action.id}
    except Exception as exc:
        complete_action(action, error=str(exc))
        raise


def enroll_confirm(machine_id: int, fingerprint: str, actor: str) -> dict:
    machine = Machine.get_by_id(machine_id)
    action = new_action("enroll", actor, machine=machine, state="running")
    try:
        actual = ssh.probe_host_key(machine.address, machine.port)
        if actual != fingerprint:
            raise ssh.HostKeyMismatch(
                f"presented fingerprint {actual} does not match confirmed {fingerprint}"
            )
        machine.host_key_fingerprint = fingerprint
        machine.enrolled = True
        db_write(machine.save)

        def work(client):
            code, _, err = ssh.run(client, "true", sudo=True)
            if code != 0:
                raise ssh.CommandFailed(code, err, "sudo -n true")
            return True

        with_connection(machine, work, expected_fingerprint=fingerprint)
        summary = _refresh_machine_work(machine.id)
        complete_action(action, {"enrolled": True, **summary})
        return {"enrolled": True, "action_id": action.id, **summary}
    except Exception as exc:
        complete_action(action, error=str(exc))
        raise


# --- Panel user deletion ---------------------------------------------------


def delete_panel_user(user: User) -> None:
    """Delete a panel user only. Keys -> no_owner, requests -> revoked,
    linked local accounts -> unmanaged/unlinked. No remote actions."""

    def _delete():
        SSHKey.update(user=None, state="no_owner").where(SSHKey.user == user).execute()
        AccessRequest.update(state="revoked").where(
            (AccessRequest.user == user)
            & (AccessRequest.state.in_(["pending", "approved", "active"]))
        ).execute()
        LocalAccount.update(user=None, state="unmanaged").where(
            LocalAccount.user == user
        ).execute()
        user.delete_instance()

    db_write(_delete)


# --- Retry dispatch --------------------------------------------------------


def retry_action(action: RemoteAction, actor: str) -> RemoteAction:
    """Re-dispatch a known action type from a stored (failed/interrupted) row."""
    machine = action.machine
    account = action.account
    key = action.key
    request = action.request
    kind = action.action

    if kind == "refresh_machine" and machine:
        return refresh_machine(machine, actor)
    if kind == "install_key" and request:
        return approve_request(request, actor)[0]
    if kind == "install_key" and account and key:
        return install_key_action(machine, account, key, actor)
    if kind == "remove_key" and request:
        return revoke_request(request, actor)[0]
    if kind == "remove_key" and account and key:
        return remove_key_action(machine, account, key, actor)
    if kind == "delete_account" and account:
        return delete_local_account(account, False, actor)
    if kind == "set_groups" and account:
        return set_account_groups(account, [], [], actor)
    if kind == "scan_usage":
        mount = action.mount
        if mount is not None:
            return scan_mount(mount, actor)
        raise ConflictError(
            "cannot retry scan: original mount no longer exists; "
            "re-run the scan from the storage page"
        )
    raise ConflictError(f"action type '{kind}' cannot be retried automatically")
