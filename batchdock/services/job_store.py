from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app

ALL_STATUSES = ("waiting", "in_progress", "finished", "failed", "cancelled")
TERMINAL_STATUSES = {"finished", "failed", "cancelled"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _database_path() -> str:
    return current_app.config["DATABASE_PATH"]


def _connect() -> sqlite3.Connection:
    database_path = _database_path()
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_db() -> None:
    with closing(_connect()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                celery_task_id TEXT,
                retry_of_job_id TEXT,
                task_type TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                stage TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                input_file TEXT,
                output_json TEXT,
                error_message TEXT,
                event_log_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (retry_of_job_id) REFERENCES jobs(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            """
        )
        connection.commit()


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _row_to_job(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    job = dict(row)
    job["parameters"] = _loads(job.pop("parameters_json"), {})
    job["output"] = _loads(job.pop("output_json"), None)
    job["events"] = _loads(job.pop("event_log_json"), [])
    return job


def create_job(
    *,
    task_type: str,
    description: str,
    parameters: dict[str, Any],
    input_file: str | None = None,
    retry_of_job_id: str | None = None,
) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    timestamp = utc_now()
    events = [
        {
            "time": timestamp,
            "level": "info",
            "message": "Job record created and waiting for queue submission.",
        }
    ]

    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, retry_of_job_id, task_type, description, status, progress, stage,
                parameters_json, input_file, event_log_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                retry_of_job_id,
                task_type,
                description,
                "waiting",
                0,
                "Waiting for worker",
                json.dumps(parameters, sort_keys=True),
                input_file,
                json.dumps(events),
                timestamp,
                timestamp,
            ),
        )
        connection.commit()

    return get_job(job_id)


def get_job(job_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row)


def list_jobs(
    *, search: str = "", status: str = "", limit: int = 100
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 250))
    clauses: list[str] = []
    values: list[Any] = []

    if search:
        wildcard = f"%{search.lower()}%"
        clauses.append(
            "(LOWER(id) LIKE ? OR LOWER(description) LIKE ? OR LOWER(task_type) LIKE ?)"
        )
        values.extend([wildcard, wildcard, wildcard])

    if status:
        clauses.append("status = ?")
        values.append(status)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(limit)

    with closing(_connect()) as connection:
        rows = connection.execute(
            f"SELECT * FROM jobs {where_clause} ORDER BY created_at DESC LIMIT ?", values
        ).fetchall()
    return [_row_to_job(row) for row in rows]


def status_counts() -> dict[str, int]:
    counts = {status: 0 for status in ALL_STATUSES}
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
        ).fetchall()
    for row in rows:
        if row["status"] in counts:
            counts[row["status"]] = row["count"]
    return counts


def attach_celery_task(job_id: str, celery_task_id: str) -> dict[str, Any] | None:
    return update_job(job_id, celery_task_id=celery_task_id)


def update_job(
    job_id: str,
    *,
    celery_task_id: str | None = None,
    status: str | None = None,
    progress: int | None = None,
    stage: str | None = None,
    output: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> dict[str, Any] | None:
    existing = get_job(job_id)
    if not existing:
        return None

    timestamp = utc_now()
    assignments = ["updated_at = ?"]
    values: list[Any] = [timestamp]

    if celery_task_id is not None:
        assignments.append("celery_task_id = ?")
        values.append(celery_task_id)

    if status is not None:
        if status not in ALL_STATUSES:
            raise ValueError(f"Unknown job status: {status}")
        assignments.append("status = ?")
        values.append(status)
        if status == "in_progress" and not existing["started_at"]:
            assignments.append("started_at = ?")
            values.append(timestamp)
        if status in TERMINAL_STATUSES and not existing["completed_at"]:
            assignments.append("completed_at = ?")
            values.append(timestamp)

    if progress is not None:
        assignments.append("progress = ?")
        values.append(max(0, min(int(progress), 100)))

    if stage is not None:
        assignments.append("stage = ?")
        values.append(stage)

    if output is not None:
        assignments.append("output_json = ?")
        values.append(json.dumps(output, sort_keys=True))

    if error_message is not None:
        assignments.append("error_message = ?")
        values.append(error_message)

    values.append(job_id)
    with closing(_connect()) as connection:
        connection.execute(
            f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values
        )
        connection.commit()
    return get_job(job_id)


def append_event(job_id: str, message: str, level: str = "info") -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT event_log_json FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None

        events = _loads(row["event_log_json"], [])
        events.append({"time": utc_now(), "level": level, "message": message})
        connection.execute(
            "UPDATE jobs SET event_log_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(events), utc_now(), job_id),
        )
        connection.commit()
    return get_job(job_id)


def delete_job(job_id: str) -> bool:
    with closing(_connect()) as connection:
        cursor = connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        connection.commit()
    return cursor.rowcount > 0
