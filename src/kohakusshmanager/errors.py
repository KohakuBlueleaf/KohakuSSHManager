"""Domain error hierarchy and FastAPI exception handlers.

Endpoints may raise these (or ``HTTPException`` directly). One set of handlers
maps them to status codes with a uniform ``{"detail": "..."}`` body.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kohakusshmanager.logger import get_logger

logger = get_logger("API")


class KSMError(Exception):
    """Base class for expected application errors."""


class NotFoundError(KSMError):
    """A referenced resource does not exist -> 404."""


class ConflictError(KSMError):
    """A uniqueness/state conflict -> 409."""


class ValidationError(KSMError):
    """Invalid input that pydantic did not catch -> 400."""


def _json(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def add_exception_handlers(app: FastAPI) -> None:
    # Imported here to avoid a config/ssh import cycle at module load.
    from kohakusshmanager.ssh import (
        CommandFailed,
        HostKeyMismatch,
        SSHAuthFailed,
        SSHTimeout,
        SSHUnreachable,
    )

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError):
        return _json(404, str(exc))

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError):
        return _json(409, str(exc))

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError):
        return _json(400, str(exc))

    @app.exception_handler(HostKeyMismatch)
    async def _host_key(request: Request, exc: HostKeyMismatch):
        return _json(409, str(exc))

    @app.exception_handler(SSHTimeout)
    async def _timeout(request: Request, exc: SSHTimeout):
        return _json(504, str(exc))

    @app.exception_handler(SSHUnreachable)
    async def _unreachable(request: Request, exc: SSHUnreachable):
        return _json(502, str(exc))

    @app.exception_handler(SSHAuthFailed)
    async def _auth_failed(request: Request, exc: SSHAuthFailed):
        return _json(502, str(exc))

    @app.exception_handler(CommandFailed)
    async def _command_failed(request: Request, exc: CommandFailed):
        return _json(502, str(exc))

    @app.exception_handler(KSMError)
    async def _ksm_error(request: Request, exc: KSMError):
        logger.exception("Unhandled KSMError")
        return _json(500, str(exc))
