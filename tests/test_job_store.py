from batchdock.services import job_store


def test_job_store_lifecycle():
    job = job_store.create_job(
        task_type="demo",
        description="Store lifecycle",
        parameters={"steps": 3},
    )
    assert job["status"] == "waiting"
    assert job["progress"] == 0

    job_store.attach_celery_task(job["id"], "celery-123")
    job_store.update_job(job["id"], status="in_progress", progress=40, stage="Working")
    job_store.append_event(job["id"], "Halfway through")
    updated = job_store.get_job(job["id"])

    assert updated["celery_task_id"] == "celery-123"
    assert updated["status"] == "in_progress"
    assert updated["started_at"] is not None
    assert updated["events"][-1]["message"] == "Halfway through"

    job_store.update_job(job["id"], status="finished", progress=100, output={"ok": True})
    finished = job_store.get_job(job["id"])
    assert finished["completed_at"] is not None
    assert finished["output"] == {"ok": True}


def test_job_store_search_and_status_counts():
    job_store.create_job(task_type="demo", description="Alpha workload", parameters={})
    failed = job_store.create_job(task_type="demo", description="Beta workload", parameters={})
    job_store.update_job(failed["id"], status="failed", error_message="test")

    assert len(job_store.list_jobs(search="alpha")) == 1
    assert len(job_store.list_jobs(status="failed")) == 1
    counts = job_store.status_counts()
    assert counts["waiting"] == 1
    assert counts["failed"] == 1
