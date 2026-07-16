"""Action runner lifecycle, interrupted marking, and per-machine locking."""

import threading
import time

from kohakusshmanager import runner, ssh
from kohakusshmanager.models import RemoteAction


def test_action_success_and_failure(dbfile):
    runner.set_sync(True)
    try:
        ok = RemoteAction.create(action="x", actor="t", state="pending")
        runner.submit_action(ok.id, lambda: {"done": True})
        ok = RemoteAction.get_by_id(ok.id)
        assert ok.state == "succeeded"
        assert ok.result == {"done": True}
        assert ok.started_at is not None and ok.finished_at is not None

        bad = RemoteAction.create(action="x", actor="t", state="pending")

        def boom():
            raise RuntimeError("kaboom")

        runner.submit_action(bad.id, boom)
        bad = RemoteAction.get_by_id(bad.id)
        assert bad.state == "failed"
        assert "kaboom" in bad.error
    finally:
        runner.set_sync(False)


def test_mark_interrupted_actions(dbfile):
    RemoteAction.create(action="x", actor="t", state="pending")
    RemoteAction.create(action="x", actor="t", state="running")
    RemoteAction.create(action="x", actor="t", state="succeeded")
    count = runner.mark_interrupted_actions()
    assert count == 2
    interrupted = (
        RemoteAction.select().where(RemoteAction.state == "interrupted").count()
    )
    assert interrupted == 2


def test_result_bounding(dbfile):
    huge = {"blob": "a" * 40000}
    bounded = runner.bounded_result(huge)
    assert bounded.get("truncated") is True


def test_machine_lock_serializes():
    order: list[tuple[str, str]] = []
    lock_id = 4242

    def worker(tag: str):
        with ssh.machine_lock(lock_id):
            order.append(("start", tag))
            time.sleep(0.05)
            order.append(("end", tag))

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Mutations serialize: each start is immediately followed by its own end.
    assert [o[0] for o in order] == ["start", "end", "start", "end"]


def test_machine_lock_registry_returns_same_lock():
    assert ssh.machine_lock(7) is ssh.machine_lock(7)
    assert ssh.machine_lock(7) is not ssh.machine_lock(8)
