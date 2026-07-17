"""Existing-machine initialization: preview and apply (key-file archival)."""

from kohakusshmanager import remote, ssh, webhook
from kohakusshmanager.db import db_write
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import AccountKey, LocalAccount, Machine, SSHKey
from kohakusshmanager.services_base import (
    complete_action,
    new_action,
    upsert_account_link,
    with_connection,
)

logger = get_logger("SERVICES")


def initialize_machine_preview(machine: Machine, actor: str) -> dict:
    action = new_action("init_preview", actor, machine=machine, state="running")
    try:

        def work(client):
            accounts = remote.inspect_accounts(client)
            eligible = []
            for acc in accounts:
                if acc["username"] == machine.management_user:
                    continue
                keys = remote.inspect_authorized_keys(
                    client, acc["username"], acc["home"]
                )
                la = LocalAccount.get_or_none(
                    (LocalAccount.machine == machine)
                    & (LocalAccount.username == acc["username"])
                )
                archived = bool(la and la.key_file_archived)
                eligible.append(
                    {
                        "username": acc["username"],
                        "home": acc["home"],
                        "uid": acc["uid"],
                        "keys": keys,
                        "already_archived": archived,
                        "key_file_archived": archived,
                    }
                )
            return eligible

        eligible = with_connection(machine, work)
        complete_action(action, {"count": len(eligible)})
        return {"machine": machine.name, "accounts": eligible, "action_id": action.id}
    except Exception as exc:
        complete_action(action, error=str(exc))
        raise


def _record_archived_keys(account: LocalAccount, keys: list[dict]) -> None:
    for k in keys:
        sshkey = SSHKey.get_or_none(SSHKey.fingerprint == k["fingerprint"])
        if sshkey is None:
            sshkey = SSHKey.create(
                user=None,
                public_key=k["public_key"],
                fingerprint=k["fingerprint"],
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
                observed=False,
                managed=False,
                origin="archive",
            )
        else:
            ak.origin = "archive"
            ak.observed = False
            ak.save()


def initialize_machine_apply(
    machine: Machine, usernames: list[str], actor: str
) -> dict:
    action = new_action("init_apply", actor, machine=machine, state="running")
    results: list[dict] = []
    try:

        def work(client):
            per = []
            for username in usernames:
                if username == machine.management_user:
                    per.append(
                        {
                            "username": username,
                            "status": "skipped",
                            "skipped": True,
                            "reason": "management account excluded",
                        }
                    )
                    continue
                acc_info = remote.get_account(client, username)
                if acc_info is None:
                    per.append(
                        {
                            "username": username,
                            "status": "error",
                            "error": "account not found",
                        }
                    )
                    continue
                archive = remote.archive_authorized_keys(
                    client, username, acc_info["home"]
                )
                per.append(
                    {
                        "username": username,
                        "home": acc_info["home"],
                        "acc_info": acc_info,
                        "archive": archive,
                    }
                )
            return per

        # Hold the per-machine lock so this inline flow serializes with
        # runner-dispatched key/account mutations (which acquire the same lock);
        # archive rewrites authorized_keys and must not interleave with them.
        with ssh.machine_lock(machine.id):
            per = with_connection(machine, work)

        def _persist():
            for item in per:
                if item.get("skipped") or item.get("error"):
                    results.append(item)
                    continue
                username = item["username"]
                archive = item["archive"]
                account = upsert_account_link(machine, username, None, item["acc_info"])
                if archive.get("skipped"):
                    account.key_file_archived = True
                    account.save()
                    results.append(
                        {
                            "username": username,
                            "status": "skipped",
                            "skipped": True,
                            "reason": "already archived",
                        }
                    )
                    continue
                _record_archived_keys(account, archive["keys"])
                account.key_file_archived = True
                account.save()
                results.append(
                    {
                        "username": username,
                        "status": "archived",
                        "archived": True,
                        "backup_path": archive.get("backup_path"),
                        "keys": [k["fingerprint"] for k in archive["keys"]],
                    }
                )

        db_write(_persist)
        complete_action(action, {"results": results})
        return {"machine": machine.name, "results": results, "action_id": action.id}
    except Exception as exc:
        complete_action(action, error=str(exc))
        webhook.send(
            "init.failed",
            f"Initialization of '{machine.name}' failed: {exc}",
            {"machine": machine.name},
        )
        raise
