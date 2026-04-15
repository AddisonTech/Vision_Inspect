"""
SQLite persistence layer for Vision_Inspect.
Uses Python's built-in sqlite3 — no extra dependencies.
One connection per call (lightweight for a shop-floor write rate).
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "vision_inspect.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS inspections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        TEXT    UNIQUE NOT NULL,
    timestamp     TEXT    NOT NULL,
    task_type     TEXT    NOT NULL DEFAULT '',
    source        TEXT    NOT NULL DEFAULT '',
    model_used    TEXT    NOT NULL DEFAULT '',
    pass_fail     TEXT    NOT NULL DEFAULT 'UNKNOWN',
    confidence    REAL    NOT NULL DEFAULT 0.0,
    latency_ms    REAL    NOT NULL DEFAULT 0.0,
    finding_count INTEGER NOT NULL DEFAULT 0,
    notes         TEXT    NOT NULL DEFAULT '',
    findings      TEXT    NOT NULL DEFAULT '[]',
    report_path   TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON inspections (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_task_type ON inspections (task_type);
CREATE INDEX IF NOT EXISTS idx_pass_fail  ON inspections (pass_fail);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
    logger.info("Database ready at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_inspection(data: dict) -> None:
    """Insert or replace a completed inspection record."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO inspections
                (job_id, timestamp, task_type, source, model_used,
                 pass_fail, confidence, latency_ms, finding_count,
                 notes, findings, report_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["job_id"],
                data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                data.get("task_type", ""),
                data.get("source", ""),
                data.get("model_used", ""),
                data.get("pass_fail", "UNKNOWN"),
                float(data.get("confidence", 0.0)),
                float(data.get("latency_ms", 0.0)),
                len(data.get("findings", [])),
                data.get("notes", ""),
                json.dumps(data.get("findings", [])),
                data.get("report_path", ""),
            ),
        )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["findings"] = json.loads(d["findings"])
    except (json.JSONDecodeError, TypeError):
        d["findings"] = []
    return d


def get_inspection(job_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM inspections WHERE job_id = ?", (job_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_inspections(
    limit: int = 50,
    offset: int = 0,
    task_type: str | None = None,
    pass_fail: str | None = None,
    since: str | None = None,         # ISO timestamp
) -> list[dict]:
    clauses, params = [], []
    if task_type:
        clauses.append("task_type = ?"); params.append(task_type)
    if pass_fail:
        clauses.append("pass_fail = ?"); params.append(pass_fail.upper())
    if since:
        clauses.append("timestamp >= ?"); params.append(since)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params += [limit, offset]

    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM inspections {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_stats() -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                                          AS total,
                SUM(CASE WHEN pass_fail = 'PASS'    THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN pass_fail = 'FAIL'    THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN pass_fail = 'REVIEW'  THEN 1 ELSE 0 END) AS review,
                SUM(CASE WHEN pass_fail = 'UNKNOWN' THEN 1 ELSE 0 END) AS unknown,
                ROUND(AVG(confidence),  3)                        AS avg_confidence,
                ROUND(AVG(latency_ms),  0)                        AS avg_latency_ms,
                SUM(finding_count)                                AS total_findings
            FROM inspections
            """
        ).fetchone()
        today_count = conn.execute(
            "SELECT COUNT(*) FROM inspections WHERE timestamp >= ?",
            (datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00"),),
        ).fetchone()[0]

        by_task = conn.execute(
            """
            SELECT task_type,
                   COUNT(*) AS count,
                   ROUND(AVG(confidence), 3) AS avg_confidence,
                   SUM(CASE WHEN pass_fail='PASS' THEN 1 ELSE 0 END) AS passed
            FROM inspections
            GROUP BY task_type
            ORDER BY count DESC
            """
        ).fetchall()

    d = dict(row)
    total = d["total"] or 0
    passed = d["passed"] or 0
    d["today"] = today_count
    d["pass_rate"] = round(passed / total * 100, 1) if total else 0.0
    d["by_task"] = [dict(r) for r in by_task]
    return d
