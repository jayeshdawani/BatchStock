from __future__ import annotations

import csv
import statistics
import time
from pathlib import Path
from typing import Any

from celery import shared_task
from celery.exceptions import Ignore

from .services import job_store


def _skip_if_cancelled(task, job_id: str) -> None:
    job = job_store.get_job(job_id)
    if not job:
        raise RuntimeError("The local job record no longer exists.")
    if job["status"] == "cancelled":
        job_store.append_event(job_id, "Worker skipped execution because the job was cancelled.")
        task.update_state(state="REVOKED", meta={"status": "Cancelled before execution"})
        raise Ignore()


def _mark_running(job_id: str, stage: str) -> None:
    job_store.update_job(job_id, status="in_progress", progress=0, stage=stage)
    job_store.append_event(job_id, "Worker started processing the job.")


def _report_progress(task, job_id: str, progress: int, stage: str) -> None:
    progress = max(0, min(int(progress), 100))
    job_store.update_job(job_id, status="in_progress", progress=progress, stage=stage)
    task.update_state(state="PROGRESS", meta={"progress": progress, "stage": stage})


def _mark_finished(job_id: str, output: dict[str, Any]) -> None:
    job_store.update_job(job_id, status="finished", progress=100, stage="Job completed", output=output)
    job_store.append_event(job_id, "Job completed successfully.")


def _mark_failed(job_id: str, exc: Exception) -> None:
    message = str(exc) or exc.__class__.__name__
    job_store.update_job(job_id, status="failed", stage="Job failed", error_message=message)
    job_store.append_event(job_id, f"Job failed: {message}", "error")


@shared_task(bind=True, ignore_result=False, name="batchdock.run_demo_workload")
def run_demo_workload(
    self,
    *,
    job_id: str,
    steps: int,
    step_seconds: float,
    fail_at_step: int | None = None,
) -> dict[str, Any]:
    """Run a small timed workload that exposes progress updates."""
    try:
        _skip_if_cancelled(self, job_id)
        _mark_running(job_id, "Preparing demo workload")

        stage_names = [
            "Preparing input",
            "Processing local batch",
            "Calculating summary",
            "Formatting output",
        ]
        for step in range(1, steps + 1):
            if fail_at_step and step == fail_at_step:
                raise RuntimeError(
                    f"Controlled demo failure triggered at step {step}. Retry with failure disabled."
                )
            stage = f"{stage_names[(step - 1) % len(stage_names)]} · step {step} of {steps}"
            _report_progress(self, job_id, round(step * 100 / steps), stage)
            time.sleep(step_seconds)

        output = {
            "message": "Timed demo workload finished successfully.",
            "steps_completed": steps,
            "seconds_per_step": step_seconds,
        }
        _mark_finished(job_id, output)
        return output
    except Ignore:
        raise
    except Exception as exc:
        _mark_failed(job_id, exc)
        raise


@shared_task(bind=True, ignore_result=False, name="batchdock.analyze_csv_file")
def analyze_csv_file(self, *, job_id: str, file_path: str) -> dict[str, Any]:
    """Read a local CSV upload and return a small structured summary."""
    try:
        _skip_if_cancelled(self, job_id)
        _mark_running(job_id, "Opening CSV input")
        _report_progress(self, job_id, 10, "Opening CSV input")

        path = Path(file_path)
        if not path.exists():
            raise RuntimeError("The uploaded CSV file is no longer available.")

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            if not headers:
                raise RuntimeError("The CSV file must include a header row.")
            if len(headers) != len(set(headers)):
                raise RuntimeError("The CSV file contains duplicate column names.")

            _report_progress(self, job_id, 30, "Reading CSV rows")
            numeric_values: dict[str, list[float]] = {header: [] for header in headers}
            non_empty_counts = {header: 0 for header in headers}
            invalid_numeric_counts = {header: 0 for header in headers}
            row_count = 0

            for row in reader:
                row_count += 1
                for header in headers:
                    value = (row.get(header) or "").strip()
                    if not value:
                        continue
                    non_empty_counts[header] += 1
                    try:
                        numeric_values[header].append(float(value))
                    except ValueError:
                        invalid_numeric_counts[header] += 1

        if row_count == 0:
            raise RuntimeError("The CSV file must contain at least one data row.")

        _report_progress(self, job_id, 75, "Calculating numeric summaries")
        numeric_summary: dict[str, dict[str, float | int]] = {}
        for header in headers:
            values = numeric_values[header]
            if values and invalid_numeric_counts[header] == 0:
                numeric_summary[header] = {
                    "count": len(values),
                    "min": round(min(values), 4),
                    "max": round(max(values), 4),
                    "mean": round(statistics.fmean(values), 4),
                }

        _report_progress(self, job_id, 90, "Formatting CSV report")
        output = {
            "message": "CSV summary report generated.",
            "file_name": path.name,
            "rows": row_count,
            "columns": len(headers),
            "headers": headers,
            "numeric_columns": numeric_summary,
            "non_empty_values": non_empty_counts,
        }
        _mark_finished(job_id, output)
        return output
    except Ignore:
        raise
    except Exception as exc:
        _mark_failed(job_id, exc)
        raise
