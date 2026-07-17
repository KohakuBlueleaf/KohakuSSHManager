"""Shared test fixtures and an in-memory FakeSSH layer.

No real SSH is ever used. We monkeypatch ``ssh.connect`` / ``ssh.probe_host_key``
/ ``ssh.run`` on the ssh module; the real ``ssh.run_checked`` then executes
against a fake in-memory machine (accounts + authorized_keys + canned outputs).
"""

import os
import shlex

os.environ.setdefault("KSM_ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("KSM_SECRET", "test-deployment-secret")
os.environ.setdefault("KSM_LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)
from fastapi.testclient import TestClient  # noqa: E402

from kohakusshmanager import runner, ssh  # noqa: E402
from kohakusshmanager.app import create_app  # noqa: E402
from kohakusshmanager.db import (  # noqa: E402
    db,
    init_db,
    reset_db_pool,
    run_migrations,
)

# --- Fake machine ----------------------------------------------------------


class FakeMachine:
    def __init__(self, fingerprint: str = "SHA256:FAKEFINGERPRINT0001"):
        self.host_fingerprint = fingerprint
        self.sudo_ok = True
        self.reachable = True
        self.accounts: dict[str, dict] = {}
        self.authorized: dict[str, str] = {}
        self.backups: dict[str, dict[str, str]] = {}
        self.tmp: dict[str, str] = {}
        self._tmp_counter = 0
        self.usage_owners: list[tuple[int, int, int]] = []
        self.facts = {
            "cat /etc/os-release": 'PRETTY_NAME="Ubuntu 22.04.3 LTS"\nID=ubuntu\n',
            "hostname": "fakehost",
            "uname -r": "5.15.0-generic",
            "nproc": "8",
            "grep -m1 'model name' /proc/cpuinfo": "model name\t: Fake CPU X",
            "grep MemTotal /proc/meminfo": "MemTotal:       16000000 kB",
            "findmnt -rn -o TARGET,SOURCE,FSTYPE,SIZE": (
                "/ /dev/sda1 ext4 100G\n/data nas1:/data nfs 1T"
            ),
            "df -B1 --output=target,size,used,avail -x tmpfs -x devtmpfs": (
                "target size used avail\n"
                "/ 107374182400 5000000000 100000000000\n"
                "/data 1099511627776 500000000000 599511627775"
            ),
        }

    # -- setup helpers --
    def add_account(
        self,
        username: str,
        uid: int,
        gid: int | None = None,
        home: str | None = None,
        shell: str = "/bin/bash",
        groups: list[str] | None = None,
        keys: list[str] | None = None,
        locked: bool = False,
    ) -> None:
        home = home or f"/home/{username}"
        self.accounts[username] = {
            "uid": uid,
            "gid": gid if gid is not None else uid,
            "gecos": "",
            "home": home,
            "shell": shell,
            "groups": groups or [username],
            "locked": locked,
        }
        if keys is not None:
            self.authorized[username] = "\n".join(keys) + ("\n" if keys else "")

    # -- path resolution --
    def _user_for_akpath(self, path: str) -> str | None:
        for name, acc in self.accounts.items():
            base = f"{acc['home'].rstrip('/')}/.ssh/authorized_keys"
            if path == base or path.startswith(base + "."):
                return name
        return None

    def _user_for_sshdir(self, ssh_dir: str) -> str | None:
        for name, acc in self.accounts.items():
            if ssh_dir == f"{acc['home'].rstrip('/')}/.ssh":
                return name
        return None

    def _passwd_all(self) -> str:
        lines = [
            "root:x:0:0:root:/root:/bin/bash",
            "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin",
        ]
        for name, acc in self.accounts.items():
            lines.append(
                f"{name}:x:{acc['uid']}:{acc['gid']}:{acc['gecos']}:"
                f"{acc['home']}:{acc['shell']}"
            )
        return "\n".join(lines)

    def _getent_one(self, arg: str):
        if arg.isdigit():
            uid = int(arg)
            for name, acc in self.accounts.items():
                if acc["uid"] == uid:
                    return (
                        0,
                        f"{name}:x:{uid}:{acc['gid']}:{acc['gecos']}:"
                        f"{acc['home']}:{acc['shell']}\n",
                        "",
                    )
            return 2, "", ""
        acc = self.accounts.get(arg)
        if not acc:
            return 2, "", ""
        return (
            0,
            f"{arg}:x:{acc['uid']}:{acc['gid']}:{acc['gecos']}:"
            f"{acc['home']}:{acc['shell']}\n",
            "",
        )

    def _usage_owner_output(self) -> str:
        owners = self.usage_owners or [
            (acc["uid"], 1000 * acc["uid"], 3) for acc in self.accounts.values()
        ]
        return "\n".join(f"{uid} {size} {count}" for uid, size, count in owners)

    # -- command dispatch --
    def run(self, command: str, sudo: bool = False, input: str | None = None):
        if command in self.facts:
            return 0, self.facts[command], ""
        if command.startswith("nvidia-smi"):
            return 1, "", "nvidia-smi: command not found"
        if command == "true":
            return (0, "", "") if self.sudo_ok else (1, "", "sudo failed")
        if command == "getent passwd":
            return 0, self._passwd_all(), ""
        if command.startswith("getent passwd "):
            return self._getent_one(command.split(" ", 2)[2])
        if command.startswith("id -Gn "):
            name = shlex.split(command)[2]
            acc = self.accounts.get(name)
            return (0, " ".join(acc["groups"]), "") if acc else (1, "", "no such user")
        if command.startswith("passwd -S "):
            name = shlex.split(command)[2]
            acc = self.accounts.get(name)
            if not acc:
                return 1, "", ""
            state = "L" if acc["locked"] else "P"
            return 0, f"{name} {state} 01/01/2020 0 99999 7 -1\n", ""
        if command.startswith("useradd "):
            name = shlex.split(command)[-1]
            if name not in self.accounts:
                uid = 2000 + len(self.accounts)
                self.add_account(name, uid)
                self.authorized.pop(name, None)
            return 0, "", ""
        if command.startswith("usermod -aG "):
            parts = shlex.split(command)
            group, name = parts[2], parts[3]
            if name in self.accounts and group not in self.accounts[name]["groups"]:
                self.accounts[name]["groups"].append(group)
            return 0, "", ""
        if command.startswith("gpasswd -d "):
            parts = shlex.split(command)
            name, group = parts[2], parts[3]
            if name in self.accounts and group in self.accounts[name]["groups"]:
                self.accounts[name]["groups"].remove(group)
            return 0, "", ""
        if command.startswith("userdel"):
            name = shlex.split(command)[-1]
            self.accounts.pop(name, None)
            self.authorized.pop(name, None)
            return 0, "", ""
        if command.startswith(("mkdir -p ", "chmod ", "chown ")):
            return 0, "", ""
        if command.startswith("mktemp"):
            self._tmp_counter += 1
            path = f"/tmp/ksmfake{self._tmp_counter}"
            self.tmp[path] = ""
            return 0, path + "\n", ""
        if command.startswith("tee "):
            tmp = shlex.split(command.replace("> /dev/null", ""))[1]
            self.tmp[tmp] = input or ""
            return 0, "", ""
        if command.startswith("mv -f "):
            parts = shlex.split(command)
            src, dest = parts[2], parts[3]
            content = self.tmp.pop(src, "")
            user = self._user_for_akpath(dest)
            if user is not None:
                self.authorized[user] = content
            return 0, "", ""
        if command.startswith("mv "):
            parts = shlex.split(command)
            src, dest = parts[1], parts[2]
            user = self._user_for_akpath(src)
            if user is not None:
                backup_name = dest.rsplit("/", 1)[1]
                self.backups.setdefault(user, {})[backup_name] = self.authorized.get(
                    user, ""
                )
                self.authorized.pop(user, None)
            return 0, "", ""
        if command.startswith("cat "):
            path = shlex.split(command)[1]
            user = self._user_for_akpath(path)
            if user is not None and user in self.authorized:
                return 0, self.authorized[user], ""
            return 1, "", "No such file or directory"
        if command.startswith("ls -1 "):
            ssh_dir = shlex.split(command)[2]
            user = self._user_for_sshdir(ssh_dir)
            names = []
            if user is not None:
                if user in self.authorized:
                    names.append("authorized_keys")
                names.extend(self.backups.get(user, {}).keys())
            return 0, "\n".join(names), ""
        if command.startswith("mountpoint -q "):
            return 0, "", ""
        if command.startswith("df -B1 --output=size,used,avail "):
            return 0, "size used avail\n1099511627776 500000000000 599511627775\n", ""
        if command.startswith("find "):
            return 0, self._usage_owner_output(), ""
        if command.startswith("du -sB1 "):
            path = shlex.split(command)[2]
            return 0, f"123456789\t{path}\n", ""
        if command.startswith("findmnt -rn -o TARGET --target"):
            path = shlex.split(command)[-1]
            return 0, path + "\n", ""
        return 127, "", f"command not found: {command}"


class FakeClient:
    def __init__(self, machine: FakeMachine):
        self.machine = machine

    def close(self):
        pass


class FakeRegistry:
    def __init__(self):
        self.machines: dict[str, FakeMachine] = {}

    def add(self, address: str, **kwargs) -> FakeMachine:
        machine = FakeMachine(**kwargs)
        self.machines[address] = machine
        return machine


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def dbfile(tmp_path):
    path = str(tmp_path / "ksm.db")
    init_db(path, force=True)
    # Fresh single-thread DB pool bound to this test's file (the pool thread
    # holds its own connection, so it must be recreated when the path changes).
    reset_db_pool()
    run_migrations(db)
    yield path
    if not db.is_closed():
        db.close()


@pytest.fixture
def client(dbfile):
    runner.set_sync(True)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    runner.set_sync(False)


@pytest.fixture
def fake(monkeypatch):
    registry = FakeRegistry()

    def fake_connect(machine, private_key_pem, expected_fingerprint=None):
        fm = registry.machines.get(machine.address)
        if fm is None or not fm.reachable:
            raise ssh.SSHUnreachable(f"fake host {machine.address} unreachable")
        return FakeClient(fm)

    def fake_probe(address, port=22):
        fm = registry.machines.get(address)
        if fm is None or not fm.reachable:
            raise ssh.SSHUnreachable(f"fake host {address} unreachable")
        return fm.host_fingerprint

    def fake_run(client, command, *, timeout=None, sudo=False, input=None):
        return client.machine.run(command, sudo=sudo, input=input)

    monkeypatch.setattr(ssh, "connect", fake_connect)
    monkeypatch.setattr(ssh, "probe_host_key", fake_probe)
    monkeypatch.setattr(ssh, "run", fake_run)
    return registry


# --- Auth helpers ----------------------------------------------------------


ADMIN_TOKEN = os.environ["KSM_ADMIN_TOKEN"]


def make_pubkey(comment: str = "test@host") -> str:
    private = Ed25519PrivateKey.generate()
    pub = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
        .decode("ascii")
    )
    return f"{pub} {comment}" if comment else pub


def login_admin(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login", json={"username": "__token__", "password": ADMIN_TOKEN}
    )
    assert resp.status_code == 200, resp.text


def login_user(client: TestClient, username: str, password: str) -> None:
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text


def create_user(
    client: TestClient, username: str, password: str, role: str = "member"
) -> dict:
    resp = client.post(
        "/api/users",
        json={
            "username": username,
            "password": password,
            "role": role,
            "display_name": username,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def register_machine(
    client: TestClient, name: str, address: str, mgmt_user: str = "mgr"
) -> dict:
    resp = client.post(
        "/api/machines",
        json={"name": name, "address": address, "management_user": mgmt_user},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def enroll_machine(client: TestClient, machine_id: int, fingerprint: str) -> None:
    probe = client.post(f"/api/machines/{machine_id}/enroll")
    assert probe.status_code == 200, probe.text
    confirm = client.post(
        f"/api/machines/{machine_id}/enroll/confirm",
        json={"fingerprint": fingerprint},
    )
    assert confirm.status_code == 200, confirm.text
