"""Module 4: explainable cluster intelligence. Every sentence is generated from the cluster's actual
statistics. No causal claims and no invented descriptions."""
from __future__ import annotations

import numpy as np
import pandas as pd

IMPACT_COLS = ["deaths_total", "injuries_total", "property_damage_usd", "crop_damage_usd", "duration_hours", "magnitude"]


def _top(series: pd.Series, k: int = 3) -> list[dict]:
    vc = series.value_counts(normalize=True).head(k)
    return [{"name": str(i), "share_pct": round(float(v) * 100, 1)} for i, v in vc.items()]


def feature_importance(frame: pd.DataFrame, labels: np.ndarray, columns: list[str]) -> list[dict]:
    """Between-cluster separation per feature = eta squared (share of variance explained by cluster
    membership), computed on clustered points only. Descriptive, not causal."""
    m = np.asarray(labels) != -1
    out = []
    f = frame.loc[m].reset_index(drop=True)
    lab = np.asarray(labels)[m]
    for c in columns:
        if c not in f.columns:
            continue
        x = pd.to_numeric(f[c], errors="coerce")
        ok = x.notna()
        if ok.sum() < 3 or x[ok].var() == 0:
            continue
        gm = x[ok].mean()
        ss_tot = ((x[ok] - gm) ** 2).sum()
        ss_between = sum(((x[ok & (lab == k)].mean() - gm) ** 2) * (ok & (lab == k)).sum() for k in np.unique(lab))
        out.append({"feature": c, "eta_squared": round(float(ss_between / ss_tot), 4)})
    return sorted(out, key=lambda d: -d["eta_squared"])


def build_profiles(frame: pd.DataFrame, labels: np.ndarray, point_type: np.ndarray | None = None) -> list[dict]:
    frame = frame.reset_index(drop=True).copy()
    frame["cluster"] = np.asarray(labels)
    overall = {c: frame[c].mean() for c in IMPACT_COLS if c in frame}
    overall_median = {c: frame[c].median() for c in IMPACT_COLS if c in frame}
    profiles = []
    for cid, g in sorted(frame.groupby("cluster"), key=lambda kv: kv[0]):
        n = len(g)
        stats = {}
        for c in IMPACT_COLS:
            if c in g:
                s = pd.to_numeric(g[c], errors="coerce")
                stats[c] = {"mean": None if s.notna().sum() == 0 else round(float(s.mean()), 3),
                            "median": None if s.notna().sum() == 0 else round(float(s.median()), 3),
                            "max": None if s.notna().sum() == 0 else round(float(s.max()), 3),
                            "reported": int(s.notna().sum())}
        profile = {
            "cluster_id": int(cid), "is_noise": bool(cid == -1), "event_count": int(n),
            "share_pct": round(n / len(frame) * 100, 2),
            "dominant_event_types": _top(g["event_type"]),
            "top_states": _top(g["state"]),
            "year_distribution": {int(k): int(v) for k, v in g["year"].value_counts().sort_index().items()},
            "season_distribution": {str(k): int(v) for k, v in g["season"].value_counts().items()},
            "month_distribution": {int(k): int(v) for k, v in g["month"].value_counts().sort_index().items()},
            "totals": {"deaths": int(g["deaths_total"].sum()), "injuries": int(g["injuries_total"].sum()),
                       "property_damage_usd": float(g["property_damage_usd"].sum()),
                       "crop_damage_usd": float(g["crop_damage_usd"].sum())},
            "stats": stats,
            "events_with_coordinates": int(g["has_coordinates"].sum()) if "has_coordinates" in g else None,
            "events_with_impact": int(g["has_impact"].sum()) if "has_impact" in g else None,
        }
        if point_type is not None:
            pt = pd.Series(np.asarray(point_type)[frame["cluster"].values == cid])
            profile["point_types"] = {str(k): int(v) for k, v in pt.value_counts().items()}
        profile["differences"] = _differences(stats, overall, overall_median)
        profile["explanation"] = explain(profile)
        profiles.append(profile)
    return profiles


def _differences(stats: dict, overall: dict, overall_median: dict) -> list[dict]:
    diffs = []
    for c, s in stats.items():
        if s["mean"] is None or not overall.get(c) or np.isnan(overall[c]) or overall[c] == 0:
            continue
        ratio = s["mean"] / overall[c]
        diffs.append({"feature": c, "cluster_mean": s["mean"], "overall_mean": round(float(overall[c]), 3),
                      "ratio_to_overall": round(float(ratio), 2)})
    return sorted(diffs, key=lambda d: -abs(np.log(max(d["ratio_to_overall"], 1e-6))))[:4]


def explain(p: dict) -> str:
    """Plain-English summary built only from numbers in the profile."""
    label = "Noise points (not assigned to any cluster)" if p["is_noise"] else f"Cluster {p['cluster_id']}"
    types = ", ".join(f"{t['name']} ({t['share_pct']}%)" for t in p["dominant_event_types"])
    parts = [f"{label} holds {p['event_count']:,} events ({p['share_pct']}% of the analysed sample). "
             f"Most common event types: {types}."]
    states = ", ".join(t["name"] for t in p["top_states"][:3])
    parts.append(f"Most records come from {states}.")
    seasons = p["season_distribution"]
    if seasons:
        top_season = max(seasons, key=seasons.get)
        parts.append(f"The largest share occurred in {top_season} ({seasons[top_season] / p['event_count'] * 100:.0f}%).")
    t = p["totals"]
    if t["deaths"] or t["injuries"] or t["property_damage_usd"] or t["crop_damage_usd"]:
        parts.append(f"Recorded impacts: {t['deaths']} deaths, {t['injuries']} injuries, "
                     f"${t['property_damage_usd']:,.0f} property damage, ${t['crop_damage_usd']:,.0f} crop damage.")
    else:
        parts.append("No deaths, injuries or damage amounts are recorded for these events.")
    if p["differences"]:
        d = p["differences"][0]
        direction = "higher" if d["ratio_to_overall"] > 1 else "lower"
        parts.append(f"Largest difference from the overall sample: mean {d['feature'].replace('_', ' ')} is "
                     f"{d['ratio_to_overall']}x the overall mean ({direction}).")
    parts.append("This is a description of historical records, not a prediction or a statement of cause.")
    return " ".join(parts)
