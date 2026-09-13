"""
Open-Meteo weather lookups and WMO code mapping. No ERP except the site/trailer coordinate lookup.

Split out of the original single-file work_tool.py. Everything here is
re-exported by work_tool/__init__.py, so each name is still reachable as
`work_tool.<name>` exactly as before.
"""

import time
import requests
import csv
import os
import sys
import re
import json
import asyncio
import subprocess
import tempfile
import shlex
import zabbix_tool
import unit_history
import multiprocessing
import paramiko
import threading
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from urllib.parse import quote
import urllib3

from ._core import (  # noqa: F401  (re-exported dependencies)
    _fetch_erp_site_doc_raw,
    _fetch_mu_component_doc,
    _normalize_netsheet_unit,
    missing,
    resolve_attached_mu_code,
    resolve_dashboard_site_id,
)


def _parse_nonzero_coords(lat, lon):
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None
    if lat_f == 0.0 and lon_f == 0.0:
        return None
    return lat_f, lon_f
def _coords_from_site_addresses(site_doc):
    """Primary weather coords: main Site Address, else first address with GPS."""
    addresses = (site_doc or {}).get("addresses") or []
    if not isinstance(addresses, list):
        return None
    ordered = [row for row in addresses if isinstance(row, dict)]
    if not ordered:
        return None
    mains = [row for row in ordered if row.get("main_address")]
    for row in (mains + ordered):
        coords = _parse_nonzero_coords(row.get("latitude"), row.get("longitude"))
        if coords:
            return coords
    return None
def _coords_from_trailer_component(unit, subject=""):
    """Fallback weather coords: attached trailer (MU) Component lat/lon."""
    mu_code = resolve_attached_mu_code(unit, subject)
    if not mu_code:
        return None, ""
    doc, component_name, error = _fetch_mu_component_doc(mu_code)
    if error or not doc:
        return None, mu_code
    coords = _parse_nonzero_coords(doc.get("latitude"), doc.get("longitude"))
    if not coords:
        return None, mu_code or component_name
    return coords, mu_code or component_name
_WMO_WEATHER_LABELS = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Slight rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Slight snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}
def _wmo_weather_label(code):
    try:
        key = int(code)
    except (TypeError, ValueError):
        return "Unknown"
    return _WMO_WEATHER_LABELS.get(key, f"Code {key}")
def _wmo_icon_class(code, cloud_cover=None):
    try:
        value = int(code)
    except (TypeError, ValueError):
        value = None
    if value is None:
        icon = "cloud"
    elif value in (0, 1):
        icon = "sun"
    elif value == 2:
        icon = "sun-cloud"  # partly cloudy
    elif value == 3:
        icon = "cloud"  # overcast
    elif value in (45, 48):
        icon = "fog"
    elif value in (71, 73, 75, 77, 85, 86):
        icon = "cloud-snow"
    elif value in (95, 96, 99):
        icon = "cloud-lightning"
    elif value >= 50:
        icon = "cloud-rain"
    else:
        icon = "cloud"

    # Prefer cloud cover for Google-style partly / mostly cloudy.
    try:
        cover = float(cloud_cover)
    except (TypeError, ValueError):
        return icon
    if cover >= 85 and icon in ("sun", "sun-cloud"):
        return "cloud-mostly"
    if cover >= 50 and icon == "sun":
        return "sun-cloud"
    return icon
def _fetch_open_meteo_current(lat, lon):
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,weather_code,wind_speed_10m,"
                "relative_humidity_2m,cloud_cover"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",
        },
        timeout=20,
    )
    if not response.ok:
        return None, f"Open-Meteo HTTP {response.status_code}"
    payload = response.json() or {}
    current = payload.get("current")
    if not isinstance(current, dict):
        return None, "Open-Meteo response missing current conditions"
    weather_code = current.get("weather_code")
    cloud_cover = current.get("cloud_cover")
    temp = current.get("temperature_2m")
    wind = current.get("wind_speed_10m")
    humidity = current.get("relative_humidity_2m")
    conditions = _wmo_weather_label(weather_code)
    try:
        cover_f = float(cloud_cover)
        if cover_f >= 85 and weather_code in (0, 1, 2):
            conditions = "Mostly cloudy"
        elif cover_f >= 50 and weather_code in (0, 1):
            conditions = "Partly cloudy"
    except (TypeError, ValueError):
        pass
    try:
        temp_label = f"{round(float(temp))}°F"
    except (TypeError, ValueError):
        temp_label = "?°F"
    try:
        wind_label = f"{round(float(wind))} mph"
    except (TypeError, ValueError):
        wind_label = "? mph"
    try:
        humidity_label = f"{int(round(float(humidity)))}%"
    except (TypeError, ValueError):
        humidity_label = "?%"
    return {
        "temperature_f": temp,
        "temperature_label": temp_label,
        "weather_code": weather_code,
        "cloud_cover": cloud_cover,
        "conditions": conditions,
        "icon": _wmo_icon_class(weather_code, cloud_cover),
        "wind_mph": wind,
        "wind_label": wind_label,
        "humidity": humidity,
        "humidity_label": humidity_label,
        "timezone": payload.get("timezone") or "",
        "observed_at": current.get("time") or "",
    }, None
def get_unit_weather(unit, subject=""):
    """
    Resolve site/trailer GPS and fetch current weather from Open-Meteo.
    Returns (payload_dict, error_message).
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None, f"Invalid unit: {unit}"

    subject_text = str(subject or "").strip()
    site_id = ""
    site_name = ""
    site_error = ""
    resolved_site_id, resolve_error = resolve_dashboard_site_id(unit_key, subject_text)
    if resolve_error:
        site_error = resolve_error
    elif resolved_site_id:
        site_id = str(resolved_site_id).strip()

    lat = lon = None
    coord_source = ""
    trailer = ""

    if site_id:
        raw_site, raw_error = _fetch_erp_site_doc_raw(site_id)
        if raw_error:
            site_error = raw_error
        elif raw_site:
            site_name = str(raw_site.get("site_name") or "").strip()
            coords = _coords_from_site_addresses(raw_site)
            if coords:
                lat, lon = coords
                coord_source = "site"

    if lat is None:
        trailer_coords, trailer = _coords_from_trailer_component(unit_key, subject_text)
        if trailer_coords:
            lat, lon = trailer_coords
            coord_source = "trailer"

    if lat is None:
        bits = ["No GPS on site address or trailer"]
        if site_id:
            bits.append(f"site {site_id}")
        if trailer:
            bits.append(f"trailer {trailer}")
        if site_error:
            bits.append(site_error)
        return None, " — ".join(bits)

    weather, weather_error = _fetch_open_meteo_current(lat, lon)
    if weather_error:
        return None, weather_error

    place = site_name or (f"site {site_id}" if site_id else unit_key)
    coord_label = f"{lat:.3f},{lon:.3f}"
    message = (
        f"{unit_key} weather @ {place} [{coord_source} {coord_label}]: "
        f"{weather['temperature_label']}, {weather['conditions']}, "
        f"wind {weather['wind_label']}, humidity {weather['humidity_label']}"
    )
    return {
        "unit": unit_key,
        "site_id": site_id,
        "site_name": site_name,
        "trailer": trailer,
        "coord_source": coord_source,
        "latitude": lat,
        "longitude": lon,
        **weather,
        "message": message,
    }, None
# Metro coords for subject region codes (airport-metro centers). Zero ERP.
REGION_WEATHER_COORDS = {
    "LAX": (33.9425, -118.4081),
    "OAK": (37.80437, -122.2708),
    "HOU": (29.76328, -95.36327),
    "PHX": (33.44838, -112.07404),
    "SLC": (40.76078, -111.89105),
    "DEN": (39.73915, -104.9847),
}
_REGION_WEATHER_CACHE = {}
_REGION_WEATHER_CACHE_TTL_SEC = 30 * 60
_REGION_WEATHER_CACHE_LOCK = threading.Lock()
def region_code_from_subject(subject):
    """Parse leading region code from subjects like 'PHX - RD...' or 'PHX-RD...'."""
    text = str(subject or "").strip().upper()
    if not text:
        return ""
    codes = "|".join(sorted(REGION_WEATHER_COORDS.keys(), key=len, reverse=True))
    match = re.match(rf"^({codes})\b", text)
    if match:
        return match.group(1)
    return ""
def get_weather_for_regions(regions, force=False):
    """
    Current weather for unique subject region codes (LAX/OAK/HOU/PHX/SLC/DEN).
    Open-Meteo only — no ERP. Returns (regions_map, error_message).
    """
    wanted = []
    seen = set()
    for raw in regions or []:
        code = str(raw or "").strip().upper()
        if code in REGION_WEATHER_COORDS and code not in seen:
            seen.add(code)
            wanted.append(code)
    if not wanted:
        return {}, None

    now = time.time()
    out = {}
    missing = []
    with _REGION_WEATHER_CACHE_LOCK:
        for code in wanted:
            cached = _REGION_WEATHER_CACHE.get(code)
            if (
                not force
                and cached
                and cached.get("expires_at", 0) > now
            ):
                payload = dict(cached.get("payload") or {})
                payload["cached"] = True
                out[code] = payload
            else:
                missing.append(code)

    for code in missing:
        lat, lon = REGION_WEATHER_COORDS[code]
        weather, error = _fetch_open_meteo_current(lat, lon)
        if error:
            continue
        payload = {
            "region": code,
            "latitude": lat,
            "longitude": lon,
            "coord_source": "region",
            **weather,
            "message": (
                f"{code}: {weather['temperature_label']}, {weather['conditions']}"
            ),
            "cached": False,
        }
        with _REGION_WEATHER_CACHE_LOCK:
            _REGION_WEATHER_CACHE[code] = {
                "expires_at": now + _REGION_WEATHER_CACHE_TTL_SEC,
                "payload": dict(payload),
            }
        out[code] = payload

    return out, None
def _fetch_open_meteo_daily_outlook(lat, lon, days=5):
    """
    Multi-day cloud-cover outlook at a coordinate — the forecast half of the
    battery/weather correlation below. A day counts "cloudy" at >=60% mean
    cloud cover, which is a coarse cutoff but matches the coarse question
    being asked (is solar charging about to have a bad week, not exactly how
    bad). Returns (days_list, error).
    """
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "cloud_cover_mean,weather_code",
                "forecast_days": days,
                "timezone": "auto",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        return None, f"Open-Meteo forecast failed: {exc}"
    if not response.ok:
        return None, f"Open-Meteo HTTP {response.status_code}"
    daily = (response.json() or {}).get("daily") or {}
    dates = daily.get("time") or []
    covers = daily.get("cloud_cover_mean") or []
    codes = daily.get("weather_code") or []
    out = []
    for i, date in enumerate(dates):
        cover = covers[i] if i < len(covers) else None
        code = codes[i] if i < len(codes) else None
        try:
            cloudy = float(cover) >= 60
        except (TypeError, ValueError):
            cloudy = False
        out.append({
            "date": date,
            "cloud_cover_mean": cover,
            "weather_code": code,
            "conditions": _wmo_weather_label(code),
            "cloudy": cloudy,
        })
    return out, None
def _vrm_credentials():
    """(id_user, victron_token, error) from .env, or error set if either is missing."""
    id_user = (os.getenv("idUser") or "").strip().strip('"').strip("'")
    victron_token = (os.getenv("victron_token") or "").strip().strip('"').strip("'")
    if not id_user or not victron_token:
        return None, None, "Set idUser/victron_token in .env — VRM lookups need API access"
    return id_user, victron_token, None
def _resolve_vrm_site(unit_key, subject, id_user, victron_token):
    """
    Match a unit to its VRM installation via the attached MU trailer —
    VRM installations are named after the trailer, not the RD/FD head, and
    the two are numbered independently (RD3231's trailer is MU5031 — there
    is no numeric relationship to exploit). resolve_attached_mu_code()
    already does this correctly: RD####(MU####) in the subject first, then
    ERP's parent_component, and a bare MU unit returns itself (the
    "all-in-one" case, no separate trailer). Some RD/FD heads genuinely
    have no trailer and are correctly absent from VRM — that's not an
    error, it's reported as one so callers give a straight answer instead
    of a wrong guess.
    Returns (site_id, installation_name, error).
    """
    mu_code = resolve_attached_mu_code(unit_key, subject)
    if not mu_code:
        return None, None, f"{unit_key} has no attached MU trailer — nothing to look up in VRM"

    try:
        installations_resp = requests.get(
            f"https://vrmapi.victronenergy.com/v2/users/{id_user}/installations",
            headers={"idUser": id_user, "X-Authorization": f"Token {victron_token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, None, f"VRM installations lookup failed: {exc}"
    if installations_resp.status_code != 200:
        return None, None, f"VRM installations lookup failed: HTTP {installations_resp.status_code}"

    for record in (installations_resp.json().get("records") or []):
        name = str(record.get("name") or "").strip()
        if name.upper() == mu_code.upper():
            return record.get("idSite"), name, None
    return None, None, f"No VRM installation named {mu_code} (attached trailer for {unit_key})"
def unit_battery_weather_outlook(unit, subject=""):
    """
    Correlates a trailer's Victron VRM battery SOC with the multi-day cloud
    outlook for its site/trailer location — a battery at 45% heading into
    three sunny days is a different story than the same 45% heading into
    three cloudy ones, and this fleet had never connected those two signals
    despite already having both independently (a weather icon and a VRM
    link that just opens VRM in a new tab).

    One VRM installations lookup + one VRM diagnostics lookup + one
    Open-Meteo forecast call, all reads. idUser/victron_token come from
    .env — the same VRM API the CLI battery tool used, called fresh per
    request instead of through that tool's fleet-wide scan + module-level
    globals. Returns (info, error).
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None, f"Invalid unit: {unit}"
    subject_text = str(subject or "").strip()

    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error
    site_id, installation_name, site_error = _resolve_vrm_site(unit_key, subject_text, id_user, victron_token)
    if site_error:
        return None, site_error

    try:
        diagnostics_resp = requests.get(
            f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/diagnostics",
            headers={"idSite": str(site_id), "X-Authorization": f"Token {victron_token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, f"VRM diagnostics lookup failed: {exc}"
    if diagnostics_resp.status_code != 200:
        return None, f"VRM diagnostics lookup failed: HTTP {diagnostics_resp.status_code}"

    battery_soc_percent = None
    for record in (diagnostics_resp.json().get("records") or []):
        if record.get("description") == "Battery SOC":
            match = re.match(r"\s*(\d+(?:\.\d+)?)\s*%", str(record.get("formattedValue") or ""))
            if match:
                battery_soc_percent = float(match.group(1))
            break
    if battery_soc_percent is None:
        return None, f"VRM diagnostics for {installation_name or unit_key} had no Battery SOC reading"

    # Same coordinate resolution as get_unit_weather() (site address, else
    # trailer), duplicated rather than shared — this is an experimental
    # feature and get_unit_weather() backs the live weather icons, so it
    # stays untouched rather than refactored to serve a second caller.
    lat = lon = None
    location_label = unit_key
    resolved_site_id, resolve_error = resolve_dashboard_site_id(unit_key, subject_text)
    if resolved_site_id:
        raw_site, raw_error = _fetch_erp_site_doc_raw(str(resolved_site_id).strip())
        if not raw_error and raw_site:
            coords = _coords_from_site_addresses(raw_site)
            if coords:
                lat, lon = coords
                location_label = str(raw_site.get("site_name") or "").strip() or location_label
    if lat is None:
        trailer_coords, trailer = _coords_from_trailer_component(unit_key, subject_text)
        if trailer_coords:
            lat, lon = trailer_coords
            location_label = trailer or location_label

    forecast = None
    weather_error = None
    if lat is not None:
        forecast, weather_error = _fetch_open_meteo_daily_outlook(lat, lon)
    else:
        weather_error = "No GPS on site address or trailer"

    cloudy_days = sum(1 for day in (forecast or []) if day.get("cloudy"))
    total_days = len(forecast or [])
    risk = None
    if battery_soc_percent is not None and forecast:
        if battery_soc_percent < 40 and cloudy_days >= 3:
            risk = "high"
        elif battery_soc_percent < 60 and cloudy_days >= 2:
            risk = "elevated"
        else:
            risk = "low"

    summary_parts = [f"Battery SOC {battery_soc_percent:g}%"]
    if forecast:
        summary_parts.append(f"{cloudy_days}/{total_days} cloudy day(s) ahead at {location_label}")
    if risk:
        summary_parts.append(f"risk: {risk}")
    summary = f"{unit_key} — " + ", ".join(summary_parts)

    return {
        "unit": unit_key,
        "installation_name": installation_name,
        "battery_soc_percent": battery_soc_percent,
        "location": location_label,
        "forecast": forecast,
        "cloudy_days": cloudy_days,
        "forecast_days": total_days,
        "risk": risk,
        "weather_error": weather_error,
        "summary": summary,
    }, None
# One VRM attribute code per chart the UI offers. VRM's own single-letter/
# short codes (bv, bs, ...) aren't something a NOC tech should have to know,
# so the UI only ever sees these keys and labels.
BATTERY_HISTORY_METRICS = {
    "voltage": {"code": "bv", "label": "Battery Voltage", "unit": "V"},
    "soc": {"code": "bs", "label": "Battery SOC", "unit": "%"},
    "current": {"code": "bc", "label": "Battery Current", "unit": "A"},
    "pv_power": {"code": "PVP", "label": "Solar (PV) Power", "unit": "W"},
}
def unit_battery_history(unit, hours=24, subject=""):
    """
    Time-series for a trailer's battery voltage/SOC/current/solar power, via
    VRM's /stats endpoint — one request, several attribute codes, real
    historical data (not just the instant-snapshot /diagnostics call the
    other battery features use). Returns (info, error).
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None, f"Invalid unit: {unit}"
    try:
        hours = max(1, min(int(hours), 24 * 30))
    except (TypeError, ValueError):
        hours = 24

    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error
    site_id, installation_name, site_error = _resolve_vrm_site(
        unit_key, str(subject or "").strip(), id_user, victron_token
    )
    if site_error:
        return None, site_error

    end = int(time.time())
    start = end - hours * 3600
    # 15-minute buckets up to 2 days, hourly beyond that — otherwise a
    # 30-day window would ask VRM for ~2900 points per metric.
    interval = "15mins" if hours <= 48 else "hours"
    params = [("type", "custom"), ("start", start), ("end", end), ("interval", interval)]
    for metric in BATTERY_HISTORY_METRICS.values():
        params.append(("attributeCodes[]", metric["code"]))

    try:
        stats_resp = requests.get(
            f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/stats",
            headers={"idSite": str(site_id), "X-Authorization": f"Token {victron_token}"},
            params=params,
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, f"VRM stats lookup failed: {exc}"
    if stats_resp.status_code != 200:
        return None, f"VRM stats lookup failed: HTTP {stats_resp.status_code}"
    payload = stats_resp.json() or {}
    if not payload.get("success"):
        return None, "VRM stats lookup did not succeed"

    records = payload.get("records") or {}
    charts = {}
    for key, metric in BATTERY_HISTORY_METRICS.items():
        series = records.get(metric["code"]) or []
        # VRM returns [timestamp_ms, value] or [timestamp_ms, avg, min, max];
        # the average (second element) is what every chart here plots.
        points = [
            {"t": point[0], "v": point[1]}
            for point in series
            if isinstance(point, list) and len(point) >= 2 and point[1] is not None
        ]
        values = [p["v"] for p in points]
        charts[key] = {
            "label": metric["label"],
            "unit": metric["unit"],
            "points": points,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "latest": values[-1] if values else None,
        }

    return {
        "unit": unit_key,
        "installation_name": installation_name,
        "hours": hours,
        "interval": interval,
        "charts": charts,
    }, None
def _vrm_diagnostic_alarm_detail(site_id, victron_token):
    """Fetch one site's full /diagnostics and return its first active alarm's
    description, or None. Used only for the (small) set of sites that the
    cheap fleet call already flagged alarm=true — see vrm_active_alarms_by_unit."""
    try:
        response = requests.get(
            f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/diagnostics",
            headers={"idSite": str(site_id), "X-Authorization": f"Token {victron_token}"},
            timeout=20,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    for record in (response.json().get("records") or []):
        description = str(record.get("description") or "")
        value = str(record.get("formattedValue") or "").strip().lower()
        if "alarm" in description.lower() and value not in ("", "no alarm"):
            return description
    return None
def vrm_active_alarms_by_unit(max_age_hours=6):
    """
    Every VRM installation currently reporting alarm=true, fleet-wide.

    Two stages, kept cheap: one bulk call (installations?extended=1) finds
    every alarm=true, recently-reporting site — usually a few dozen out of
    the whole fleet — then only THOSE sites get a follow-up /diagnostics
    call (concurrent) for the specific alarm text, since the bulk call's
    extended attributes don't reliably carry it. Installations that haven't
    reported in max_age_hours are dropped before that follow-up: some
    alarm=true sites are long-dead test installations (one hadn't reported
    in ~236 days when this was checked live), not real current alerts.
    Returns ({installation_name: {...}}, error).
    """
    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error
    try:
        response = requests.get(
            f"https://vrmapi.victronenergy.com/v2/users/{id_user}/installations",
            headers={"idUser": id_user, "X-Authorization": f"Token {victron_token}"},
            params={"extended": 1},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, f"VRM installations lookup failed: {exc}"
    if response.status_code != 200:
        return None, f"VRM installations lookup failed: HTTP {response.status_code}"

    now = time.time()
    cutoff = now - max_age_hours * 3600
    candidates = []
    for record in (response.json().get("records") or []):
        if not record.get("alarm"):
            continue
        last_timestamp = record.get("last_timestamp") or 0
        if last_timestamp < cutoff:
            continue
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        extended = record.get("extended") or []
        soc = next((item.get("formattedValue") for item in extended if item.get("code") == "bs"), None)
        candidates.append({
            "installation_name": name,
            "site_id": record.get("idSite"),
            "battery_soc": soc,
            "last_seen_age_minutes": round((now - last_timestamp) / 60) if last_timestamp else None,
        })

    if candidates:
        with ThreadPoolExecutor(max_workers=min(10, len(candidates))) as pool:
            details = list(pool.map(
                lambda c: _vrm_diagnostic_alarm_detail(c["site_id"], victron_token),
                candidates,
            ))
        for candidate, detail in zip(candidates, details):
            candidate["alarm_detail"] = detail or "Alarm active (no matching detail on follow-up read)"

    return {c["installation_name"]: c for c in candidates}, None
