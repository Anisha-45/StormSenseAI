"""Module 3: Hierarchical Agglomerative Clustering, DBSCAN and (optional) HDBSCAN, with evaluation,
PCA, parameter sensitivity and stability. Pure functions over a numeric matrix."""
from __future__ import annotations

import time
import tracemalloc

import numpy as np
from scipy.cluster import hierarchy as sch
from sklearn.cluster import DBSCAN, AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.metrics import (adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_samples,
                             silhouette_score)
from sklearn.neighbors import NearestNeighbors

from ..core import config

LINKAGES = ["ward", "complete", "average", "single"]
METRICS = ["euclidean", "manhattan", "chebyshev", "cosine"]


def _timed(fn):
    tracemalloc.start()
    t0 = time.perf_counter()
    out = fn()
    secs = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return out, round(secs, 3), round(peak / 1e6, 1)


def run_hierarchical(X: np.ndarray, n_clusters: int = 6, linkage: str = "ward", metric: str = "euclidean") -> dict:
    if linkage not in LINKAGES:
        raise ValueError(f"linkage must be one of {LINKAGES}")
    if linkage == "ward":
        metric = "euclidean"  # Ward is only defined for Euclidean distance
    if len(X) > config.MAX_HIERARCHICAL_ROWS:
        raise ValueError(f"Hierarchical clustering is limited to {config.MAX_HIERARCHICAL_ROWS} rows on this hardware "
                         f"(got {len(X)}). Use a smaller sample.")
    if not 2 <= n_clusters < len(X):
        raise ValueError("n_clusters must be between 2 and n_rows-1")
    model = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage, metric=metric)
    labels, secs, peak = _timed(lambda: model.fit_predict(X))
    return {"algorithm": "hierarchical", "labels": labels, "seconds": secs, "peak_mb": peak,
            "params": {"n_clusters": n_clusters, "linkage": linkage, "metric": metric}}


def dendrogram_data(X: np.ndarray, linkage: str = "ward", metric: str = "euclidean", max_rows: int = 600,
                    truncate_p: int = 30, seed: int = 42) -> dict:
    """Dendrogram for a small subsample (a dendrogram of thousands of leaves is unreadable)."""
    if linkage == "ward":
        metric = "euclidean"
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(X), size=min(max_rows, len(X)), replace=False)
    Z = sch.linkage(X[idx], method=linkage, metric=metric)
    d = sch.dendrogram(Z, p=truncate_p, truncate_mode="lastp", no_plot=True)
    return {"icoord": d["icoord"], "dcoord": d["dcoord"], "leaves": [int(x) for x in d["leaves"]],
            "ivl": d["ivl"], "sample_rows": int(len(idx)), "linkage": linkage,
            "merge_heights_last_20": [round(float(h), 4) for h in Z[-20:, 2]]}


def run_dbscan(X: np.ndarray, eps: float = 1.0, min_samples: int = 10, metric: str = "euclidean") -> dict:
    if metric not in METRICS:
        raise ValueError(f"metric must be one of {METRICS}")
    if eps <= 0 or min_samples < 1:
        raise ValueError("eps must be > 0 and min_samples >= 1")
    algo = "brute" if metric == "cosine" else "auto"
    model = DBSCAN(eps=eps, min_samples=min_samples, metric=metric, algorithm=algo, n_jobs=-1)
    labels, secs, peak = _timed(lambda: model.fit_predict(X))
    point_type = np.full(len(X), "noise", dtype=object)
    border = labels != -1
    point_type[border] = "border"
    point_type[model.core_sample_indices_] = "core"
    return {"algorithm": "dbscan", "labels": labels, "seconds": secs, "peak_mb": peak, "point_type": point_type,
            "params": {"eps": eps, "min_samples": min_samples, "metric": metric},
            "core_count": int(len(model.core_sample_indices_)), "border_count": int((point_type == "border").sum())}


def run_hdbscan(X: np.ndarray, min_cluster_size: int = 20, min_samples: int | None = None) -> dict:
    from sklearn.cluster import HDBSCAN
    model = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples, copy=True)
    labels, secs, peak = _timed(lambda: model.fit_predict(X))
    return {"algorithm": "hdbscan", "labels": labels, "seconds": secs, "peak_mb": peak,
            "params": {"min_cluster_size": min_cluster_size, "min_samples": min_samples}}


def k_distance(X: np.ndarray, k: int = 10) -> list[float]:
    """Sorted distance to the k-th nearest neighbour; the 'knee' suggests a DBSCAN eps."""
    k = min(k, len(X) - 1)
    nn = NearestNeighbors(n_neighbors=k + 1).fit(X)
    dist, _ = nn.kneighbors(X)
    return np.sort(dist[:, -1]).round(4).tolist()


def suggest_eps(kdist: list[float]) -> float:
    """Knee by maximum distance from the chord between first and last point of the sorted k-distance curve."""
    y = np.asarray(kdist)
    if len(y) < 3:
        return float(y[-1]) if len(y) else 1.0
    x = np.linspace(0, 1, len(y))
    yn = (y - y.min()) / max(y.max() - y.min(), 1e-12)
    d = np.abs(yn - x) / np.sqrt(2)
    # knee of a convex-upward curve: furthest point BELOW the chord
    return float(y[int(np.argmax(x - yn))]) if (x - yn).max() > 0 else float(np.median(y))


def evaluate(X: np.ndarray, labels: np.ndarray, silhouette_cap: int = 8000, seed: int = 42) -> dict:
    """Validity-aware metrics. Noise (-1) is excluded from all internal indices; each index is only
    computed when its assumptions hold (>=2 clusters and at least one cluster with >1 point)."""
    labels = np.asarray(labels)
    n = len(labels)
    noise = labels == -1
    clustered = ~noise
    ids, counts = np.unique(labels[clustered], return_counts=True)
    out = {"n_rows": int(n), "n_clusters": int(len(ids)), "noise_count": int(noise.sum()),
           "noise_pct": round(float(noise.mean() * 100), 2),
           "cluster_sizes": {int(i): int(c) for i, c in zip(ids, counts)},
           "silhouette": None, "davies_bouldin": None, "calinski_harabasz": None, "notes": []}
    if len(ids) >= 2 and clustered.sum() > len(ids):
        Xc, lc = X[clustered], labels[clustered]
        if len(Xc) > silhouette_cap:
            rng = np.random.default_rng(seed)
            sel = rng.choice(len(Xc), size=silhouette_cap, replace=False)
            if len(np.unique(lc[sel])) >= 2:
                out["silhouette"] = round(float(silhouette_score(Xc[sel], lc[sel])), 4)
                out["notes"].append(f"Silhouette computed on a {silhouette_cap}-point random subset of clustered points.")
        else:
            out["silhouette"] = round(float(silhouette_score(Xc, lc)), 4)
        out["davies_bouldin"] = round(float(davies_bouldin_score(Xc, lc)), 4)
        out["calinski_harabasz"] = round(float(calinski_harabasz_score(Xc, lc)), 2)
        if noise.any():
            out["notes"].append("Noise points were excluded from Silhouette, Davies-Bouldin and Calinski-Harabasz.")
    else:
        out["notes"].append("Fewer than 2 clusters: internal validity indices are undefined and were not computed.")
    out["notes"].append("A high Silhouette does not mean the grouping is the most useful for analysts: density-based "
                        "clusters are rarely convex, and the indices favour compact spherical groups.")
    return out


def silhouette_per_cluster(X: np.ndarray, labels: np.ndarray, cap: int = 6000, seed: int = 42) -> dict:
    labels = np.asarray(labels)
    m = labels != -1
    Xc, lc = X[m], labels[m]
    if len(np.unique(lc)) < 2 or len(Xc) < 3:
        return {}
    if len(Xc) > cap:
        sel = np.random.default_rng(seed).choice(len(Xc), size=cap, replace=False)
        Xc, lc = Xc[sel], lc[sel]
        if len(np.unique(lc)) < 2:
            return {}
    s = silhouette_samples(Xc, lc)
    return {int(c): round(float(s[lc == c].mean()), 4) for c in np.unique(lc)}


def pca_projection(X: np.ndarray, n_components: int = 2, seed: int = 42) -> dict:
    k = min(n_components, X.shape[1], X.shape[0])
    pca = PCA(n_components=k, random_state=seed)
    coords = pca.fit_transform(X)
    return {"coords": coords, "explained_variance_ratio": [round(float(v), 4) for v in pca.explained_variance_ratio_],
            "components": pca.components_}


def hierarchical_linkage_comparison(X: np.ndarray, n_clusters: int, metric: str = "euclidean") -> list[dict]:
    rows = []
    for lk in LINKAGES:
        res = run_hierarchical(X, n_clusters, lk, metric)
        ev = evaluate(X, res["labels"])
        rows.append({"linkage": lk, "seconds": res["seconds"], **{k: ev[k] for k in (
            "n_clusters", "cluster_sizes", "silhouette", "davies_bouldin", "calinski_harabasz")}})
    return rows


def dbscan_sensitivity(X: np.ndarray, eps_values: list[float], min_samples_values: list[int], metric: str = "euclidean") -> list[dict]:
    grid = []
    for eps in eps_values:
        for ms in min_samples_values:
            res = run_dbscan(X, eps, ms, metric)
            ev = evaluate(X, res["labels"])
            grid.append({"eps": eps, "min_samples": ms, "n_clusters": ev["n_clusters"], "noise_pct": ev["noise_pct"],
                         "silhouette": ev["silhouette"], "largest_cluster": max(ev["cluster_sizes"].values(), default=0),
                         "seconds": res["seconds"]})
    return grid


def stability(X: np.ndarray, runner, n_runs: int = 5, fraction: float = 0.8, seed: int = 42) -> dict:
    """Subsample stability: cluster a random fraction of rows several times and compare each run with the
    baseline on the shared rows using the Adjusted Rand Index (1 = identical grouping, ~0 = random)."""
    base = runner(X)
    rng = np.random.default_rng(seed)
    scores = []
    for _ in range(n_runs):
        idx = np.sort(rng.choice(len(X), size=int(len(X) * fraction), replace=False))
        sub = runner(X[idx])
        scores.append(float(adjusted_rand_score(base[idx], sub)))
    return {"ari_mean": round(float(np.mean(scores)), 4), "ari_std": round(float(np.std(scores)), 4),
            "ari_runs": [round(s, 4) for s in scores], "runs": n_runs, "fraction": fraction,
            "interpretation": "ARI near 1 means the grouping is reproducible under resampling; below ~0.5 it is fragile."}


def assemble_result(X, raw: dict, with_pca: bool = True) -> dict:
    labels = raw["labels"]
    ev = evaluate(X, labels)
    res = {**{k: v for k, v in raw.items() if k not in ("labels", "point_type")}, "metrics": ev,
           "silhouette_by_cluster": silhouette_per_cluster(X, labels)}
    if with_pca:
        p = pca_projection(X)
        res["pca"] = {"explained_variance_ratio": p["explained_variance_ratio"]}
        res["pca_coords"] = p["coords"]
    return res
