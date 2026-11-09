"""Module 16 reporting: PDF (ReportLab) and CSV exports built from real computed results, always with the
data period, source, methodology and limitations."""
from __future__ import annotations

import csv
import io
import time
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..core import config
from . import analytics as A

LIMITATIONS = [
    "The details file covers Feb 2017 - Sep 2020 and about 94% of its events fall in 2020; year-to-year comparisons are unreliable.",
    "About 23% of events (mostly forecast-zone events such as heat, drought and winter storms) have no coordinates and cannot be mapped.",
    "Damage values are estimates entered by NWS offices and are missing for roughly a fifth of events.",
    "Clustering describes similarity between historical records. It does not predict future events or establish causes.",
    "Silhouette, Davies-Bouldin and Calinski-Harabasz favour compact groups and are computed without noise points.",
]


def _table(rows: list[list], col_widths=None) -> Table:
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f9")]), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _fmt(v):
    if v is None or (isinstance(v, float) and v != v):
        return "-"
    if isinstance(v, float):
        return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"
    return str(v)


def build_pdf(title: str, df: pd.DataFrame, manifest: dict, experiment: dict | None = None, filters: dict | None = None) -> bytes:
    filters = {k: v for k, v in (filters or {}).items() if v}
    f = A.apply_filters(df, **filters)
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=title)
    s = [Paragraph(title, styles["Title"]),
         Paragraph(f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by StormSense AI. Source: NOAA Storm Events Database extract "
                   f"(dataset version {manifest['dataset_version']}). Data period: {manifest['date_range'][0][:10]} to {manifest['date_range'][1][:10]}.", styles["Normal"]),
         Paragraph(f"Filters: {filters or 'none'}. Historical records only; not a forecast, warning or live alert.", styles["Italic"]), Spacer(1, 6)]

    summ = A.impact_summary(df, **filters)
    s += [Paragraph("1. Summary", styles["Heading2"]),
          _table([["Events", "Deaths", "Injuries", "Property damage (USD)", "Crop damage (USD)"],
                  [_fmt(summ["events"]), _fmt(summ["deaths"]), _fmt(summ["injuries"]), _fmt(summ["property_damage_usd"]), _fmt(summ["crop_damage_usd"])]])]

    top = f["event_type"].value_counts().head(10)
    s += [Paragraph("2. Event types", styles["Heading2"]), _table([["Event type", "Events"]] + [[i, _fmt(int(v))] for i, v in top.items()])]
    yr = A.temporal(df, "yearly", **filters)["series"]
    s += [Paragraph("3. Yearly distribution", styles["Heading2"]),
          _table([["Year", "Events", "Deaths", "Injuries"]] + [[r["year"], _fmt(r["events"]), _fmt(r["deaths"]), _fmt(r["injuries"])] for r in yr]),
          Paragraph(A.COVERAGE_CAVEAT, styles["Italic"])]
    reg = A.impact_by(df, "region", top=10, **filters)["rows"]
    s += [Paragraph("4. Regions with most recorded fatalities", styles["Heading2"]),
          _table([["Region", "Events", "Deaths", "Injuries", "Property damage"]] +
                 [[r["state"], _fmt(r["events"]), _fmt(r["deaths"]), _fmt(r["injuries"]), _fmt(r["property_damage_usd"])] for r in reg])]

    if experiment:
        m = experiment["metrics"]
        s += [Paragraph("5. Clustering experiment", styles["Heading2"]),
              Paragraph(f"Experiment {experiment['id']} | algorithm: {experiment['algorithm']} | parameters: {experiment['params']} | seed: {experiment['seed']} | "
                        f"features: {', '.join(experiment['config']['features'])} | scaler: {experiment['config']['scaler']} | "
                        f"sample: {experiment['config']['sample_size']:,} of {experiment['config']['population_after_filters']:,} events.", styles["Normal"]),
              _table([["Clusters", "Noise", "Silhouette", "Davies-Bouldin", "Calinski-Harabasz", "Seconds"],
                      [_fmt(m["n_clusters"]), f"{m['noise_count']} ({m['noise_pct']}%)", _fmt(m["silhouette"]), _fmt(m["davies_bouldin"]),
                       _fmt(m["calinski_harabasz"]), _fmt(experiment["seconds"])]])]
        for p in experiment["profiles"][:12]:
            s.append(Paragraph(p["explanation"], styles["BodyText"]))

    s += [Paragraph("Methodology and limitations", styles["Heading2"])] + [Paragraph("- " + l, styles["BodyText"]) for l in LIMITATIONS]
    doc.build(s)
    return buf.getvalue()


def build_csv(df: pd.DataFrame, filters: dict | None = None, columns: list[str] | None = None, max_rows: int = 100_000) -> bytes:
    filters = {k: v for k, v in (filters or {}).items() if v}
    f = A.apply_filters(df, **filters)
    cols = columns or ["event_id", "event_type", "state", "begin_dt", "end_dt", "year", "month", "season", "magnitude", "deaths_total",
                       "injuries_total", "DAMAGE_PROPERTY", "property_damage_usd", "DAMAGE_CROPS", "crop_damage_usd", "lat", "lon"]
    cols = [c for c in cols if c in f.columns]
    out = io.StringIO()
    out.write("# Source: NOAA Storm Events Database extract. Historical records only.\n")
    f[cols].head(max_rows).to_csv(out, index=False, quoting=csv.QUOTE_MINIMAL)
    return out.getvalue().encode()


def save_report(con, user_id: int, title: str, kind: str, fmt: str, params: dict, content: bytes) -> dict:
    from ..db import database as db
    folder = config.UPLOAD_DIR.parent / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"report_{time.time_ns()}.{fmt}"
    path.write_bytes(content)
    cur = con.execute("INSERT INTO reports(title,kind,params_json,file_path,format,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                      (title, kind, db.dumps(params), str(path), fmt, user_id, db.now()))
    return db.one(con, "SELECT id,title,kind,format,created_at FROM reports WHERE id=?", (cur.lastrowid,))
