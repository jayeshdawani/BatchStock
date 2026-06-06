from io import BytesIO

from batchdock import tasks
from batchdock.services import job_store, queue_service


def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"BatchDock" in response.data


def test_demo_submission_runs_in_eager_mode(client, monkeypatch):
    monkeypatch.setattr(tasks.time, "sleep", lambda _seconds: None)
    response = client.post(
        "/api/jobs",
        data={
            "task_type": "demo",
            "description": "Route demo",
            "steps": "3",
            "step_seconds": "0.25",
            "start_delay_seconds": "0",
            "fail_at_step": "0",
        },
    )
    assert response.status_code == 201
    created = response.get_json()["job"]
    stored = job_store.get_job(created["id"])
    assert stored["status"] == "finished"


def test_csv_submission_runs_in_eager_mode(client):
    response = client.post(
        "/api/jobs",
        data={
            "task_type": "csv_summary",
            "description": "Uploaded metrics",
            "start_delay_seconds": "0",
            "csv_file": (BytesIO(b"day,value\nMon,1\nTue,3\n"), "metrics.csv"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    created = response.get_json()["job"]
    assert job_store.get_job(created["id"])["status"] == "finished"


def test_invalid_demo_submission_returns_readable_error(client):
    response = client.post(
        "/api/jobs",
        data={"task_type": "demo", "steps": "100", "step_seconds": "1", "start_delay_seconds": "0", "fail_at_step": "0"},
    )
    assert response.status_code == 400
    assert "between 3 and 20" in response.get_json()["error"]


def test_worker_status_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        queue_service,
        "worker_status",
        lambda: {"available": True, "worker_count": 1, "workers": ["celery@test"], "checked_at": "now", "message": "ok"},
    )
    response = client.get("/api/worker-status")
    assert response.status_code == 200
    assert response.get_json()["worker_status"]["worker_count"] == 1
