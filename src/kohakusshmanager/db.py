"""SQLite database handle, time helpers, and the migration runner.

The database is created deferred (``SqliteDatabase(None)``) so tests can point it
at a temp file before connecting. Schema is owned by ordered Python migrations in
``migrations/mNNN_name.py``; each exposes ``migrate(db)`` and applied names are
tracked in a ``schema_migrations`` table.
"""

import importlib
import pkgutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from peewee import SqliteDatabase

from kohakusshmanager.logger import get_logger

logger = get_logger("DB")

_PRAGMAS = {"journal_mode": "wal", "foreign_keys": 1, "busy_timeout": 10000}

db = SqliteDatabase(None)

# SQLite permits only one writer at a time. The action runner writes from a
# bounded thread pool and the background health timer writes from the event
# loop, so concurrent transactions would otherwise raise "database is locked".
# Instead of locking, every write runs on a single dedicated DB thread (one
# connection), which serializes writers by construction. Reads stay concurrent
# on their own thread-local connections under WAL.
#
# IMPORTANT: never call ``db_write`` from inside another ``db_write`` callable.
# The pool has a single worker, so a nested call would wait on itself forever.
# Wrap only top-level transactions; helpers they call must use raw DB ops.
_db_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ksm-db")


def db_write(fn, *args, **kwargs):
    """Run ``fn`` inside a transaction on the dedicated DB thread and return it."""

    def _tx():
        with db.atomic():
            return fn(*args, **kwargs)

    return _db_pool.submit(_tx).result()


def db_shutdown() -> None:
    _db_pool.shutdown(wait=False)


def reset_db_pool() -> None:
    """Recreate the DB thread. Used by tests that rebind the database file so
    the pool thread opens a fresh connection to the new path."""
    global _db_pool
    _db_pool.shutdown(wait=False)
    _db_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ksm-db")


def utcnow() -> datetime:
    """Naive UTC timestamp (stored as ISO by peewee's DateTimeField)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_iso_z(dt: datetime | None) -> str | None:
    """Serialize a stored naive-UTC datetime as ISO-8601 with a Z suffix."""
    if dt is None:
        return None
    if isinstance(dt, str):
        # Peewee occasionally hands back the raw string; normalize it.
        dt = dt.replace(" ", "T")
        return dt if dt.endswith("Z") else dt + "Z"
    return dt.replace(microsecond=dt.microsecond).isoformat() + "Z"


def init_db(path: str | None = None, force: bool = False) -> SqliteDatabase:
    """Bind the deferred database to a file path and open it. Idempotent."""
    from kohakusshmanager.config import cfg

    if db.database is not None and not force:
        db.connect(reuse_if_open=True)
        return db
    if not db.is_closed():
        db.close()
    path = path or cfg.app.db_path
    if path != ":memory:":
        Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    db.init(path, pragmas=_PRAGMAS)
    db.connect(reuse_if_open=True)
    logger.info("Database initialized at {}", path)
    return db


def _discover_migrations() -> list[tuple[str, object]]:
    from kohakusshmanager import migrations

    found: list[tuple[str, object]] = []
    for info in pkgutil.iter_modules(migrations.__path__):
        if info.name.startswith("m") and info.name[1:4].isdigit():
            module = importlib.import_module(f"{migrations.__name__}.{info.name}")
            found.append((info.name, module))
    found.sort(key=lambda item: item[0])
    return found


def run_migrations(database: SqliteDatabase | None = None) -> list[str]:
    """Apply pending migrations; return the names newly applied."""
    database = database or db
    database.connect(reuse_if_open=True)
    database.execute_sql(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(name TEXT PRIMARY KEY, applied_at TEXT)"
    )
    applied = {
        row[0]
        for row in database.execute_sql("SELECT name FROM schema_migrations").fetchall()
    }
    newly: list[str] = []
    for name, module in _discover_migrations():
        if name in applied:
            continue
        logger.info("Applying migration {}", name)
        with database.atomic():
            module.migrate(database)
            database.execute_sql(
                "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                (name, utcnow().isoformat()),
            )
        newly.append(name)
    return newly
