"""Modules 11-12: live official alerts (National Weather Service) and routes (OSRM / OpenStreetMap).
Nothing here is ever fabricated: when an upstream service fails the caller gets an explicit error and, for
alerts, the last cached real response clearly labelled as stale."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import requests

from ..core import config
from ..db import database as db

ALERT_DISCLAIMER = ("Live alerts come from the US National Weather Service (api.weather.gov). They are separate from the "
                    "historical clustering results and are not produced by StormSense AI.")
ROUTE_DISCLAIMER = ("Routes are computed from OpenStreetMap data and do not guarantee safety. Follow official emergency "
                    "instructions and check current road-closure information from the responsible authority. Historical hazard "
                    "overlays are past records, not evidence of a current hazard.")
HEADERS = {"User-Agent": config.HTTP_USER_AGENT, "Accept": "application/geo+json"}


class UpstreamError(Exception):
    pass


def normalise_alert(feature: dict) -> dict:
    p = feature.get("properties", {})
    return {"id": p.get("id"), "event": p.get("event"), "headline": p.get("headline"), "description": p.get("description"),
            "instruction": p.get("instruction"), "area": p.get("areaDesc"), "severity": p.get("severity"), "urgency": p.get("urgency"),
            "certainty": p.get("certainty"), "sent": p.get("sent"), "effective": p.get("effective"), "onset": p.get("onset"),
            "expires": p.get("expires"), "sender": p.get("senderName"), "source_url": p.get("@id") or feature.get("id"),
            "geometry": feature.get("geometry")}


def fetch_alerts(state: str | None = None, severity: str | None = None, event: str | None = None, client: requests.Session | None = None) -> dict:
    params = {"status": "actual"}
    if state:
        if len(state) != 2 or not state.isalpha():
            raise ValueError("state must be a two-letter US state code")
        params["area"] = state.upper()
    own = client is None
    client = client or requests.Session()
    client.headers.update(HEADERS)
    try:
        r = client.get(f"{config.NWS_BASE}/alerts/active", params=params, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        cached = _read_cache()
        if cached:
            return {**cached, "stale": True, "error": f"Live fetch failed ({type(e).__name__}); showing last successful fetch.",
                    "disclaimer": ALERT_DISCLAIMER}
        raise UpstreamError(f"Could not reach the National Weather Service API ({type(e).__name__}). No alerts are shown rather than guessing.") from e
    finally:
        if own:
            client.close()
    alerts = [normalise_alert(f) for f in data.get("features", [])]
    payload = {"alerts": alerts, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "api.weather.gov",
               "stale": False, "count": len(alerts)}
    _write_cache(payload) if not state else None
    return _filter(payload, severity, event)


def _filter(payload: dict, severity, event) -> dict:
    alerts = payload["alerts"]
    if severity:
        alerts = [a for a in alerts if (a.get("severity") or "").lower() == severity.lower()]
    if event:
        alerts = [a for a in alerts if event.lower() in (a.get("event") or "").lower()]
    return {**payload, "alerts": alerts, "count": len(alerts), "disclaimer": ALERT_DISCLAIMER}


def _write_cache(payload: dict) -> None:
    try:
        with db.session() as con:
            con.execute("INSERT OR REPLACE INTO alert_cache(id,fetched_at,payload_json) VALUES(1,?,?)", (payload["fetched_at"], json.dumps(payload)))
    except Exception:  # cache failure must never break the request
        pass


def _read_cache() -> dict | None:
    try:
        with db.session() as con:
            r = db.one(con, "SELECT payload_json FROM alert_cache WHERE id=1")
        return json.loads(r["payload_json"]) if r else None
    except Exception:
        return None


def fetch_routes(origin: tuple[float, float], destination: tuple[float, float], alternatives: bool = True,
                 client: requests.Session | None = None) -> dict:
    for lat, lon in (origin, destination):
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Coordinates out of range")
    coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    own = client is None
    client = client or requests.Session()
    client.headers.update({"User-Agent": config.HTTP_USER_AGENT})
    try:
        r = client.get(f"{config.OSRM_BASE}/route/v1/driving/{coords}", timeout=config.HTTP_TIMEOUT,
                       params={"overview": "full", "geometries": "geojson", "steps": "true", "alternatives": "true" if alternatives else "false"})
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        raise UpstreamError(f"Routing service unavailable ({type(e).__name__}).") from e
    finally:
        if own:
            client.close()
    if data.get("code") != "Ok":
        raise UpstreamError(f"Routing service returned: {data.get('code')}")
    routes = []
    for i, rt in enumerate(data["routes"]):
        steps = [{"instruction": _step_text(s), "distance_m": s["distance"]} for leg in rt["legs"] for s in leg["steps"]]
        routes.append({"index": i, "distance_km": round(rt["distance"] / 1000, 2), "duration_min": round(rt["duration"] / 60, 1),
                       "geometry": rt["geometry"], "steps": steps})
    return {"routes": routes, "source": "OSRM on OpenStreetMap data", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "road_closures": "No current road-closure feed is integrated. Check your state's transport authority or 511 service.",
            "disclaimer": ROUTE_DISCLAIMER}


def _step_text(step: dict) -> str:
    m = step.get("maneuver", {})
    verb = (m.get("modifier") or "").replace("_", " ")
    kind = (m.get("type") or "continue").replace("_", " ")
    road = step.get("name") or "the road"
    return f"{kind.capitalize()} {verb} onto {road}".replace("  ", " ")
