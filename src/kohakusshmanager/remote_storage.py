"""Remote storage usage scanning (split from remote.py to keep files small)."""

import shlex

from kohakusshmanager import ssh
from kohakusshmanager.config import cfg
from kohakusshmanager.errors import ValidationError
from kohakusshmanager.logger import get_logger
from kohakusshmanager.remote import require_path

logger = get_logger("SCAN")


def _verify_mountpoint(client, path: str) -> None:
    exit_code, _, _ = ssh.run(client, f"mountpoint -q {shlex.quote(path)}")
    if exit_code == 127:  # mountpoint(1) unavailable; fall back to findmnt
        _, out, _ = ssh.run(
            client, f"findmnt -rn -o TARGET --target {shlex.quote(path)}"
        )
        if out.strip() != path:
            raise ValidationError(f"{path} is not a mount point")
    elif exit_code != 0:
        raise ValidationError(f"{path} is not a mount point")


def _scan_total(client, path: str) -> dict:
    timeout = cfg.ssh.scan_timeout
    _, out, _ = ssh.run(
        client,
        f"df -B1 --output=size,used,avail {shlex.quote(path)}",
        timeout=timeout,
    )
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit():
            return {
                "size": int(parts[0]),
                "bytes": int(parts[1]),
                "avail": int(parts[2]),
            }
    return {"size": None, "bytes": None, "avail": None}


def _scan_owners(client, path: str) -> list[dict]:
    timeout = cfg.ssh.scan_timeout
    command = (
        f"find {shlex.quote(path)} -xdev -type f -printf '%U %s\\n' 2>/dev/null "
        "| awk '{s[$1]+=$2; c[$1]++} END {for (u in s) print u, s[u], c[u]}'"
    )
    _, out, _ = ssh.run(client, command, sudo=True, timeout=timeout)
    owners: list[dict] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit():
            uid = int(parts[0])
            name = _resolve_owner(client, uid)
            owners.append(
                {
                    "uid": uid,
                    "bytes": int(parts[1]),
                    "file_count": int(parts[2]),
                    "owner_name": name,
                }
            )
    owners.sort(key=lambda r: r["bytes"], reverse=True)
    return owners


def _resolve_owner(client, uid: int) -> str | None:
    exit_code, out, _ = ssh.run(client, f"getent passwd {int(uid)}")
    if exit_code == 0 and ":" in out:
        return out.split(":", 1)[0]
    return None


def _scan_directories(client, path: str, subdirs: list[str]) -> list[dict]:
    timeout = cfg.ssh.scan_timeout
    results: list[dict] = []
    for subdir in subdirs:
        require_path(subdir)
        exit_code, out, _ = ssh.run(
            client, f"du -sB1 {shlex.quote(subdir)}", sudo=True, timeout=timeout
        )
        parts = out.split()
        size = int(parts[0]) if parts and parts[0].isdigit() else None
        results.append({"path": subdir, "bytes": size, "ok": exit_code == 0})
    return results


def scan_usage(client, path: str, subdirs: list[str] | None = None) -> dict:
    """Scan a mount: total usage, aggregate size by owner uid, per-subdir usage."""
    require_path(path)
    subdirs = subdirs or []
    _verify_mountpoint(client, path)
    return {
        "path": path,
        "total": _scan_total(client, path),
        "by_owner": _scan_owners(client, path),
        "by_directory": _scan_directories(client, path, subdirs),
    }
