"""Environment-based configuration (KSM_ prefix).

Loaded once into a nested pydantic model. An optional ``config.toml`` in the
working directory provides base values; ``KSM_*`` environment variables (and the
``*_FILE`` secret indirections) override them.
"""

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None


class AppConfig(BaseModel):
    db_path: str = "./data/ksm.db"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_dist: str = "./frontend/dist"
    log_level: str = "INFO"
    log_dir: str | None = None
    # Per-request HTTP access logs. Off by default to avoid log flood; the
    # remaining uvicorn logs are still routed through the app logger.
    access_log: bool = False


class AuthConfig(BaseModel):
    # Deployment secret for management-key encryption. None => mgmt-key ops 503.
    secret: str | None = None
    # Admin login token (plaintext); only its bcrypt hash is retained at runtime.
    admin_token: str | None = None
    session_ttl_hours: int = 72


class SSHConfig(BaseModel):
    connect_timeout: int = 10
    command_timeout: int = 60
    scan_timeout: int = 3600
    output_limit: int = 1048576
    max_workers: int = 8
    max_concurrent_scans: int = 2


class WebhookConfig(BaseModel):
    url: str = ""


class AuditConfig(BaseModel):
    retention_days: int = 365


class HealthConfig(BaseModel):
    interval: int = 0


class Config(BaseModel):
    app: AppConfig = AppConfig()
    auth: AuthConfig = AuthConfig()
    ssh: SSHConfig = SSHConfig()
    webhook: WebhookConfig = WebhookConfig()
    audit: AuditConfig = AuditConfig()
    health: HealthConfig = HealthConfig()


def _read_secret_file(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _get(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _load_toml() -> dict:
    path = os.environ.get("KSM_CONFIG", "config.toml")
    if tomllib is None:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        with p.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, ValueError):
        return {}


def _parse_env_file(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from a .env body into a dict.

    Blank lines and ``#`` comment lines are ignored, an optional leading
    ``export`` is tolerated, the value is split on the first ``=``, surrounding
    whitespace is stripped, and one pair of matching single or double quotes
    around the value is removed. Malformed lines (no ``=`` or empty key) are
    skipped silently.
    """
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        result[key] = value
    return result


def _load_dotenv() -> None:
    """Load a .env file into the environment before the config is read.

    Real environment variables always win (``os.environ.setdefault``). The path
    defaults to ``.env`` in the working directory; ``KSM_ENV_FILE`` overrides it.
    A missing or unreadable file is a no-op.
    """
    path = os.environ.get("KSM_ENV_FILE", ".env")
    p = Path(path)
    if not p.is_file():
        return
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return
    for key, value in _parse_env_file(text).items():
        os.environ.setdefault(key, value)


@lru_cache(maxsize=1)
def load_config() -> Config:
    base = _load_toml()
    cfg = Config(**base) if base else Config()

    # --- App ---
    cfg.app.db_path = _get("KSM_DB_PATH", cfg.app.db_path)
    cfg.app.host = _get("KSM_HOST", cfg.app.host)
    cfg.app.port = _get_int("KSM_PORT", cfg.app.port)
    cfg.app.frontend_dist = _get("KSM_FRONTEND_DIST", cfg.app.frontend_dist)
    cfg.app.log_level = _get("KSM_LOG_LEVEL", cfg.app.log_level)
    cfg.app.log_dir = _get("KSM_LOG_DIR", cfg.app.log_dir)
    cfg.app.access_log = _get_bool("KSM_ACCESS_LOG", cfg.app.access_log)

    # --- Auth / secrets (env inline wins; else *_FILE; else toml default) ---
    secret = _get("KSM_SECRET") or _read_secret_file(_get("KSM_SECRET_FILE"))
    cfg.auth.secret = secret if secret else cfg.auth.secret
    token = _get("KSM_ADMIN_TOKEN") or _read_secret_file(_get("KSM_ADMIN_TOKEN_FILE"))
    cfg.auth.admin_token = token if token else cfg.auth.admin_token
    cfg.auth.session_ttl_hours = _get_int(
        "KSM_SESSION_TTL_HOURS", cfg.auth.session_ttl_hours
    )

    # --- SSH ---
    cfg.ssh.connect_timeout = _get_int(
        "KSM_SSH_CONNECT_TIMEOUT", cfg.ssh.connect_timeout
    )
    cfg.ssh.command_timeout = _get_int(
        "KSM_SSH_COMMAND_TIMEOUT", cfg.ssh.command_timeout
    )
    cfg.ssh.scan_timeout = _get_int("KSM_SCAN_TIMEOUT", cfg.ssh.scan_timeout)
    cfg.ssh.output_limit = _get_int("KSM_SSH_OUTPUT_LIMIT", cfg.ssh.output_limit)
    cfg.ssh.max_workers = _get_int("KSM_MAX_WORKERS", cfg.ssh.max_workers)
    cfg.ssh.max_concurrent_scans = _get_int(
        "KSM_MAX_CONCURRENT_SCANS", cfg.ssh.max_concurrent_scans
    )

    # --- Webhook / audit / health ---
    cfg.webhook.url = _get("KSM_WEBHOOK_URL", cfg.webhook.url)
    cfg.audit.retention_days = _get_int(
        "KSM_AUDIT_RETENTION_DAYS", cfg.audit.retention_days
    )
    cfg.health.interval = _get_int("KSM_HEALTH_INTERVAL", cfg.health.interval)

    return cfg


def _data_dir() -> Path:
    return Path(load_config().app.db_path).expanduser().resolve().parent


def _chmod_600(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - filesystem/OS dependent
        pass


def ensure_secrets() -> dict:
    """Zero-config first run: materialize KSM_SECRET / KSM_ADMIN_TOKEN.

    Env (and *_FILE) values always win. Otherwise a value under the data
    directory is reused, or generated and persisted (chmod 0600 where possible).
    Returns a small info dict describing where each secret came from.
    """
    c = load_config()
    data_dir = _data_dir()
    info: dict[str, str] = {}

    if c.auth.secret:
        info["secret_source"] = "env"
    else:
        path = data_dir / "secret.key"
        if path.is_file():
            c.auth.secret = path.read_text(encoding="utf-8").strip()
            info["secret_source"] = "file"
        else:
            data_dir.mkdir(parents=True, exist_ok=True)
            c.auth.secret = secrets.token_urlsafe(48)
            path.write_text(c.auth.secret, encoding="utf-8")
            _chmod_600(path)
            info["secret_source"] = "generated"
        info["secret_path"] = str(path)

    if c.auth.admin_token:
        info["admin_token_source"] = "env"
    else:
        path = data_dir / "admin_token.txt"
        if path.is_file():
            c.auth.admin_token = path.read_text(encoding="utf-8").strip()
            info["admin_token_source"] = "file"
        else:
            data_dir.mkdir(parents=True, exist_ok=True)
            c.auth.admin_token = secrets.token_urlsafe(32)
            path.write_text(c.auth.admin_token, encoding="utf-8")
            _chmod_600(path)
            info["admin_token_source"] = "generated"
        info["admin_token_path"] = str(path)

    return info


def validate_production_safety() -> list[str]:
    """Return human-readable warnings about a risky configuration."""
    c = load_config()
    warnings: list[str] = []
    if not c.auth.admin_token:
        warnings.append(
            "KSM_ADMIN_TOKEN is not set; admin login is disabled until configured."
        )
    if not c.auth.secret:
        warnings.append(
            "KSM_SECRET is not set; management-key endpoints return 503 until configured."
        )
    if c.auth.secret and c.auth.admin_token and c.auth.secret == c.auth.admin_token:
        warnings.append(
            "KSM_SECRET must differ from KSM_ADMIN_TOKEN "
            "(do not tie key encryption to a login credential)."
        )
    return warnings


_load_dotenv()
cfg = load_config()
