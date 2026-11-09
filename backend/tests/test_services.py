import json

import pandas as pd
import pytest
import requests

from app.core import security as S
from app.db import database as db
from app.services import analytics as A
from app.services import assistant as AS
from app.services import auth as AU
from app.services import datasets as DS
from app.services import experiments as E
from app.services import external as X
from app.services import operations as OP
from app.services import reports as R


# ---- analytics --------------------------------------------------------------------------
def test_temporal_and_caveats(real_events):
    t = A.temporal(real_events, "yearly")
    assert sum(r["events"] for r in t["series"]) == len(real_events) and "climate" in t["caveat"]
    assert A.temporal(real_events, "monthly")["missing_months"] is not None
    seasons = [r["season"] for r in A.temporal(real_events, "seasonal")["series"]]
    assert seasons == ["Winter", "Spring", "Summer", "Autumn"]


def test_trends_flag_partial_years(real_events):
    assert 2020 in A.trends(real_events)["partial_years"]


def test_geo_only_returns_events_with_coordinates(real_events):
    g = A.geo_events(real_events, state="Texas", limit=200)
    assert all(e["lat"] is not None for e in g["events"]) and g["returned"] <= 200 and g["with_coordinates"] <= g["matching_events"]


def test_hotspot_caveat(real_events):
    assert "not a prediction" in A.hotspots(real_events)["caveat"]


def test_impact_totals_consistent(real_events):
    s = A.impact_summary(real_events)
    assert s["deaths"] == int(real_events["deaths_total"].sum())
    by = A.impact_by(real_events, "event-type", top=100)["rows"]
    assert sum(r["deaths"] for r in by) == s["deaths"]


def test_severity_is_configurable_and_labelled(real_events):
    a = A.high_impact(real_events, top=3)
    b = A.high_impact(real_events, top=3, weights={"death_weight": 0, "injury_weight": 0})
    assert a["events"][0]["severity_score"] != b["events"][0]["severity_score"] and "not an official" in a["note"]


def test_similarity(real_events):
    eid = int(real_events[(real_events.event_type == "Hail") & real_events.has_coordinates].event_id.iloc[0])
    s = A.similar_events(real_events, eid, k=5)
    sims = [x["similarity"] for x in s["similar"]]
    assert len(sims) == 5 and sims == sorted(sims, reverse=True)
    assert all(x["event_type"] == "Hail" for x in s["similar"]) and eid not in [x["event_id"] for x in s["similar"]]
    with pytest.raises(KeyError):
        A.similar_events(real_events, -1)


def test_search_pagination_and_filters(real_events):
    r = A.search_events(real_events, state="Texas", event_type="Hail", page_size=5)
    assert len(r["rows"]) == 5 and r["total"] > 5
    assert all(x["event_type"] == "Hail" for x in r["rows"])
    assert A.search_events(real_events, page_size=9999)["page_size"] == 200


def test_multi_hazard_never_pairs_same_type_and_warns(real_events):
    r = A.multi_hazard(real_events, radius_km=25, window_hours=3)
    assert r["pairs"] and all(p["type_a"] != p["type_b"] for p in r["pairs"])
    assert all(p["hours_apart"] <= 3 for p in r["pairs"])
    assert "does not imply" in r["caveat"]


def test_nearby_handles_event_without_coordinates(real_events):
    eid = int(real_events[~real_events.has_coordinates].event_id.iloc[0])
    assert "no recorded coordinates" in A.nearby_events(real_events, eid)["note"]


# ---- assistant --------------------------------------------------------------------------
@pytest.mark.parametrize("q,intent", [("Which states have the highest number of flood events?", "top_states_events"),
                                      ("Which event types have the highest fatalities?", "top_types_deaths"),
                                      ("What seasonal pattern appears in tornado records?", "seasonal"),
                                      ("Show the yearly distribution of hail events", "yearly"),
                                      ("Compare Texas and Oklahoma", "compare_regions"),
                                      ("blah blah", "unknown")])
def test_assistant_intents(real_events, q, intent):
    r = AS.answer(q, real_events)
    assert r["intent"] == intent and r["source"] and "not live alerts" in r["note"]


def test_assistant_answers_match_data(real_events):
    r = AS.answer("How many tornado events are there?", real_events)
    assert f"{int((real_events.event_type == 'Tornado').sum()):,}" in r["answer"]


def test_assistant_never_answers_live_questions_from_history(real_events):
    r = AS.answer("is there a tornado warning right now?", real_events)
    assert "warning is active" not in r["answer"].lower() and "no active" not in r["answer"].lower()
    assert "not live alerts" in r["note"]


def test_assistant_input_limits(real_events):
    with pytest.raises(ValueError):
        AS.answer("", real_events)
    with pytest.raises(ValueError):
        AS.answer("x" * 501, real_events)


# ---- experiments & reports --------------------------------------------------------------
def test_experiment_roundtrip(tmp_app, con):
    out = E.run_experiment("dbscan", {"min_samples": 8}, {"sample_size": 800}, con=con, seed=11)
    got = E.get_experiment(con, out["experiment_id"])
    assert got["seed"] == 11 and got["config"]["features"] and got["params"]["min_samples"] == 8 and got["dataset_version"]
    assert got["noise_count"] == got["metrics"]["noise_count"] and got["profiles"]
    assert len(E.get_assignments(con, got["id"])) == got["config"]["sample_size"]


def test_experiment_compare_flags_degenerate(tmp_app, con):
    a = E.run_experiment("hierarchical", {"n_clusters": 5}, {"sample_size": 600}, con=con)
    b = E.run_experiment("hierarchical", {"n_clusters": 5, "linkage": "single"}, {"sample_size": 600}, con=con)
    c = E.compare_experiments(con, [a["experiment_id"], b["experiment_id"]])
    assert len(c["experiments"]) == 2 and any("one cluster" in x for x in c["caveats"])
    with pytest.raises(KeyError):
        E.compare_experiments(con, [999])


def test_experiment_rejects_bad_algorithm(tmp_app, con):
    with pytest.raises(ValueError):
        E.run_experiment("kmeans", {}, con=con)


def test_reports(real_events):
    man = {"dataset_version": "t", "date_range": ["2017-02-08 00:00:00", "2020-09-30 00:00:00"]}
    pdf = R.build_pdf("T", real_events, man, None, {"state": "Texas"})
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000
    csv_bytes = R.build_csv(real_events, {"event_type": "Tornado"})
    assert csv_bytes.startswith(b"# Source") and b"Tornado" in csv_bytes


# ---- auth & security --------------------------------------------------------------------
def test_password_hash_and_verify():
    h = S.hash_password("Storm1234")
    assert h != "Storm1234" and S.verify_password("Storm1234", h) and not S.verify_password("nope", h)


def test_register_login_flow(con):
    u = AU.register(con, "A@B.co", "Ann", "Storm1234")
    assert u["role"] == "citizen" and "password_hash" not in u
    tok = AU.login(con, "a@b.co", "Storm1234")["access_token"]
    assert AU.user_from_token(con, tok)["email"] == "a@b.co"


def test_cannot_self_register_privileged_role(con):
    with pytest.raises(AU.Forbidden):
        AU.register(con, "x@y.co", "Eve", "Storm1234", role="administrator")


def test_weak_password_and_duplicate_email(con):
    with pytest.raises(ValueError):
        AU.register(con, "a@b.co", "Ann", "short")
    AU.register(con, "a@b.co", "Ann", "Storm1234")
    with pytest.raises(ValueError):
        AU.register(con, "a@b.co", "Ann", "Storm1234")


def test_login_errors_do_not_reveal_which_part_failed(con):
    AU.register(con, "a@b.co", "Ann", "Storm1234")
    msgs = set()
    for e, p in (("a@b.co", "wrong"), ("nobody@b.co", "Storm1234")):
        with pytest.raises(AU.AuthError) as ex:
            AU.login(con, e, p)
        msgs.add(str(ex.value))
    assert len(msgs) == 1


def test_invalid_and_tampered_tokens_rejected(con):
    for t in ("garbage", S.create_token(1, "citizen") + "x"):
        with pytest.raises(AU.AuthError):
            AU.user_from_token(con, t)


def test_role_comes_from_database_not_token(con):
    u = AU.register(con, "a@b.co", "Ann", "Storm1234")
    forged = S.create_token(u["id"], "administrator")
    assert AU.user_from_token(con, forged)["role"] == "citizen"


def test_permission_matrix():
    assert not S.has_permission("citizen", "manage_resources") and not S.has_permission("citizen", "view_all_incidents")
    assert S.has_permission("coordinator", "review_incidents") and not S.has_permission("coordinator", "admin")
    assert S.has_permission("researcher", "run_experiments") and not S.has_permission("researcher", "review_incidents")
    with pytest.raises(AU.Forbidden):
        AU.require({"role": "citizen"}, "admin")


def test_admin_can_create_privileged_user(con):
    admin = {"id": 1, "role": "administrator"}
    u = AU.create_privileged_user(con, admin, "c@d.co", "Coord", "Storm1234", "coordinator")
    assert u["role"] == "coordinator"
    with pytest.raises(AU.Forbidden):
        AU.create_privileged_user(con, {"id": 2, "role": "citizen"}, "e@f.co", "Eve", "Storm1234", "coordinator")


# ---- uploads ----------------------------------------------------------------------------
def test_upload_ok_and_profiled(con):
    csv = b"EVENT_ID,EVENT_TYPE,BEGIN_LAT,BEGIN_LON\n1,Hail,30,-97\n2,Flood,,\n"
    r = DS.save_upload(con, 1, "../../etc/my data.csv", csv)
    assert r["rows"] == 2 and "/" not in r["filename"] and DS.get_quality(con, r["id"])["rows"] == 2


@pytest.mark.parametrize("name,data", [("x.exe", b"a,b\n1,2\n"), ("x.csv", b""), ("x.csv", b"\x00\x01\x02" * 100), ("x.csv", b"onlyonecolumn\n1\n2\n")])
def test_upload_rejections(con, name, data):
    with pytest.raises(DS.UploadError):
        DS.save_upload(con, 1, name, data)


def test_upload_size_limit(con, monkeypatch):
    monkeypatch.setattr(DS.config, "MAX_UPLOAD_MB", 0)
    with pytest.raises(DS.UploadError, match="limit"):
        DS.save_upload(con, 1, "x.csv", b"a,b\n1,2\n")


# ---- incidents --------------------------------------------------------------------------
def _user(con, email, role="citizen"):
    u = AU.register(con, email, "User", "Storm1234")
    con.execute("UPDATE users SET role=? WHERE id=?", (role, u["id"]))
    return {"id": u["id"], "role": role}


def test_incident_is_unverified_and_labelled(con):
    u = _user(con, "c@x.co")
    i = OP.create_incident(con, u["id"], "flooded_road", "Road is under water near the bridge", 30.0, -97.0)
    assert i["verification"] == "unverified" and i["status"] == "submitted" and "Not an official" in i["notice"]


def test_incident_validation(con):
    u = _user(con, "c@x.co")
    for kw in ({"category": "nope", "description": "long enough text"}, {"category": "fallen_tree", "description": "short"},
               {"category": "fallen_tree", "description": "long enough text", "lat": 200.0, "lon": 0.0},
               {"category": "fallen_tree", "description": "long enough text", "lat": 10.0}):
        with pytest.raises(OP.Invalid):
            OP.create_incident(con, u["id"], **kw)


def test_incident_spam_controls(con):
    u = _user(con, "c@x.co")
    OP.create_incident(con, u["id"], "fallen_tree", "A tree fell across the road")
    with pytest.raises(OP.Invalid, match="identical"):
        OP.create_incident(con, u["id"], "fallen_tree", "A tree fell across the road")
    for i in range(OP.RATE_LIMIT_PER_HOUR - 1):
        OP.create_incident(con, u["id"], "fallen_tree", f"Distinct report number {i} here")
    with pytest.raises(OP.Invalid, match="Rate limit"):
        OP.create_incident(con, u["id"], "fallen_tree", "One more distinct report please")


def test_citizens_only_see_their_own_reports(con):
    a, b = _user(con, "a@x.co"), _user(con, "b@x.co")
    coord = _user(con, "z@x.co", "coordinator")
    OP.create_incident(con, a["id"], "blocked_road", "Road blocked by debris near mall")
    OP.create_incident(con, b["id"], "power_outage", "Power is out on the whole street")
    assert len(OP.list_incidents(con, a)) == 1 and OP.list_incidents(con, a)[0]["reporter_id"] == a["id"]
    assert len(OP.list_incidents(con, coord)) == 2


def test_review_changes_verification_and_is_audited(con):
    a, coord = _user(con, "a@x.co"), _user(con, "z@x.co", "coordinator")
    i = OP.create_incident(con, a["id"], "blocked_road", "Road blocked by debris near mall")
    r = OP.review_incident(con, i["id"], coord["id"], "under_review", "verified", "Confirmed by field team")
    assert r["verification"] == "verified" and r["notice"] is None
    assert db.one(con, "SELECT COUNT(*) n FROM audit_log WHERE action='incident_review'")["n"] == 1
    with pytest.raises(OP.Invalid):
        OP.review_incident(con, i["id"], coord["id"], "bogus", None, None)


def test_photo_validation(con, tmp_app):
    u = _user(con, "c@x.co")
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    i = OP.create_incident(con, u["id"], "fallen_tree", "Tree down across two lanes", photo_bytes=png)
    assert i["photo_path"].endswith(".png")
    with pytest.raises(OP.Invalid, match="JPEG or PNG"):
        OP.create_incident(con, u["id"], "fallen_tree", "Another tree down somewhere", photo_bytes=b"<?php evil ?>")


# ---- resources, assignments, tasks ------------------------------------------------------
def test_no_preloaded_resources(con):
    assert OP.list_resources(con) == []


def test_resource_lifecycle_and_availability(con):
    coord = _user(con, "z@x.co", "coordinator")
    r = OP.create_resource(con, coord["id"], "ambulance", "Unit 7", 3)
    a = OP.propose_assignment(con, coord["id"], r["id"], 2)
    assert a["status"] == "proposed" and OP.list_resources(con)[0]["available"] == 3  # proposing does not reserve
    OP.set_assignment_status(con, coord["id"], a["id"], "approved")
    assert OP.list_resources(con)[0]["available"] == 1
    OP.set_assignment_status(con, coord["id"], a["id"], "completed")
    assert OP.list_resources(con)[0]["available"] == 3
    with pytest.raises(OP.Invalid):
        OP.propose_assignment(con, coord["id"], r["id"], 99)


def test_resource_validation(con):
    coord = _user(con, "z@x.co", "coordinator")
    with pytest.raises(OP.Invalid):
        OP.create_resource(con, coord["id"], "tank", "X", 1)
    r = OP.create_resource(con, coord["id"], "rescue_team", "Team A", 2)
    with pytest.raises(OP.Invalid):
        OP.update_resource(con, coord["id"], r["id"], {"available": 5})


def test_responder_can_only_update_own_tasks(con):
    coord, resp, other = _user(con, "z@x.co", "coordinator"), _user(con, "r@x.co", "responder"), _user(con, "o@x.co", "responder")
    t = OP.create_task(con, coord["id"], "Clear Main St", None, assignee_id=resp["id"])
    assert OP.update_task_status(con, resp, t["id"], "in_progress")["status"] == "in_progress"
    with pytest.raises(PermissionError):
        OP.update_task_status(con, other, t["id"], "done")


def test_coordination_overview_counts_real_records(con):
    a, coord = _user(con, "a@x.co"), _user(con, "z@x.co", "coordinator")
    OP.create_incident(con, a["id"], "blocked_road", "Road blocked by debris near mall", 30, -97)
    o = OP.coordination_overview(con)
    assert o["incidents"][0]["n"] == 1 and len(o["open_incident_locations"]) == 1 and o["resources"] == []


# ---- external services (mocked HTTP: never invented, never silent) -----------------------
class FakeResp:
    def __init__(self, data, status=200): self.data, self.status = data, status
    def raise_for_status(self):
        if self.status >= 400: raise requests.HTTPError(str(self.status))
    def json(self): return self.data


class FakeSession:
    def __init__(self, resp=None, exc=None): self.resp, self.exc, self.headers = resp, exc, {}
    def get(self, *a, **k):
        if self.exc: raise self.exc
        return self.resp
    def close(self): pass


NWS = {"features": [{"id": "x1", "geometry": None, "properties": {"id": "x1", "event": "Flood Warning", "severity": "Severe", "urgency": "Immediate",
                                                                    "areaDesc": "Travis", "sent": "2020-01-01T00:00:00Z", "expires": "2020-01-01T06:00:00Z",
                                                                    "@id": "https://api.weather.gov/alerts/x1", "senderName": "NWS Austin"}},
                     {"id": "x2", "geometry": None, "properties": {"id": "x2", "event": "Heat Advisory", "severity": "Minor", "areaDesc": "Bexar"}}]}


def test_alerts_normalised_filtered_and_labelled(tmp_app):
    r = X.fetch_alerts(client=FakeSession(FakeResp(NWS)))
    assert r["count"] == 2 and r["alerts"][0]["source_url"] and "not produced by StormSense" in r["disclaimer"] and r["fetched_at"]
    r2 = X.fetch_alerts(severity="severe", client=FakeSession(FakeResp(NWS)))
    assert r2["count"] == 1


def test_alert_failure_uses_labelled_stale_cache_never_invents(tmp_app):
    X.fetch_alerts(client=FakeSession(FakeResp(NWS)))
    r = X.fetch_alerts(client=FakeSession(exc=requests.ConnectionError("down")))
    assert r["stale"] is True and "failed" in r["error"] and r["count"] == 2


def test_alert_failure_without_cache_raises(tmp_app):
    with pytest.raises(X.UpstreamError):
        X.fetch_alerts(client=FakeSession(exc=requests.Timeout("slow")))


def test_alert_state_validation():
    with pytest.raises(ValueError):
        X.fetch_alerts("Texas")


OSRM = {"code": "Ok", "routes": [{"distance": 12345, "duration": 900, "geometry": {"type": "LineString", "coordinates": [[-97, 30], [-97.1, 30.1]]},
                                   "legs": [{"steps": [{"distance": 100, "name": "Main St", "maneuver": {"type": "turn", "modifier": "left"}}]}]}]}


def test_routes_parse_and_disclaim():
    r = X.fetch_routes((30, -97), (30.1, -97.1), client=FakeSession(FakeResp(OSRM)))
    assert r["routes"][0]["distance_km"] == 12.35 and r["routes"][0]["duration_min"] == 15.0
    assert "do not guarantee safety" in r["disclaimer"] and r["routes"][0]["steps"][0]["instruction"]


def test_routes_errors():
    with pytest.raises(X.UpstreamError):
        X.fetch_routes((30, -97), (30.1, -97.1), client=FakeSession(exc=requests.Timeout()))
    with pytest.raises(X.UpstreamError):
        X.fetch_routes((30, -97), (30.1, -97.1), client=FakeSession(FakeResp({"code": "NoRoute"})))
    with pytest.raises(ValueError):
        X.fetch_routes((95, 0), (0, 0))
