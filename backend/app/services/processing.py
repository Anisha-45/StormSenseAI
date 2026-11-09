"""Modules 1-2: NOAA integration, cleaning and feature engineering.

Rules followed here (from the project brief):
- details is the single event-level source; one output row per EVENT_ID.
- locations and fatalities are one-to-many, so they are AGGREGATED per EVENT_ID before joining.
- locations/fatalities rows whose EVENT_ID is not in details are NOT joined; they are counted and logged.
- raw values (original damage strings, raw timestamps) are preserved next to derived columns.
- nothing is dropped silently: every problem goes to the issues log returned with the result.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..core import config
from ..core.storage import load_table, save_table
from .damage import parse_damage_series
from .quality import NOAA_DT_FORMAT

DETAILS_COLUMNS = [
    "EVENT_ID", "EPISODE_ID", "STATE", "STATE_FIPS", "YEAR", "MONTH_NAME", "EVENT_TYPE", "CZ_TYPE", "CZ_FIPS",
    "CZ_NAME", "WFO", "BEGIN_DATE_TIME", "END_DATE_TIME", "BEGIN_YEARMONTH", "INJURIES_DIRECT", "INJURIES_INDIRECT",
    "DEATHS_DIRECT", "DEATHS_INDIRECT", "DAMAGE_PROPERTY", "DAMAGE_CROPS", "SOURCE", "MAGNITUDE", "MAGNITUDE_TYPE",
    "FLOOD_CAUSE", "TOR_F_SCALE", "TOR_LENGTH", "TOR_WIDTH", "BEGIN_LAT", "BEGIN_LON", "END_LAT", "END_LON",
    "BEGIN_LOCATION", "EVENT_NARRATIVE",
]
SEASONS = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
           6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}
FILL_COUNT_COLUMNS = ["INJURIES_DIRECT", "INJURIES_INDIRECT", "DEATHS_DIRECT", "DEATHS_INDIRECT"]

DEFAULT_PROCESSING_CONFIG = {
    "name": "default",
    "event_type_case": "title",
    "damage_missing_policy": "keep_nan_and_flag",   # NaN stays NaN; *_reported flag is added
    "coordinate_policy": "flag_missing",            # events without coordinates stay, flagged has_coordinates=False
    "snap_zero_coordinates_to_missing": True,
}


class IssueLog:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, table: str, issue: str, count: int, detail: str = "", sample_ids: list | None = None):
        if count:
            self.items.append({"table": table, "issue": issue, "count": int(count), "detail": detail,
                               "sample_ids": [int(x) for x in (sample_ids or [])[:10]]})


def read_raw(raw_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    raw_dir = Path(raw_dir or config.RAW_DIR)
    details = pd.read_csv(raw_dir / config.DETAILS_FILE, usecols=lambda c: c in DETAILS_COLUMNS, low_memory=False)
    locations = pd.read_csv(raw_dir / config.LOCATIONS_FILE, low_memory=False)
    fatalities = pd.read_csv(raw_dir / config.FATALITIES_FILE, low_memory=False)
    return {"details": details, "locations": locations, "fatalities": fatalities}


def aggregate_locations(loc: pd.DataFrame, valid_ids: set, log: IssueLog) -> pd.DataFrame:
    loc = loc.copy()
    malformed = loc["EVENT_ID"].isna() | loc["LATITUDE"].isna() | loc["LONGITUDE"].isna()
    log.add("locations", "rows with missing EVENT_ID/LATITUDE/LONGITUDE (excluded from aggregation)", malformed.sum(),
            "kept in raw file, excluded from aggregation")
    loc = loc[~malformed]
    orphan = ~loc["EVENT_ID"].isin(valid_ids)
    log.add("locations", "rows whose EVENT_ID is not in the details file (not joined)", orphan.sum(),
            f"{loc.loc[orphan, 'EVENT_ID'].nunique()} distinct events; details covers a different period")
    loc = loc[~orphan]
    g = loc.groupby("EVENT_ID").agg(
        loc_row_count=("LOCATION_INDEX", "size"),
        loc_mean_lat=("LATITUDE", "mean"),
        loc_mean_lon=("LONGITUDE", "mean"),
        loc_max_range=("RANGE", "max"),
    ).reset_index()
    return g


def aggregate_fatalities(fat: pd.DataFrame, valid_ids: set, log: IssueLog) -> pd.DataFrame:
    orphan = ~fat["EVENT_ID"].isin(valid_ids)
    log.add("fatalities", "rows whose EVENT_ID is not in the details file (not joined)", orphan.sum(),
            f"{fat.loc[orphan, 'EVENT_ID'].nunique()} distinct events")
    fat = fat[~orphan]
    g = fat.groupby("EVENT_ID").agg(
        fatality_rows=("FATALITY_ID", "size"),
        fatality_mean_age=("FATALITY_AGE", "mean"),
        fatality_male=("FATALITY_SEX", lambda s: int((s == "M").sum())),
        fatality_female=("FATALITY_SEX", lambda s: int((s == "F").sum())),
    ).reset_index()
    return g


def process(raw_dir: Path | None = None, out_dir: Path | None = None, config_overrides: dict | None = None) -> dict:
    """Run the full pipeline. Writes events (+ issues log + manifest) and returns the manifest."""
    t0 = time.time()
    cfg = {**DEFAULT_PROCESSING_CONFIG, **(config_overrides or {})}
    out_dir = Path(out_dir or config.PROCESSED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = IssueLog()
    raw = read_raw(raw_dir)
    d, loc, fat = raw["details"], raw["locations"], raw["fatalities"]
    raw_counts = {k: int(len(v)) for k, v in raw.items()}

    # --- identifiers -------------------------------------------------------------------------
    if d["EVENT_ID"].isna().any():
        log.add("details", "rows with missing EVENT_ID (excluded)", int(d["EVENT_ID"].isna().sum()))
        d = d[d["EVENT_ID"].notna()]
    dup = d["EVENT_ID"].duplicated(keep="first")
    log.add("details", "duplicate EVENT_ID rows (first kept)", dup.sum(), sample_ids=d.loc[dup, "EVENT_ID"].tolist())
    d = d[~dup].copy()
    d["EVENT_ID"] = d["EVENT_ID"].astype("int64")
    valid_ids = set(d["EVENT_ID"])

    # --- categories --------------------------------------------------------------------------
    d["EVENT_TYPE"] = d["EVENT_TYPE"].astype(str).str.strip()
    if cfg["event_type_case"] == "title":
        d["EVENT_TYPE"] = d["EVENT_TYPE"].str.title()
    d["STATE"] = d["STATE"].astype(str).str.strip().str.title()

    # --- dates -------------------------------------------------------------------------------
    d["begin_dt"] = pd.to_datetime(d["BEGIN_DATE_TIME"], format=NOAA_DT_FORMAT, errors="coerce")
    d["end_dt"] = pd.to_datetime(d["END_DATE_TIME"], format=NOAA_DT_FORMAT, errors="coerce")
    bad_b = d["begin_dt"].isna()
    log.add("details", "unparseable BEGIN_DATE_TIME (kept, date features NaN)", bad_b.sum(), sample_ids=d.loc[bad_b, "EVENT_ID"].tolist())
    # NOAA two-digit years: pandas maps 69-99 to 1969-1999, so 2010+ parse correctly; guard anyway.
    d["year"] = d["begin_dt"].dt.year.fillna(d["YEAR"]).astype("int64")
    d["month"] = d["begin_dt"].dt.month
    d["month"] = d["month"].fillna(d["BEGIN_YEARMONTH"] % 100).astype("int64")
    d["season"] = d["month"].map(SEASONS)
    d["begin_hour"] = d["begin_dt"].dt.hour
    d["duration_hours"] = (d["end_dt"] - d["begin_dt"]).dt.total_seconds() / 3600.0
    neg = d["duration_hours"] < 0
    log.add("details", "END before BEGIN (duration set to NaN)", neg.sum(), sample_ids=d.loc[neg, "EVENT_ID"].tolist())
    d.loc[neg, "duration_hours"] = np.nan

    # --- damage (originals preserved) --------------------------------------------------------
    d["property_damage_usd"], bad_p = parse_damage_series(d["DAMAGE_PROPERTY"])
    d["crop_damage_usd"], bad_c = parse_damage_series(d["DAMAGE_CROPS"])
    log.add("details", "unparseable DAMAGE_PROPERTY strings", len(bad_p), detail=str(bad_p.unique()[:5].tolist()))
    log.add("details", "unparseable DAMAGE_CROPS strings", len(bad_c), detail=str(bad_c.unique()[:5].tolist()))
    d["property_damage_reported"] = d["DAMAGE_PROPERTY"].notna()
    d["crop_damage_reported"] = d["DAMAGE_CROPS"].notna()

    # --- impacts -----------------------------------------------------------------------------
    for c in FILL_COUNT_COLUMNS:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["injuries_total"] = d["INJURIES_DIRECT"].fillna(0) + d["INJURIES_INDIRECT"].fillna(0)
    d["deaths_total"] = d["DEATHS_DIRECT"].fillna(0) + d["DEATHS_INDIRECT"].fillna(0)
    d["total_damage_usd"] = d[["property_damage_usd", "crop_damage_usd"]].sum(axis=1, min_count=1)
    d["has_impact"] = (d["injuries_total"] > 0) | (d["deaths_total"] > 0) | (d["total_damage_usd"].fillna(0) > 0)
    d["magnitude_reported"] = d["MAGNITUDE"].notna()

    # --- coordinates -------------------------------------------------------------------------
    for c in ("BEGIN_LAT", "BEGIN_LON", "END_LAT", "END_LON"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    if cfg["snap_zero_coordinates_to_missing"]:
        zero = (d["BEGIN_LAT"] == 0) | (d["BEGIN_LON"] == 0)
        log.add("details", "zero latitude/longitude treated as missing", zero.sum())
        d.loc[zero, ["BEGIN_LAT", "BEGIN_LON"]] = np.nan
    out_of_range = d["BEGIN_LAT"].notna() & ~(d["BEGIN_LAT"].between(-90, 90) & d["BEGIN_LON"].between(-180, 180))
    log.add("details", "begin coordinates out of valid range (set to missing)", out_of_range.sum(), sample_ids=d.loc[out_of_range, "EVENT_ID"].tolist())
    d.loc[out_of_range, ["BEGIN_LAT", "BEGIN_LON"]] = np.nan
    d["has_coordinates"] = d["BEGIN_LAT"].notna() & d["BEGIN_LON"].notna()
    n_nocoord = int((~d["has_coordinates"]).sum())
    log.add("details", "events without coordinates (kept; excluded from map and spatial analysis only)", n_nocoord,
            detail="mostly forecast-zone (CZ_TYPE=Z) events; the locations file contains no rows for them")

    # --- related tables, aggregated (never multiplied) ---------------------------------------
    loc_g = aggregate_locations(loc, valid_ids, log)
    fat_g = aggregate_fatalities(fat, valid_ids, log)
    events = d.merge(loc_g, on="EVENT_ID", how="left", validate="one_to_one")
    events = events.merge(fat_g, on="EVENT_ID", how="left", validate="one_to_one")
    events["loc_row_count"] = events["loc_row_count"].fillna(0).astype("int64")
    events["fatality_rows"] = events["fatality_rows"].fillna(0).astype("int64")
    assert len(events) == len(d), "join must not change the number of events"
    assert events["EVENT_ID"].is_unique

    # consistency between details deaths and fatality records (only where fatality rows exist)
    both = events["fatality_rows"] > 0
    mism = both & (events["fatality_rows"] != events["deaths_total"])
    log.add("fatalities", "events where fatality record count differs from details deaths", mism.sum(), sample_ids=events.loc[mism, "EVENT_ID"].tolist())
    unmatched_deaths = (events["deaths_total"] > 0) & (events["fatality_rows"] == 0)
    log.add("fatalities", "events with deaths in details but no row in the fatalities file", unmatched_deaths.sum(),
            detail="expected for most events: the fatalities file covers a different period than details")

    events = events.rename(columns={"EVENT_TYPE": "event_type", "STATE": "state", "EVENT_ID": "event_id",
                                    "EPISODE_ID": "episode_id", "BEGIN_LAT": "lat", "BEGIN_LON": "lon",
                                    "MAGNITUDE": "magnitude", "MAGNITUDE_TYPE": "magnitude_type"})
    events["begin_dt"] = events["begin_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
    events["end_dt"] = events["end_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
    events = events.sort_values("event_id").reset_index(drop=True)

    save_table(events, out_dir, "events")
    manifest = {
        "dataset_id": "noaa_storm_events_2010_2020_extract",
        "dataset_version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_row_counts": raw_counts,
        "unique_events": int(len(events)),
        "events_with_coordinates": int(events["has_coordinates"].sum()),
        "events_with_location_rows": int((events["loc_row_count"] > 0).sum()),
        "events_with_fatality_rows": int((events["fatality_rows"] > 0).sum()),
        "year_counts": {int(k): int(v) for k, v in events["year"].value_counts().sort_index().items()},
        "date_range": [events["begin_dt"].min(), events["begin_dt"].max()],
        "config": cfg,
        "issues": log.items,
        "processing_seconds": round(time.time() - t0, 2),
        "notes": [
            "Details is the event-level source; locations and fatalities were aggregated per EVENT_ID before joining.",
            "The details file covers a narrower period than its filename suggests; see year_counts.",
            "Original DAMAGE_PROPERTY / DAMAGE_CROPS strings are preserved beside the numeric dollar columns.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


def load_manifest(out_dir: Path | None = None) -> dict:
    p = Path(out_dir or config.PROCESSED_DIR) / "manifest.json"
    if not p.exists():
        raise FileNotFoundError("Processing has not been run yet.")
    return json.loads(p.read_text())


def load_events(columns: list[str] | None = None, out_dir: Path | None = None) -> pd.DataFrame:
    return load_table(Path(out_dir or config.PROCESSED_DIR), "events", columns)
