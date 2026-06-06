from __future__ import annotations

from typing import Any

STATUS_LABELS = {
    "waiting": "Waiting",
    "in_progress": "In Progress",
    "finished": "Finished",
    "failed": "Failed",
    "cancelled": "Cancelled",
}

TASK_TYPE_LABELS = {
    "demo": "Timed Demo",
    "csv_summary": "CSV Summary",
}


def serialize_job(job: dict[str, Any], *, include_events: bool = False) -> dict[str, Any]:
    result = {
        "id": job["id"],
        "celery_task_id": job["celery_task_id"],
        "retry_of_job_id": job["retry_of_job_id"],
        "task_type": job["task_type"],
        "task_type_label": TASK_TYPE_LABELS.get(job["task_type"], job["task_type"]),
        "description": job["description"],
        "status": job["status"],
        "status_label": STATUS_LABELS.get(job["status"], job["status"]),
        "progress": int(job["progress"]),
        "stage": job["stage"],
        "parameters": job["parameters"],
        "output": job["output"],
        "error_message": job["error_message"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
        "updated_at": job["updated_at"],
        "actions": {
            "can_retry": job["status"] == "failed",
            "can_cancel": job["status"] == "waiting",
            "can_remove": job["status"] in {"finished", "failed", "cancelled"},
        },
    }
    if include_events:
        result["events"] = job["events"]
    return result
