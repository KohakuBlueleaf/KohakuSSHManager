"""``kohakusshmanager service`` — set up a systemd unit for this installation.

The unit always runs the exact interpreter this command was invoked with
(``sys.executable``), so whichever venv/conda env has kohakusshmanager
installed is the one systemd uses. The working directory is captured from the
current directory, because ``./data`` and ``.env`` resolve relative to it.
"""

import argparse
import getpass
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_UNIT = """\
[Unit]
Description=KohakuSSHManager panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
{user_lines}WorkingDirectory={workdir}
ExecStart={python} -m kohakusshmanager
Restart=on-failure
RestartSec=3

[Install]
WantedBy={wanted_by}
"""


def build_unit(python: str, workdir: str, user: str | None, scope: str) -> str:
    """Render the unit file. ``scope`` is "system" or "user"."""
    user_lines = f"User={user}\nGroup={user}\n" if scope == "system" and user else ""
    wanted_by = "multi-user.target" if scope == "system" else "default.target"
    return _UNIT.format(
        user_lines=user_lines, workdir=workdir, python=python, wanted_by=wanted_by
    )


def _run(cmd: list[str]) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _install_system(name: str, unit: str) -> None:
    target = f"/etc/systemd/system/{name}.service"
    if os.geteuid() == 0:
        Path(target).write_text(unit, encoding="utf-8")
        print(f"  wrote {target}")
        _run(["systemctl", "daemon-reload"])
        _run(["systemctl", "enable", "--now", name])
    else:
        # Not root: stage the unit and escalate only the install steps.
        with tempfile.NamedTemporaryFile(
            "w", suffix=".service", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(unit)
            staged = fh.name
        try:
            _run(["sudo", "install", "-m", "0644", staged, target])
            _run(["sudo", "systemctl", "daemon-reload"])
            _run(["sudo", "systemctl", "enable", "--now", name])
        finally:
            os.unlink(staged)
    print(f"\nService installed and started. Useful commands:")
    print(f"  systemctl status {name}")
    print(f"  journalctl -u {name} -f")


def _install_user(name: str, unit: str) -> None:
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    target = unit_dir / f"{name}.service"
    target.write_text(unit, encoding="utf-8")
    print(f"  wrote {target}")
    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", name])
    print(f"\nService installed and started. Useful commands:")
    print(f"  systemctl --user status {name}")
    print(f"  journalctl --user -u {name} -f")
    print(
        "To keep it running after logout / start it at boot, enable lingering once:"
        f"\n  sudo loginctl enable-linger {getpass.getuser()}"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="kohakusshmanager service",
        description=(
            "Install a systemd service that runs kohakusshmanager from the "
            "current directory using the current Python environment."
        ),
    )
    parser.add_argument("--name", default="kohakusshmanager", help="systemd unit name")
    parser.add_argument(
        "--user",
        action="store_true",
        help="install a user-level unit (~/.config/systemd/user) instead of a system one",
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the generated unit file and exit without installing",
    )
    args = parser.parse_args(argv)

    scope = "user" if args.user else "system"
    unit = build_unit(
        python=sys.executable,
        workdir=str(Path.cwd()),
        user=getpass.getuser(),
        scope=scope,
    )

    print(f"Python:            {sys.executable}")
    print(f"Working directory: {Path.cwd()}  (data/ and .env resolve here)")
    print()

    if args.print_only:
        print(unit)
        return

    if platform.system() != "Linux" or shutil.which("systemctl") is None:
        print(
            "systemd is not available here; rerun with --print and install the "
            "unit manually on the target machine."
        )
        raise SystemExit(1)

    try:
        if scope == "user":
            _install_user(args.name, unit)
        else:
            _install_system(args.name, unit)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"command failed with exit code {exc.returncode}") from exc
