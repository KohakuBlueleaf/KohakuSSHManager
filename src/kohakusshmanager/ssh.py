"""Paramiko SSH wrapper: connect, host-key verification, run, per-machine locks.

Everything here is synchronous and is called from worker threads (or via
``asyncio.to_thread``). Tests never invoke real SSH; they monkeypatch
``connect`` / ``probe_host_key`` / ``run`` on this module.
"""

import base64
import io
import socket
import threading
from hashlib import sha256

import paramiko

from kohakusshmanager.config import cfg
from kohakusshmanager.logger import get_logger

logger = get_logger("SSH")


# --- Error hierarchy -------------------------------------------------------


class SSHError(Exception):
    """Base class for SSH failures."""


class SSHUnreachable(SSHError):
    """Host could not be reached / connection refused."""


class SSHAuthFailed(SSHError):
    """Authentication with the management key failed."""


class HostKeyMismatch(SSHError):
    """Presented host key did not match the enrolled fingerprint."""


class SSHTimeout(SSHError):
    """Connection or command timed out."""


class CommandFailed(SSHError):
    """A remote command exited non-zero."""

    def __init__(self, exit_code: int, stderr: str, command: str = ""):
        self.exit_code = exit_code
        self.stderr = stderr
        self.command = command
        msg = f"command failed (exit {exit_code})"
        if stderr:
            msg += f": {stderr.strip()[:300]}"
        super().__init__(msg)


# --- Host-key handling -----------------------------------------------------


def host_key_fingerprint(key: paramiko.PKey) -> str:
    """OpenSSH-style SHA256 fingerprint of a host key."""
    digest = sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class _VerifyingPolicy(paramiko.MissingHostKeyPolicy):
    """Accept only if the presented host key matches the expected fingerprint."""

    def __init__(self, expected: str | None):
        self.expected = expected

    def missing_host_key(self, client, hostname, key):
        actual = host_key_fingerprint(key)
        if self.expected is None or actual != self.expected:
            raise HostKeyMismatch(
                f"host key mismatch for {hostname}: "
                f"expected {self.expected}, got {actual}"
            )
        # Match: accept for this session (do not persist to a known_hosts file).


# --- Per-machine locks -----------------------------------------------------

_registry_lock = threading.Lock()
_machine_locks: dict[int, threading.Lock] = {}


def machine_lock(machine_id: int) -> threading.Lock:
    with _registry_lock:
        lock = _machine_locks.get(machine_id)
        if lock is None:
            lock = threading.Lock()
            _machine_locks[machine_id] = lock
        return lock


# --- Connection ------------------------------------------------------------


def _load_pkey(private_key_pem: str) -> paramiko.PKey:
    return paramiko.Ed25519Key.from_private_key(io.StringIO(private_key_pem))


def probe_host_key(address: str, port: int = 22) -> str:
    """Fetch the remote host-key fingerprint WITHOUT authenticating."""
    sock = None
    transport = None
    try:
        sock = socket.create_connection(
            (address, port), timeout=cfg.ssh.connect_timeout
        )
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=cfg.ssh.connect_timeout)
        key = transport.get_remote_server_key()
        return host_key_fingerprint(key)
    except socket.timeout as exc:
        raise SSHTimeout(f"timed out probing {address}:{port}") from exc
    except (OSError, paramiko.SSHException) as exc:
        raise SSHUnreachable(f"cannot reach {address}:{port}: {exc}") from exc
    finally:
        if transport is not None:
            transport.close()
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def connect(machine, private_key_pem: str, expected_fingerprint=None):
    """Open an authenticated SSHClient, verifying the host key fingerprint."""
    expected = (
        expected_fingerprint
        if expected_fingerprint is not None
        else machine.host_key_fingerprint
    )
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(_VerifyingPolicy(expected))
    try:
        client.connect(
            hostname=machine.address,
            port=machine.port,
            username=machine.management_user,
            pkey=_load_pkey(private_key_pem),
            timeout=cfg.ssh.connect_timeout,
            banner_timeout=cfg.ssh.connect_timeout,
            auth_timeout=cfg.ssh.connect_timeout,
            allow_agent=False,
            look_for_keys=False,
        )
    except HostKeyMismatch:
        client.close()
        raise
    except paramiko.AuthenticationException as exc:
        client.close()
        raise SSHAuthFailed(f"authentication failed for {machine.address}") from exc
    except socket.timeout as exc:
        client.close()
        raise SSHTimeout(f"connection to {machine.address} timed out") from exc
    except (socket.error, paramiko.SSHException) as exc:
        client.close()
        raise SSHUnreachable(f"cannot connect to {machine.address}: {exc}") from exc
    return client


# --- Command execution -----------------------------------------------------


def run(
    client,
    command: str,
    *,
    timeout: int | None = None,
    sudo: bool = False,
    input: str | None = None,
) -> tuple[int, str, str]:
    """Run a command; return (exit_code, stdout, stderr). Output is capped."""
    timeout = timeout if timeout is not None else cfg.ssh.command_timeout
    full = f"sudo -n -H {command}" if sudo else command
    limit = cfg.ssh.output_limit
    try:
        stdin, stdout, stderr = client.exec_command(full, timeout=timeout)
        if input is not None:
            stdin.write(input)
            stdin.flush()
            stdin.channel.shutdown_write()
        out = stdout.read(limit).decode("utf-8", "replace")
        err = stderr.read(limit).decode("utf-8", "replace")
        exit_code = stdout.channel.recv_exit_status()
        return exit_code, out, err
    except socket.timeout as exc:
        raise SSHTimeout(f"command timed out after {timeout}s") from exc
    except paramiko.SSHException as exc:
        raise SSHUnreachable(f"ssh error while running command: {exc}") from exc


def run_checked(
    client,
    command: str,
    *,
    timeout: int | None = None,
    sudo: bool = False,
    input: str | None = None,
) -> str:
    """Run a command, raising CommandFailed on non-zero exit; return stdout."""
    exit_code, out, err = run(client, command, timeout=timeout, sudo=sudo, input=input)
    if exit_code != 0:
        raise CommandFailed(exit_code, err, command)
    return out
