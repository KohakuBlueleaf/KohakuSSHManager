"""Shared service primitives: management key, connection, action + persistence.

Flow modules (services_access / services_init / services_storage) and the
services facade build on these. This module imports no other services_* module,
keeping the dependency graph acyclic.
"""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kohakusshmanager import crypto, remote, runner, ssh
from kohakusshmanager.db import db, utcnow
from kohakusshmanager.errors import NotFoundError
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import (
    AccountKey,
    LocalAccount,
    Machine,
    ManagementKey,
    RemoteAction,
    SSHKey,
    User,
)

logger = get_logger("SERVICES")


# --- Management key --------------------------------------------------------


def get_active_management_key() -> ManagementKey | None:
    return ManagementKey.get_or_none(ManagementKey.active == True)  # noqa: E712


def generate_management_key() -> ManagementKey:
    """Generate the single shared ed25519 management key once (idempotent)."""
    existing = get_active_management_key()
    if existing is not None:
        return existing
    private = Ed25519PrivateKey.generate()
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    public_line = public_bytes.decode("ascii") + " kohakusshmanager"
    nonce, ciphertext = crypto.encrypt(private_bytes)
    return ManagementKey.create(
        public_key=public_line, ciphertext=ciphertext, nonce=nonce, active=True
    )


def management_private_key() -> str:
    mk = get_active_management_key()
    if mk is None:
        raise NotFoundError("management key has not been generated yet")
    return crypto.decrypt(mk.nonce, mk.ciphertext).decode("utf-8")


# --- Connection ------------------------------------------------------------


def connect(machine: Machine, expected_fingerprint: str | None = None):
    return ssh.connect(
        machine, management_private_key(), expected_fingerprint=expected_fingerprint
    )


def with_connection(machine: Machine, work, expected_fingerprint: str | None = None):
    client = connect(machine, expected_fingerprint)
    try:
        return work(client)
    finally:
        try:
            client.close()
        except Exception:  # pragma: no cover - defensive close
            pass


def account_home(client, account: LocalAccount) -> str:
    if account.home:
        return account.home
    info = remote.get_account(client, account.username)
    return info["home"] if info else f"/home/{account.username}"


# --- RemoteAction helpers --------------------------------------------------


def new_action(
    action_type: str,
    actor: str,
    *,
    machine=None,
    account=None,
    key=None,
    request=None,
    mount=None,
    input_summary: str = "",
    state: str = "pending",
) -> RemoteAction:
    return RemoteAction.create(
        action=action_type,
        actor=actor,
        machine=machine,
        account=account,
        key=key,
        request=request,
        mount=mount,
        input_summary=input_summary[:500],
        state=state,
        started_at=utcnow() if state == "running" else None,
    )


def complete_action(action: RemoteAction, result=None, error: str | None = None):
    action.state = "failed" if error else "succeeded"
    action.result = runner.bounded_result(result)
    action.error = error
    action.finished_at = utcnow()
    action.save()


def dispatch(
    action_type: str,
    actor: str,
    fn,
    *,
    machine=None,
    account=None,
    key=None,
    request=None,
    mount=None,
    input_summary: str = "",
    is_scan: bool = False,
) -> RemoteAction:
    with db.atomic():
        action = new_action(
            action_type,
            actor,
            machine=machine,
            account=account,
            key=key,
            request=request,
            mount=mount,
            input_summary=input_summary,
        )
    runner.submit_action(
        action.id, fn, machine_id=machine.id if machine else None, is_scan=is_scan
    )
    return action


# --- Account/key persistence helpers --------------------------------------


def upsert_account_link(
    machine: Machine, username: str, user: User | None, acc_info: dict | None
) -> LocalAccount:
    account = LocalAccount.get_or_none(
        (LocalAccount.machine == machine) & (LocalAccount.username == username)
    )
    if account is None:
        account = LocalAccount(machine=machine, username=username, state="managed")
        if user is not None:
            account.user = user
    else:
        if user is not None and account.user is None:
            account.user = user
            if account.state == "unmanaged":
                account.state = "adopted"
    if acc_info:
        account.uid = acc_info.get("uid")
        account.gid = acc_info.get("gid")
        account.home = acc_info.get("home") or account.home
        account.shell = acc_info.get("shell") or account.shell
    account.present = True
    account.last_seen_at = utcnow()
    account.save()
    return account


def link_managed_key(account: LocalAccount, sshkey: SSHKey) -> None:
    ak = AccountKey.get_or_none(
        (AccountKey.account == account) & (AccountKey.key == sshkey)
    )
    if ak is None:
        AccountKey.create(
            account=account, key=sshkey, observed=True, managed=True, origin="kohaku"
        )
    else:
        ak.managed = True
        ak.origin = "kohaku"
        ak.observed = True
        ak.save()


def apply_account_keys(account: LocalAccount, observed_keys: list[dict]) -> None:
    """Reconcile an account's AccountKey rows against the observed key file."""
    observed_fps = set()
    for k in observed_keys:
        fp = k["fingerprint"]
        observed_fps.add(fp)
        sshkey = SSHKey.get_or_none(SSHKey.fingerprint == fp)
        if sshkey is None:
            sshkey = SSHKey.create(
                user=None,
                public_key=k["public_key"],
                fingerprint=fp,
                comment=k.get("comment", ""),
                state="no_owner",
            )
        ak = AccountKey.get_or_none(
            (AccountKey.account == account) & (AccountKey.key == sshkey)
        )
        if ak is None:
            AccountKey.create(
                account=account,
                key=sshkey,
                observed=True,
                managed=False,
                origin="discovered",
            )
        elif not ak.observed:
            ak.observed = True
            ak.save()
    for ak in AccountKey.select().where(AccountKey.account == account):
        if ak.observed and ak.key.fingerprint not in observed_fps:
            ak.observed = False
            ak.save()


def active_user_keys(user: User) -> list[SSHKey]:
    return list(
        SSHKey.select().where((SSHKey.user == user) & (SSHKey.state == "active"))
    )
