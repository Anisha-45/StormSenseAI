"""Versioned REST API (/api/v1). Thin layer: validation, authentication/authorisation and HTTP error mapping.
All logic lives in app/services and app/ml, which are unit tested independently of the web framework."""
from __future__ import annotations

import json
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from ..core import config
from ..db import database as db
from ..ml import anomaly as AN
from ..ml import clustering as C
from ..ml import features as F
from ..services import analytics as A
from ..services import assistant as AS
from ..services import auth as AU
from ..services import datasets as DS
from ..services import experiments as E
from ..services import external as X
from ..services import operations as OP
from ..services import processing as PR
from ..services import quality as Q
from ..services import reports as R

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------ dependencies
def get_con():
    con = db.connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), con=Depends(get_con)) -> dict:
    if cred is None:
        raise HTTPException(401, "Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        return AU.user_from_token(con, cred.credentials)
    except AU.AuthError as e:
        raise HTTPException(401, str(e), headers={"WWW-Authenticate": "Bearer"})


def needs(permission: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        try:
            AU.require(user, permission)
        except AU.Forbidden as e:
            raise HTTPException(403, str(e))
        return user
    return dep


def events_df() -> pd.DataFrame:
    try:
        return E.get_events()[0]
    except FileNotFoundError:
        raise HTTPException(503, "The dataset has not been processed yet. Run POST /api/v1/processing/run or `python -m app.cli process`.")


def _bad(e: Exception, code: int = 400):
    raise HTTPException(code, str(e))


# ------------------------------------------------------------------ schemas
class RegisterIn(BaseModel):
    email: str
    name: str
    password: str
    role: Literal["citizen", "researcher"] = "citizen"


class LoginIn(BaseModel):
    email: str
    password: str


class AdminUserIn(RegisterIn):
    role: Literal["administrator", "coordinator", "responder", "researcher", "citizen"] = "citizen"


class FeatureConfig(BaseModel):
    features: list[str] = Field(default_factory=lambda: list(F.DEFAULT_FEATURES))
    sample_size: int = Field(5000, ge=200, le=30000)
    scaler: Literal["standard", "robust", "minmax"] = "standard"
    impute: Literal["median", "zero"] = "median"
    event_types: Optional[list[str]] = None
    years: Optional[list[int]] = None


class HierarchicalIn(BaseModel):
    n_clusters: int = Field(6, ge=2, le=50)
    linkage: Literal["ward", "complete", "average", "single"] = "ward"
    metric: Literal["euclidean", "manhattan", "chebyshev", "cosine"] = "euclidean"
    seed: int = 42
    with_stability: bool = False
    feature_config: FeatureConfig = FeatureConfig()


class DbscanIn(BaseModel):
    eps: Optional[float] = Field(None, gt=0, description="Omit to use the k-distance knee suggestion")
    min_samples: int = Field(10, ge=1, le=500)
    metric: Literal["euclidean", "manhattan", "chebyshev", "cosine"] = "euclidean"
    seed: int = 42
    with_stability: bool = False
    feature_config: FeatureConfig = FeatureConfig()


class HdbscanIn(BaseModel):
    min_cluster_size: int = Field(20, ge=2, le=1000)
    seed: int = 42
    with_stability: bool = False
    feature_config: FeatureConfig = FeatureConfig()


class SensitivityIn(BaseModel):
    eps_values: list[float] = Field(min_length=1, max_length=12)
    min_samples_values: list[int] = Field(min_length=1, max_length=6)
    metric: Literal["euclidean", "manhattan", "chebyshev", "cosine"] = "euclidean"
    feature_config: FeatureConfig = FeatureConfig(sample_size=3000)


class AnomalyIn(BaseModel):
    method: Literal["isolation_forest", "lof", "statistical"] = "isolation_forest"
    features: Optional[list[str]] = None
    contamination: float = Field(0.01, gt=0, lt=0.5)
    z_threshold: float = Field(3.0, gt=0)
    seed: int = 42
    top: int = Field(100, ge=1, le=500)


class IncidentStatusIn(BaseModel):
    status: Optional[str] = None
    verification: Optional[str] = None
    note: Optional[str] = None


class ResourceIn(BaseModel):
    kind: str
    name: str
    quantity: int = Field(1, ge=0)
    lat: Optional[float] = None
    lon: Optional[float] = None
    notes: Optional[str] = None


class ResourcePatch(BaseModel):
    name: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    available: Optional[int] = Field(None, ge=0)
    lat: Optional[float] = None
    lon: Optional[float] = None
    notes: Optional[str] = None


class AssignmentIn(BaseModel):
    resource_id: int
    quantity: int = Field(1, ge=1)
    incident_id: Optional[int] = None
    task_id: Optional[int] = None


class StatusIn(BaseModel):
    status: str


class TaskIn(BaseModel):
    title: str
    description: Optional[str] = None
    incident_id: Optional[int] = None
    assignee_id: Optional[int] = None


class ReportIn(BaseModel):
    title: str = "StormSense AI historical weather report"
    format: Literal["pdf", "csv"] = "pdf"
    experiment_id: Optional[int] = None
    state: Optional[str] = None
    event_type: Optional[str] = None
    year: Optional[int] = None


class AssistantIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    experiment_id: Optional[int] = None


# ------------------------------------------------------------------ health
@router.get("/health", tags=["system"])
def health():
    return {"status": "ok", "dataset_processed": _processed_exists()}


def _processed_exists() -> bool:
    try:
        PR.load_manifest()
        return True
    except FileNotFoundError:
        return False


# ------------------------------------------------------------------ auth
@router.post("/auth/register", status_code=201, tags=["auth"])
def register(body: RegisterIn, con=Depends(get_con)):
    try:
        return AU.register(con, body.email, body.name, body.password, body.role)
    except AU.Forbidden as e:
        _bad(e, 403)
    except ValueError as e:
        _bad(e, 400)


@router.post("/auth/login", tags=["auth"])
def login(body: LoginIn, con=Depends(get_con)):
    try:
        return AU.login(con, body.email, body.password)
    except AU.AuthError as e:
        raise HTTPException(401, str(e))


@router.get("/auth/profile", tags=["auth"])
def profile(user: dict = Depends(current_user)):
    return user


@router.post("/auth/users", status_code=201, tags=["auth"])
def admin_create_user(body: AdminUserIn, admin: dict = Depends(needs("admin")), con=Depends(get_con)):
    try:
        return AU.create_privileged_user(con, admin, body.email, body.name, body.password, body.role)
    except ValueError as e:
        _bad(e)


# ------------------------------------------------------------------ datasets & processing
@router.post("/datasets/upload", status_code=201, tags=["datasets"])
async def upload_dataset(file: UploadFile = File(...), name: Optional[str] = Form(None), user: dict = Depends(needs("upload_data")),
                         con=Depends(get_con)):
    data = await file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    try:
        return DS.save_upload(con, user["id"], file.filename or "upload.csv", data, name)
    except DS.UploadError as e:
        _bad(e, 400)


@router.get("/datasets", tags=["datasets"])
def list_datasets(con=Depends(get_con)):
    builtin = None
    try:
        m = PR.load_manifest()
        builtin = {"id": "builtin", "name": "NOAA Storm Events (project dataset)", "rows": m["unique_events"], "dataset_version": m["dataset_version"],
                   "date_range": m["date_range"], "raw_row_counts": m["raw_row_counts"]}
    except FileNotFoundError:
        pass
    return {"builtin": builtin, "uploads": DS.list_datasets(con)}


@router.get("/datasets/{dataset_id}", tags=["datasets"])
def get_dataset(dataset_id: str, con=Depends(get_con)):
    if dataset_id == "builtin":
        try:
            return PR.load_manifest()
        except FileNotFoundError:
            raise HTTPException(404, "Built-in dataset not processed yet.")
    if not dataset_id.isdigit():
        raise HTTPException(404, "Dataset not found")
    d = DS.get_dataset(con, int(dataset_id))
    if not d:
        raise HTTPException(404, "Dataset not found")
    return d


@router.get("/datasets/{dataset_id}/quality", tags=["datasets"])
def dataset_quality(dataset_id: str, table: Literal["details", "locations", "fatalities"] = "details", con=Depends(get_con)):
    if dataset_id == "builtin":
        cache = config.PROCESSED_DIR / f"quality_{table}.json"
        if cache.exists():
            return json.loads(cache.read_text())
        fname = {"details": config.DETAILS_FILE, "locations": config.LOCATIONS_FILE, "fatalities": config.FATALITIES_FILE}[table]
        path = config.RAW_DIR / fname
        if not path.exists():
            raise HTTPException(404, f"{fname} not found in {config.RAW_DIR}")
        rep = Q.profile_csv(path, source=fname)
        cache.write_text(db.dumps(rep))
        return rep
    q = DS.get_quality(con, int(dataset_id)) if dataset_id.isdigit() else None
    if q is None:
        raise HTTPException(404, "Dataset not found")
    return q


@router.post("/processing/run", tags=["processing"])
def run_processing(overrides: Optional[dict] = None, user: dict = Depends(needs("upload_data"))):
    try:
        m = PR.process(config_overrides=overrides)
    except FileNotFoundError as e:
        _bad(e, 404)
    E.clear_cache()
    return m


@router.get("/processing/{processing_id}", tags=["processing"])
def get_processing(processing_id: str):
    try:
        m = PR.load_manifest()
    except FileNotFoundError:
        raise HTTPException(404, "No processing run exists yet.")
    if processing_id not in ("latest", m["dataset_version"]):
        raise HTTPException(404, "Unknown processing id; use 'latest' or the dataset_version.")
    return {k: v for k, v in m.items() if k != "issues"}


@router.get("/processing/{processing_id}/report", tags=["processing"])
def processing_report(processing_id: str):
    try:
        m = PR.load_manifest()
    except FileNotFoundError:
        raise HTTPException(404, "No processing run exists yet.")
    return {"dataset_version": m["dataset_version"], "issues": m["issues"], "notes": m["notes"], "config": m["config"],
            "features_available": {"numeric": F.NUMERIC_FEATURES, "categorical": F.CATEGORICAL_FEATURES, "default": F.DEFAULT_FEATURES}}


# ------------------------------------------------------------------ clustering
def _run(algorithm: str, params: dict, fc: FeatureConfig, user: dict, con, with_stability: bool, seed: int):
    try:
        out = E.run_experiment(algorithm, params, fc.model_dump(), user["id"], con, with_stability, seed)
    except (ValueError, KeyError) as e:
        _bad(e, 400)
    except FileNotFoundError as e:
        _bad(e, 503)
    return {k: v for k, v in out.items()}


@router.post("/clustering/hierarchical", tags=["clustering"])
def hierarchical(body: HierarchicalIn, user: dict = Depends(needs("run_experiments")), con=Depends(get_con)):
    return _run("hierarchical", {"n_clusters": body.n_clusters, "linkage": body.linkage, "metric": body.metric}, body.feature_config, user, con,
                body.with_stability, body.seed)


@router.post("/clustering/dbscan", tags=["clustering"])
def dbscan(body: DbscanIn, user: dict = Depends(needs("run_experiments")), con=Depends(get_con)):
    params = {"min_samples": body.min_samples, "metric": body.metric}
    if body.eps:
        params["eps"] = body.eps
    return _run("dbscan", params, body.feature_config, user, con, body.with_stability, body.seed)


@router.post("/clustering/hdbscan", tags=["clustering"])
def hdbscan(body: HdbscanIn, user: dict = Depends(needs("run_experiments")), con=Depends(get_con)):
    return _run("hdbscan", {"min_cluster_size": body.min_cluster_size}, body.feature_config, user, con, body.with_stability, body.seed)


@router.get("/clustering/features", tags=["clustering"])
def clustering_features():
    return {"numeric": F.NUMERIC_FEATURES, "categorical": F.CATEGORICAL_FEATURES, "default": F.DEFAULT_FEATURES,
            "linkages": C.LINKAGES, "metrics": C.METRICS, "max_hierarchical_rows": config.MAX_HIERARCHICAL_ROWS}


@router.post("/clustering/linkage-comparison", tags=["clustering"])
def linkage_comparison(n_clusters: int = Query(6, ge=2, le=30), fc: FeatureConfig = FeatureConfig(sample_size=3000), user: dict = Depends(needs("run_experiments"))):
    events = events_df()
    try:
        b = F.build_matrix(events, **fc.model_dump())
        rows = C.hierarchical_linkage_comparison(b["X"], n_clusters)
    except ValueError as e:
        _bad(e)
    for r in rows:
        r["largest_cluster_share_pct"] = round(max(r["cluster_sizes"].values(), default=0) / len(b["X"]) * 100, 1)
    return {"rows": rows, "config": b["config"],
            "caveat": "A high Silhouette with one giant cluster (see largest_cluster_share_pct) is a degenerate solution, not a good one."}


@router.post("/clustering/dendrogram", tags=["clustering"])
def dendrogram(linkage: str = "ward", fc: FeatureConfig = FeatureConfig(sample_size=3000), user: dict = Depends(needs("run_experiments"))):
    events = events_df()
    if linkage not in C.LINKAGES:
        _bad(ValueError(f"linkage must be one of {C.LINKAGES}"))
    try:
        b = F.build_matrix(events, **fc.model_dump())
    except ValueError as e:
        _bad(e)
    return C.dendrogram_data(b["X"], linkage)


@router.post("/clustering/dbscan/k-distance", tags=["clustering"])
def k_distance(k: int = Query(10, ge=2, le=200), fc: FeatureConfig = FeatureConfig(sample_size=3000), user: dict = Depends(needs("run_experiments"))):
    events = events_df()
    try:
        b = F.build_matrix(events, **fc.model_dump())
    except ValueError as e:
        _bad(e)
    kd = C.k_distance(b["X"], k)
    step = max(1, len(kd) // 400)
    return {"k": k, "k_distances": kd[::step], "suggested_eps": C.suggest_eps(kd), "rows": len(kd)}


@router.post("/clustering/dbscan/sensitivity", tags=["clustering"])
def dbscan_sensitivity(body: SensitivityIn, user: dict = Depends(needs("run_experiments"))):
    events = events_df()
    try:
        b = F.build_matrix(events, **body.feature_config.model_dump())
        grid = C.dbscan_sensitivity(b["X"], body.eps_values, body.min_samples_values, body.metric)
    except ValueError as e:
        _bad(e)
    return {"grid": grid, "config": b["config"]}


@router.get("/clustering/experiments", tags=["clustering"])
def experiments(con=Depends(get_con)):
    return E.list_experiments(con)


@router.get("/clustering/compare", tags=["clustering"])
def compare(ids: str = Query(..., description="Comma-separated experiment ids"), con=Depends(get_con)):
    try:
        return E.compare_experiments(con, [int(i) for i in ids.split(",") if i.strip()])
    except (KeyError, ValueError) as e:
        _bad(e, 404 if isinstance(e, KeyError) else 400)


@router.get("/clustering/{experiment_id}", tags=["clustering"])
def experiment(experiment_id: int, con=Depends(get_con)):
    e = E.get_experiment(con, experiment_id)
    if not e:
        raise HTTPException(404, "Experiment not found")
    return e


@router.get("/clustering/{experiment_id}/assignments", tags=["clustering"])
def experiment_assignments(experiment_id: int, cluster: Optional[int] = None, limit: int = Query(5000, ge=1, le=30000), con=Depends(get_con)):
    if not E.get_experiment(con, experiment_id):
        raise HTTPException(404, "Experiment not found")
    return E.get_assignments(con, experiment_id, cluster, limit)


@router.get("/clustering/{experiment_id}/comparison", tags=["clustering"])
def experiment_comparison(experiment_id: int, con=Depends(get_con)):
    """Compare this experiment with every other experiment run on the same sample size."""
    base = E.get_experiment(con, experiment_id)
    if not base:
        raise HTTPException(404, "Experiment not found")
    ids = [r["id"] for r in E.list_experiments(con) if r["id"] != experiment_id][:5]
    return E.compare_experiments(con, [experiment_id] + ids)


# ------------------------------------------------------------------ cluster intelligence
@router.get("/clusters/{cluster_id}/profile", tags=["clusters"])
def cluster_profile(cluster_id: int, experiment_id: int = Query(...), con=Depends(get_con)):
    r = db.one(con, "SELECT profile_json FROM cluster_profiles WHERE experiment_id=? AND cluster_id=?", (experiment_id, cluster_id))
    if not r:
        raise HTTPException(404, "Cluster profile not found")
    return json.loads(r["profile_json"])


@router.get("/clusters/{cluster_id}/events", tags=["clusters"])
def cluster_events(cluster_id: int, experiment_id: int = Query(...), limit: int = Query(200, ge=1, le=2000), con=Depends(get_con)):
    a = E.get_assignments(con, experiment_id, cluster_id, limit)
    ids = [x["event_id"] for x in a]
    df = events_df()
    rows = df[df["event_id"].isin(ids)][["event_id", "event_type", "state", "begin_dt", "deaths_total", "injuries_total", "property_damage_usd"]]
    return {"cluster_id": cluster_id, "experiment_id": experiment_id, "events": A._clean(rows.to_dict("records"))}


# ------------------------------------------------------------------ analytics
@router.get("/overview", tags=["overview"])
def overview(con=Depends(get_con)):
    df = events_df()
    return A.overview(df, E.get_events()[1], E.list_experiments(con))


@router.get("/geography/events", tags=["geography"])
def geo_events(state: Optional[str] = None, event_type: Optional[str] = None, year: Optional[int] = None, limit: int = Query(3000, ge=1, le=10000)):
    return A.geo_events(events_df(), limit, state=state, event_type=event_type, year=year)


@router.get("/geography/hotspots", tags=["geography"])
def geo_hotspots(cell_deg: float = Query(1.0, ge=0.1, le=10), top: int = Query(25, ge=1, le=200), state: Optional[str] = None,
                 event_type: Optional[str] = None, year: Optional[int] = None):
    return A.hotspots(events_df(), cell_deg, top, state=state, event_type=event_type, year=year)


@router.get("/geography/regions", tags=["geography"])
def geo_regions(event_type: Optional[str] = None, year: Optional[int] = None):
    return A.regional_distribution(events_df(), event_type=event_type, year=year)


@router.get("/geography/clusters", tags=["geography"])
def geo_clusters(experiment_id: int = Query(...), con=Depends(get_con)):
    if not E.get_experiment(con, experiment_id):
        raise HTTPException(404, "Experiment not found")
    a = pd.DataFrame(E.get_assignments(con, experiment_id, limit=30000))
    return A.cluster_geography(a, events_df())


@router.get("/geography/filters", tags=["geography"])
def geo_filters():
    df = events_df()
    return {"states": sorted(df["state"].unique().tolist()), "event_types": sorted(df["event_type"].unique().tolist()),
            "years": sorted(df["year"].unique().tolist())}


@router.get("/temporal/yearly", tags=["temporal"])
def t_yearly(state: Optional[str] = None, event_type: Optional[str] = None):
    return A.temporal(events_df(), "yearly", state=state, event_type=event_type)


@router.get("/temporal/monthly", tags=["temporal"])
def t_monthly(state: Optional[str] = None, event_type: Optional[str] = None, year: Optional[int] = None):
    return A.temporal(events_df(), "monthly", state=state, event_type=event_type, year=year)


@router.get("/temporal/seasonal", tags=["temporal"])
def t_seasonal(state: Optional[str] = None, event_type: Optional[str] = None, year: Optional[int] = None):
    return A.temporal(events_df(), "seasonal", state=state, event_type=event_type, year=year)


@router.get("/temporal/trends", tags=["temporal"])
def t_trends(state: Optional[str] = None, event_type: Optional[str] = None):
    return A.trends(events_df(), state=state, event_type=event_type)


@router.post("/anomalies/run", tags=["anomalies"])
def anomalies_run(body: AnomalyIn, user: dict = Depends(needs("run_experiments")), con=Depends(get_con)):
    bad = [f for f in (body.features or []) if f not in AN.DEFAULT_FEATURES + ["month_sin", "month_cos"]]
    if bad:
        _bad(ValueError(f"Unsupported anomaly features: {bad}"))
    try:
        res = AN.run(events_df(), body.method, body.features, body.contamination, body.seed, body.top, body.z_threshold)
    except ValueError as e:
        _bad(e)
    summary = {k: res[k] for k in ("method", "features", "contamination", "rows_scored", "anomalies_flagged")}
    con.execute("INSERT INTO anomaly_runs(method,params_json,summary_json,results_json,created_at) VALUES(?,?,?,?,?)",
                (body.method, db.dumps(body.model_dump()), db.dumps(summary), db.dumps(res["results"]), db.now()))
    return res


@router.get("/anomalies/results", tags=["anomalies"])
def anomalies_results(run_id: Optional[int] = None, con=Depends(get_con)):
    r = db.one(con, "SELECT * FROM anomaly_runs WHERE id=?", (run_id,)) if run_id else db.one(con, "SELECT * FROM anomaly_runs ORDER BY id DESC LIMIT 1")
    if not r:
        raise HTTPException(404, "No anomaly run found. Run one first.")
    return {"run_id": r["id"], "created_at": r["created_at"], "params": json.loads(r["params_json"]),
            "summary": json.loads(r["summary_json"]), "results": json.loads(r["results_json"])}


@router.get("/events/search", tags=["events"])
def events_search(state: Optional[str] = None, event_type: Optional[str] = None, year: Optional[int] = None, season: Optional[str] = None,
                  event_id: Optional[int] = None, min_magnitude: Optional[float] = None, max_magnitude: Optional[float] = None,
                  min_deaths: Optional[int] = None, min_damage: Optional[float] = None, text: Optional[str] = None,
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    return A.search_events(events_df(), event_id, min_magnitude, max_magnitude, text, page, page_size, state=state, event_type=event_type,
                           year=year, season=season, min_deaths=min_deaths, min_damage=min_damage)


@router.get("/events/{event_id}", tags=["events"])
def event_record(event_id: int):
    try:
        return A.event_record(events_df(), event_id)
    except KeyError as e:
        _bad(e, 404)


@router.get("/events/{event_id}/similar", tags=["events"])
def event_similar(event_id: int, k: int = Query(10, ge=1, le=50), same_type: bool = True):
    try:
        return A.similar_events(events_df(), event_id, k, same_type)
    except KeyError as e:
        _bad(e, 404)


@router.get("/events/{event_id}/nearby", tags=["events"])
def event_nearby(event_id: int, radius_km: float = Query(50, gt=0, le=500), window_hours: float = Query(24, gt=0, le=720)):
    try:
        return A.nearby_events(events_df(), event_id, radius_km, window_hours)
    except KeyError as e:
        _bad(e, 404)


@router.get("/multi-hazard", tags=["multi-hazard"])
def multi_hazard(radius_km: float = Query(50, gt=0, le=500), window_hours: float = Query(24, gt=0, le=720), type_a: Optional[str] = None,
                 type_b: Optional[str] = None, state: Optional[str] = None, year: Optional[int] = None):
    return A.multi_hazard(events_df(), radius_km, window_hours, type_a, type_b, state=state, year=year)


@router.get("/impact/summary", tags=["impact"])
def impact_summary(state: Optional[str] = None, event_type: Optional[str] = None, year: Optional[int] = None):
    return A.impact_summary(events_df(), state=state, event_type=event_type, year=year)


@router.get("/impact/by-region", tags=["impact"])
def impact_region(event_type: Optional[str] = None, year: Optional[int] = None, top: int = Query(30, ge=1, le=100)):
    return A.impact_by(events_df(), "region", top, event_type=event_type, year=year)


@router.get("/impact/by-event-type", tags=["impact"])
def impact_type(state: Optional[str] = None, year: Optional[int] = None, top: int = Query(30, ge=1, le=100)):
    return A.impact_by(events_df(), "event-type", top, state=state, year=year)


@router.get("/impact/by-cluster", tags=["impact"])
def impact_cluster(experiment_id: int = Query(...), con=Depends(get_con)):
    if not E.get_experiment(con, experiment_id):
        raise HTTPException(404, "Experiment not found")
    return A.impact_by_cluster(pd.DataFrame(E.get_assignments(con, experiment_id, limit=30000)), events_df())


@router.get("/impact/high-impact", tags=["impact"])
def impact_high(top: int = Query(25, ge=1, le=200), death_weight: float = Query(10, ge=0), injury_weight: float = Query(3, ge=0),
                damage_per_point_usd: float = Query(1_000_000, gt=0), state: Optional[str] = None, event_type: Optional[str] = None,
                year: Optional[int] = None):
    return A.high_impact(events_df(), top, {"death_weight": death_weight, "injury_weight": injury_weight, "damage_per_point_usd": damage_per_point_usd},
                         state=state, event_type=event_type, year=year)


# ------------------------------------------------------------------ alerts & routes
@router.get("/alerts", tags=["alerts"])
def alerts(state: Optional[str] = Query(None, min_length=2, max_length=2), severity: Optional[str] = None, event: Optional[str] = None):
    try:
        return X.fetch_alerts(state, severity, event)
    except ValueError as e:
        _bad(e)
    except X.UpstreamError as e:
        raise HTTPException(502, str(e))


@router.get("/routes", tags=["routes"])
def routes(origin_lat: float = Query(..., ge=-90, le=90), origin_lon: float = Query(..., ge=-180, le=180),
           dest_lat: float = Query(..., ge=-90, le=90), dest_lon: float = Query(..., ge=-180, le=180), alternatives: bool = True):
    try:
        return X.fetch_routes((origin_lat, origin_lon), (dest_lat, dest_lon), alternatives)
    except ValueError as e:
        _bad(e)
    except X.UpstreamError as e:
        raise HTTPException(502, str(e))


# ------------------------------------------------------------------ incidents
@router.get("/incidents/categories", tags=["incidents"])
def incident_categories():
    return {"categories": OP.INCIDENT_CATEGORIES, "statuses": OP.INCIDENT_STATUSES, "verifications": OP.VERIFICATIONS, "notice": OP.UNVERIFIED_NOTICE}


@router.post("/incidents", status_code=201, tags=["incidents"])
async def create_incident(category: str = Form(...), description: str = Form(...), lat: Optional[float] = Form(None), lon: Optional[float] = Form(None),
                          photo: Optional[UploadFile] = File(None), user: dict = Depends(needs("report_incident")), con=Depends(get_con)):
    data = await photo.read(config.MAX_PHOTO_MB * 1024 * 1024 + 1) if photo else None
    try:
        return OP.create_incident(con, user["id"], category, description, lat, lon, data)
    except OP.Invalid as e:
        _bad(e, 429 if str(e).startswith("Rate limit") else 400)


@router.get("/incidents", tags=["incidents"])
def list_incidents(status: Optional[str] = None, verification: Optional[str] = None, user: dict = Depends(current_user), con=Depends(get_con)):
    return OP.list_incidents(con, user, status, verification)


@router.patch("/incidents/{incident_id}/status", tags=["incidents"])
def incident_status(incident_id: int, body: IncidentStatusIn, user: dict = Depends(needs("review_incidents")), con=Depends(get_con)):
    try:
        return OP.review_incident(con, incident_id, user["id"], body.status, body.verification, body.note)
    except KeyError as e:
        _bad(e, 404)
    except OP.Invalid as e:
        _bad(e)


# ------------------------------------------------------------------ resources, assignments, tasks
@router.get("/resources", tags=["resources"])
def list_resources(kind: Optional[str] = None, user: dict = Depends(needs("view_resources")), con=Depends(get_con)):
    return {"resources": OP.list_resources(con, kind),
            "notice": "Only resources entered by authorised staff appear here. Nothing is pre-loaded or simulated."}


@router.post("/resources", status_code=201, tags=["resources"])
def create_resource(body: ResourceIn, user: dict = Depends(needs("manage_resources")), con=Depends(get_con)):
    try:
        return OP.create_resource(con, user["id"], body.kind, body.name, body.quantity, body.lat, body.lon, body.notes)
    except OP.Invalid as e:
        _bad(e)


@router.patch("/resources/{resource_id}", tags=["resources"])
def patch_resource(resource_id: int, body: ResourcePatch, user: dict = Depends(needs("manage_resources")), con=Depends(get_con)):
    try:
        return OP.update_resource(con, user["id"], resource_id, body.model_dump(exclude_unset=True))
    except KeyError as e:
        _bad(e, 404)
    except OP.Invalid as e:
        _bad(e)


@router.get("/assignments", tags=["resources"])
def list_assignments(user: dict = Depends(needs("view_resources")), con=Depends(get_con)):
    return db.rows(con, "SELECT * FROM assignments ORDER BY id DESC LIMIT 500")


@router.post("/assignments", status_code=201, tags=["resources"])
def propose_assignment(body: AssignmentIn, user: dict = Depends(needs("manage_resources")), con=Depends(get_con)):
    try:
        return OP.propose_assignment(con, user["id"], body.resource_id, body.quantity, body.incident_id, body.task_id)
    except KeyError as e:
        _bad(e, 404)
    except OP.Invalid as e:
        _bad(e)


@router.patch("/assignments/{assignment_id}/status", tags=["resources"])
def assignment_status(assignment_id: int, body: StatusIn, user: dict = Depends(needs("manage_resources")), con=Depends(get_con)):
    try:
        return OP.set_assignment_status(con, user["id"], assignment_id, body.status)
    except KeyError as e:
        _bad(e, 404)
    except OP.Invalid as e:
        _bad(e)


@router.get("/tasks", tags=["tasks"])
def list_tasks(user: dict = Depends(needs("view_tasks")), con=Depends(get_con)):
    if AU.S.has_permission(user["role"], "manage_tasks"):
        return db.rows(con, "SELECT * FROM tasks ORDER BY id DESC LIMIT 500")
    return db.rows(con, "SELECT * FROM tasks WHERE assignee_id=? ORDER BY id DESC LIMIT 500", (user["id"],))


@router.post("/tasks", status_code=201, tags=["tasks"])
def create_task(body: TaskIn, user: dict = Depends(needs("manage_tasks")), con=Depends(get_con)):
    try:
        return OP.create_task(con, user["id"], body.title, body.description, body.incident_id, body.assignee_id)
    except OP.Invalid as e:
        _bad(e)


@router.patch("/tasks/{task_id}/status", tags=["tasks"])
def task_status(task_id: int, body: StatusIn, user: dict = Depends(needs("view_tasks")), con=Depends(get_con)):
    try:
        return OP.update_task_status(con, user, task_id, body.status)
    except KeyError as e:
        _bad(e, 404)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except OP.Invalid as e:
        _bad(e)


@router.get("/coordination/overview", tags=["coordination"])
def coordination(user: dict = Depends(needs("view_all_incidents")), con=Depends(get_con)):
    return OP.coordination_overview(con)


@router.get("/admin/audit-log", tags=["admin"])
def audit_log(limit: int = Query(100, ge=1, le=1000), user: dict = Depends(needs("admin")), con=Depends(get_con)):
    return db.rows(con, "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


@router.get("/admin/users", tags=["admin"])
def admin_users(user: dict = Depends(needs("admin")), con=Depends(get_con)):
    return db.rows(con, "SELECT id,email,name,role,active,created_at FROM users ORDER BY id")


# ------------------------------------------------------------------ reports & assistant
@router.post("/reports/generate", tags=["reports"])
def generate_report(body: ReportIn, user: dict = Depends(needs("generate_reports")), con=Depends(get_con)):
    df = events_df()
    manifest = E.get_events()[1]
    filters = {"state": body.state, "event_type": body.event_type, "year": body.year}
    if body.format == "csv":
        content = R.build_csv(df, filters)
    else:
        exp = E.get_experiment(con, body.experiment_id) if body.experiment_id else None
        if body.experiment_id and not exp:
            raise HTTPException(404, "Experiment not found")
        content = R.build_pdf(body.title, df, manifest, exp, filters)
    meta = R.save_report(con, user["id"], body.title, "historical_summary", body.format, body.model_dump(), content)
    db.audit(con, user["id"], "report_generate", f"report:{meta['id']}", body.format)
    return meta


@router.get("/reports", tags=["reports"])
def list_reports(user: dict = Depends(needs("generate_reports")), con=Depends(get_con)):
    return db.rows(con, "SELECT id,title,kind,format,created_at FROM reports WHERE created_by=? ORDER BY id DESC LIMIT 200", (user["id"],))


@router.get("/reports/{report_id}/download", tags=["reports"])
def download_report(report_id: int, user: dict = Depends(needs("generate_reports")), con=Depends(get_con)):
    r = db.one(con, "SELECT * FROM reports WHERE id=? AND created_by=?", (report_id, user["id"]))
    if not r:
        raise HTTPException(404, "Report not found")
    from pathlib import Path
    data = Path(r["file_path"]).read_bytes()
    media = "application/pdf" if r["format"] == "pdf" else "text/csv"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="stormsense_report_{r["id"]}.{r["format"]}"'})


@router.post("/assistant/query", tags=["assistant"])
def assistant_query(body: AssistantIn, con=Depends(get_con)):
    df = events_df()
    exp = None
    if body.experiment_id:
        exp = E.get_experiment(con, body.experiment_id)
    else:
        rows = E.list_experiments(con)
        exp = E.get_experiment(con, rows[0]["id"]) if rows else None
    try:
        return AS.answer(body.question, df, exp)
    except ValueError as e:
        _bad(e)
