"""In-process RemoteAction runner: a bounded thread pool + per-machine locks.

Not a distributed job system. It exists so the UI can show progress and so a
restart does not erase what was requested. On startup, leftover pending/running
actions are marked interrupted.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from kohakusshmanager import ssh, webhook
from kohakusshmanager.config import cfg
from kohakusshmanager.crypto import redact
from kohakusshmanager.db import db, utcnow
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import RemoteAction

logger = get_logger("RUNNER")

_RESULT_LIMIT = 16384

_executor: ThreadPoolExecutor | None = None
_scan_semaphore = threading.Semaphore(cfg.ssh.max_concurrent_scans)
_SYNC = False  # tests may flip this to run submitted actions inline


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=cfg.ssh.max_workers, thread_name_prefix="ksm-action"
        )
    return _executor


def set_sync(value: bool) -> None:
    """Run submitted actions inline (used by tests for determinism)."""
    global _SYNC
    _SYNC = value


def _bounded_result(result) -> dict | None:
    if result is None:
        return None
    if not isinstance(result, dict):
        result = {"value": str(result)}
    try:
        encoded = json.dumps(result)
    except (TypeError, ValueError):
        return {"summary": str(result)[:2000]}
    if len(encoded) > _RESULT_LIMIT:
        return {"truncated": True, "summary": encoded[:2000]}
    return result


# Public alias used by services when finalizing sync (non-pool) actions.
bounded_result = _bounded_result


def _finish(action_id: int, state: str, result=None, error: str | None = None) -> None:
    with db.atomic():
        RemoteAction.update(
            state=state,
            result=_bounded_result(result),
            error=redact(error) if error else None,
            finished_at=utcnow(),
        ).where(RemoteAction.id == action_id).execute()


def _run(action_id: int, fn: Callable[[], dict], machine_id, is_scan: bool) -> None:
    with db.atomic():
        RemoteAction.update(state="running", started_at=utcnow()).where(
            RemoteAction.id == action_id
        ).execute()

    lock = ssh.machine_lock(machine_id) if machine_id else None
    try:
        if is_scan:
            _scan_semaphore.acquire()
        try:
            if lock is not None:
                lock.acquire()
            try:
                result = fn()
            finally:
                if lock is not None:
                    lock.release()
        finally:
            if is_scan:
                _scan_semaphore.release()
        _finish(action_id, "succeeded", result=result)
    except Exception as exc:  # noqa: BLE001 - runner records all failures
        logger.exception("Action {} failed", action_id)
        _finish(action_id, "failed", error=str(exc))
        _notify_failure(action_id, exc)


def _notify_failure(action_id: int, exc: Exception) -> None:
    action = RemoteAction.get_or_none(RemoteAction.id == action_id)
    if action is None:
        return
    webhook.send(
        "action.failed",
        f"Action '{action.action}' failed: {exc}",
        {"action_id": action_id, "action": action.action},
    )


def submit_action(
    action_id: int,
    fn: Callable[[], dict],
    *,
    machine_id: int | None = None,
    is_scan: bool = False,
) -> None:
    """Schedule ``fn`` (a zero-arg callable returning a result dict)."""
    if _SYNC:
        _run(action_id, fn, machine_id, is_scan)
        return
    _get_executor().submit(_run, action_id, fn, machine_id, is_scan)


def mark_interrupted_actions() -> int:
    """Mark leftover pending/running actions interrupted (called on startup)."""
    count = (
        RemoteAction.update(state="interrupted", finished_at=utcnow())
        .where(RemoteAction.state.in_(["pending", "running"]))
        .execute()
    )
    if count:
        logger.info("Marked {} interrupted actions from a previous run", count)
    return count


def shutdown() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None
