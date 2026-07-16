"""Loguru-based logging with private-key redaction.

Usage:

    from kohakusshmanager.logger import get_logger
    logger = get_logger("AUTH")
    logger.info("...")

A global patcher runs every record's message through ``crypto.redact`` so PEM
private-key blocks never reach a sink.
"""

import sys
from pathlib import Path

from loguru import logger as _logger

from kohakusshmanager.config import cfg
from kohakusshmanager.crypto import redact

_configured = False

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[tag]}</cyan> | "
    "{message}"
)


def _patch(record) -> None:
    message = record.get("message")
    if isinstance(message, str):
        record["message"] = redact(message)


def _setup() -> None:
    global _configured
    if _configured:
        return
    _logger.remove()
    _logger.configure(patcher=_patch, extra={"tag": "APP"})
    _logger.add(
        sys.stderr,
        level=cfg.app.log_level,
        format=_FORMAT,
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    if cfg.app.log_dir:
        log_dir = Path(cfg.app.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        _logger.add(
            log_dir / "ksm.log",
            level=cfg.app.log_level,
            format=_FORMAT,
            rotation="10 MB",
            retention=10,
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )
    _configured = True


def get_logger(tag: str):
    """Return a logger bound to a short uppercase tag (e.g. "AUTH", "SSH")."""
    _setup()
    return _logger.bind(tag=tag)
