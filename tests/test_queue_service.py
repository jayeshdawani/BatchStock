import pytest

from batchdock.services import job_store, queue_service


def test_retry_creates_new_job(monkeypatch):
    monkeypatch.setattr(queue_service, "_dispatch", lambda job, celery_task_id: None)
    original = job_store.create_job(
        task_type="demo",
        description="Original",
        parameters={"steps": 3, "step_seconds": 0.25, "start_delay_seconds": 0, "fail_at_step": 2},
    )
    job_store.update_job(original["id"], status="failed", error_message="failed")

    retry = queue_service.retry_failed_job(original["id"])
    assert retry["id"] != original["id"]
    assert retry["retry_of_job_id"] == original["id"]
    assert retry["status"] == "waiting"
    assert retry["parameters"]["fail_at_step"] is None


def test_remove_rejects_active_job():
    job = job_store.create_job(task_type="demo", description="Active", parameters={})
    with pytest.raises(queue_service.JobActionError, match="Only finished"):
        queue_service.remove_terminal_job(job["id"])


def test_cancel_waiting_job(monkeypatch, app):
    job = job_store.create_job(task_type="demo", description="Delayed", parameters={})
    job_store.attach_celery_task(job["id"], "task-123")
    calls = []
    monkeypatch.setattr(app.extensions["celery"].control, "revoke", lambda task_id, terminate: calls.append((task_id, terminate)))

    cancelled = queue_service.cancel_waiting_job(job["id"])
    assert calls == [("task-123", False)]
    assert cancelled["status"] == "cancelled"
