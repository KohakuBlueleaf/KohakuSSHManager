"""Typed remote operations built from validated inputs + shlex.quote.

Every function takes a live paramiko client (from ``ssh.connect``) and returns a
plain dict, raising ``SSHError`` subclasses on failure. Calls go through the
``ssh`` module attributes (``ssh.run`` / ``ssh.run_checked``) so tests can
monkeypatch them.
"""

import re
import shlex
from datetime import datetime, timezone

from kohakusshmanager import ssh
from kohakusshmanager.errors import ValidationError
from kohakusshmanager.logger import get_logger
from kohakusshmanager.sshkeys import VALID_KEY_TYPES, parse_ssh_public_key

logger = get_logger("REMOTE")

_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_PATH_META = set(";&|<>$`\\!*?(){}[]~\"' \t\n\r")
_NOLOGIN_SHELLS = {
    "/usr/sbin/nologin",
    "/sbin/nologin",
    "/bin/false",
    "/usr/bin/false",
    "/bin/sync",
}


# --- Validation ------------------------------------------------------------


def valid_username(name: str) -> bool:
    return bool(_NAME_RE.match(name or ""))


def valid_group(name: str) -> bool:
    return bool(_NAME_RE.match(name or ""))


def valid_path(path: str) -> bool:
    if not path or not path.startswith("/"):
        return False
    if ".." in path:
        return False
    if any(c in _PATH_META for c in path):
        return False
    if any(ord(c) < 32 for c in path):
        return False
    return True


def require_username(name: str) -> str:
    if not valid_username(name):
        raise ValidationError(f"invalid username: {name!r}")
    return name


def require_group(name: str) -> str:
    if not valid_group(name):
        raise ValidationError(f"invalid group name: {name!r}")
    return name


def require_path(path: str) -> str:
    if not valid_path(path):
        raise ValidationError(f"invalid path: {path!r}")
    return path


# --- Small helpers ---------------------------------------------------------


def _out(client, command: str, *, sudo: bool = False) -> str:
    """Best-effort stdout (empty string on non-zero exit)."""
    exit_code, out, _ = ssh.run(client, command, sudo=sudo)
    return out.strip() if exit_code == 0 else ""


def _authorized_keys_path(home: str) -> str:
    return f"{home.rstrip('/')}/.ssh/authorized_keys"


def _extract_key(line: str):
    """Parse an authorized_keys line, tolerating a leading options field."""
    parts = line.split()
    for i, part in enumerate(parts):
        if part in VALID_KEY_TYPES:
            try:
                return parse_ssh_public_key(" ".join(parts[i:]))
            except ValidationError:
                return None
    return None


def _serialize_key(parsed) -> dict:
    return {
        "public_key": parsed.normalized,
        "fingerprint": parsed.fingerprint,
        "comment": parsed.comment,
        "key_type": parsed.key_type,
    }


# --- Inspection ------------------------------------------------------------


def inspect_machine(client) -> dict:
    """Collect a compact machine-facts snapshot (best-effort per field)."""
    facts: dict = {
        "os": None,
        "hostname": None,
        "kernel": None,
        "cpu_model": None,
        "cpu_count": None,
        "mem_bytes": None,
        "gpus": [],
        "mounts": [],
        "disks": [],
    }

    os_release = _out(client, "cat /etc/os-release")
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME="):
            facts["os"] = line.split("=", 1)[1].strip().strip('"')
            break

    facts["hostname"] = _out(client, "hostname") or None
    facts["kernel"] = _out(client, "uname -r") or None

    nproc = _out(client, "nproc")
    if nproc.isdigit():
        facts["cpu_count"] = int(nproc)

    cpu = _out(client, "grep -m1 'model name' /proc/cpuinfo")
    if ":" in cpu:
        facts["cpu_model"] = cpu.split(":", 1)[1].strip()

    mem = _out(client, "grep MemTotal /proc/meminfo")
    m = re.search(r"(\d+)", mem)
    if m:
        facts["mem_bytes"] = int(m.group(1)) * 1024

    gpu = _out(
        client,
        "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader",
    )
    for line in gpu.splitlines():
        if "," in line:
            name, mem_total = line.split(",", 1)
            facts["gpus"].append(
                {"name": name.strip(), "memory_total": mem_total.strip()}
            )

    mounts = _out(client, "findmnt -rn -o TARGET,SOURCE,FSTYPE,SIZE")
    if not mounts:
        mounts = _out(client, "cat /proc/mounts")
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            facts["mounts"].append(
                {
                    "target": parts[0],
                    "source": parts[1],
                    "fstype": parts[2],
                    "size": parts[3] if len(parts) > 3 else None,
                }
            )

    disks = _out(client, "df -B1 --output=target,size,used,avail -x tmpfs -x devtmpfs")
    for line in disks.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[1].isdigit():
            facts["disks"].append(
                {
                    "target": parts[0],
                    "size": int(parts[1]),
                    "used": int(parts[2]),
                    "avail": int(parts[3]),
                }
            )

    return facts


def inspect_accounts(client) -> list[dict]:
    """Login accounts (uid>=1000, real shell) with groups and lock state."""
    out = ssh.run_checked(client, "getent passwd")
    accounts: list[dict] = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 7:
            continue
        name, _, uid_s, gid_s, gecos, home, shell = parts[:7]
        if not uid_s.isdigit():
            continue
        uid = int(uid_s)
        if uid == 0 or uid < 1000:
            continue
        if shell in _NOLOGIN_SHELLS:
            continue
        groups = _out(client, f"id -Gn {shlex.quote(name)}").split()
        locked = None
        status = _out(client, f"passwd -S {shlex.quote(name)}", sudo=True)
        fields = status.split()
        if len(fields) >= 2:
            locked = fields[1] == "L"
        accounts.append(
            {
                "username": name,
                "uid": uid,
                "gid": int(gid_s) if gid_s.isdigit() else None,
                "gecos": gecos,
                "home": home,
                "shell": shell,
                "groups": groups,
                "locked": locked,
            }
        )
    return accounts


def get_account(client, username: str) -> dict | None:
    """Return a single account's passwd fields, or None if it does not exist."""
    require_username(username)
    exit_code, out, _ = ssh.run(client, f"getent passwd {shlex.quote(username)}")
    if exit_code != 0 or not out.strip():
        return None
    parts = out.strip().split(":")
    if len(parts) < 7:
        return None
    return {
        "username": parts[0],
        "uid": int(parts[2]) if parts[2].isdigit() else None,
        "gid": int(parts[3]) if parts[3].isdigit() else None,
        "home": parts[5],
        "shell": parts[6],
    }


def get_groups(client, username: str) -> list[str]:
    """Return the account's group names (best-effort)."""
    require_username(username)
    return _out(client, f"id -Gn {shlex.quote(username)}").split()


def inspect_authorized_keys(client, username: str, home: str) -> list[dict]:
    require_username(username)
    if not home:
        return []
    path = _authorized_keys_path(home)
    exit_code, out, _ = ssh.run(client, f"cat {shlex.quote(path)}", sudo=True)
    if exit_code != 0:
        return []
    keys: list[dict] = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = _extract_key(stripped)
        if parsed is not None:
            keys.append(_serialize_key(parsed))
    return keys


# --- Account mutations -----------------------------------------------------


def create_account(client, username: str, groups: list[str] | None = None) -> dict:
    require_username(username)
    groups = groups or []
    for g in groups:
        require_group(g)
    exists = ssh.run(client, f"getent passwd {shlex.quote(username)}")[0] == 0
    if not exists:
        ssh.run_checked(
            client,
            f"useradd -m -s /bin/bash {shlex.quote(username)}",
            sudo=True,
        )
    for g in groups:
        ssh.run_checked(
            client,
            f"usermod -aG {shlex.quote(g)} {shlex.quote(username)}",
            sudo=True,
        )
    return {"username": username, "created": not exists, "existed": exists}


def delete_account(client, username: str, delete_home: bool = False) -> dict:
    require_username(username)
    flag = "-r " if delete_home else ""
    ssh.run_checked(client, f"userdel {flag}{shlex.quote(username)}", sudo=True)
    return {"username": username, "deleted": True, "home_removed": delete_home}


def set_account_groups(
    client,
    username: str,
    add: list[str] | None = None,
    remove: list[str] | None = None,
) -> dict:
    require_username(username)
    add = add or []
    remove = remove or []
    for g in add:
        require_group(g)
        ssh.run_checked(
            client,
            f"usermod -aG {shlex.quote(g)} {shlex.quote(username)}",
            sudo=True,
        )
    for g in remove:
        require_group(g)
        ssh.run_checked(
            client,
            f"gpasswd -d {shlex.quote(username)} {shlex.quote(g)}",
            sudo=True,
        )
    return {"username": username, "added": add, "removed": remove}


# --- authorized_keys management -------------------------------------------


def _ensure_ssh_dir(client, username: str, home: str) -> str:
    ssh_dir = f"{home.rstrip('/')}/.ssh"
    q_dir = shlex.quote(ssh_dir)
    ssh.run_checked(client, f"mkdir -p {q_dir}", sudo=True)
    ssh.run_checked(client, f"chmod 700 {q_dir}", sudo=True)
    ssh.run_checked(client, f"chown {shlex.quote(username)}: {q_dir}", sudo=True)
    return ssh_dir


def _write_authorized_keys(client, username: str, home: str, lines: list[str]) -> None:
    """Atomically write authorized_keys, preserving nothing but the given lines."""
    ssh_dir = _ensure_ssh_dir(client, username, home)
    path = f"{ssh_dir}/authorized_keys"
    content = "\n".join(lines)
    if content:
        content += "\n"
    # Create the temp file inside .ssh so the final mv is an atomic
    # same-filesystem rename (mv across filesystems is copy+unlink).
    tmp = ssh.run_checked(
        client,
        f"mktemp -p {shlex.quote(ssh_dir)} .authorized_keys.XXXXXXXX",
        sudo=True,
    ).strip()
    q_tmp = shlex.quote(tmp)
    ssh.run_checked(client, f"tee {q_tmp} > /dev/null", sudo=True, input=content)
    ssh.run_checked(client, f"chmod 600 {q_tmp}", sudo=True)
    ssh.run_checked(client, f"chown {shlex.quote(username)}: {q_tmp}", sudo=True)
    ssh.run_checked(client, f"mv -f {q_tmp} {shlex.quote(path)}", sudo=True)


def _read_raw_authorized_keys(client, home: str) -> list[str]:
    path = _authorized_keys_path(home)
    exit_code, out, _ = ssh.run(client, f"cat {shlex.quote(path)}", sudo=True)
    if exit_code != 0:
        return []
    return out.splitlines()


def install_key(client, username: str, home: str, key_line: str) -> dict:
    require_username(username)
    parsed = parse_ssh_public_key(key_line)
    lines = _read_raw_authorized_keys(client, home)
    already = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        existing = _extract_key(stripped)
        if existing is not None and existing.fingerprint == parsed.fingerprint:
            already = True
            break
    if not already:
        lines.append(parsed.normalized)
        _write_authorized_keys(client, username, home, lines)
    return {
        "username": username,
        "fingerprint": parsed.fingerprint,
        "installed": not already,
        "already_present": already,
    }


def remove_key(client, username: str, home: str, fingerprint_or_line: str) -> dict:
    require_username(username)
    if fingerprint_or_line.startswith("SHA256:"):
        target_fp = fingerprint_or_line
    else:
        target_fp = parse_ssh_public_key(fingerprint_or_line).fingerprint
    lines = _read_raw_authorized_keys(client, home)
    kept: list[str] = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(line)
            continue
        existing = _extract_key(stripped)
        if existing is not None and existing.fingerprint == target_fp:
            removed = True
            continue
        kept.append(line)
    if removed:
        _write_authorized_keys(client, username, home, kept)
    return {"username": username, "fingerprint": target_fp, "removed": removed}


def archive_authorized_keys(client, username: str, home: str) -> dict:
    """Rename an existing authorized_keys to a unique backup; never overwrite."""
    require_username(username)
    ssh_dir = f"{home.rstrip('/')}/.ssh"
    path = f"{ssh_dir}/authorized_keys"

    exit_code, listing, _ = ssh.run(client, f"ls -1 {shlex.quote(ssh_dir)}", sudo=True)
    names = listing.split() if exit_code == 0 else []
    if any(n.startswith("authorized_keys.ksm-backup-") for n in names):
        return {"skipped": True, "reason": "backup already exists", "keys": []}

    discovered = inspect_authorized_keys(client, username, home)
    backup_path = None
    if "authorized_keys" in names:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = f"{path}.ksm-backup-{stamp}"
        ssh.run_checked(
            client,
            f"mv {shlex.quote(path)} {shlex.quote(backup_path)}",
            sudo=True,
        )
    _write_authorized_keys(client, username, home, [])
    return {"skipped": False, "backup_path": backup_path, "keys": discovered}
