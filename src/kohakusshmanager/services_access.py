"""Access approval/revocation, per-key install/remove, groups, account delete."""

from kohakusshmanager import remote, webhook
from kohakusshmanager.db import db_write, utcnow
from kohakusshmanager.errors import ConflictError
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import (
    AccessRequest,
    AccountKey,
    LocalAccount,
    Machine,
    RemoteAction,
    SSHKey,
    User,
)
from kohakusshmanager.services_base import (
    account_home,
    active_user_keys,
    apply_account_keys,
    dispatch,
    link_managed_key,
    upsert_account_link,
    with_connection,
)

logger = get_logger("SERVICES")


# --- Access approval / revocation -----------------------------------------


def _approve_work(request_id: int) -> dict:
    req = AccessRequest.get_by_id(request_id)
    machine = req.machine
    user = req.user
    username = req.username
    keys = active_user_keys(user) if user else []

    def work(client):
        # Defense in depth: never install a user's key into the management
        # account or a pre-existing privileged/system account (uid < 1000),
        # regardless of how the request was created or approved.
        if username == machine.management_user:
            raise ValueError("refusing to install keys into the management account")
        remote.create_account(client, username)
        acc_info = remote.get_account(client, username)
        if acc_info and acc_info.get("uid") is not None and acc_info["uid"] < 1000:
            raise ValueError(
                f"refusing to install keys into privileged account "
                f"{username!r} (uid {acc_info['uid']})"
            )
        home = acc_info["home"] if acc_info else f"/home/{username}"
        installs = []
        for key in keys:
            installs.append(
                (key.id, remote.install_key(client, username, home, key.public_key))
            )
        observed = remote.inspect_authorized_keys(client, username, home)
        return acc_info, installs, observed

    try:
        acc_info, installs, observed = with_connection(machine, work)
    except Exception as exc:
        err = str(exc)

        def _fail():
            r = AccessRequest.get_by_id(request_id)
            r.state = "failed"
            r.last_error = err
            r.save()

        db_write(_fail)
        raise

    def _persist():
        req = AccessRequest.get_by_id(request_id)
        account = upsert_account_link(machine, username, user, acc_info)
        for key_id, _res in installs:
            key = SSHKey.get_or_none(SSHKey.id == key_id)
            if key is not None:
                link_managed_key(account, key)
        apply_account_keys(account, observed)
        req.account = account
        req.state = "active"
        req.last_error = None
        req.save()

    db_write(_persist)

    webhook.send(
        "access_request.approved",
        f"Access to '{machine.name}' as '{username}' is active.",
        {"machine": machine.name, "username": username},
    )
    return {
        "machine": machine.name,
        "username": username,
        "installed": [fp["fingerprint"] for _k, fp in installs],
        "state": "active",
    }


def approve_request(req: AccessRequest, actor: str) -> list[RemoteAction]:
    def _approve():
        req.state = "approved"
        req.decided_by = actor
        req.decided_at = utcnow()
        req.save()

    db_write(_approve)
    action = dispatch(
        "install_key",
        actor,
        lambda rid=req.id: _approve_work(rid),
        machine=req.machine,
        request=req,
        input_summary=f"approve access {req.username}@{req.machine.name}",
    )
    return [action]


def _revoke_work(request_id: int) -> dict:
    req = AccessRequest.get_by_id(request_id)
    account = req.account
    machine = req.machine
    user = req.user
    managed_keys = [
        ak.key
        for ak in AccountKey.select().where(
            (AccountKey.account == account) & (AccountKey.managed == True)  # noqa: E712
        )
        if user is not None and ak.key.user_id == user.id
    ]

    def work(client):
        home = account_home(client, account)
        for key in managed_keys:
            remote.remove_key(client, account.username, home, key.fingerprint)
        return remote.inspect_authorized_keys(client, account.username, home)

    observed = with_connection(machine, work)

    def _persist():
        req = AccessRequest.get_by_id(request_id)
        acct = LocalAccount.get_by_id(account.id)
        apply_account_keys(acct, observed)
        for key in managed_keys:
            ak = AccountKey.get_or_none(
                (AccountKey.account == acct) & (AccountKey.key == key)
            )
            if ak is not None:
                ak.managed = False
                ak.save()
        req.state = "revoked"
        req.decided_at = utcnow()
        req.save()

    db_write(_persist)

    webhook.send(
        "access_request.revoked",
        f"Access to '{machine.name}' as '{account.username}' revoked.",
        {"machine": machine.name, "username": account.username},
    )
    return {
        "machine": machine.name,
        "username": account.username,
        "removed": [k.fingerprint for k in managed_keys],
        "state": "revoked",
    }


def revoke_request(req: AccessRequest, actor: str) -> list[RemoteAction]:
    if req.account is None:

        def _revoke():
            req.state = "revoked"
            req.decided_by = actor
            req.decided_at = utcnow()
            req.save()

        db_write(_revoke)
        return []
    action = dispatch(
        "remove_key",
        actor,
        lambda rid=req.id: _revoke_work(rid),
        machine=req.machine,
        account=req.account,
        request=req,
        input_summary=f"revoke access {req.username}@{req.machine.name}",
    )
    return [action]


# --- Key install / removal across links -----------------------------------


def install_key_action(
    machine: Machine, account: LocalAccount, sshkey: SSHKey, actor: str
) -> RemoteAction:
    acc_id, key_id = account.id, sshkey.id

    def fn():
        acct = LocalAccount.get_by_id(acc_id)
        key = SSHKey.get_by_id(key_id)

        def work(client):
            home = account_home(client, acct)
            res = remote.install_key(client, acct.username, home, key.public_key)
            observed = remote.inspect_authorized_keys(client, acct.username, home)
            return res, observed

        res, observed = with_connection(machine, work)

        def _persist():
            link_managed_key(acct, key)
            apply_account_keys(acct, observed)

        db_write(_persist)
        return {
            "machine": machine.name,
            "username": acct.username,
            "fingerprint": key.fingerprint,
            "installed": res["installed"],
        }

    return dispatch(
        "install_key",
        actor,
        fn,
        machine=machine,
        account=account,
        key=sshkey,
        input_summary=f"install key {sshkey.fingerprint} for {account.username}",
    )


def remove_key_action(
    machine: Machine, account: LocalAccount, sshkey: SSHKey, actor: str
) -> RemoteAction:
    acc_id, key_id = account.id, sshkey.id

    def fn():
        acct = LocalAccount.get_by_id(acc_id)
        key = SSHKey.get_by_id(key_id)

        def work(client):
            home = account_home(client, acct)
            res = remote.remove_key(client, acct.username, home, key.fingerprint)
            observed = remote.inspect_authorized_keys(client, acct.username, home)
            return res, observed

        res, observed = with_connection(machine, work)

        def _persist():
            ak = AccountKey.get_or_none(
                (AccountKey.account == acct) & (AccountKey.key == key)
            )
            if ak is not None:
                ak.managed = False
                ak.save()
            apply_account_keys(acct, observed)

        db_write(_persist)
        return {
            "machine": machine.name,
            "username": acct.username,
            "fingerprint": key.fingerprint,
            "removed": res["removed"],
        }

    return dispatch(
        "remove_key",
        actor,
        fn,
        machine=machine,
        account=account,
        key=sshkey,
        input_summary=f"remove key {sshkey.fingerprint} from {account.username}",
    )


def install_user_key_everywhere(
    user: User, sshkey: SSHKey, actor: str
) -> list[RemoteAction]:
    actions: list[RemoteAction] = []
    requests = AccessRequest.select().where(
        (AccessRequest.user == user) & (AccessRequest.state == "active")
    )
    for req in requests:
        if req.account is None:
            continue
        actions.append(install_key_action(req.machine, req.account, sshkey, actor))
    return actions


def sync_user_keys(user: User, actor: str) -> list[RemoteAction]:
    """Reconcile machines with the panel state for one user.

    Installs every active key on every active access link and removes revoked
    keys still observed on the user's own accounts. Each dispatched action is
    idempotent, so syncing repeatedly is safe.
    """
    actions: list[RemoteAction] = []
    requests = AccessRequest.select().where(
        (AccessRequest.user == user) & (AccessRequest.state == "active")
    )
    active_keys = active_user_keys(user)
    for req in requests:
        if req.account is None:
            continue
        for key in active_keys:
            actions.append(install_key_action(req.machine, req.account, key, actor))
    revoked = SSHKey.select().where((SSHKey.user == user) & (SSHKey.state == "revoked"))
    for key in revoked:
        links = AccountKey.select().where(
            (AccountKey.key == key) & (AccountKey.observed == True)  # noqa: E712
        )
        for ak in links:
            if ak.account.user_id == user.id:
                actions.append(
                    remove_key_action(ak.account.machine, ak.account, key, actor)
                )
    return actions


def revoke_user_key(sshkey: SSHKey, actor: str) -> list[RemoteAction]:
    def _revoke():
        sshkey.state = "revoked"
        sshkey.save()

    db_write(_revoke)
    actions: list[RemoteAction] = []
    # Remove from every managed link, not only currently-observed ones: a key
    # on a machine that was offline at the last refresh must still be scheduled
    # for removal so the failure is visible rather than silently skipped.
    links = AccountKey.select().where(
        (AccountKey.key == sshkey) & (AccountKey.managed == True)  # noqa: E712
    )
    for ak in links:
        account = ak.account
        actions.append(remove_key_action(account.machine, account, sshkey, actor))
    return actions


# --- Account groups / deletion --------------------------------------------


def _reject_if_management(account: LocalAccount) -> None:
    if account.username == account.machine.management_user:
        raise ConflictError("refusing to modify the machine's management account")


def set_account_groups(
    account: LocalAccount, add: list[str], remove: list[str], actor: str
) -> RemoteAction:
    _reject_if_management(account)
    acc_id = account.id

    def fn():
        acct = LocalAccount.get_by_id(acc_id)

        def work(client):
            res = remote.set_account_groups(
                client, acct.username, add=add, remove=remove
            )
            groups = remote.get_groups(client, acct.username)
            return res, groups

        res, groups = with_connection(account.machine, work)

        def _persist():
            a = LocalAccount.get_by_id(acc_id)
            a.groups = groups
            a.save()

        db_write(_persist)
        return res

    return dispatch(
        "set_groups",
        actor,
        fn,
        machine=account.machine,
        account=account,
        input_summary=f"set groups for {account.username}",
    )


def delete_local_account(
    account: LocalAccount, delete_home: bool, actor: str
) -> RemoteAction:
    _reject_if_management(account)
    acc_id = account.id

    def fn():
        acct = LocalAccount.get_by_id(acc_id)

        def work(client):
            return remote.delete_account(client, acct.username, delete_home=delete_home)

        res = with_connection(account.machine, work)

        def _persist():
            a = LocalAccount.get_by_id(acc_id)
            a.present = False
            a.state = "unmanaged"
            a.save()

        db_write(_persist)
        return res

    return dispatch(
        "delete_account",
        actor,
        fn,
        machine=account.machine,
        account=account,
        input_summary=f"delete account {account.username}",
    )
