"""Modules 5, 6, 8, 9, 10: geographic, temporal, similarity, multi-hazard and impact analytics.
All functions take the processed events DataFrame and return JSON-safe structures. Every result carries
data-period caveats where relevant."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree, NearestNeighbors
from sklearn.preprocessing import StandardScaler

COVERAGE_CAVEAT = ("Event counts reflect what was recorded in this extract. Recording practices, event-type definitions and "
                   "extract coverage change over time, so count changes must not be read as climate trends.")
HOTSPOT_CAVEAT = "A historical concentration of records is not a prediction of future hazard."
EARTH_KM = 6371.0088


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if (obj != obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if obj is pd.NaT:
        return None
    return obj


def apply_filters(df: pd.DataFrame, state=None, event_type=None, year=None, season=None, month=None,
                  min_deaths=None, min_damage=None, has_coordinates=None) -> pd.DataFrame:
    m = pd.Series(True, index=df.index)
    if state:
        m &= df["state"].str.lower() == str(state).lower()
    if event_type:
        m &= df["event_type"].str.lower() == str(event_type).lower()
    if year:
        m &= df["year"] == int(year)
    if season:
        m &= df["season"].str.lower() == str(season).lower()
    if month:
        m &= df["month"] == int(month)
    if min_deaths is not None:
        m &= df["deaths_total"] >= min_deaths
    if min_damage is not None:
        m &= df["total_damage_usd"].fillna(0) >= min_damage
    if has_coordinates is not None:
        m &= df["has_coordinates"] == bool(has_coordinates)
    return df[m]


# ----------------------------------------------------------------------------- overview
def overview(df: pd.DataFrame, manifest: dict, experiments: list[dict]) -> dict:
    latest = experiments[0] if experiments else None
    return _clean({
        "total_unique_events": len(df), "event_types": int(df["event_type"].nunique()),
        "states_or_regions": int(df["state"].nunique()), "years": sorted(df["year"].unique().tolist()),
        "date_range": manifest.get("date_range"),
        "missing_pct_cells": round(float(df[["property_damage_usd", "crop_damage_usd", "magnitude", "lat"]].isna().mean().mean() * 100), 2),
        "events_with_coordinates": int(df["has_coordinates"].sum()),
        "completed_experiments": len(experiments),
        "latest_experiment": None if not latest else {k: latest[k] for k in ("id", "algorithm", "n_clusters", "noise_pct", "silhouette", "created_at")},
        "top_event_types": df["event_type"].value_counts().head(8).to_dict(),
        "totals": {"deaths": int(df["deaths_total"].sum()), "injuries": int(df["injuries_total"].sum()),
                   "property_damage_usd": float(df["property_damage_usd"].sum()), "crop_damage_usd": float(df["crop_damage_usd"].sum())},
        "year_counts": manifest.get("year_counts"),
        "caveats": [COVERAGE_CAVEAT, "The details file covers Feb 2017 - Sep 2020, with 2020 holding most records."],
    })


# ----------------------------------------------------------------------------- geography
def geo_events(df: pd.DataFrame, limit: int = 3000, **filters) -> dict:
    f = apply_filters(df, **filters)
    total, with_c = len(f), int(f["has_coordinates"].sum())
    f = f[f["has_coordinates"]]
    if len(f) > limit:
        f = f.sample(n=limit, random_state=42)
    cols = ["event_id", "event_type", "state", "year", "month", "lat", "lon", "deaths_total", "injuries_total",
            "property_damage_usd", "crop_damage_usd", "magnitude", "begin_dt"]
    return _clean({"events": f[cols].to_dict("records"), "matching_events": total, "with_coordinates": with_c,
                   "returned": len(f), "sampled": with_c > len(f),
                   "note": "Only events with recorded coordinates can be mapped; forecast-zone events have none."})


def hotspots(df: pd.DataFrame, cell_deg: float = 1.0, top: int = 25, **filters) -> dict:
    f = apply_filters(df, has_coordinates=True, **filters)
    if f.empty:
        return {"cells": [], "caveat": HOTSPOT_CAVEAT}
    g = f.assign(cy=(f["lat"] // cell_deg) * cell_deg, cx=(f["lon"] // cell_deg) * cell_deg)
    agg = g.groupby(["cy", "cx"]).agg(events=("event_id", "size"), deaths=("deaths_total", "sum"), injuries=("injuries_total", "sum"),
                                      damage=("total_damage_usd", "sum"), top_type=("event_type", lambda s: s.value_counts().index[0]),
                                      top_state=("state", lambda s: s.value_counts().index[0])).reset_index()
    agg["lat"], agg["lon"] = agg["cy"] + cell_deg / 2, agg["cx"] + cell_deg / 2
    agg = agg.sort_values("events", ascending=False)
    return _clean({"cells": agg.head(top).drop(columns=["cy", "cx"]).to_dict("records"), "cell_degrees": cell_deg,
                   "total_cells": len(agg), "caveat": HOTSPOT_CAVEAT})


def regional_distribution(df: pd.DataFrame, **filters) -> list[dict]:
    f = apply_filters(df, **filters)
    g = f.groupby("state").agg(events=("event_id", "size"), deaths=("deaths_total", "sum"), injuries=("injuries_total", "sum"),
                               property_damage_usd=("property_damage_usd", "sum"), crop_damage_usd=("crop_damage_usd", "sum")).reset_index()
    return _clean(g.sort_values("events", ascending=False).to_dict("records"))


def cluster_geography(assignments: pd.DataFrame, df: pd.DataFrame) -> dict:
    m = assignments.merge(df[["event_id", "event_type", "state", "year", "lat", "lon", "has_coordinates"]], on="event_id", how="left")
    mapped = m[m["has_coordinates"] == True]  # noqa: E712
    out = {"points": mapped[["event_id", "cluster", "event_type", "state", "year", "lat", "lon"]].to_dict("records"),
           "unmapped_events": int(len(m) - len(mapped)), "caveat": HOTSPOT_CAVEAT}
    cent = mapped.groupby("cluster").agg(lat=("lat", "mean"), lon=("lon", "mean"), events=("event_id", "size")).reset_index()
    out["centroids"] = cent.to_dict("records")
    return _clean(out)


# ----------------------------------------------------------------------------- temporal
def temporal(df: pd.DataFrame, by: str, **filters) -> dict:
    f = apply_filters(df, **filters)
    key = {"yearly": "year", "monthly": "month", "seasonal": "season"}[by]
    g = f.groupby(key).agg(events=("event_id", "size"), deaths=("deaths_total", "sum"), injuries=("injuries_total", "sum"),
                           property_damage_usd=("property_damage_usd", "sum"), crop_damage_usd=("crop_damage_usd", "sum"),
                           mean_duration_hours=("duration_hours", "mean")).reset_index()
    if by == "seasonal":
        order = {"Winter": 0, "Spring": 1, "Summer": 2, "Autumn": 3}
        g = g.sort_values(key, key=lambda s: s.map(order))
    else:
        g = g.sort_values(key)
    by_type = f.groupby([key, "event_type"]).size().reset_index(name="events")
    top_types = f["event_type"].value_counts().head(6).index
    pivot = by_type[by_type["event_type"].isin(top_types)].pivot(index=key, columns="event_type", values="events").fillna(0)
    return _clean({"series": g.to_dict("records"), "by_event_type": pivot.reset_index().to_dict("records"),
                   "caveat": COVERAGE_CAVEAT, "missing_months": _missing_months(df) if by == "monthly" else None})


def _missing_months(df: pd.DataFrame) -> list[str]:
    ym = pd.to_datetime(df["begin_dt"]).dt.to_period("M")
    full = pd.period_range(ym.min(), ym.max(), freq="M")
    return [str(p) for p in full.difference(pd.PeriodIndex(ym.unique()))]


def trends(df: pd.DataFrame, **filters) -> dict:
    """Year-over-year change for count and impacts. Descriptive only, with coverage warnings."""
    f = apply_filters(df, **filters)
    g = f.groupby("year").agg(events=("event_id", "size"), deaths=("deaths_total", "sum"), injuries=("injuries_total", "sum"),
                              property_damage_usd=("property_damage_usd", "sum"), crop_damage_usd=("crop_damage_usd", "sum")).sort_index()
    yoy = g.pct_change().replace([np.inf, -np.inf], np.nan) * 100
    months_per_year = pd.to_datetime(f["begin_dt"]).dt.to_period("M").groupby(f["year"]).nunique()
    partial = [int(y) for y, n in months_per_year.items() if n < 12]
    return _clean({"yearly": g.reset_index().to_dict("records"), "yoy_pct_change": yoy.reset_index().to_dict("records"),
                   "partial_years": partial, "months_covered": months_per_year.to_dict(),
                   "caveat": COVERAGE_CAVEAT + f" Years with fewer than 12 recorded months: {partial}."})


# ----------------------------------------------------------------------------- impact
SEVERITY_DEFAULTS = {"death_weight": 10.0, "injury_weight": 3.0, "damage_per_point_usd": 1_000_000.0}


def severity_score(df: pd.DataFrame, death_weight=10.0, injury_weight=3.0, damage_per_point_usd=1_000_000.0) -> pd.Series:
    """User-configurable index = deaths*w_d + injuries*w_i + total_damage/damage_per_point. Not an official scale."""
    return df["deaths_total"] * death_weight + df["injuries_total"] * injury_weight + df["total_damage_usd"].fillna(0) / damage_per_point_usd


def _impact_group(df, key):
    g = df.groupby(key).agg(events=("event_id", "size"), deaths=("deaths_total", "sum"), injuries=("injuries_total", "sum"),
                            property_damage_usd=("property_damage_usd", "sum"), crop_damage_usd=("crop_damage_usd", "sum"),
                            events_with_impact=("has_impact", "sum")).reset_index()
    g["deaths_per_1000_events"] = (g["deaths"] / g["events"] * 1000).round(2)
    return g


IMPACT_NOTE = ("Damage amounts are missing for about a fifth of events and are estimates reported by NWS offices. "
               "The severity score is a configurable project index, not an official classification.")


def impact_summary(df: pd.DataFrame, **filters) -> dict:
    f = apply_filters(df, **filters)
    return _clean({"events": len(f), "deaths": int(f["deaths_total"].sum()), "injuries": int(f["injuries_total"].sum()),
                   "property_damage_usd": float(f["property_damage_usd"].sum()), "crop_damage_usd": float(f["crop_damage_usd"].sum()),
                   "events_with_impact": int(f["has_impact"].sum()),
                   "property_damage_reported_pct": round(float(f["property_damage_reported"].mean() * 100), 1) if len(f) else None,
                   "note": IMPACT_NOTE})


def impact_by(df: pd.DataFrame, dimension: str, top: int = 30, **filters) -> dict:
    col = {"region": "state", "event-type": "event_type"}[dimension]
    f = apply_filters(df, **filters)
    g = _impact_group(f, col).sort_values(["deaths", "property_damage_usd"], ascending=False).head(top)
    return _clean({"rows": g.to_dict("records"), "note": IMPACT_NOTE})


def impact_by_cluster(assignments: pd.DataFrame, df: pd.DataFrame) -> dict:
    m = assignments.merge(df, on="event_id", how="left")
    g = _impact_group(m, "cluster").sort_values("cluster")
    return _clean({"rows": g.to_dict("records"), "note": IMPACT_NOTE})


def high_impact(df: pd.DataFrame, top: int = 25, weights: dict | None = None, **filters) -> dict:
    w = {**SEVERITY_DEFAULTS, **(weights or {})}
    f = apply_filters(df, **filters).copy()
    f["severity_score"] = severity_score(f, **w)
    f = f.sort_values("severity_score", ascending=False).head(top)
    cols = ["event_id", "event_type", "state", "begin_dt", "deaths_total", "injuries_total", "property_damage_usd",
            "crop_damage_usd", "severity_score"]
    return _clean({"events": f[cols].to_dict("records"), "weights": w,
                   "note": "severity_score = deaths*death_weight + injuries*injury_weight + total_damage/damage_per_point_usd. "
                           "Configurable project index, not an official classification."})


# ----------------------------------------------------------------------------- similarity
SIM_FEATURES = ["log_property_damage", "log_crop_damage", "injuries_total", "deaths_total", "log_duration_hours", "magnitude",
                "month_sin", "month_cos", "lat", "lon"]
SIM_LABELS = {"log_property_damage": "property damage", "log_crop_damage": "crop damage", "injuries_total": "injuries",
              "deaths_total": "deaths", "log_duration_hours": "duration", "magnitude": "magnitude", "month_sin": "time of year",
              "month_cos": "time of year", "lat": "location", "lon": "location"}


def _sim_matrix(df: pd.DataFrame):
    from ..ml.features import add_engineered
    e = add_engineered(df)
    X = e[SIM_FEATURES].astype(float)
    # a column can be entirely empty within a pool (e.g. magnitude for tornadoes): its median is NaN, so use 0.
    # StandardScaler leaves a constant column at 0, so it simply stops contributing to the distance.
    X = X.fillna(X.median()).fillna(0.0)
    scaler = StandardScaler().fit(X.values)
    return e, scaler.transform(X.values), scaler


def similar_events(df: pd.DataFrame, event_id: int, k: int = 10, same_type: bool = True) -> dict:
    row = df[df["event_id"] == event_id]
    if row.empty:
        raise KeyError(f"Event {event_id} not found")
    pool = df[df["event_type"] == row.iloc[0]["event_type"]] if same_type else df
    pool = pool[pool["event_id"] != event_id]
    e_pool, Xp, scaler = _sim_matrix(pd.concat([row, pool]))
    q, Xp = Xp[:1], Xp[1:]
    k = min(k, len(Xp))
    nn = NearestNeighbors(n_neighbors=k).fit(Xp)
    dist, idx = nn.kneighbors(q)
    sims = 1.0 / (1.0 + dist[0])
    base = e_pool.iloc[0]
    out = []
    for d, s, i in zip(dist[0], sims, idx[0]):
        r = e_pool.iloc[i + 1]
        contrib = np.abs(q[0] - Xp[i])
        grp: dict[str, float] = {}
        for f_, c in zip(SIM_FEATURES, contrib):
            grp[SIM_LABELS[f_]] = grp.get(SIM_LABELS[f_], 0.0) + float(c)
        closest = sorted(grp, key=grp.get)[:3]
        out.append({"event_id": int(r["event_id"]), "similarity": round(float(s), 4), "distance": round(float(d), 4),
                    "event_type": r["event_type"], "state": r["state"], "begin_dt": r["begin_dt"], "deaths_total": r["deaths_total"],
                    "injuries_total": r["injuries_total"], "property_damage_usd": r["property_damage_usd"],
                    "closest_on": closest, "explanation": f"Most similar on {', '.join(closest)}."})
    return _clean({"query": {k_: base[k_] for k_ in ("event_id", "event_type", "state", "begin_dt", "deaths_total", "injuries_total",
                                                       "property_damage_usd", "crop_damage_usd", "magnitude", "lat", "lon")},
                   "similar": out, "method": "Euclidean distance on standardised features; missing values filled with the median.",
                   "features": sorted(set(SIM_LABELS.values())), "similarity_formula": "1 / (1 + distance)"})


def search_events(df: pd.DataFrame, event_id=None, min_magnitude=None, max_magnitude=None, text=None, page: int = 1,
                  page_size: int = 25, **filters) -> dict:
    f = apply_filters(df, **filters)
    if event_id:
        f = f[f["event_id"] == int(event_id)]
    if min_magnitude is not None:
        f = f[f["magnitude"] >= min_magnitude]
    if max_magnitude is not None:
        f = f[f["magnitude"] <= max_magnitude]
    if text:
        f = f[f["event_type"].str.contains(text, case=False, na=False) | f["state"].str.contains(text, case=False, na=False)]
    total = len(f)
    page_size = max(1, min(page_size, 200))
    start = (max(page, 1) - 1) * page_size
    cols = ["event_id", "event_type", "state", "year", "begin_dt", "magnitude", "deaths_total", "injuries_total",
            "property_damage_usd", "crop_damage_usd", "has_coordinates"]
    return _clean({"total": total, "page": page, "page_size": page_size, "rows": f.iloc[start:start + page_size][cols].to_dict("records")})


def event_record(df: pd.DataFrame, event_id: int) -> dict:
    r = df[df["event_id"] == event_id]
    if r.empty:
        raise KeyError(f"Event {event_id} not found")
    return _clean(r.iloc[0].to_dict())


# ----------------------------------------------------------------------------- multi-hazard
def multi_hazard(df: pd.DataFrame, radius_km: float = 50.0, window_hours: float = 24.0, type_a: str | None = None,
                 type_b: str | None = None, max_pairs: int = 20000, **filters) -> dict:
    """Pairs of DIFFERENT event types recorded within radius_km and window_hours. Proximity only, never causation."""
    f = apply_filters(df, has_coordinates=True, **filters).copy()
    f["t"] = pd.to_datetime(f["begin_dt"])
    f = f.dropna(subset=["t"]).reset_index(drop=True)
    caveat = "Spatial and temporal proximity of records does not imply that one event caused another."
    if len(f) < 2:
        return {"pairs": [], "combinations": [], "caveat": caveat, "events_considered": len(f)}
    tree = BallTree(np.radians(f[["lat", "lon"]].values), metric="haversine")
    nbrs = tree.query_radius(np.radians(f[["lat", "lon"]].values), r=radius_km / EARTH_KM)
    ts = f["t"].values.astype("datetime64[s]").astype("int64")
    win = window_hours * 3600
    types = f["event_type"].values
    ids = f["event_id"].values
    pairs, truncated = [], False
    for i, nb in enumerate(nbrs):
        for j in nb:
            if j <= i or types[i] == types[j]:
                continue
            dt = abs(ts[i] - ts[j])
            if dt > win:
                continue
            a, b = sorted((types[i], types[j]))
            if (type_a and type_a.lower() not in (a.lower(), b.lower())) or (type_b and type_b.lower() not in (a.lower(), b.lower())):
                continue
            pairs.append((int(ids[i]), int(ids[j]), a, b, round(dt / 3600, 2)))
            if len(pairs) >= max_pairs:
                truncated = True
                break
        if truncated:
            break
    combo = pd.DataFrame(pairs, columns=["event_a", "event_b", "type_a", "type_b", "hours_apart"])
    combos = (combo.groupby(["type_a", "type_b"]).agg(pairs=("event_a", "size"), median_hours_apart=("hours_apart", "median"))
              .reset_index().sort_values("pairs", ascending=False) if len(combo) else pd.DataFrame())
    return _clean({"radius_km": radius_km, "window_hours": window_hours, "events_considered": len(f), "pair_count": len(pairs),
                   "truncated": truncated, "combinations": combos.head(30).to_dict("records") if len(combos) else [],
                   "pairs": combo.head(200).to_dict("records"), "caveat": caveat})


def nearby_events(df: pd.DataFrame, event_id: int, radius_km: float = 50.0, window_hours: float = 24.0) -> dict:
    row = df[df["event_id"] == event_id]
    if row.empty:
        raise KeyError(f"Event {event_id} not found")
    r = row.iloc[0]
    if not r["has_coordinates"]:
        return {"event": _clean(r[["event_id", "event_type", "state", "begin_dt"]].to_dict()), "nearby": [],
                "note": "This event has no recorded coordinates, so spatial search is not possible.",
                "caveat": "Proximity does not imply causation."}
    c = df[df["has_coordinates"] & (df["event_id"] != event_id)].copy()
    lat1, lon1 = np.radians(r["lat"]), np.radians(r["lon"])
    lat2, lon2 = np.radians(c["lat"].values), np.radians(c["lon"].values)
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    c["km"] = 2 * EARTH_KM * np.arcsin(np.sqrt(a))
    c["hours"] = (pd.to_datetime(c["begin_dt"]) - pd.to_datetime(r["begin_dt"])).dt.total_seconds() / 3600
    c = c[(c["km"] <= radius_km) & (c["hours"].abs() <= window_hours)].sort_values("hours")
    cols = ["event_id", "event_type", "state", "begin_dt", "km", "hours", "deaths_total", "property_damage_usd"]
    return _clean({"event": r[["event_id", "event_type", "state", "begin_dt", "lat", "lon"]].to_dict(),
                   "nearby": c[cols].round({"km": 1, "hours": 2}).head(200).to_dict("records"),
                   "caveat": "Proximity does not imply causation. Negative hours = recorded before the selected event."})
