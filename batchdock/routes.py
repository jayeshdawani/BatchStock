from __future__ import annotations

import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from .services import job_store, queue_service
from .services.result_formatter import serialize_job

dashboard_bp = Blueprint("dashboard", __name__)


def _error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def _parse_int(name: str, *, minimum: int, maximum: int, default: int | None = None) -> int:
    raw_value = request.form.get(name, "").strip()
    if not raw_value and default is not None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name.replace('_', ' ').title()} must be a whole number.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name.replace('_', ' ').title()} must be between {minimum} and {maximum}.")
    return value


def _parse_float(name: str, *, minimum: float, maximum: float, default: float) -> float:
    raw_value = request.form.get(name, "").strip()
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name.replace('_', ' ').title()} must be a number.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name.replace('_', ' ').title()} must be between {minimum} and {maximum}.")
    return value


@dashboard_bp.get("/")
def dashboard():
    return render_template("dashboard.html")


@dashboard_bp.get("/jobs/<job_id>")
def job_details(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        return render_template("job_details.html", missing_job_id=job_id), 404
    return render_template("job_details.html", job=serialize_job(job, include_events=True))


@dashboard_bp.get("/api/jobs")
def list_jobs():
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()
    if status and status not in job_store.ALL_STATUSES:
        return _error("Unknown status filter.")

    jobs = job_store.list_jobs(
        search=search,
        status=status,
        limit=current_app.config["JOB_HISTORY_LIMIT"],
    )
    return jsonify(
        {
            "jobs": [serialize_job(job) for job in jobs],
            "counts": job_store.status_counts(),
        }
    )


@dashboard_bp.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        return _error("Job not found.", 404)
    return jsonify({"job": serialize_job(job, include_events=True)})


@dashboard_bp.post("/api/jobs")
def submit_job():
    task_type = request.form.get("task_type", "").strip()
    description = request.form.get("description", "").strip()
    if len(description) > 120:
        return _error("Description must be 120 characters or fewer.")

    saved_file: Path | None = None
    try:
        if task_type == "demo":
            steps = _parse_int("steps", minimum=3, maximum=20, default=8)
            step_seconds = _parse_float("step_seconds", minimum=0.25, maximum=3.0, default=1.0)
            start_delay_seconds = _parse_int("start_delay_seconds", minimum=0, maximum=60, default=0)
            fail_at_step = _parse_int("fail_at_step", minimum=0, maximum=steps, default=0)
            parameters = {
                "steps": steps,
                "step_seconds": step_seconds,
                "start_delay_seconds": start_delay_seconds,
                "fail_at_step": fail_at_step or None,
            }
            job = queue_service.enqueue_job(
                task_type="demo",
                description=description or "Timed demo workload",
                parameters=parameters,
            )

        elif task_type == "csv_summary":
            upload = request.files.get("csv_file")
            if not upload or not upload.filename:
                return _error("Choose a CSV file before submitting the job.")
            original_name = secure_filename(upload.filename)
            if not original_name.lower().endswith(".csv"):
                return _error("Only .csv files are accepted.")

            start_delay_seconds = _parse_int("start_delay_seconds", minimum=0, maximum=60, default=0)
            stored_name = f"{uuid.uuid4().hex[:10]}_{original_name}"
            saved_file = Path(current_app.config["UPLOAD_FOLDER"]) / stored_name
            upload.save(saved_file)
            parameters = {
                "original_file_name": original_name,
                "start_delay_seconds": start_delay_seconds,
            }
            job = queue_service.enqueue_job(
                task_type="csv_summary",
                description=description or f"CSV summary · {original_name}",
                parameters=parameters,
                input_file=str(saved_file),
            )
        else:
            return _error("Choose a supported job type.")

    except ValueError as exc:
        if saved_file and saved_file.exists():
            saved_file.unlink()
        return _error(str(exc))
    except queue_service.QueueServiceError as exc:
        if saved_file and saved_file.exists():
            saved_file.unlink()
        return _error(str(exc), 503)

    return jsonify({"job": serialize_job(job)}), 201


@dashboard_bp.post("/api/jobs/<job_id>/retry")
def retry_job(job_id: str):
    try:
        job = queue_service.retry_failed_job(job_id)
    except queue_service.JobActionError as exc:
        return _error(str(exc))
    except queue_service.QueueServiceError as exc:
        return _error(str(exc), 503)
    return jsonify({"job": serialize_job(job)}), 201


@dashboard_bp.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id: str):
    try:
        job = queue_service.cancel_waiting_job(job_id)
    except queue_service.JobActionError as exc:
        return _error(str(exc))
    except queue_service.QueueServiceError as exc:
        return _error(str(exc), 503)
    return jsonify({"job": serialize_job(job)})


@dashboard_bp.delete("/api/jobs/<job_id>")
def remove_job(job_id: str):
    try:
        queue_service.remove_terminal_job(job_id)
    except queue_service.JobActionError as exc:
        return _error(str(exc))
    return jsonify({"removed": True})


@dashboard_bp.get("/api/worker-status")
def get_worker_status():
    return jsonify({"worker_status": queue_service.worker_status()})
