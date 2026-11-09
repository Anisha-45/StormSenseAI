"""Module 7: anomaly detection. Isolation Forest, robust statistical outliers (modified z-score / MAD) and
Local Outlier Factor. An anomaly is an unusual record, not necessarily an error and not necessarily dangerous.
A DBSCAN noise point is a different concept and is NOT treated as an anomaly here."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler

from .features import add_engineered, stratified_sample

DEFAULT_FEATURES = ["log_property_damage", "log_crop_damage", "injuries_total", "deaths_total", "log_duration_hours", "magnitude"]
LOF_MAX_ROWS = 20000


def _prepare(events: pd.DataFrame, features: list[str]):
    e = add_engineered(events)
    X = e[features].astype(float)
    X = X.fillna(X.median()).fillna(0.0)  # all-empty column -> 0 (constant, contributes nothing)
    return e, RobustScaler().fit_transform(X.values)


def robust_score(series: pd.Series) -> pd.Series:
    """Tukey-fence distance: how many IQRs a value lies beyond the nearest quartile (0 inside the fences'
    inner range). Zero-inflated columns (most impact fields) use the non-zero values as the reference,
    otherwise every non-zero value would look extreme against a median of 0. Unlike a plain MAD z-score this
    is stable for bimodal columns such as duration."""
    x = series.astype(float)
    zero_inflated = (x.fillna(0) == 0).mean() > 0.5
    ref = x[(x != 0) & x.notna()] if zero_inflated else x.dropna()
    if len(ref) < 20:
        return pd.Series(0.0, index=x.index)
    q1, q3 = ref.quantile(0.25), ref.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        iqr = ref.std() or 1.0
    s = pd.Series(0.0, index=x.index)
    s = s.where(~(x > q3), (x - q3) / iqr)
    s = s.where(~(x < q1), (x - q1) / iqr)  # negative for low outliers
    s = s.fillna(0.0)
    if zero_inflated:
        s = s.where(x != 0, 0.0)
    return s


modified_z = robust_score  # backwards-compatible alias


def run(events: pd.DataFrame, method: str = "isolation_forest", features: list[str] | None = None, contamination: float = 0.01,
        seed: int = 42, top: int = 100, z_threshold: float = 3.0, n_neighbors: int = 35) -> dict:
    features = features or DEFAULT_FEATURES
    if not 0 < contamination < 0.5:
        raise ValueError("contamination must be between 0 and 0.5")
    e, X = _prepare(events, features)
    e = e.reset_index(drop=True)
    notes = []
    if method == "isolation_forest":
        model = IsolationForest(n_estimators=200, contamination=contamination, random_state=seed, n_jobs=-1).fit(X)
        score = -model.score_samples(X)           # higher = more anomalous
        flag = model.predict(X) == -1
    elif method == "lof":
        if len(e) > LOF_MAX_ROWS:
            sub_idx = stratified_sample(e, LOF_MAX_ROWS, seed).index
            e, X = e.loc[sub_idx].reset_index(drop=True), X[sub_idx]
            notes.append(f"LOF was run on a stratified {LOF_MAX_ROWS}-row sample (neighbour search is expensive).")
        model = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination, n_jobs=-1)
        flag = model.fit_predict(X) == -1
        score = -model.negative_outlier_factor_
    elif method == "statistical":
        z = pd.DataFrame({f: modified_z(e[f]) for f in features})
        score = z.abs().max(axis=1).values
        flag = score >= z_threshold
        notes.append(f"Flagged when any selected feature lies at least {z_threshold} IQRs beyond the quartiles (Tukey fence; zero-heavy columns are judged against their non-zero values).")
    else:
        raise ValueError("method must be isolation_forest, lof or statistical")

    e = e.assign(anomaly_score=np.asarray(score, dtype=float), is_anomaly=np.asarray(flag, dtype=bool))
    # explanation: which selected features are most extreme for each flagged row
    z_all = pd.DataFrame({f: modified_z(e[f]) for f in features})
    top_rows = e[e["is_anomaly"]].sort_values("anomaly_score", ascending=False).head(top)
    results = []
    for idx, r in top_rows.iterrows():
        zz = z_all.loc[idx].abs().sort_values(ascending=False)
        drivers = [{"feature": f, "value": None if pd.isna(r[f]) else float(r[f]), "robust_score": round(float(z_all.loc[idx, f]), 2)}
                   for f in zz.index[:3]]
        combo = _unusual_combo(r)
        results.append({"event_id": int(r["event_id"]), "event_type": r["event_type"], "state": r["state"], "begin_dt": r["begin_dt"],
                        "anomaly_score": round(float(r["anomaly_score"]), 4), "classification": _classify(r, drivers),
                        "drivers": drivers, "unusual_combination": combo,
                        "deaths_total": float(r["deaths_total"]), "injuries_total": float(r["injuries_total"]),
                        "property_damage_usd": None if pd.isna(r["property_damage_usd"]) else float(r["property_damage_usd"])})
    return {"method": method, "features": features, "contamination": contamination, "seed": seed, "rows_scored": int(len(e)),
            "anomalies_flagged": int(e["is_anomaly"].sum()), "results": results, "notes": notes,
            "caveat": "An anomaly is an unusual record relative to the selected features. It may reflect a rare severe event, "
                      "a reporting quirk or a data-entry error; it is not by itself dangerous or wrong."}


def _classify(r, drivers: list[dict]) -> str:
    names = {d["feature"] for d in drivers[:2]}
    if names & {"deaths_total", "injuries_total"}:
        return "unusual human impact"
    if names & {"log_property_damage", "log_crop_damage"}:
        return "unusual damage"
    if "log_duration_hours" in names:
        return "unusual duration"
    if "magnitude" in names:
        return "unusual magnitude"
    return "unusual combination"


def _unusual_combo(r) -> str | None:
    if r["deaths_total"] > 0 and (pd.isna(r["property_damage_usd"]) or r["property_damage_usd"] == 0):
        return "deaths recorded with no property damage amount"
    if r["property_damage_usd"] and r["property_damage_usd"] > 1e7 and r["injuries_total"] == 0 and r["deaths_total"] == 0:
        return "very high property damage with no recorded casualties"
    if r["duration_hours"] and r["duration_hours"] > 240 and r["event_type"] not in ("Drought",):
        return "very long duration for this event type"
    return None
