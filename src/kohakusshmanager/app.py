"""FastAPI application factory, lifespan, and console entrypoint."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kohakusshmanager import __version__
from kohakusshmanager.api import api_router
from kohakusshmanager.audit import cleanup_audit
from kohakusshmanager.auth import init_admin_token
from kohakusshmanager.config import cfg, ensure_secrets, validate_production_safety
from kohakusshmanager.db import init_db, run_migrations
from kohakusshmanager.errors import add_exception_handlers
from kohakusshmanager.logger import get_logger
from kohakusshmanager.models import Machine
from kohakusshmanager.runner import (
    mark_interrupted_actions,
    shutdown as runner_shutdown,
)

logger = get_logger("APP")

_ONE_DAY = 24 * 3600


async def _health_timer() -> None:
    from kohakusshmanager import services

    while True:
        await asyncio.sleep(cfg.health.interval)
        try:
            for machine in Machine.select().where(
                Machine.enrolled == True
            ):  # noqa: E712
                services.refresh_machine(machine, "system")
        except Exception:  # pragma: no cover - background best-effort
            logger.exception("Health timer refresh failed")


async def _audit_cleanup_timer() -> None:
    while True:
        await asyncio.sleep(_ONE_DAY)
        try:
            cleanup_audit()
        except Exception:  # pragma: no cover - background best-effort
            logger.exception("Audit cleanup failed")


def _log_banner(secret_info: dict) -> None:
    dist = _spa_dir()
    logger.info("=" * 60)
    logger.info("KohakuSSHManager {} starting", __version__)
    logger.info("Panel URL:   http://{}:{}", cfg.app.host, cfg.app.port)
    logger.info("Database:    {}", cfg.app.db_path)
    logger.info("Frontend:    {}", str(dist) if dist else "not found (API only)")
    secret_src = secret_info.get("secret_source")
    if secret_src == "env":
        logger.info("Deploy secret: from environment")
    else:
        logger.info(
            "Deploy secret: {} at {}", secret_src, secret_info.get("secret_path")
        )
    token_src = secret_info.get("admin_token_source")
    if token_src == "env":
        logger.info("Admin login:  username '__token__' (token from environment)")
    else:
        logger.info(
            "Admin login:  username '__token__' (token {} at {})",
            token_src,
            secret_info.get("admin_token_path"),
        )
    logger.info("=" * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    applied = run_migrations()
    if applied:
        logger.info("Applied migrations: {}", ", ".join(applied))
    secret_info = ensure_secrets()
    init_admin_token()
    _log_banner(secret_info)
    for warning in validate_production_safety():
        logger.warning(warning)
    mark_interrupted_actions()
    cleanup_audit()

    tasks: list[asyncio.Task] = []
    if cfg.health.interval > 0:
        tasks.append(asyncio.create_task(_health_timer()))
    tasks.append(asyncio.create_task(_audit_cleanup_timer()))

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        runner_shutdown()


def _spa_dir() -> Path | None:
    packaged = Path(__file__).parent / "web_dist"
    if (packaged / "index.html").is_file():
        return packaged
    configured = Path(cfg.app.frontend_dist)
    if (configured / "index.html").is_file():
        return configured
    return None


def _mount_spa(app: FastAPI) -> None:
    dist = _spa_dir()
    if dist is None:
        logger.info("No frontend build found; serving API only")
        return
    dist = dist.resolve()
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        candidate = (dist / full_path).resolve()
        if candidate.is_relative_to(dist) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")

    logger.info("Serving SPA from {}", dist)


def create_app() -> FastAPI:
    app = FastAPI(
        title="KohakuSSHManager",
        version=__version__,
        lifespan=lifespan,
    )
    add_exception_handlers(app)
    app.include_router(api_router, prefix="/api")

    @app.get("/api/healthz")
    async def healthz():
        return {"status": "ok", "version": __version__}

    _mount_spa(app)
    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "kohakusshmanager.app:app",
        host=cfg.app.host,
        port=cfg.app.port,
    )


if __name__ == "__main__":
    main()
