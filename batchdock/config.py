import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _resolve_local_path(value: str, default: Path) -> str:
    configured = Path(value) if value else default
    if not configured.is_absolute():
        configured = BASE_DIR / configured
    return str(configured.resolve())


class Config:
    """Environment-backed settings for local development."""

    SECRET_KEY = os.getenv("SECRET_KEY", "batchdock-local-development-only")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    DATABASE_PATH = _resolve_local_path(
        os.getenv("DATABASE_PATH", ""), BASE_DIR / "instance" / "batchdock.sqlite3"
    )
    UPLOAD_FOLDER = _resolve_local_path(
        os.getenv("UPLOAD_FOLDER", ""), BASE_DIR / "instance" / "uploads"
    )

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    WORKER_PING_TIMEOUT = float(os.getenv("WORKER_PING_TIMEOUT", "0.5"))
    JOB_HISTORY_LIMIT = int(os.getenv("JOB_HISTORY_LIMIT", "100"))

    CELERY = {
        "broker_url": REDIS_URL,
        "result_backend": REDIS_URL,
        "task_ignore_result": False,
        "task_track_started": True,
        "broker_connection_retry_on_startup": True,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "result_expires": 86400,
        "broker_transport_options": {"visibility_timeout": 3600},
        "result_backend_transport_options": {"retry_policy": {"timeout": 5.0}},
    }
