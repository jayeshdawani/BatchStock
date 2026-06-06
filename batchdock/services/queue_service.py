from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app

from . import job_store


class QueueServiceError(RuntimeError):
    pass


class JobActionError(RuntimeError):
    pass


def _celery_app():
    return current_app.extensions["celery"]


def _dispatch(job: dict[str, Any], celery_task_id: str):
    from batchdock.tasks import analyze_csv_file, run_demo_workload

    parameters = job["parameters"]
    countdown = int(parameters.get("start_delay_seconds", 0))

    if job["task_type"] == "demo":
        return run_demo_workload.apply_async(
            kwargs={
                "job_id": job["id"],
                "steps": int(parameters["steps"]),
                "step_seconds": float(parameters["step_seconds"]),
                "fail_at_step": parameters.get("fail_at_step"),
            },
            countdown=countdown,
            task_id=celery_task_id,
        )

    if job["task_type"] == "csv_summary":
        if not job["input_file"] or not Path(job["input_file"]).exists():
            raise QueueServiceError("The stored CSV input file is no longer available.")
        return analyze_csv_file.apply_async(
            kwargs={"job_id": job["id"], "file_path": job["input_file"]},
            countdown=countdown,
            task_id=celery_task_id,
        )

    raise QueueServiceError(f"Unsupported task type: {job['task_type']}")


def enqueue_job(
    *,
    task_type: str,
    description: str,
    parameters: dict[str, Any],
    input_file: str | None = None,
    retry_of_job_id: str | None = None,
) -> dict[str, Any]:
    job = job_store.create_job(
        task_type=task_type,
        description=description,
        parameters=parameters,
        input_file=input_file,
        retry_of_job_id=retry_of_job_id,
    )
    celery_task_id = str(uuid.uuid4())
    job_store.attach_celery_task(job["id"], celery_task_id)

    try:
        _dispatch(job_store.get_job(job["id"]), celery_task_id)
    except Exception as exc:
        message = f"Queue submission failed: {exc}"
        job_store.update_job(
            job["id"], status="failed", stage="Queue submission failed", error_message=message
        )
        job_store.append_event(job["id"], message, "error")
        raise QueueServiceError(
            "The job could not be queued. Confirm that Redis is running and try again."
        ) from exc

    delay = int(parameters.get("start_delay_seconds", 0))
    if delay:
        event = f"Submitted to Redis with a {delay}-second start delay."
    else:
        event = "Submitted to Redis and waiting for an available worker."
    job_store.append_event(job["id"], event)
    return job_store.get_job(job["id"])


def retry_failed_job(job_id: str) -> dict[str, Any]:
    original = job_store.get_job(job_id)
    if not original:
        raise JobActionError("Job not found.")
    if original["status"] != "failed":
        raise JobActionError("Only failed jobs can be retried.")

    job_store.append_event(job_id, "A retry was requested from the dashboard.")
    retry_parameters = dict(original["parameters"])
    if original["task_type"] == "demo" and retry_parameters.get("fail_at_step"):
        retry_parameters["fail_at_step"] = None

    retried_job = enqueue_job(
        task_type=original["task_type"],
        description=f"{original['description']} (retry)",
        parameters=retry_parameters,
        input_file=original["input_file"],
        retry_of_job_id=job_id,
    )
    if original["task_type"] == "demo" and original["parameters"].get("fail_at_step"):
        job_store.append_event(retried_job["id"], "Controlled demo failure was disabled for this retry.")
    return job_store.get_job(retried_job["id"])


def cancel_waiting_job(job_id: str) -> dict[str, Any]:
    job = job_store.get_job(job_id)
    if not job:
        raise JobActionError("Job not found.")
    if job["status"] != "waiting":
        raise JobActionError("Only waiting jobs can be cancelled safely from this dashboard.")
    if not job["celery_task_id"]:
        raise JobActionError("The queued task identifier is missing.")

    try:
        _celery_app().control.revoke(job["celery_task_id"], terminate=False)
    except Exception as exc:
        raise QueueServiceError(
            "Cancellation could not be sent to Redis. Confirm that Redis is running and try again."
        ) from exc

    job_store.update_job(job_id, status="cancelled", progress=0, stage="Cancelled before execution")
    job_store.append_event(job_id, "Waiting job cancellation requested; worker execution will be skipped.")
    return job_store.get_job(job_id)


def remove_terminal_job(job_id: str) -> None:
    job = job_store.get_job(job_id)
    if not job:
        raise JobActionError("Job not found.")
    if job["status"] not in job_store.TERMINAL_STATUSES:
        raise JobActionError("Only finished, failed, or cancelled records can be removed.")
    job_store.delete_job(job_id)


def worker_status() -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    timeout = float(current_app.config["WORKER_PING_TIMEOUT"])
    try:
        replies = _celery_app().control.ping(timeout=timeout) or []
    except Exception as exc:
        return {
            "available": False,
            "worker_count": 0,
            "workers": [],
            "checked_at": checked_at,
            "message": f"Worker check failed: {exc}",
        }

    workers = sorted(next(iter(reply.keys())) for reply in replies if reply)
    if not workers:
        return {
            "available": False,
            "worker_count": 0,
            "workers": [],
            "checked_at": checked_at,
            "message": "No worker replied before the status-check timeout.",
        }

    return {
        "available": True,
        "worker_count": len(workers),
        "workers": workers,
        "checked_at": checked_at,
        "message": "Worker reply received.",
    }
