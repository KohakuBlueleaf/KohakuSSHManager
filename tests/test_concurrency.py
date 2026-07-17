"""Concurrent writes must serialize through the single DB thread without
'database is locked' errors or deadlocks."""

import threading

from kohakusshmanager.db import db_write
from kohakusshmanager.models import AuditLog


def test_concurrent_writes_serialize(dbfile):
    n_threads = 16
    per_thread = 25
    errors: list[Exception] = []

    def worker(tid: int) -> None:
        try:
            for j in range(per_thread):
                db_write(
                    lambda tid=tid, j=j: AuditLog.create(
                        actor=f"t{tid}", action="write", target=str(j), detail=""
                    )
                )
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    # Every write landed exactly once (serialized, none lost to a lock error).
    assert AuditLog.select().count() == n_threads * per_thread
