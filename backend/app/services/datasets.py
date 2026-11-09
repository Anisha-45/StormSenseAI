"""Module 1 upload handling: validation, safe storage and quality profiling of user CSV files."""
from __future__ import annotations

import io
import re
import time

import pandas as pd

from ..core import config
from ..db import database as db
from . import quality

ALLOWED_EXT = {".csv"}


class UploadError(ValueError):
    pass


def safe_name(filename: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]", "_", (filename or "upload.csv").split("/")[-1].split("\\")[-1])
    return base[:80] or "upload.csv"


def save_upload(con, user_id: int, filename: str, data: bytes, name: str | None = None) -> dict:
    fname = safe_name(filename)
    if not any(fname.lower().endswith(e) for e in ALLOWED_EXT):
        raise UploadError("Only .csv files are accepted.")
    if len(data) == 0:
        raise UploadError("The file is empty.")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise UploadError(f"File exceeds the {config.MAX_UPLOAD_MB} MB limit.")
    if b"\x00" in data[:4096]:
        raise UploadError("File looks binary, not CSV text.")
    try:
        df = pd.read_csv(io.BytesIO(data), low_memory=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as e:
        raise UploadError(f"Could not parse CSV: {e}") from e
    problems = quality.validate_upload_frame(df)
    if problems:
        raise UploadError(" ".join(problems))
    report = quality.profile_dataframe(df, source=fname)
    stored = config.UPLOAD_DIR / f"{time.time_ns()}_{fname}"  # raw upload is kept untouched
    stored.write_bytes(data)
    cur = con.execute("INSERT INTO datasets(name,filename,stored_path,rows,columns,quality_score,quality_json,uploaded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (name or fname, fname, str(stored), len(df), df.shape[1], report["quality_score"], db.dumps(report), user_id, db.now()))
    return {"id": cur.lastrowid, "name": name or fname, "filename": fname, "rows": len(df), "columns": df.shape[1],
            "quality_score": report["quality_score"]}


def list_datasets(con) -> list[dict]:
    return db.rows(con, "SELECT id,name,filename,rows,columns,quality_score,created_at FROM datasets ORDER BY id DESC")


def get_dataset(con, dataset_id: int) -> dict | None:
    return db.one(con, "SELECT id,name,filename,rows,columns,quality_score,created_at FROM datasets WHERE id=?", (dataset_id,))


def get_quality(con, dataset_id: int) -> dict | None:
    import json
    r = db.one(con, "SELECT quality_json FROM datasets WHERE id=?", (dataset_id,))
    return json.loads(r["quality_json"]) if r else None
