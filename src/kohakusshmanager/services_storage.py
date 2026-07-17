"""Storage mount scanning: replace usage records atomically on success."""

from kohakusshmanager import remote_storage, webhook
from kohakusshmanager.db import db_write
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import RemoteAction, StorageMount, UsageRecord
from kohakusshmanager.services_base import dispatch, with_connection

logger = get_logger("SERVICES")


def _persist_usage(mount: StorageMount, data: dict) -> dict:
    def _write():
        UsageRecord.delete().where(UsageRecord.mount == mount).execute()
        total = data["total"]
        UsageRecord.create(
            mount=mount, scope="total", bytes=total.get("bytes") or 0, status="ok"
        )
        for owner in data["by_owner"]:
            UsageRecord.create(
                mount=mount,
                scope="owner",
                uid=owner["uid"],
                owner_name=owner["owner_name"],
                bytes=owner["bytes"],
                file_count=owner["file_count"],
                status="ok",
            )
        for directory in data["by_directory"]:
            UsageRecord.create(
                mount=mount,
                scope="directory",
                path=directory["path"],
                bytes=directory["bytes"] or 0,
                status="ok",
            )

    db_write(_write)
    return {
        "mount": mount.name,
        "owners": len(data["by_owner"]),
        "directories": len(data["by_directory"]),
    }


def scan_mount(mount: StorageMount, actor: str) -> RemoteAction:
    mount_id = mount.id
    machine = mount.machine

    def fn():
        m = StorageMount.get_by_id(mount_id)

        def work(client):
            return remote_storage.scan_usage(client, m.path, m.subdirs)

        try:
            data = with_connection(machine, work)
        except Exception as exc:
            err = str(exc)

            def _mark_failed():
                UsageRecord.delete().where(UsageRecord.mount == m).execute()
                UsageRecord.create(
                    mount=m, scope="total", status="failed", error=err, bytes=0
                )

            db_write(_mark_failed)
            webhook.send(
                "scan.failed",
                f"Scan of mount '{m.name}' on '{machine.name}' failed: {exc}",
                {"mount": m.name, "machine": machine.name},
            )
            raise

        return _persist_usage(m, data)

    return dispatch(
        "scan_usage",
        actor,
        fn,
        machine=machine,
        mount=mount,
        input_summary=f"scan {mount.name} ({mount.path})",
        is_scan=True,
    )
