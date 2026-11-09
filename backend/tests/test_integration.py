"""End-to-end workflow on the project's real data: upload -> quality -> processing manifest -> hierarchical + DBSCAN
experiments -> comparison -> explanations -> geography/impact by cluster -> assistant -> PDF/CSV report saved to history."""
import pandas as pd

from app.db import database as db
from app.services import analytics as A
from app.services import assistant as AS
from app.services import datasets as DS
from app.services import experiments as E
from app.services import processing, reports as R


def test_full_workflow(tmp_app, con, real_events):
    # 1. a user uploads a CSV and gets a quality report
    up = DS.save_upload(con, 1, "mine.csv", b"EVENT_ID,EVENT_TYPE,BEGIN_LAT,BEGIN_LON\n1,Hail,30,-97\n2,Flood,,\n")
    assert DS.get_quality(con, up["id"])["rows"] == 2

    # 2. the processed project dataset is versioned and documents its issues
    manifest = processing.load_manifest()
    assert manifest["unique_events"] == len(real_events) and manifest["issues"]

    # 3. both required algorithms run on the SAME sample/features, are saved, and are comparable
    feats = {"sample_size": 1500}
    h = E.run_experiment("hierarchical", {"n_clusters": 5, "linkage": "ward"}, feats, con=con, seed=3)
    d = E.run_experiment("dbscan", {"min_samples": 10}, feats, con=con, seed=3, with_stability=True)
    cmp = E.compare_experiments(con, [h["experiment_id"], d["experiment_id"]])
    assert [r["algorithm"] for r in cmp["experiments"]] == ["hierarchical", "dbscan"]
    assert cmp["experiments"][0]["sample_size"] == cmp["experiments"][1]["sample_size"]
    assert cmp["experiments"][1]["stability_ari"] is not None

    # 4. reproducibility: same seed + config gives identical assignments
    h2 = E.run_experiment("hierarchical", {"n_clusters": 5, "linkage": "ward"}, feats, con=con, seed=3)
    a1 = {x["event_id"]: x["cluster"] for x in E.get_assignments(con, h["experiment_id"])}
    a2 = {x["event_id"]: x["cluster"] for x in E.get_assignments(con, h2["experiment_id"])}
    assert a1 == a2

    # 5. cluster explanations exist for every cluster and cite real counts
    exp = E.get_experiment(con, h["experiment_id"])
    assert sum(p["event_count"] for p in exp["profiles"]) == exp["config"]["sample_size"]
    assert all("not a prediction" in p["explanation"] for p in exp["profiles"])

    # 6. cluster-level geography and impact are consistent with the assignments
    asg = pd.DataFrame(E.get_assignments(con, h["experiment_id"], limit=30000))
    geo = A.cluster_geography(asg, real_events)
    assert len(geo["points"]) + geo["unmapped_events"] == len(asg)
    imp = A.impact_by_cluster(asg, real_events)
    assert sum(r["events"] for r in imp["rows"]) == len(asg)

    # 7. the assistant answers a cluster question from the saved experiment
    ans = AS.answer("Which clusters have the highest property damage?", real_events, exp)
    assert ans["intent"] == "cluster_impact" and ans["table"]

    # 8. reports are generated and kept in history
    pdf = R.build_pdf("Integration report", real_events, manifest, exp, {"event_type": "Tornado"})
    meta = R.save_report(con, 1, "Integration report", "historical_summary", "pdf", {}, pdf)
    csv_meta = R.save_report(con, 1, "Data", "historical_summary", "csv", {}, R.build_csv(real_events, {"state": "Texas"}))
    rows = db.rows(con, "SELECT id,format FROM reports ORDER BY id")
    assert [r["format"] for r in rows] == ["pdf", "csv"] and meta["id"] != csv_meta["id"]
