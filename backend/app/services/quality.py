"""Module 1: dataset intelligence and data-quality monitoring.

The quality score is a transparent project-defined index. It is NOT an official NOAA score.

    score = 100 * (0.40*completeness + 0.20*uniqueness + 0.15*date_validity
                   + 0.15*coordinate_validity + 0.10*numeric_validity)

completeness       = 1 - missing_cells / total_cells (all columns; structurally sparse columns such as
                     tornado-only fields lower this on purpose, and are listed separately)
uniqueness         = 1 - duplicate_rows / rows
date_validity      = parseable dates / non-empty dates (date-time columns found by name)
coordinate_validity= lat/lon pairs inside valid ranges / non-empty pairs
numeric_validity   = 1 - impossible numeric values (negative counts, negative magnitude) / checked values
Components that cannot be evaluated for a dataset (no date or coordinate columns) are scored 1.0 and
flagged as "not_evaluated" so the score is never inflated silently.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NOAA_DT_FORMAT = "%d-%b-%y %H:%M:%S"
NON_NEGATIVE_COLUMNS = ["INJURIES_DIRECT", "INJURIES_INDIRECT", "DEATHS_DIRECT", "DEATHS_INDIRECT", "MAGNITUDE",
                        "TOR_LENGTH", "TOR_WIDTH"]
LAT_LON_PAIRS = [("BEGIN_LAT", "BEGIN_LON"), ("END_LAT", "END_LON"), ("LATITUDE", "LONGITUDE")]
SPARSE_THRESHOLD = 0.90

WEIGHTS = {"completeness": 0.40, "uniqueness": 0.20, "date_validity": 0.15,
           "coordinate_validity": 0.15, "numeric_validity": 0.10}


def _py(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    return v


def classify_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    categorical = [c for c in df.columns if c not in numeric]
    return {"numerical": numeric, "categorical": categorical}


def check_dates(df: pd.DataFrame) -> dict:
    result = {}
    for col in [c for c in df.columns if c.upper().endswith("DATE_TIME")]:
        s = df[col].dropna()
        parsed = pd.to_datetime(s, format=NOAA_DT_FORMAT, errors="coerce")
        result[col] = {"checked": int(len(s)), "invalid": int(parsed.isna().sum())}
    if "BEGIN_DATE_TIME" in result and "END_DATE_TIME" in df.columns:
        b = pd.to_datetime(df["BEGIN_DATE_TIME"], format=NOAA_DT_FORMAT, errors="coerce")
        e = pd.to_datetime(df["END_DATE_TIME"], format=NOAA_DT_FORMAT, errors="coerce")
        both = b.notna() & e.notna()
        result["end_before_begin"] = {"checked": int(both.sum()), "invalid": int((e[both] < b[both]).sum())}
    return result


def check_coordinates(df: pd.DataFrame) -> dict:
    result = {}
    for lat_c, lon_c in LAT_LON_PAIRS:
        if lat_c in df.columns and lon_c in df.columns:
            lat = pd.to_numeric(df[lat_c], errors="coerce")
            lon = pd.to_numeric(df[lon_c], errors="coerce")
            present = lat.notna() | lon.notna()
            both = lat.notna() & lon.notna()
            in_range = lat.between(-90, 90) & lon.between(-180, 180)
            half_missing = int((present & ~both).sum())
            invalid = int((both & ~in_range).sum()) + half_missing
            result[f"{lat_c}/{lon_c}"] = {"checked": int(present.sum()), "invalid": invalid,
                                          "missing_pairs": int((~present).sum())}
    return result


def check_numeric(df: pd.DataFrame) -> dict:
    result = {}
    for col in NON_NEGATIVE_COLUMNS:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            result[col] = {"checked": int(len(s)), "invalid": int((s < 0).sum())}
    return result


def check_event_types(df: pd.DataFrame, col: str = "EVENT_TYPE") -> dict:
    if col not in df.columns:
        return {"evaluated": False}
    raw = df[col].dropna().astype(str)
    normalised = raw.str.strip().str.lower()
    groups = raw.groupby(normalised).nunique()
    inconsistent = {k: sorted(raw[normalised == k].unique().tolist()) for k in groups[groups > 1].index}
    return {"evaluated": True, "distinct_raw": int(raw.nunique()), "distinct_normalised": int(normalised.nunique()),
            "inconsistent_variants": inconsistent}


def _ratio(checks: dict) -> float | None:
    checked = sum(v["checked"] for v in checks.values())
    invalid = sum(v["invalid"] for v in checks.values())
    return None if checked == 0 else max(0.0, 1.0 - invalid / checked)


def profile_dataframe(df: pd.DataFrame, source: str = "unknown", preview_rows: int = 10) -> dict:
    """Full quality profile for one table. Pure function, JSON-serialisable result."""
    rows, cols = df.shape
    if rows == 0 or cols == 0:
        return {"source": source, "rows": rows, "columns": cols, "empty": True, "quality_score": 0.0,
                "score_components": {}, "score_formula": __doc__.split("score =")[1].split("completeness")[0].strip()}

    miss = df.isna().sum()
    missing_cells = int(miss.sum())
    completeness = 1.0 - missing_cells / (rows * cols)
    dup_rows = int(df.duplicated().sum())
    uniqueness = 1.0 - dup_rows / rows

    dates = check_dates(df)
    coords = check_coordinates(df)
    numerics = check_numeric(df)
    d_ratio, g_ratio, n_ratio = _ratio(dates), _ratio(coords), _ratio(numerics)

    components = {
        "completeness": completeness,
        "uniqueness": uniqueness,
        "date_validity": 1.0 if d_ratio is None else d_ratio,
        "coordinate_validity": 1.0 if g_ratio is None else g_ratio,
        "numeric_validity": 1.0 if n_ratio is None else n_ratio,
    }
    score = 100.0 * sum(WEIGHTS[k] * v for k, v in components.items())
    not_evaluated = [k for k, r in (("date_validity", d_ratio), ("coordinate_validity", g_ratio),
                                    ("numeric_validity", n_ratio)) if r is None]

    kinds = classify_columns(df)
    columns = []
    for c in df.columns:
        columns.append({"name": c, "dtype": str(df[c].dtype), "kind": "numerical" if c in kinds["numerical"] else "categorical",
                        "missing": int(miss[c]), "missing_pct": round(float(miss[c]) / rows * 100, 2),
                        "unique": int(df[c].nunique(dropna=True))})
    sparse = [c["name"] for c in columns if c["missing_pct"] >= SPARSE_THRESHOLD * 100]

    id_col = "EVENT_ID" if "EVENT_ID" in df.columns else None
    ids = None
    if id_col:
        ids = {"column": id_col, "unique": int(df[id_col].nunique()), "duplicated_ids": int(df[id_col].duplicated().sum())}

    return {
        "source": source, "rows": int(rows), "columns": int(cols), "empty": False,
        "column_profile": columns, "numerical_columns": kinds["numerical"], "categorical_columns": kinds["categorical"],
        "missing_cells": missing_cells, "missing_pct_overall": round(missing_cells / (rows * cols) * 100, 2),
        "duplicate_rows": dup_rows, "identifier": ids,
        "date_checks": dates, "coordinate_checks": coords, "numeric_checks": numerics,
        "event_types": check_event_types(df),
        "structurally_sparse_columns": sparse,
        "score_components": {k: round(v, 4) for k, v in components.items()},
        "score_weights": WEIGHTS, "not_evaluated": not_evaluated,
        "quality_score": round(score, 2),
        "score_note": "Project-defined transparent index, not an official NOAA score.",
        "preview": df.head(preview_rows).replace({np.nan: None}).astype(object).to_dict("records"),
    }


def profile_csv(path, source: str | None = None, nrows: int | None = None) -> dict:
    df = pd.read_csv(path, low_memory=False, nrows=nrows)
    return profile_dataframe(df, source or str(path))


def validate_upload_frame(df: pd.DataFrame) -> list[str]:
    """Light structural checks for user uploads. Returns a list of problems (empty = fine)."""
    problems = []
    if df.shape[0] == 0:
        problems.append("File has no data rows.")
    if df.shape[1] < 2:
        problems.append("File has fewer than two columns; is the delimiter a comma?")
    if len(set(df.columns)) != len(df.columns):
        problems.append("Duplicate column names found.")
    return problems
