"""Modules 13-15: incident reporting, emergency resources, tasks and the coordination overview.
All records are real user input; nothing is pre-seeded or sampled. Citizens see only their own reports."""
from __future__ import annotations

import re
import time
from pathlib import Path

from ..core import config
from ..db import database as db

INCIDENT_CATEGORIES = ["flooded_road", "fallen_tree", "blocked_road", "infrastructure_damage", "power_outage", "weather_incident"]
INCIDENT_STATUSES = ["submitted", "under_review", "resolved", "dismissed"]
VERIFICATIONS = ["unverified", "verified", "rejected"]
RESOURCE_KINDS = ["ambulance", "rescue_team", "relief_supplies", "other"]
ASSIGNMENT_STATUSES = ["proposed", "approved", "active", "completed", "cancelled"]
TASK_STATUSES = ["open", "in_progress", "done", "cancelled"]
RATE_LIMIT_PER_HOUR = 10
UNVERIFIED_NOTICE = "Unverified citizen report. Not an official source and not confirmed by authorities."
ALLOWED_PHOTO = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}


class Invalid(ValueError):
    pass


def _clean_text(s: str, field: str, min_len: int, max_len: int) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", (s or "")).strip()
    if not (min_len <= len(s) <= max_len):
        raise Invalid(f"{field} must be {min_len}-{max_len} characters.")
    return s


# ------------------------------------------------------------------ incidents
def create_incident(con, user_id: int, category: str, description: str, lat=None, lon=None, photo_bytes: bytes | None = None) -> dict:
    if category not in INCIDENT_CATEGORIES:
        raise Invalid(f"category must be one of {INCIDENT_CATEGORIES}")
    description = _clean_text(description, "description", 10, 2000)
    if (lat is None) != (lon is None):
        raise Invalid("Provide both latitude and longitude, or neither.")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise Invalid("Coordinates out of range.")
    recent = db.one(con, "SELECT COUNT(*) n FROM incidents WHERE reporter_id=? AND created_at >= ?",
                    (user_id, _hours_ago(1)))["n"]
    if recent >= RATE_LIMIT_PER_HOUR:
        raise Invalid(f"Rate limit: at most {RATE_LIMIT_PER_HOUR} reports per hour.")
    dup = db.one(con, "SELECT id FROM incidents WHERE reporter_id=? AND category=? AND description=? AND created_at >= ?",
                 (user_id, category, description, _hours_ago(24)))
    if dup:
        raise Invalid("An identical report was already submitted in the last 24 hours.")
    photo_path = _save_photo(photo_bytes) if photo_bytes else None
    ts = db.now()
    cur = con.execute("INSERT INTO incidents(reporter_id,category,description,lat,lon,photo_path,status,verification,created_at,updated_at) "
                      "VALUES(?,?,?,?,?,?,'submitted','unverified',?,?)", (user_id, category, description, lat, lon, photo_path, ts, ts))
    return get_incident(con, cur.lastrowid)


def _hours_ago(h: float) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat(timespec="seconds")


def _save_photo(data: bytes) -> str:
    if len(data) > config.MAX_PHOTO_MB * 1024 * 1024:
        raise Invalid(f"Photo exceeds {config.MAX_PHOTO_MB} MB.")
    ext = next((e for sig, e in ALLOWED_PHOTO.items() if data.startswith(sig)), None)
    if ext is None:
        raise Invalid("Photo must be a JPEG or PNG image.")
    folder = config.UPLOAD_DIR / "incident_photos"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{time.time_ns()}{ext}"  # server-generated name: user filenames are never used
    path.write_bytes(data)
    return str(path)


def get_incident(con, incident_id: int) -> dict | None:
    r = db.one(con, "SELECT * FROM incidents WHERE id=?", (incident_id,))
    if r:
        r["notice"] = UNVERIFIED_NOTICE if r["verification"] == "unverified" else None
    return r


def list_incidents(con, user: dict, status: str | None = None, verification: str | None = None) -> list[dict]:
    from ..core.security import has_permission
    sql, args = "SELECT * FROM incidents WHERE 1=1", []
    if not has_permission(user["role"], "view_all_incidents"):
        sql += " AND reporter_id=?"
        args.append(user["id"])
    if status:
        sql += " AND status=?"
        args.append(status)
    if verification:
        sql += " AND verification=?"
        args.append(verification)
    rows = db.rows(con, sql + " ORDER BY id DESC LIMIT 500", args)
    privileged = has_permission(user["role"], "view_all_incidents")
    for r in rows:
        r["notice"] = UNVERIFIED_NOTICE if r["verification"] == "unverified" else None
        if not privileged:
            r.pop("reviewer_id", None)
    return rows


def review_incident(con, incident_id: int, reviewer_id: int, status: str | None, verification: str | None, note: str | None) -> dict:
    inc = get_incident(con, incident_id)
    if not inc:
        raise KeyError("Incident not found")
    if status and status not in INCIDENT_STATUSES:
        raise Invalid(f"status must be one of {INCIDENT_STATUSES}")
    if verification and verification not in VERIFICATIONS:
        raise Invalid(f"verification must be one of {VERIFICATIONS}")
    note = _clean_text(note, "note", 0, 1000) if note else inc["review_note"]
    con.execute("UPDATE incidents SET status=?,verification=?,review_note=?,reviewer_id=?,updated_at=? WHERE id=?",
                (status or inc["status"], verification or inc["verification"], note, reviewer_id, db.now(), incident_id))
    db.audit(con, reviewer_id, "incident_review", f"incident:{incident_id}", f"status={status} verification={verification}")
    return get_incident(con, incident_id)


# ------------------------------------------------------------------ resources
def create_resource(con, user_id: int, kind: str, name: str, quantity: int, lat=None, lon=None, notes: str | None = None) -> dict:
    if kind not in RESOURCE_KINDS:
        raise Invalid(f"kind must be one of {RESOURCE_KINDS}")
    if not isinstance(quantity, int) or quantity < 0 or quantity > 1_000_000:
        raise Invalid("quantity must be a non-negative integer")
    name = _clean_text(name, "name", 2, 120)
    if (lat is None) != (lon is None):
        raise Invalid("Provide both latitude and longitude, or neither.")
    ts = db.now()
    cur = con.execute("INSERT INTO resources(kind,name,quantity,available,lat,lon,notes,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (kind, name, quantity, quantity, lat, lon, notes, user_id, ts, ts))
    db.audit(con, user_id, "resource_create", f"resource:{cur.lastrowid}", name)
    return db.one(con, "SELECT * FROM resources WHERE id=?", (cur.lastrowid,))


def update_resource(con, user_id: int, resource_id: int, fields: dict) -> dict:
    r = db.one(con, "SELECT * FROM resources WHERE id=?", (resource_id,))
    if not r:
        raise KeyError("Resource not found")
    allowed = {k: fields[k] for k in ("name", "quantity", "available", "lat", "lon", "notes") if k in fields and fields[k] is not None}
    if "quantity" in allowed and (not isinstance(allowed["quantity"], int) or allowed["quantity"] < 0):
        raise Invalid("quantity must be a non-negative integer")
    q = allowed.get("quantity", r["quantity"])
    a = allowed.get("available", r["available"])
    if not isinstance(a, int) or a < 0 or a > q:
        raise Invalid("available must be between 0 and quantity")
    if allowed:
        sets = ",".join(f"{k}=?" for k in allowed)
        con.execute(f"UPDATE resources SET {sets}, updated_at=? WHERE id=?", (*allowed.values(), db.now(), resource_id))
        db.audit(con, user_id, "resource_update", f"resource:{resource_id}", str(sorted(allowed)))
    return db.one(con, "SELECT * FROM resources WHERE id=?", (resource_id,))


def list_resources(con, kind: str | None = None) -> list[dict]:
    if kind:
        return db.rows(con, "SELECT * FROM resources WHERE kind=? ORDER BY id DESC", (kind,))
    return db.rows(con, "SELECT * FROM resources ORDER BY id DESC")


def propose_assignment(con, user_id: int, resource_id: int, quantity: int, incident_id=None, task_id=None) -> dict:
    """Recommendations are only ever PROPOSED here; a human with manage_resources must approve."""
    r = db.one(con, "SELECT * FROM resources WHERE id=?", (resource_id,))
    if not r:
        raise KeyError("Resource not found")
    if quantity < 1 or quantity > r["available"]:
        raise Invalid(f"quantity must be between 1 and the {r['available']} currently available")
    ts = db.now()
    cur = con.execute("INSERT INTO assignments(resource_id,incident_id,task_id,quantity,status,created_by,created_at,updated_at) VALUES(?,?,?,?,'proposed',?,?,?)",
                      (resource_id, incident_id, task_id, quantity, user_id, ts, ts))
    return db.one(con, "SELECT * FROM assignments WHERE id=?", (cur.lastrowid,))


def set_assignment_status(con, user_id: int, assignment_id: int, status: str) -> dict:
    a = db.one(con, "SELECT * FROM assignments WHERE id=?", (assignment_id,))
    if not a:
        raise KeyError("Assignment not found")
    if status not in ASSIGNMENT_STATUSES:
        raise Invalid(f"status must be one of {ASSIGNMENT_STATUSES}")
    held = a["status"] in ("approved", "active")
    will_hold = status in ("approved", "active")
    r = db.one(con, "SELECT * FROM resources WHERE id=?", (a["resource_id"],))
    if will_hold and not held:
        if a["quantity"] > r["available"]:
            raise Invalid("Not enough availability to approve this assignment")
        con.execute("UPDATE resources SET available=available-?, updated_at=? WHERE id=?", (a["quantity"], db.now(), a["resource_id"]))
    elif held and not will_hold:
        con.execute("UPDATE resources SET available=available+?, updated_at=? WHERE id=?", (a["quantity"], db.now(), a["resource_id"]))
    con.execute("UPDATE assignments SET status=?, approved_by=COALESCE(approved_by,?), updated_at=? WHERE id=?",
                (status, user_id if will_hold else None, db.now(), assignment_id))
    db.audit(con, user_id, "assignment_status", f"assignment:{assignment_id}", status)
    return db.one(con, "SELECT * FROM assignments WHERE id=?", (assignment_id,))


# ------------------------------------------------------------------ tasks
def create_task(con, user_id: int, title: str, description: str | None, incident_id=None, assignee_id=None) -> dict:
    title = _clean_text(title, "title", 3, 200)
    ts = db.now()
    cur = con.execute("INSERT INTO tasks(title,description,incident_id,assignee_id,status,created_by,created_at,updated_at) VALUES(?,?,?,?,'open',?,?,?)",
                      (title, description, incident_id, assignee_id, user_id, ts, ts))
    db.audit(con, user_id, "task_create", f"task:{cur.lastrowid}", title)
    return db.one(con, "SELECT * FROM tasks WHERE id=?", (cur.lastrowid,))


def update_task_status(con, user: dict, task_id: int, status: str) -> dict:
    from ..core.security import has_permission
    t = db.one(con, "SELECT * FROM tasks WHERE id=?", (task_id,))
    if not t:
        raise KeyError("Task not found")
    if status not in TASK_STATUSES:
        raise Invalid(f"status must be one of {TASK_STATUSES}")
    if not has_permission(user["role"], "manage_tasks") and t["assignee_id"] != user["id"]:
        raise PermissionError("Responders may only update tasks assigned to them")
    con.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status, db.now(), task_id))
    db.audit(con, user["id"], "task_status", f"task:{task_id}", status)
    return db.one(con, "SELECT * FROM tasks WHERE id=?", (task_id,))


def coordination_overview(con) -> dict:
    inc = db.rows(con, "SELECT status, verification, COUNT(*) n FROM incidents GROUP BY status, verification")
    res = db.rows(con, "SELECT kind, COUNT(*) records, COALESCE(SUM(quantity),0) total, COALESCE(SUM(available),0) available FROM resources GROUP BY kind")
    tasks = db.rows(con, "SELECT status, COUNT(*) n FROM tasks GROUP BY status")
    asg = db.rows(con, "SELECT status, COUNT(*) n FROM assignments GROUP BY status")
    mapped = db.rows(con, "SELECT id,category,lat,lon,status,verification FROM incidents WHERE lat IS NOT NULL AND status NOT IN ('resolved','dismissed') ORDER BY id DESC LIMIT 500")
    activity = db.rows(con, "SELECT action,target,detail,created_at FROM audit_log ORDER BY id DESC LIMIT 20")
    return {"incidents": inc, "resources": res, "tasks": tasks, "assignments": asg, "open_incident_locations": mapped,
            "recent_activity": activity,
            "notice": "All figures are records entered into this system. Unverified citizen reports are not official."}
