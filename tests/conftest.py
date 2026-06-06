from pathlib import Path

import pytest

from batchdock import create_app


@pytest.fixture()
def app(tmp_path: Path):
    upload_folder = tmp_path / "uploads"
    celery_config = {
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "task_ignore_result": False,
        "task_always_eager": True,
        "task_eager_propagates": True,
        "task_store_eager_result": True,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
    }
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE_PATH": str(tmp_path / "batchdock-test.sqlite3"),
            "UPLOAD_FOLDER": str(upload_folder),
            "CELERY": celery_config,
            "JOB_HISTORY_LIMIT": 50,
            "WORKER_PING_TIMEOUT": 0.01,
        }
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def app_context(app):
    with app.app_context():
        yield
