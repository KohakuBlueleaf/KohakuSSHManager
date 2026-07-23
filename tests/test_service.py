"""systemd unit generation for `kohakusshmanager service`."""

from kohakusshmanager.service import build_unit


def test_system_unit_pins_python_workdir_and_user():
    unit = build_unit(
        python="/opt/venv/bin/python",
        workdir="/srv/ksm",
        user="cvlab",
        scope="system",
    )
    assert "ExecStart=/opt/venv/bin/python -m kohakusshmanager" in unit
    assert "WorkingDirectory=/srv/ksm" in unit
    assert "User=cvlab" in unit
    assert "Group=cvlab" in unit
    assert "WantedBy=multi-user.target" in unit
    assert "Restart=on-failure" in unit


def test_user_unit_omits_user_lines_and_targets_default():
    unit = build_unit(
        python="/opt/venv/bin/python",
        workdir="/srv/ksm",
        user="cvlab",
        scope="user",
    )
    assert "User=" not in unit
    assert "WantedBy=default.target" in unit
