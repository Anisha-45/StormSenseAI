"""Feature selection, missing-value treatment, encoding, scaling and representative sampling."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler

NUMERIC_FEATURES = {
    "log_property_damage": "log1p of property damage (USD)",
    "log_crop_damage": "log1p of crop damage (USD)",
    "injuries_total": "direct + indirect injuries",
    "deaths_total": "direct + indirect deaths",
    "log_duration_hours": "log1p of event duration in hours",
    "magnitude": "reported magnitude (type specific: wind kt/mph, hail inches)",
    "month_sin": "cyclic month (sine)",
    "month_cos": "cyclic month (cosine)",
    "lat": "begin latitude (events without coordinates are excluded when selected)",
    "lon": "begin longitude (events without coordinates are excluded when selected)",
}
CATEGORICAL_FEATURES = {"event_type": "event type (one-hot)", "season": "season (one-hot)"}
DEFAULT_FEATURES = ["log_property_damage", "log_crop_damage", "injuries_total", "deaths_total", "log_duration_hours",
                    "month_sin", "month_cos", "event_type"]
SCALERS = {"standard": StandardScaler, "robust": RobustScaler, "minmax": MinMaxScaler}
SOURCE_COLUMNS = ["event_id", "event_type", "state", "year", "month", "season", "property_damage_usd", "crop_damage_usd",
                  "injuries_total", "deaths_total", "duration_hours", "magnitude", "lat", "lon", "has_coordinates",
                  "has_impact", "total_damage_usd", "begin_dt", "episode_id"]


def add_engineered(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["log_property_damage"] = np.log1p(out["property_damage_usd"])
    out["log_crop_damage"] = np.log1p(out["crop_damage_usd"])
    out["log_duration_hours"] = np.log1p(out["duration_hours"])
    ang = 2 * np.pi * (out["month"] - 1) / 12.0
    out["month_sin"], out["month_cos"] = np.sin(ang), np.cos(ang)
    return out


def stratified_sample(df: pd.DataFrame, n: int, seed: int = 42, floor: int = 20) -> pd.DataFrame:
    """Representative sample, NOT the first N rows. Strata = event_type x has_impact x year. Every stratum
    keeps at least min(size, floor) rows so rare but important events (deaths, tornadoes) survive; the rest
    of the budget is allocated in proportion to stratum size."""
    if n >= len(df):
        return df.copy()
    key = df["event_type"].astype(str) + "|" + df["has_impact"].astype(str) + "|" + df["year"].astype(str)
    sizes = key.value_counts()
    base = sizes.clip(upper=floor)
    if base.sum() >= n:  # budget too small for floors: pure proportional
        alloc = (sizes / sizes.sum() * n).round().astype(int).clip(lower=1)
    else:
        remaining = n - base.sum()
        extra_cap = sizes - base
        share = extra_cap / max(extra_cap.sum(), 1) * remaining
        alloc = (base + share.round().astype(int)).clip(upper=sizes)
    rng = np.random.default_rng(seed)
    picks = []
    for k, grp_idx in df.groupby(key).groups.items():
        take = int(min(alloc.get(k, 0), len(grp_idx)))
        if take:
            picks.extend(rng.choice(np.asarray(grp_idx), size=take, replace=False).tolist())
    sample = df.loc[picks]
    if len(sample) > n:  # rounding overshoot: trim randomly
        sample = sample.sample(n=n, random_state=seed)
    return sample.sort_index()


def build_matrix(events: pd.DataFrame, features: list[str] | None = None, sample_size: int | None = None,
                 scaler: str = "standard", impute: str = "median", seed: int = 42,
                 event_types: list[str] | None = None, years: list[int] | None = None) -> dict:
    """Returns the scaled matrix plus everything needed to reproduce and explain it."""
    features = list(features or DEFAULT_FEATURES)
    unknown = [f for f in features if f not in NUMERIC_FEATURES and f not in CATEGORICAL_FEATURES]
    if unknown:
        raise ValueError(f"Unknown features: {unknown}")
    if not features:
        raise ValueError("Select at least one feature.")
    if scaler not in SCALERS:
        raise ValueError(f"scaler must be one of {list(SCALERS)}")
    if impute not in ("median", "zero"):
        raise ValueError("impute must be 'median' or 'zero'")

    df = add_engineered(events)
    n_start = len(df)
    if event_types:
        df = df[df["event_type"].isin(event_types)]
    if years:
        df = df[df["year"].isin(years)]
    excluded = {}
    if any(f in ("lat", "lon") for f in features):
        m = df["lat"].isna() | df["lon"].isna()
        excluded["missing_coordinates"] = int(m.sum())
        df = df[~m]
    if len(df) == 0:
        raise ValueError("No rows left after filters.")
    population = len(df)
    if sample_size and sample_size < len(df):
        df = stratified_sample(df, sample_size, seed)

    num_cols = [f for f in features if f in NUMERIC_FEATURES]
    cat_cols = [f for f in features if f in CATEGORICAL_FEATURES]
    parts, names, imputed = [], [], {}
    if num_cols:
        num = df[num_cols].astype(float)
        for c in num_cols:
            n_missing = int(num[c].isna().sum())
            if n_missing:
                med = num[c].median()
                fill = 0.0 if (impute == "zero" or pd.isna(med)) else float(med)
                imputed[c] = {"missing": n_missing, "fill_value": fill}
                num[c] = num[c].fillna(fill)
        scaled = SCALERS[scaler]().fit_transform(num.values)
        parts.append(scaled)
        names += num_cols
    for c in cat_cols:
        dummies = pd.get_dummies(df[c].astype(str), prefix=c, dtype=float)
        # scale one-hot columns down so a 49-level category does not dominate the distance
        parts.append(dummies.values / np.sqrt(max(dummies.shape[1], 1)) * 1.5)
        names += dummies.columns.tolist()
    X = np.hstack(parts)
    return {
        "X": X, "feature_names": names, "frame": df.reset_index(drop=True), "selected_features": features,
        "config": {"features": features, "scaler": scaler, "impute": impute, "encoding": "one-hot (damped by 1.5/sqrt(levels))",
                   "sample_size": int(len(df)), "population_after_filters": int(population), "rows_before_filters": int(n_start),
                   "seed": seed, "event_types": event_types, "years": years, "excluded": excluded, "imputed": imputed},
    }
