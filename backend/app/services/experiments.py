"""Reproducible clustering experiments: run, persist (config, params, seed, metrics, assignments, profiles), compare."""
from __future__ import annotations

import json

import numpy as np

from ..db import database as db
from ..ml import clustering as C
from ..ml import features as F
from ..ml import profiles as P
from .processing import load_events, load_manifest

_EVENTS_CACHE: dict = {}


def get_events():
    """Process-level cache so repeated experiments do not re-read the processed table."""
    m = load_manifest()
    key = m["dataset_version"]
    if _EVENTS_CACHE.get("key") != key:
        _EVENTS_CACHE.clear()
        _EVENTS_CACHE.update(key=key, events=load_events(), manifest=m)
    return _EVENTS_CACHE["events"], _EVENTS_CACHE["manifest"]


def clear_cache():
    _EVENTS_CACHE.clear()


def run_experiment(algorithm: str, params: dict, feature_config: dict | None = None, user_id: int | None = None,
                   con=None, with_stability: bool = False, seed: int = 42) -> dict:
    events, manifest = get_events()
    fc = dict(feature_config or {})
    fc.setdefault("sample_size", 5000)
    build = F.build_matrix(events, seed=seed, **fc)
    X, frame = build["X"], build["frame"]

    if algorithm == "hierarchical":
        p = {"n_clusters": 6, "linkage": "ward", "metric": "euclidean", **params}
        raw = C.run_hierarchical(X, **p)
        runner = lambda M: C.run_hierarchical(M, **p)["labels"]
    elif algorithm == "dbscan":
        p = dict(params)
        if "eps" not in p:
            p["eps"] = C.suggest_eps(C.k_distance(X, p.get("min_samples", 10)))
        p.setdefault("min_samples", 10)
        p.setdefault("metric", "euclidean")
        raw = C.run_dbscan(X, **p)
        runner = lambda M: C.run_dbscan(M, **p)["labels"]
    elif algorithm == "hdbscan":
        p = {"min_cluster_size": 20, **params}
        raw = C.run_hdbscan(X, **p)
        runner = lambda M: C.run_hdbscan(M, **p)["labels"]
    else:
        raise ValueError("algorithm must be hierarchical, dbscan or hdbscan")

    result = C.assemble_result(X, raw)
    labels = raw["labels"]
    profiles = P.build_profiles(frame, labels, raw.get("point_type"))
    importance = P.feature_importance(frame, labels, ["deaths_total", "injuries_total", "property_damage_usd",
                                                      "crop_damage_usd", "duration_hours", "magnitude", "month", "lat", "lon"])
    stab = C.stability(X, runner, n_runs=4) if with_stability else None
    metrics = {**result["metrics"], "silhouette_by_cluster": result["silhouette_by_cluster"],
               "pca_explained_variance": result["pca"]["explained_variance_ratio"],
               "feature_importance": importance, "stability": stab,
               "core_count": raw.get("core_count"), "border_count": raw.get("border_count")}
    out = {"algorithm": algorithm, "params": result["params"], "config": build["config"], "metrics": metrics,
           "seconds": result["seconds"], "peak_mb": result["peak_mb"], "profiles": profiles}

    own = con is None
    if own:
        db.init_db()
    cm = db.session() if own else _Passthrough(con)
    with cm as c:
        cur = c.execute(
            "INSERT INTO experiments(algorithm,dataset_id,dataset_version,config_json,params_json,seed,n_clusters,noise_count,"
            "noise_pct,metrics_json,seconds,peak_mb,notes,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (algorithm, manifest["dataset_id"], manifest["dataset_version"], db.dumps(build["config"]), db.dumps(result["params"]),
             seed, metrics["n_clusters"], metrics["noise_count"], metrics["noise_pct"], db.dumps(metrics), result["seconds"],
             result["peak_mb"], " | ".join(metrics["notes"]), user_id, db.now()))
        eid = cur.lastrowid
        pcs = result["pca_coords"]
        pt = raw.get("point_type")
        c.executemany("INSERT INTO cluster_assignments(experiment_id,event_id,cluster,point_type,pc1,pc2) VALUES(?,?,?,?,?,?)",
                      [(eid, int(frame["event_id"].iat[i]), int(labels[i]), None if pt is None else str(pt[i]),
                        float(pcs[i, 0]), float(pcs[i, 1]) if pcs.shape[1] > 1 else 0.0) for i in range(len(frame))])
        c.executemany("INSERT INTO cluster_profiles(experiment_id,cluster_id,profile_json) VALUES(?,?,?)",
                      [(eid, p_["cluster_id"], db.dumps(p_)) for p_ in profiles])
    out["experiment_id"] = eid
    return out


class _Passthrough:
    def __init__(self, con): self.con = con
    def __enter__(self): return self.con
    def __exit__(self, *a): return False


def list_experiments(con) -> list[dict]:
    rows = db.rows(con, "SELECT id,algorithm,dataset_version,params_json,n_clusters,noise_count,noise_pct,seconds,peak_mb,"
                        "metrics_json,created_at FROM experiments ORDER BY id DESC")
    for r in rows:
        m = json.loads(r.pop("metrics_json"))
        r["params"] = json.loads(r.pop("params_json"))
        r["silhouette"], r["davies_bouldin"], r["calinski_harabasz"] = m.get("silhouette"), m.get("davies_bouldin"), m.get("calinski_harabasz")
        r["stability_ari"] = (m.get("stability") or {}).get("ari_mean")
    return rows


def get_experiment(con, eid: int) -> dict | None:
    r = db.one(con, "SELECT * FROM experiments WHERE id=?", (eid,))
    if not r:
        return None
    for k in ("config_json", "params_json", "metrics_json"):
        r[k.replace("_json", "")] = json.loads(r.pop(k))
    r["profiles"] = [json.loads(x["profile_json"]) for x in db.rows(
        con, "SELECT profile_json FROM cluster_profiles WHERE experiment_id=? ORDER BY cluster_id", (eid,))]
    return r


def get_assignments(con, eid: int, cluster: int | None = None, limit: int = 5000) -> list[dict]:
    sql = "SELECT event_id,cluster,point_type,pc1,pc2 FROM cluster_assignments WHERE experiment_id=?"
    args: list = [eid]
    if cluster is not None:
        sql += " AND cluster=?"
        args.append(cluster)
    return db.rows(con, sql + " LIMIT ?", (*args, limit))


def compare_experiments(con, ids: list[int]) -> dict:
    exps = [get_experiment(con, i) for i in ids]
    missing = [i for i, e in zip(ids, exps) if e is None]
    if missing:
        raise KeyError(f"Experiments not found: {missing}")
    rows = []
    for e in exps:
        m = e["metrics"]
        rows.append({"id": e["id"], "algorithm": e["algorithm"], "params": e["params"], "n_clusters": m["n_clusters"],
                     "noise_count": m["noise_count"], "noise_pct": m["noise_pct"], "silhouette": m["silhouette"],
                     "davies_bouldin": m["davies_bouldin"], "calinski_harabasz": m["calinski_harabasz"],
                     "seconds": e["seconds"], "peak_mb": e["peak_mb"], "largest_cluster_share_pct": round(
                         max(m["cluster_sizes"].values(), default=0) / max(m["n_rows"], 1) * 100, 1),
                     "stability_ari": (m.get("stability") or {}).get("ari_mean"), "sample_size": e["config"]["sample_size"]})
    caveats = ["Metrics are only directly comparable between experiments that used the same features and sample.",
               "The highest Silhouette is not automatically the best clustering: a solution that places almost every event "
               "in one cluster can score high while telling analysts nothing."]
    degenerate = [r["id"] for r in rows if r["largest_cluster_share_pct"] > 90]
    if degenerate:
        caveats.append(f"Experiments {degenerate} put more than 90% of events in one cluster; treat their scores with caution.")
    return {"experiments": rows, "caveats": caveats}
