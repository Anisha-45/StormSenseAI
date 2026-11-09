import numpy as np
import pytest
from sklearn.datasets import make_blobs

from app.ml import anomaly as AN
from app.ml import clustering as C
from app.ml import features as F
from app.ml import profiles as P


@pytest.fixture(scope="module")
def blobs():
    X, y = make_blobs(n_samples=400, centers=[[0, 0], [8, 8], [-8, 8]], cluster_std=0.6, random_state=0)
    return X, y


# ---- hierarchical ----------------------------------------------------------------------
@pytest.mark.parametrize("linkage", C.LINKAGES)
def test_hierarchical_all_linkages(blobs, linkage):
    X, _ = blobs
    r = C.run_hierarchical(X, 3, linkage)
    assert len(r["labels"]) == len(X) and len(set(r["labels"])) == 3 and r["seconds"] >= 0


def test_ward_forces_euclidean(blobs):
    assert C.run_hierarchical(blobs[0], 3, "ward", "manhattan")["params"]["metric"] == "euclidean"


def test_hierarchical_recovers_known_blobs(blobs):
    from sklearn.metrics import adjusted_rand_score
    X, y = blobs
    assert adjusted_rand_score(y, C.run_hierarchical(X, 3, "ward")["labels"]) > 0.95


def test_hierarchical_validation(blobs):
    with pytest.raises(ValueError):
        C.run_hierarchical(blobs[0], 1)
    with pytest.raises(ValueError):
        C.run_hierarchical(blobs[0], 3, "bogus")


def test_hierarchical_row_cap(monkeypatch, blobs):
    monkeypatch.setattr(C.config, "MAX_HIERARCHICAL_ROWS", 100)
    with pytest.raises(ValueError, match="limited"):
        C.run_hierarchical(blobs[0], 3)


def test_dendrogram_data(blobs):
    d = C.dendrogram_data(blobs[0], "ward", max_rows=100)
    assert d["sample_rows"] == 100 and len(d["icoord"]) == len(d["dcoord"]) > 0


# ---- DBSCAN ----------------------------------------------------------------------------
def test_dbscan_finds_clusters_and_noise(blobs):
    X, _ = blobs
    X2 = np.vstack([X, [[50, 50], [-50, -50]]])
    r = C.run_dbscan(X2, eps=1.0, min_samples=5)
    assert len(set(r["labels"]) - {-1}) == 3
    assert (r["labels"][-2:] == -1).all()                                   # outliers are noise
    assert (r["point_type"][-2:] == "noise").all()
    assert r["core_count"] + r["border_count"] == int((r["labels"] != -1).sum())


def test_dbscan_validation(blobs):
    with pytest.raises(ValueError):
        C.run_dbscan(blobs[0], eps=0)
    with pytest.raises(ValueError):
        C.run_dbscan(blobs[0], metric="bogus")


@pytest.mark.parametrize("metric", C.METRICS)
def test_dbscan_metrics_run(blobs, metric):
    assert len(C.run_dbscan(blobs[0], eps=0.5 if metric == "cosine" else 1.5, min_samples=5, metric=metric)["labels"]) == len(blobs[0])


def test_k_distance_and_eps_suggestion(blobs):
    kd = C.k_distance(blobs[0], 5)
    assert kd == sorted(kd)
    assert 0 < C.suggest_eps(kd) <= kd[-1]


def test_dbscan_sensitivity_grid(blobs):
    g = C.dbscan_sensitivity(blobs[0], [0.3, 1.0], [3, 10])
    assert len(g) == 4 and all("noise_pct" in r for r in g)
    # a larger eps (same min_samples) can never create MORE noise than a smaller one
    by = {(r["eps"], r["min_samples"]): r["noise_pct"] for r in g}
    assert by[(1.0, 3)] <= by[(0.3, 3)] and by[(1.0, 10)] <= by[(0.3, 10)]


def test_hdbscan_runs(blobs):
    assert len(set(C.run_hdbscan(blobs[0], 10)["labels"]) - {-1}) >= 2


# ---- evaluation ------------------------------------------------------------------------
def test_metrics_exclude_noise_and_are_valid(blobs):
    X, _ = blobs
    labels = C.run_hierarchical(X, 3)["labels"].copy()
    labels[:10] = -1
    ev = C.evaluate(X, labels)
    assert ev["noise_count"] == 10 and ev["n_clusters"] == 3
    assert -1 < ev["silhouette"] <= 1 and ev["davies_bouldin"] > 0 and ev["calinski_harabasz"] > 0
    assert any("Noise points were excluded" in n for n in ev["notes"])


def test_metrics_undefined_for_single_cluster(blobs):
    ev = C.evaluate(blobs[0], np.zeros(len(blobs[0]), dtype=int))
    assert ev["silhouette"] is None and ev["davies_bouldin"] is None


def test_metrics_all_noise(blobs):
    ev = C.evaluate(blobs[0], -np.ones(len(blobs[0]), dtype=int))
    assert ev["n_clusters"] == 0 and ev["noise_pct"] == 100.0 and ev["silhouette"] is None


def test_pca_shapes(blobs):
    p = C.pca_projection(blobs[0])
    assert p["coords"].shape == (400, 2) and 0 < sum(p["explained_variance_ratio"]) <= 1


def test_stability_high_for_clear_structure(blobs):
    s = C.stability(blobs[0], lambda M: C.run_hierarchical(M, 3)["labels"], n_runs=3)
    assert s["ari_mean"] > 0.9


def test_linkage_comparison(blobs):
    rows = C.hierarchical_linkage_comparison(blobs[0], 3)
    assert [r["linkage"] for r in rows] == C.LINKAGES


def test_reproducible_with_seed(real_events):
    a = F.build_matrix(real_events, sample_size=800, seed=7)
    b = F.build_matrix(real_events, sample_size=800, seed=7)
    assert (a["frame"]["event_id"].values == b["frame"]["event_id"].values).all()
    assert np.allclose(a["X"], b["X"])
    la = C.run_hierarchical(a["X"], 4)["labels"]
    lb = C.run_hierarchical(b["X"], 4)["labels"]
    assert (la == lb).all()


# ---- features / sampling ---------------------------------------------------------------
def test_sampling_is_representative_not_first_n(real_events):
    b = F.build_matrix(real_events, sample_size=3000)
    fr = b["frame"]
    assert fr["event_type"].nunique() == real_events["event_type"].nunique()      # every type survives
    assert set(fr["year"].unique()) == set(real_events["year"].unique())
    assert fr["has_impact"].mean() > real_events["has_impact"].mean()              # rare impactful events are kept
    assert not np.array_equal(fr["event_id"].values[:100], np.sort(real_events["event_id"].values)[:100])
    assert abs(len(fr) - 3000) <= 50


def test_coordinate_features_exclude_missing_and_report_it(real_events):
    b = F.build_matrix(real_events, features=["lat", "lon", "deaths_total"], sample_size=500)
    assert b["config"]["excluded"]["missing_coordinates"] == int((~real_events["has_coordinates"]).sum())
    assert b["frame"]["has_coordinates"].all()


def test_scalers_and_imputation_recorded(real_events):
    b = F.build_matrix(real_events, features=["magnitude", "deaths_total", "event_type"], scaler="robust", impute="median", sample_size=500)
    assert b["config"]["scaler"] == "robust" and "magnitude" in b["config"]["imputed"]
    assert not np.isnan(b["X"]).any()


def test_all_empty_feature_does_not_crash(real_events):
    b = F.build_matrix(real_events, features=["magnitude", "deaths_total"], event_types=["Tornado"], sample_size=300)
    assert not np.isnan(b["X"]).any()


def test_bad_feature_inputs(real_events):
    with pytest.raises(ValueError):
        F.build_matrix(real_events, features=["nope"])
    with pytest.raises(ValueError):
        F.build_matrix(real_events, scaler="bogus")
    with pytest.raises(ValueError):
        F.build_matrix(real_events, event_types=["Not A Type"])


# ---- profiles --------------------------------------------------------------------------
def test_profiles_use_real_statistics(real_events):
    b = F.build_matrix(real_events, sample_size=1500)
    labels = C.run_hierarchical(b["X"], 5)["labels"]
    profs = P.build_profiles(b["frame"], labels)
    assert sum(p["event_count"] for p in profs) == len(b["frame"])
    p0 = profs[0]
    assert str(p0["event_count"]) in p0["explanation"] or f"{p0['event_count']:,}" in p0["explanation"]
    assert "not a prediction" in p0["explanation"]
    g = b["frame"][labels == p0["cluster_id"]]
    assert p0["totals"]["deaths"] == int(g["deaths_total"].sum())


# ---- anomaly ---------------------------------------------------------------------------
@pytest.mark.parametrize("method", ["isolation_forest", "statistical", "lof"])
def test_anomaly_methods(real_events, method):
    r = AN.run(real_events, method, contamination=0.01)
    assert r["anomalies_flagged"] > 0 and r["results"] and "not by itself dangerous" in r["caveat"]
    assert r["results"][0]["drivers"] and r["results"][0]["classification"]


def test_statistical_flags_a_small_fraction(real_events):
    r = AN.run(real_events, "statistical")
    assert r["anomalies_flagged"] / len(real_events) < 0.08


def test_anomaly_validation(real_events):
    with pytest.raises(ValueError):
        AN.run(real_events, "bogus")
    with pytest.raises(ValueError):
        AN.run(real_events, "isolation_forest", contamination=0.9)
