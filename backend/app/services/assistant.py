"""Module 16: controlled rule-based query engine over the processed historical data. Every answer is computed
from the data and carries its source and period. It never answers from memory and never speaks about live
conditions. An LLM can be plugged in later by replacing `interpret` while keeping `execute`."""
from __future__ import annotations

import re

import pandas as pd

from . import analytics as A

SOURCE = "NOAA Storm Events Database (extract: details/locations/fatalities CSVs supplied with the project)"
NOT_LIVE = "These are historical records, not live alerts or forecasts. For current warnings see the Live Alerts page or weather.gov."
HELP_EXAMPLES = ["Which states have the most flood events?", "Which event types have the highest fatalities?",
                 "What seasonal pattern appears in tornado records?", "Show the yearly distribution of hail events",
                 "Compare Texas and Oklahoma", "Which clusters have the highest property damage?",
                 "Explain cluster 2", "Find events similar to 917518"]


def _types(df: pd.DataFrame) -> dict[str, str]:
    return {t.lower(): t for t in df["event_type"].unique()}


def _find_type(q: str, types: dict[str, str]) -> str | None:
    """Longest event-type name (or its singular/plural form) found in the question."""
    for low in sorted(types, key=len, reverse=True):
        if re.search(rf"\b{re.escape(low)}s?\b", q):
            return types[low]
    if "flood" in q and "flash" not in q:
        return "Flood"
    if "storm" in q and "thunder" in q:
        return "Thunderstorm Wind"
    return None


def _find_states(q: str, df: pd.DataFrame) -> list[str]:
    found = []
    for st in sorted(df["state"].unique(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(st.lower())}\b", q):
            found.append(st)
            q = q.replace(st.lower(), " ")
    return found


def _find_year(q: str) -> int | None:
    m = re.search(r"\b(20[12]\d)\b", q)
    return int(m.group(1)) if m else None


def _result(answer: str, df: pd.DataFrame | None = None, chart: dict | None = None, rows: list | None = None, intent: str = "") -> dict:
    return {"answer": answer, "intent": intent, "chart": chart, "table": rows, "source": SOURCE, "note": NOT_LIVE}


def interpret(question: str, df: pd.DataFrame) -> dict:
    q = question.lower().strip()
    types = _types(df)
    etype = _find_type(q, types)
    states = _find_states(q, df)
    intent = None
    m_id = re.search(r"\b(\d{5,7})\b", q)
    m_cluster = re.search(r"cluster\s+(-?\d+)", q)
    if "similar" in q and m_id:
        intent = "similar"
    elif m_cluster and any(w in q for w in ("explain", "characteristic", "describe", "what is", "about")):
        intent = "cluster_explain"
    elif "cluster" in q and any(w in q for w in ("damage", "fatal", "death", "injur", "impact", "highest")):
        intent = "cluster_impact"
    elif "compare" in q and len(states) >= 2:
        intent = "compare_regions"
    elif any(w in q for w in ("season", "seasonal")):
        intent = "seasonal"
    elif any(w in q for w in ("yearly", "per year", "by year", "each year", "year-wise", "distribution")) and "month" not in q:
        intent = "yearly"
    elif "month" in q:
        intent = "monthly"
    elif any(w in q for w in ("fatal", "death", "died", "killed")):
        intent = "top_types_deaths" if not states and "state" not in q else "top_states_deaths"
    elif any(w in q for w in ("injur",)):
        intent = "top_types_injuries"
    elif any(w in q for w in ("damage", "costly", "expensive", "cost")):
        intent = "top_damage"
    elif "state" in q or "which" in q and ("region" in q or "where" in q):
        intent = "top_states_events"
    elif any(w in q for w in ("how many", "count", "number of", "total")):
        intent = "count"
    return {"intent": intent, "event_type": etype, "states": states, "year": _find_year(q),
            "event_id": int(m_id.group(1)) if m_id else None, "cluster": int(m_cluster.group(1)) if m_cluster else None}


def execute(parsed: dict, df: pd.DataFrame, experiment: dict | None = None, assignments: pd.DataFrame | None = None) -> dict:
    intent, et, states, year = parsed["intent"], parsed["event_type"], parsed["states"], parsed["year"]
    f = A.apply_filters(df, event_type=et, year=year, state=states[0] if len(states) == 1 else None)
    scope = ", ".join(x for x in [et, states[0] if len(states) == 1 else None, str(year) if year else None] if x) or "all events"
    period = f"{df['begin_dt'].min()[:10]} to {df['begin_dt'].max()[:10]}"

    def tbl(g, col, label):
        rows = [{label: str(i), col: float(v)} for i, v in g.items()]
        return rows

    if intent == "top_states_events" or intent == "count":
        if intent == "count" and not (et or states or year):
            return _result(f"The processed extract contains {len(df):,} unique events ({period}).", intent=intent)
        if intent == "count":
            return _result(f"There are {len(f):,} recorded events for {scope} ({period}).", intent=intent)
        g = f["state"].value_counts().head(10)
        return _result(f"Top states by number of recorded {et or 'weather'} events ({period}): "
                       + ", ".join(f"{i} ({v:,})" for i, v in g.head(5).items()) + ".",
                       chart={"type": "bar", "x": "state", "y": "events", "data": [{"state": i, "events": int(v)} for i, v in g.items()]},
                       rows=[{"state": i, "events": int(v)} for i, v in g.items()], intent=intent)
    if intent in ("top_types_deaths", "top_types_injuries"):
        col, word = ("deaths_total", "fatalities") if intent == "top_types_deaths" else ("injuries_total", "injuries")
        g = f.groupby("event_type")[col].sum().sort_values(ascending=False).head(10)
        return _result(f"Event types with the most recorded {word} for {scope} ({period}): "
                       + ", ".join(f"{i} ({int(v)})" for i, v in g.head(5).items()) + ".",
                       chart={"type": "bar", "x": "event_type", "y": word, "data": [{"event_type": i, word: int(v)} for i, v in g.items()]},
                       rows=[{"event_type": i, word: int(v)} for i, v in g.items()], intent=intent)
    if intent == "top_states_deaths":
        g = f.groupby("state")["deaths_total"].sum().sort_values(ascending=False).head(10)
        return _result(f"States with the most recorded fatalities for {scope}: " + ", ".join(f"{i} ({int(v)})" for i, v in g.head(5).items()) + ".",
                       chart={"type": "bar", "x": "state", "y": "fatalities", "data": [{"state": i, "fatalities": int(v)} for i, v in g.items()]},
                       rows=[{"state": i, "fatalities": int(v)} for i, v in g.items()], intent=intent)
    if intent == "top_damage":
        g = f.groupby("event_type")["total_damage_usd"].sum().sort_values(ascending=False).head(10)
        return _result(f"Event types with the highest recorded damage for {scope}: "
                       + ", ".join(f"{i} (${v:,.0f})" for i, v in g.head(5).items())
                       + ". Damage amounts are missing for roughly a fifth of events.",
                       chart={"type": "bar", "x": "event_type", "y": "damage_usd", "data": [{"event_type": i, "damage_usd": float(v)} for i, v in g.items()]},
                       rows=[{"event_type": i, "damage_usd": float(v)} for i, v in g.items()], intent=intent)
    if intent == "seasonal":
        t = A.temporal(df, "seasonal", event_type=et, state=states[0] if len(states) == 1 else None, year=year)["series"]
        top = max(t, key=lambda r: r["events"]) if t else None
        ans = (f"For {scope}, the most records fall in {top['season']} ({top['events']:,} events). " if top else "No matching events. ") + \
              "Counts reflect what was recorded in this extract, not climate trends."
        return _result(ans, chart={"type": "bar", "x": "season", "y": "events", "data": [{"season": r["season"], "events": r["events"]} for r in t]}, rows=t, intent=intent)
    if intent == "monthly":
        t = A.temporal(df, "monthly", event_type=et, state=states[0] if len(states) == 1 else None, year=year)["series"]
        return _result(f"Monthly distribution for {scope}.", chart={"type": "bar", "x": "month", "y": "events", "data": [{"month": r["month"], "events": r["events"]} for r in t]}, rows=t, intent=intent)
    if intent == "yearly":
        t = A.temporal(df, "yearly", event_type=et, state=states[0] if len(states) == 1 else None)["series"]
        return _result(f"Yearly distribution for {scope}. The extract is dominated by 2020 (partial coverage in earlier years), so compare years with care.",
                       chart={"type": "bar", "x": "year", "y": "events", "data": [{"year": r["year"], "events": r["events"]} for r in t]}, rows=t, intent=intent)
    if intent == "compare_regions":
        rows = []
        for s in states[:3]:
            x = A.apply_filters(df, state=s, event_type=et, year=year)
            rows.append({"state": s, "events": len(x), "deaths": int(x["deaths_total"].sum()), "injuries": int(x["injuries_total"].sum()),
                         "property_damage_usd": float(x["property_damage_usd"].sum()),
                         "top_event_type": x["event_type"].value_counts().index[0] if len(x) else None})
        return _result("Comparison of " + " and ".join(states[:3]) + f" for {et or 'all event types'}.", rows=rows,
                       chart={"type": "bar", "x": "state", "y": "events", "data": [{"state": r["state"], "events": r["events"]} for r in rows]}, intent=intent)
    if intent == "similar":
        try:
            s = A.similar_events(df, parsed["event_id"], k=5)
        except KeyError:
            return _result(f"Event {parsed['event_id']} is not in the processed dataset.", intent=intent)
        return _result(f"Most similar historical events to {parsed['event_id']} ({s['query']['event_type']}, {s['query']['state']}): "
                       + ", ".join(f"{x['event_id']} (similarity {x['similarity']})" for x in s["similar"]) + ".",
                       rows=s["similar"], intent=intent)
    if intent in ("cluster_explain", "cluster_impact"):
        if not experiment:
            return _result("No clustering experiment exists yet. Run one in the Clustering Lab first.", intent=intent)
        profs = experiment["profiles"]
        if intent == "cluster_explain":
            p = next((x for x in profs if x["cluster_id"] == parsed["cluster"]), None)
            if not p:
                return _result(f"Cluster {parsed['cluster']} does not exist in experiment {experiment['id']}.", intent=intent)
            return _result(p["explanation"] + f" (experiment {experiment['id']}, {experiment['algorithm']})", intent=intent)
        rows = sorted(({"cluster": p["cluster_id"], "events": p["event_count"], "property_damage_usd": p["totals"]["property_damage_usd"],
                        "deaths": p["totals"]["deaths"], "injuries": p["totals"]["injuries"]} for p in profs), key=lambda r: -r["property_damage_usd"])
        return _result(f"In experiment {experiment['id']} the cluster with the highest recorded property damage is cluster {rows[0]['cluster']} "
                       f"(${rows[0]['property_damage_usd']:,.0f}).", rows=rows, intent=intent,
                       chart={"type": "bar", "x": "cluster", "y": "property_damage_usd", "data": [{"cluster": str(r["cluster"]), "property_damage_usd": r["property_damage_usd"]} for r in rows]})
    return _result("I can answer questions about the historical records only, using a fixed set of question patterns. I did not understand that one. Try: "
                   + " / ".join(f'"{e}"' for e in HELP_EXAMPLES[:4]), intent="unknown")


def answer(question: str, df: pd.DataFrame, experiment: dict | None = None) -> dict:
    if not question or len(question) > 500:
        raise ValueError("Question must be between 1 and 500 characters.")
    parsed = interpret(question, df)
    out = execute(parsed, df, experiment)
    out["question"], out["parsed"] = question, parsed
    return out
