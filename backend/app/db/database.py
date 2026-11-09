"""App database (SQLite via the standard library; the schema is plain SQL so it ports to PostgreSQL).
Holds app state only: users, experiments, cluster profiles, incidents, resources, tasks, reports, audit log.
Raw NOAA data and processed analytical tables live in data/ files and are never stored here."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from ..core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'citizen', created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS datasets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, filename TEXT NOT NULL, stored_path TEXT NOT NULL,
  rows INTEGER, columns INTEGER, quality_score REAL, quality_json TEXT, uploaded_by INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, algorithm TEXT NOT NULL, dataset_id TEXT NOT NULL, dataset_version TEXT NOT NULL,
  config_json TEXT NOT NULL, params_json TEXT NOT NULL, seed INTEGER, n_clusters INTEGER, noise_count INTEGER, noise_pct REAL,
  metrics_json TEXT NOT NULL, seconds REAL, peak_mb REAL, notes TEXT, created_by INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cluster_assignments(
  experiment_id INTEGER NOT NULL, event_id INTEGER NOT NULL, cluster INTEGER NOT NULL, point_type TEXT,
  pc1 REAL, pc2 REAL, PRIMARY KEY(experiment_id, event_id));
CREATE INDEX IF NOT EXISTS ix_assign_cluster ON cluster_assignments(experiment_id, cluster);
CREATE TABLE IF NOT EXISTS cluster_profiles(
  experiment_id INTEGER NOT NULL, cluster_id INTEGER NOT NULL, profile_json TEXT NOT NULL, PRIMARY KEY(experiment_id, cluster_id));
CREATE TABLE IF NOT EXISTS anomaly_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, method TEXT NOT NULL, params_json TEXT NOT NULL, summary_json TEXT NOT NULL,
  results_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS incidents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL,
  lat REAL, lon REAL, photo_path TEXT, status TEXT NOT NULL DEFAULT 'submitted', verification TEXT NOT NULL DEFAULT 'unverified',
  reviewer_id INTEGER, review_note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_inc_reporter ON incidents(reporter_id);
CREATE TABLE IF NOT EXISTS resources(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
  available INTEGER NOT NULL DEFAULT 1, lat REAL, lon REAL, notes TEXT, created_by INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assignments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, resource_id INTEGER NOT NULL, incident_id INTEGER, task_id INTEGER, quantity INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'proposed', approved_by INTEGER, created_by INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, incident_id INTEGER, assignee_id INTEGER,
  status TEXT NOT NULL DEFAULT 'open', created_by INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, kind TEXT NOT NULL, params_json TEXT, file_path TEXT NOT NULL,
  format TEXT NOT NULL, created_by INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL, target TEXT, detail TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alert_cache(
  id INTEGER PRIMARY KEY CHECK (id=1), fetched_at TEXT NOT NULL, payload_json TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=None) -> sqlite3.Connection:
    con = sqlite3.connect(str(path or config.DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


@contextmanager
def session(path=None):
    con = connect(path)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(path=None) -> None:
    with session(path) as con:
        con.executescript(SCHEMA)


def rows(con, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def one(con, sql: str, params=()) -> dict | None:
    r = con.execute(sql, params).fetchone()
    return dict(r) if r else None


def audit(con, user_id, action: str, target: str = "", detail: str = "") -> None:
    con.execute("INSERT INTO audit_log(user_id,action,target,detail,created_at) VALUES(?,?,?,?,?)",
                (user_id, action, target, detail, now()))


def dumps(obj) -> str:
    return json.dumps(obj, default=_json_default)


def _json_default(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not serialisable: {type(o)}")
