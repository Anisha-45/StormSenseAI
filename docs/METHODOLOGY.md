# StormSense AI — Methodology

## 1. Data integration
`details` is the only event-level source (one row per `EVENT_ID`, verified unique). `locations` (many rows per event, max 8) and `fatalities` (many rows per event, max 161) are **aggregated per `EVENT_ID` first** and then left-joined with `validate="one_to_one"`, so the join cannot multiply events (the pipeline asserts `len(events) == len(details)`). Rows whose `EVENT_ID` is absent from details are counted and logged, not joined. Raw values are preserved (original `DAMAGE_PROPERTY` / `DAMAGE_CROPS` strings sit beside the converted dollars), and every problem found is stored in `manifest.json` → `issues`.

Derived fields: year, month, season (Dec–Feb winter, Mar–May spring, Jun–Aug summer, Sep–Nov autumn), duration in hours (NaN if end precedes begin), `injuries_total`, `deaths_total`, `total_damage_usd`, `has_impact`, `has_coordinates`, `magnitude_reported`.

## 2. Data-quality score (project-defined, not an official NOAA score)
`score = 100 × (0.40·completeness + 0.20·uniqueness + 0.15·date_validity + 0.15·coordinate_validity + 0.10·numeric_validity)`
Components that cannot be evaluated for a file (no date, coordinate or numeric-range columns) score neutral (1.0) **and are listed as "not evaluated"** so the score is never silently inflated. Structurally sparse columns (≥90% empty, e.g. tornado-only fields) lower completeness by design and are listed separately.

## 3. Features and preprocessing for clustering
Numeric: log1p(property damage), log1p(crop damage), injuries, deaths, log1p(duration), magnitude, cyclic month (sin/cos), latitude, longitude. Categorical: event type, season (one-hot, damped by `1.5/√levels` so a 49-level category does not dominate Euclidean distance).
Missing values: median (default) or zero imputation, recorded per feature in the saved config; a column that is empty for the whole selection becomes constant 0. Scaling: standard (default), robust or min-max. Selecting latitude/longitude excludes events without coordinates and reports the exact count.

**Sampling.** Strata = event type × has-impact × year. Every stratum keeps at least `min(size, 20)` rows so rare, high-impact events survive; the rest of the budget is proportional. Seeded and reproducible. The first N rows are never used.

## 4. Algorithms
- **Hierarchical agglomerative:** Ward (Euclidean only), complete, average, single; any of Euclidean/Manhattan/Chebyshev/cosine for non-Ward. Dendrogram is drawn from a ≤600-row subsample with the last 30 merges (a dendrogram of thousands of leaves is unreadable).
- **DBSCAN:** configurable `eps`, `min_samples`, metric. Core / border / noise are reported per point. If `eps` is omitted it is taken from the knee of the sorted k-distance curve (a starting point, not a guarantee). A sensitivity grid shows cluster count and noise for eps × min_samples.
- **HDBSCAN** (scikit-learn) as an additional comparison method.

## 5. Evaluation
Silhouette, Davies-Bouldin and Calinski-Harabasz are computed **on clustered points only (noise excluded)** and only when valid (≥2 clusters and at least one cluster with more than one point); Silhouette uses a 8,000-point random subset when larger. The results state when noise was excluded. A high score is **not** treated as proof of a good clustering: compact-cluster indices reward solutions that discard many points as noise or put almost everything in one cluster, so the UI flags results where one cluster holds >90% of events.
**Stability:** repeated runs on random 80% subsamples compared with the full run on the shared rows via the Adjusted Rand Index (≈1 reproducible, <0.5 fragile).
**Feature interpretation:** eta-squared per feature (share of variance explained by cluster membership, clustered points only) — descriptive, not causal.

## 6. Cluster explanations
Sentences are assembled by template from the cluster's actual statistics (size, dominant types, top states, season, impact totals, largest ratio to the overall mean). They contain no causal language and end with a reminder that they describe historical records.

## 7. Anomaly detection
Isolation Forest, Local Outlier Factor (stratified 20k-row sample if larger), and a statistical detector using **Tukey fences**: a value is scored by how many IQRs it lies beyond the nearest quartile; zero-heavy columns (most impact fields) are judged against their non-zero values. (A plain median/MAD z-score was tried first and flagged 52% of all events because duration is bimodal and impact is mostly zero.) At the default threshold of 3 IQRs, 3.4% of events are flagged. An anomaly is unusual, not necessarily wrong or dangerous, and DBSCAN noise is deliberately **not** treated as an anomaly.

## 8. Similarity and multi-hazard search
Similarity: standardised Euclidean distance over impact, duration, magnitude, cyclic month and location; `similarity = 1/(1+distance)`; the result lists which feature groups the match is closest on. Multi-hazard: pairs of *different* event types within a haversine radius (BallTree) and a time window; reported as co-occurrence only — never causation.

## 9. Severity index
`severity = deaths × w_d + injuries × w_i + total_damage ÷ dollars_per_point` with user-adjustable weights (defaults 10, 3, $1M). It is a project index, labelled as such, and not an official classification.

## 10. Known limitations
Partial year coverage (2020 = 94% of events); 22.7% of events lack coordinates; damage values are estimates and often missing; locations/fatalities cover many events absent from details; hierarchical clustering is memory-bound (n²) and capped; internal validity indices favour compact groups; clustering and hotspots describe the past and do not predict future events.
