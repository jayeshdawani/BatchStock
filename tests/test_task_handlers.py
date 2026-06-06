from pathlib import Path

import pytest

from batchdock import tasks
from batchdock.services import job_store


def test_demo_workload_updates_job(monkeypatch):
    monkeypatch.setattr(tasks.time, "sleep", lambda _seconds: None)
    job = job_store.create_job(
        task_type="demo",
        description="Fast demo",
        parameters={"steps": 4, "step_seconds": 0.25},
    )

    output = tasks.run_demo_workload.apply(
        kwargs={"job_id": job["id"], "steps": 4, "step_seconds": 0.25, "fail_at_step": None}
    ).get()
    updated = job_store.get_job(job["id"])

    assert output["steps_completed"] == 4
    assert updated["status"] == "finished"
    assert updated["progress"] == 100


def test_demo_workload_records_controlled_failure(monkeypatch):
    monkeypatch.setattr(tasks.time, "sleep", lambda _seconds: None)
    job = job_store.create_job(
        task_type="demo",
        description="Failure demo",
        parameters={"steps": 4, "step_seconds": 0.25},
    )

    with pytest.raises(RuntimeError, match="Controlled demo failure"):
        tasks.run_demo_workload.apply(
            kwargs={"job_id": job["id"], "steps": 4, "step_seconds": 0.25, "fail_at_step": 2}
        ).get(propagate=True)

    updated = job_store.get_job(job["id"])
    assert updated["status"] == "failed"
    assert "step 2" in updated["error_message"]


def test_csv_summary_task(tmp_path: Path):
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text("name,value\nalpha,10\nbeta,20\n", encoding="utf-8")
    job = job_store.create_job(
        task_type="csv_summary",
        description="Metrics summary",
        parameters={},
        input_file=str(csv_path),
    )

    output = tasks.analyze_csv_file.apply(
        kwargs={"job_id": job["id"], "file_path": str(csv_path)}
    ).get()
    updated = job_store.get_job(job["id"])

    assert output["rows"] == 2
    assert output["columns"] == 2
    assert output["numeric_columns"]["value"]["mean"] == 15.0
    assert updated["status"] == "finished"
