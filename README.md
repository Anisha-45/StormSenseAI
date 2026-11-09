# StormSense AI

**Historical extreme-weather intelligence built on hierarchical and density-based clustering**
Smart India Hackathon · Problem ID SIH26078 · *Extreme Weather Event Grouping Through Hierarchical and Density-Based Clustering*

StormSense AI turns the NOAA Storm Events records you supplied into something people can explore: groups of similar events (Hierarchical Agglomerative Clustering and DBSCAN, with HDBSCAN as an extra), maps, seasonal views, impact comparisons, anomaly detection, similar-event search, a rule-based question assistant, reports, and a small operational layer (live NWS alerts, routes, citizen incident reports, resources, coordination).

> **Historical analysis is never a forecast or an official warning.** Clustering describes similarity between past records. Live alerts come only from the US National Weather Service and are kept on a separate page.

---

## 1. What is in the box

```
stormsense/
├── data/
│   ├── raw/          your 3 NOAA CSVs, never modified
│   └── processed/    events table + manifest.json (rebuilt by `python -m app.cli process`)
├── backend/          FastAPI + pandas/scikit-learn + SQLite
│   ├── app/api/      versioned REST API (/api/v1, 70+ routes)
│   ├── app/services/ data quality, processing, analytics, assistant, reports, auth, operations
│   ├── app/ml/       features + sampling, clustering, evaluation, profiles, anomaly detection
│   └── tests/        126 tests
├── frontend/         React + Vite + Tailwind + Recharts + Leaflet, 20 pages
├── docs/METHODOLOGY.md
├── docker-compose.yml
└── run-backend.bat / run-frontend.bat   (Windows 11 helpers)
```

## 2. Run it on Windows 11 (no Docker)

You need Python 3.10+ and Node 18+.

**Backend** (terminal 1)
```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.cli process                                  :: ~5 s, builds data/processed from data/raw
python -m app.cli create-admin you@example.com "Your Name" "YourPassw0rd"
uvicorn app.main:app --reload --port 8000
```
Interactive API docs: http://localhost:8000/docs

**Frontend** (terminal 2)
```bat
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Register as a *researcher* to run experiments, or sign in as the admin you created to use every page.

**With Docker:** `docker compose up --build` then open http://localhost:8080 (create the admin with `docker compose exec backend python -m app.cli create-admin ...`).

Optional environment variables are listed in `.env.example`. **Set `STORMSENSE_JWT_SECRET` to a long random value for anything other than local development.**

## 3. What the data actually contains (audit findings)

I profiled your files before building anything; these facts shaped the design:

| Finding | Consequence in the app |
|---|---|
| `StormEvents_details` has 32,671 unique events but spans **Feb 2017 – Sep 2020**, with 93.7% in 2020 (not 2010–2020) | Year-over-year and trend views carry explicit coverage warnings; nothing is presented as a climate trend |
| Only 20,975 of those events have location rows; 91.8% of the locations file belongs to events **not in details** | Locations are aggregated per event and joined only where they match; orphan rows are counted and logged, never joined |
| Only 232 of 5,100 fatality events exist in details; for those, fatality row count equals `DEATHS_DIRECT + DEATHS_INDIRECT` every time | Details is the source of truth for death totals; fatalities add age/sex only where available |
| 7,420 events (22.7%) have no coordinates, mostly forecast-zone types (heat, drought, winter storm…) | Kept in all non-spatial analysis; excluded from maps/spatial work and the exact count is always reported |
| Damage is missing for ~21–23% of events; only 1.2% of events have any casualty | Missing damage stays missing (flagged), never zero-filled; impact features are zero-inflated and handled accordingly |

All of this is visible in the app under **Data Quality** and **Data Processing Studio**.

## 4. SIH requirements → where they live

| Requirement | Implementation |
|---|---|
| Hierarchical clustering: Ward, complete, average, single; k; dendrogram; linkage comparison | `ml/clustering.py`, Clustering Lab |
| DBSCAN: eps, min_samples, metrics, noise, core/border, k-distance, sensitivity grid | same |
| HDBSCAN (extra, not a replacement) | same |
| Feature selection, imputation, one-hot encoding, scaling (standard/robust/min-max) | `ml/features.py` |
| PCA view, Silhouette, Davies-Bouldin, Calinski-Harabasz (noise excluded, validity-checked) | `evaluate()` |
| Stability under resampling (Adjusted Rand Index) | `stability()` |
| Cluster profiles + plain-English explanations from real statistics | `ml/profiles.py`, Cluster Intelligence |
| Representative sampling (not first-N) | `stratified_sample()` |
| Reproducible experiments (dataset version, features, preprocessing, algorithm, params, seed, metrics, time) | `services/experiments.py`, SQLite `experiments` table |
| Documented limitations and bias | Settings page, report PDFs, `docs/METHODOLOGY.md` |

### A snapshot of real results (5,000-event stratified sample, default features, seed 42)

| Method | Clusters | Noise | Silhouette | Davies-Bouldin | Largest cluster | Stability (ARI) | Time |
|---|---|---|---|---|---|---|---|
| Hierarchical, Ward, k=6 | 6 | – | 0.301 | 0.927 | 32% | 0.56 | 0.8 s |
| DBSCAN, auto eps = 1.73, min_samples = 10 | 4 | 1.7% | 0.396 | 0.797 | **96%** | 0.999 | 0.2 s |
| HDBSCAN, min size 20 | 62 | **35.5%** | 0.678 | 0.650 | 4% | – | 1.3 s |

**Read this table carefully — it is exactly why the app does not just pick the highest Silhouette.** HDBSCAN's score is high because 36% of events are discarded as noise. DBSCAN at its automatic eps is very stable but lumps 96% of events together; the sensitivity grid shows a narrow useful band (eps ≈ 1.0–2.0) and total collapse into one cluster at eps = 3. Average and single linkage score 0.72 only by putting ~100% of events in one cluster. The Clustering Lab flags these degenerate results.

Hierarchical clustering cost on this machine class: 10,000 rows ≈ 4 s / 450 MB; 15,000 rows ≈ 8 s / 1 GB (the default cap; memory grows with n²).

## 5. Roles and security

Roles: `administrator`, `coordinator`, `responder`, `researcher`, `citizen`. Permissions are enforced on the server (the UI only hides things). Self-registration is limited to citizen/researcher; staff roles are created by an administrator, and the role is always read from the database, never trusted from the token. Passwords use bcrypt (scrypt fallback), JWT access tokens, input validation on every endpoint, upload size/type checks with server-generated file names, per-user rate limiting and duplicate detection on incident reports, citizens can only see their own reports, and administrative/review actions are written to an audit log. No API keys exist in frontend code.

Operational data is **never seeded**: the resource list starts empty, citizen reports are labelled *unverified* until staff verify them, and resource assignments are only *proposed* until a person approves them.

## 6. Honest status: what was and was not tested

Tested here (125 automated tests passing, 1 skipped):
- Data quality checks, damage K/M/B conversion, one-to-many joins, orphan handling, duplicate IDs, missing/invalid values, empty files — on small crafted fixtures **and** on your real files
- Both required algorithms (plus HDBSCAN), all metrics and their edge cases, PCA, noise handling, sensitivity, stability, seeds/reproducibility, sampling representativeness
- Anomaly methods, similarity, multi-hazard, temporal/impact analytics, assistant, PDF/CSV reports, authentication/authorisation, upload validation, incident privacy/spam controls, resource/assignment/task rules
- External clients (NWS, OSRM) with mocked HTTP: parsing, error paths, stale-cache labelling
- A full workflow test: upload → quality → experiments → comparison → explanations → cluster geography/impact → assistant → reports
- All 71 API route handlers were imported and a representative set was called directly against the real data and services.

**Not executed in the environment where this was written** (it had no access to PyPI/npm, so FastAPI, the HTTP layer and the React app could not be installed or run):
- The live FastAPI server and `tests/test_api.py` (these skip automatically until FastAPI is installed — please run `pytest` after `pip install -r requirements.txt`)
- `npm install` / `npm run build` / the UI in a browser. The frontend was checked with esbuild (all files parse, every local import and export resolves) and a TypeScript pass found no undefined names, but it has **not been rendered**. Expect to fix small UI issues on first run.
- The live NWS and OSRM endpoints (only mocked)
- Docker images

If anything fails on your machine, the first things to check are the versions in `requirements.txt` / `package.json` and the browser console.

## 7. Deviations from the original brief (and why)

- **SQLAlchemy, DuckDB, GeoPandas, Shapely are not used.** The app database uses SQLite through the standard library (the SQL is portable to PostgreSQL), analytics run on pandas over the processed table (32k rows, a few MB), and maps need only coordinates. Adding DuckDB over Parquet becomes worthwhile for the full 2010–2020 NOAA archive; the storage layer (`core/storage.py`) already writes Parquet when `pyarrow` is installed.
- **Requests, not httpx,** for the external HTTP calls (simple and testable).
- Live alerts, routes, incident reporting, resources and coordination are implemented, but they depend on external services or on staff entering real records. No road-closure feed is integrated (the UI says so).
- The AI assistant is the controlled rule-based engine the brief asked to start with; its interpreter is isolated so an LLM can replace it later.
- Hierarchical clustering is capped at 15,000 rows by default (`STORMSENSE_MAX_HIER_ROWS`).

## 8. Suggested next steps
1. Run the backend tests and the frontend on your laptop; fix anything environment-specific.
2. Obtain the details files for 2010–2016 from NOAA so the temporal pages have real year-to-year coverage (the locations/fatalities files you have already span 2010–2020).
3. Add zone-centroid coordinates for forecast-zone events to bring heat/drought/winter-storm events onto the map.
4. Move to PostgreSQL if you need multi-user production deployment.
