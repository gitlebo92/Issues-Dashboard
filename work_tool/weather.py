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
    _erp_heads_for_mu_trailers,
    _fetch_erp_component_site_map,
    _fetch_erp_site_doc_raw,
    _fetch_mu_component_doc,
    _normalize_netsheet_unit,
    _sc_component_name,
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
# How stale a VRM reading has to be before it stops counting as "current
# evidence" — derived from a live fleet-wide check (2026-09-13), not
# guessed: 249 installations' last-report ages formed two clean clusters —
# 174 within 10 minutes (median 5.3min — normal realtime reporting) and a
# long-dead tail of decommissioned/test sites starting around 2 days out —
# with a complete gap in between (nothing reported between 10 minutes and
# 2 hours ago at the moment this was checked). That gap is what the tiers
# below are built around: FRESH covers normal reporting with headroom,
# AGING is the "one or two missed check-ins" zone that gap implies should
# be rare and brief, STALE is long enough that something is actually
# wrong, and DISCONNECTED is a full day of silence.
_VRM_FRESH_SEC = 10 * 60
_VRM_AGING_SEC = 2 * 3600
_VRM_STALE_SEC = 24 * 3600
def _vrm_freshness_tier(age_seconds):
    """FRESH / AGING / STALE / DISCONNECTED / UNKNOWN from a data age in seconds."""
    if age_seconds is None:
        return "unknown"
    if age_seconds <= _VRM_FRESH_SEC:
        return "fresh"
    if age_seconds <= _VRM_AGING_SEC:
        return "aging"
    if age_seconds <= _VRM_STALE_SEC:
        return "stale"
    return "disconnected"
def _format_age(age_seconds):
    """12 minutes / 3.4 hours / 5.2 days / 6.1 months — whatever unit reads most naturally."""
    if age_seconds is None:
        return "an unknown amount of time"
    seconds = max(0, age_seconds)
    if seconds < 3600:
        return f"{round(seconds / 60)} minute{'s' if round(seconds / 60) != 1 else ''}"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} hours"
    if seconds < 86400 * 45:
        return f"{seconds / 86400:.1f} days"
    return f"{seconds / (86400 * 30):.1f} months"
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

    extended=1 costs nothing extra here (same one bulk call, one more query
    param) but is what carries each site's last_timestamp — without it,
    callers have no way to know whether the /diagnostics reading they're
    about to fetch reflects a site that's currently reporting at all. It's
    also where the installation's own IANA timezone name comes from
    (VRM tracks this per-site, free on this same call) — used to show a
    shading dip's time window in local time instead of raw UTC.
    Returns (site_id, installation_name, last_seen_seconds_ago, timezone_name, error).
    """
    mu_code = resolve_attached_mu_code(unit_key, subject)
    if not mu_code:
        return None, None, None, None, f"{unit_key} has no attached MU trailer — nothing to look up in VRM"

    try:
        installations_resp = requests.get(
            f"https://vrmapi.victronenergy.com/v2/users/{id_user}/installations",
            headers={"idUser": id_user, "X-Authorization": f"Token {victron_token}"},
            params={"extended": 1},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, None, None, None, f"VRM installations lookup failed: {exc}"
    if installations_resp.status_code != 200:
        return None, None, None, None, f"VRM installations lookup failed: HTTP {installations_resp.status_code}"

    for record in (installations_resp.json().get("records") or []):
        name = str(record.get("name") or "").strip()
        if name.upper() == mu_code.upper():
            last_timestamp = record.get("last_timestamp") or None
            last_seen_seconds_ago = (time.time() - last_timestamp) if last_timestamp else None
            timezone_name = str(record.get("timezone") or "").strip() or None
            return record.get("idSite"), name, last_seen_seconds_ago, timezone_name, None
    return None, None, None, None, f"No VRM installation named {mu_code} (attached trailer for {unit_key})"
def _vrm_pv_history_points(site_id, victron_token, days, end=None):
    """
    Hourly PVP (solar power) points over the last `days`. Shared by the
    AC-power solar-ceiling fallback and the shading-dip detector below —
    both need "what has this trailer's solar produced, hour by hour,
    recently" and differ only in what they do with it. Returns a list of
    (timestamp_ms, watts) or None on any failure (network, non-success
    response, or no data at all) — callers treat None the same as "can't
    tell," never as "confirmed zero."
    """
    end = end if end is not None else int(time.time())
    try:
        response = requests.get(
            f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/stats",
            headers={"idSite": str(site_id), "X-Authorization": f"Token {victron_token}"},
            params=[
                ("type", "custom"), ("start", end - days * 24 * 3600), ("end", end),
                ("interval", "hours"), ("attributeCodes[]", "PVP"),
            ],
            timeout=30,
        )
        payload = response.json()
    except requests.RequestException:
        return None
    if not payload.get("success"):
        return None
    series = payload.get("records", {}).get("PVP") or []
    points = [(p[0], p[1]) for p in series if isinstance(p, list) and p[1] is not None]
    return points or None


def _vrm_pv_ceiling_by_hour(pv_points, hour_tolerance=1):
    """
    (ceiling_by_hour, flat_ceiling) from a list of (timestamp_ms, watts)
    points — the max PVP ever seen in each UTC hour, +/-hour_tolerance, plus
    the flat all-time max as a fallback for hours with no history at all.
    Bucketing by UTC hour (not local time) keeps this internally consistent
    without needing to know the site's actual timezone: a fixed UTC offset
    cancels out as long as every comparison uses the same one.
    """
    flat_ceiling = max((v for _, v in pv_points), default=0)
    ceiling_by_hour = {}
    for t, value in pv_points:
        hour = datetime.utcfromtimestamp(t / 1000).hour
        for offset in range(-hour_tolerance, hour_tolerance + 1):
            bucket = (hour + offset) % 24
            if value > ceiling_by_hour.get(bucket, 0):
                ceiling_by_hour[bucket] = value
    return ceiling_by_hour, flat_ceiling


def _vrm_pv_typical_by_hour(pv_points, hour_tolerance=1):
    """
    typical_by_hour from a list of (timestamp_ms, watts) points — the
    MEDIAN of non-zero PVP readings seen in each UTC hour, +/-hour_tolerance.

    Deliberately the median, not the max (_vrm_pv_ceiling_by_hour above,
    which the AC-power spike check correctly wants as a strict upper
    bound). Checked live (2026-09-13) running a fleet-wide shading pass:
    ~58% of the fleet came back "shaded," almost entirely at dawn/dusk
    hours. A max-based ceiling at a twilight hour is set by whichever
    single day in the window happened to have the earliest sunrise/latest
    sunset — one MU1002 hour had a 117W max ceiling made of one outlier
    reading, while the other 20 days in the same window never broke 63W in
    that hour. Every normal day then reads as "way below ceiling" by
    comparison — the false positive was in the ceiling, not the shading
    check's logic. The median is robust to that one-off day and reflects
    what the hour actually, typically looks like.
    """
    from statistics import median
    by_hour_values = {}
    for t, value in pv_points:
        if value <= 0:
            continue
        hour = datetime.utcfromtimestamp(t / 1000).hour
        for offset in range(-hour_tolerance, hour_tolerance + 1):
            bucket = (hour + offset) % 24
            by_hour_values.setdefault(bucket, []).append(value)
    return {hour: median(values) for hour, values in by_hour_values.items()}


# How far below its own hour-of-day TYPICAL output (median, not max — see
# _vrm_pv_typical_by_hour) a reading has to fall before it counts as a
# shading dip rather than ordinary cloud-driven variance. Checked live
# against a real "shaded" ERP ticket (RD3421/MU8064, ISS-2026-10642, opened
# 2026-08-26): the day the ticket was filed, several daylight hours read
# 6-37% of what that same trailer typically produced in those same hours on
# other days — comfortably past this cutoff.
_SHADE_DEFICIT_RATIO = 0.35
# Only judge hours this trailer's own history shows are genuinely, TYPICALLY
# productive — a low ratio against a near-zero median is meaningless noise,
# not shading. Raised from an earlier max-based 100W after the false-positive
# finding above: a median-based baseline runs lower than a max-based one for
# the same hour by construction, so this needed to move too. 150W sits above
# every dawn/dusk median observed live (all under 110W) and comfortably below
# a real midday median (200W+ on the same units).
_SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS = 150
# A single noisy sample shouldn't read as "shaded" — require the deficit to
# hold for at least this many consecutive readings.
_SHADE_MIN_CONSECUTIVE_POINTS = 2
# SHADED_V2 (2026-09-13 rule-improvement pass): moving shade (a tree branch
# in wind, a passing cloud edge) can produce one brief non-dip reading in
# the middle of an otherwise-real shading run — a strict "any non-dip
# breaks the run" rule was too easily defeated by that flicker. Each real
# dip earns exactly one grace point that tolerates the very next reading
# even if it isn't itself a dip; a second consecutive non-dip still ends
# the run. Deliberately NOT the looser "2 of any 4 readings" a sliding-
# window count would give — that let a run drift forward through readings
# nowhere near shaded once two dips happened to be anywhere in its recent
# past (checked against this file's own fixtures: it stretched the classic
# morning-ramp case forward through two fully-normal hours). One grace
# point per dip stays bounded and self-corrects the moment shading
# actually stops.
_SHADE_FLICKER_TOLERANCE = 1
# SHADED_V2: how much of the WHOLE ceiling_days baseline has to also read
# as a dip at the run's worst hour before this stops looking like a new,
# transient dip and starts looking like it's been there the entire
# window — see detect_solar_shading's exclusion and
# detect_persistent_obstruction (PERSISTENT_OBSTRUCTION_V1) below.
_SHADE_PERSISTENT_EXCLUSION_DAY_FRACTION = 0.80
# SHADED_V2: how close to its own typical a neighboring hour has to hold
# for the deficit to count as angle-dependent (shading) rather than
# hour-independent (more consistent with hardware — see detect_dead_panel's
# mirror-image proportional-loss check).
_SHADE_ANGLE_DEPENDENCE_NEIGHBOR_RATIO = 0.70


def _find_shading_dip_run(points, typical_by_hour):
    """
    Pure logic half of detect_solar_shading, split out so it's testable
    without a live VRM call: given chronological (timestamp_ms, watts)
    points and an hour -> typical-watts map (see _vrm_pv_typical_by_hour),
    find the longest contiguous run of points where watts fall below
    _SHADE_DEFICIT_RATIO of that hour's typical output, restricted to hours
    whose typical output clears _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS (skips
    dawn/dusk/night hours, where a low ratio against a near-zero baseline is
    meaningless). Tolerates a single non-dip reading immediately after a
    real dip (see _SHADE_FLICKER_TOLERANCE) so one flickery recovery point
    doesn't split an otherwise-continuous shading run in two. Returns a
    list of (t, value, typical) tuples — empty if nothing qualifies; a
    tolerated non-dip point is included (it's part of the shaded window),
    but never counts as the run's OWN dip evidence on its own.
    """
    run = []
    best_run = []
    gap_budget = 0
    for t, value in sorted(points):
        hour = datetime.utcfromtimestamp(t / 1000).hour
        typical = typical_by_hour.get(hour, 0)
        is_dip = typical >= _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS and value < typical * _SHADE_DEFICIT_RATIO
        if is_dip:
            run.append((t, value, typical))
            gap_budget = _SHADE_FLICKER_TOLERANCE
        elif run and gap_budget > 0:
            run.append((t, value, typical))
            gap_budget -= 1
        else:
            if len(run) > len(best_run):
                best_run = run
            run = []
            gap_budget = 0
    if len(run) > len(best_run):
        best_run = run
    return best_run


def detect_solar_shading(site_id, victron_token, ceiling_days=21, recent_hours=30, hour_tolerance=1):
    """
    Look for a run of solar-power readings well below what this trailer's
    own recent history says that hour normally produces — the telemetry
    signature of something (a tree, a building, another structure) casting
    a shadow across the panels during hours they'd otherwise be productive.

    Deliberately NOT "does wattage look low right now" against some fixed
    number — panel count and site conditions vary per trailer (checked
    across 176 real installations building the AC-power fallback above),
    so the only fair comparison is a trailer against its own history, the
    same principle _vrm_pv_ceiling_and_recent_spike already uses, just
    checking for a deficit instead of a spike.

    Real limitation, stated plainly rather than papered over: a widely
    overcast day depresses every hour at once and would also show a low
    ratio here — this function cannot distinguish "this trailer is shaded"
    from "it is cloudy everywhere today" on telemetry alone. Confidence is
    deliberately capped well short of certain to reflect that; the caller
    should treat this as "worth a look," not a confirmed diagnosis.

    Returns (found, detail, confidence, window) where found is True/False
    (None on a data problem — see _vrm_pv_history_points) and window is
    None or {"start_ts_ms", "end_ts_ms", "hours_utc"} — the dip's own
    start/end (it's a contiguous run by construction, not just a sample of
    hours it touched), for the caller to render as an actual time window
    rather than a single "worst" instant.
    """
    ceiling_points = _vrm_pv_history_points(site_id, victron_token, ceiling_days)
    if not ceiling_points:
        return None, "No solar-power history available to build a baseline", None, None
    typical_by_hour = _vrm_pv_typical_by_hour(ceiling_points, hour_tolerance)

    # _vrm_pv_history_points fetches in whole days; round up and add a day
    # of buffer so a sub-24h or non-whole-day recent_hours still gets full
    # coverage, then filter down to the exact cutoff below.
    recent_fetch_days = -(-recent_hours // 24) + 1
    recent_points = _vrm_pv_history_points(site_id, victron_token, days=recent_fetch_days)
    if not recent_points:
        return None, "No recent solar-power data available to check for shading", None, None
    cutoff = int(time.time()) - recent_hours * 3600
    recent_points = [(t, v) for t, v in recent_points if t / 1000 >= cutoff]
    if not recent_points:
        return None, "No solar-power data in the requested recent window", None, None

    best_run = _find_shading_dip_run(recent_points, typical_by_hour)

    if len(best_run) < _SHADE_MIN_CONSECUTIVE_POINTS:
        return False, (
            f"No sustained solar-power deficit found in the last {recent_hours}h "
            f"(checked against this trailer's own {ceiling_days}-day hour-of-day typical output)"
        ), None, None

    worst = min(best_run, key=lambda row: row[1] / row[2])
    worst_t, worst_value, worst_typical = worst
    worst_ratio = worst_value / worst_typical
    worst_hour = datetime.utcfromtimestamp(worst_t / 1000).hour

    # best_run is contiguous by construction (a non-dip point resets the run),
    # so its first/last points ARE the dip's actual time window, not just a
    # sample of hours it touched. worst_hour_utc is the single deepest point
    # in that window — the hour a scheduled snapshot should aim for, not
    # just any hour the dip touched.
    window = {
        "start_ts_ms": best_run[0][0],
        "end_ts_ms": best_run[-1][0],
        "hours_utc": sorted({datetime.utcfromtimestamp(t / 1000).hour for t, _, _ in best_run}),
        "worst_hour_utc": worst_hour,
    }

    # SHADED_V2 exclusion: if the worst hour ALSO reads as a dip on most
    # days across the whole ceiling_days baseline (not just the recent
    # window this run came from), it didn't just start — it's been there
    # the whole time this function has history for. That's
    # PERSISTENT_OBSTRUCTION_V1's territory (a fixed obstruction), not a
    # new transient shading event, so decline rather than mislabel it.
    #
    # Deliberately compares against this hour's own MAX-ever reading
    # (ceiling), not the median typical used above — a majority of days
    # can never read below a fraction of their own MEDIAN by definition
    # (that's what a median is), so a median-based version of this check
    # could never actually fire above ~50%. The ceiling doesn't have that
    # problem: a chronically-obstructed hour can sit well below its own
    # best-ever day on 80%+ of days without contradiction.
    ceiling_by_hour_for_exclusion, _ = _vrm_pv_ceiling_by_hour(ceiling_points, hour_tolerance)
    worst_hour_ceiling = ceiling_by_hour_for_exclusion.get(worst_hour, worst_typical)
    by_day_worst_hour = {}
    for t, v in ceiling_points:
        if datetime.utcfromtimestamp(t / 1000).hour != worst_hour:
            continue
        day = datetime.utcfromtimestamp(t / 1000).date()
        by_day_worst_hour[day] = max(by_day_worst_hour.get(day, 0), v)
    total_days_observed = len(by_day_worst_hour)
    persistent_dip_days = sum(
        1 for v in by_day_worst_hour.values() if v < worst_hour_ceiling * _SHADE_DEFICIT_RATIO
    )
    if (
        total_days_observed
        and persistent_dip_days / total_days_observed >= _SHADE_PERSISTENT_EXCLUSION_DAY_FRACTION
    ):
        return False, (
            f"Hour {worst_hour}:00 (UTC) reads this low on {persistent_dip_days} of "
            f"{total_days_observed} day(s) in the {ceiling_days}d baseline itself, not just the recent "
            f"window — this predates any recent change, so it's not a new transient dip. Check for a "
            f"persistent obstruction at that hour instead"
        ), None, None

    # utcfromtimestamp, not fromtimestamp — this box's local clock is
    # US Mountain (UTC-7 year-round, same as Arizona), which happens to
    # equal Pacific Daylight Time's offset in September and would silently
    # mislabel every other timezone (including Mountain itself once DST
    # elsewhere shifts) as "UTC" if plain fromtimestamp were used here.
    start_when = datetime.utcfromtimestamp(window["start_ts_ms"] / 1000).strftime("%Y-%m-%d %H:%M")
    end_when = datetime.utcfromtimestamp(window["end_ts_ms"] / 1000).strftime("%Y-%m-%d %H:%M")
    # Confidence scales with how deep the deficit ran and how long it held —
    # a two-point dip to 30% of typical is weaker evidence than an
    # eight-point dip to 5%. Capped below the AC-power checks' ceiling
    # (see docstring: cloud cover is an unresolved confound here) and
    # floored above pure noise.
    depth_score = max(0, (_SHADE_DEFICIT_RATIO - worst_ratio) / _SHADE_DEFICIT_RATIO)
    length_score = min(1.0, len(best_run) / 8)
    confidence = round(35 + depth_score * 30 + length_score * 15)

    # SHADED_V2 signal: does the deficit vary across surrounding hours
    # (angle-dependent — the shading signature) or hit the neighbors about
    # as hard (more consistent with a uniform, hour-independent cause —
    # see detect_dead_panel's own proportional-loss check for the mirror
    # image of this same idea)? Only speaks up when there's actual recent
    # data for a neighbor hour to compare; silent otherwise rather than
    # guessing.
    recent_by_hour = {}
    for t, v in recent_points:
        recent_by_hour[datetime.utcfromtimestamp(t / 1000).hour] = v
    neighbor_ratios = []
    for neighbor_hour in (worst_hour - 1, worst_hour + 1):
        neighbor_hour %= 24
        neighbor_typical = typical_by_hour.get(neighbor_hour, 0)
        neighbor_value = recent_by_hour.get(neighbor_hour)
        if neighbor_typical >= _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS and neighbor_value is not None:
            neighbor_ratios.append(neighbor_value / neighbor_typical)
    angle_dependence_note = ""
    if neighbor_ratios:
        neighbor_avg_ratio = sum(neighbor_ratios) / len(neighbor_ratios)
        if neighbor_avg_ratio >= _SHADE_ANGLE_DEPENDENCE_NEIGHBOR_RATIO:
            confidence = min(95, confidence + 10)
            angle_dependence_note = (
                f" Neighboring hours held {round(neighbor_avg_ratio * 100)}% of their own typical — "
                f"angle-dependent, consistent with shading rather than a hardware-wide loss."
            )
        elif neighbor_avg_ratio < _SHADE_DEFICIT_RATIO:
            confidence = max(20, confidence - 10)
            angle_dependence_note = (
                f" Neighboring hours are also running low ({round(neighbor_avg_ratio * 100)}% of "
                f"typical) — worth checking for a hardware-wide cause (see the dead-panel check) "
                f"rather than assuming shading alone."
            )

    detail = (
        f"Solar power ran {round(worst_ratio * 100)}% or less of this trailer's own hour-of-day "
        f"typical output from {start_when} to {end_when} (UTC) — worst point {round(worst_value)}W vs a "
        f"typical {round(worst_typical)}W for that hour (observed over {ceiling_days}d) — "
        f"consistent with shading, but a broadly cloudy day would look similar."
        f"{angle_dependence_note}"
    )
    return True, detail, confidence, window


# PERSISTENT_OBSTRUCTION_V1 (2026-09-13 rule-improvement pass): a fixed
# obstruction (a building, another trailer, a sign) that has been blocking
# one specific sun-angle hour for the ENTIRE lookback window is invisible
# to detect_solar_shading above — that function's baseline is this same
# hour's own history, and if the obstruction predates the whole window,
# the "typical" for that hour already reflects the blockage. There is no
# dip to find against a baseline that's already suppressed.
#
# This compares a day's reading at hour h against its IMMEDIATE NEIGHBOR
# HOURS' reading THE SAME DAY instead of against hour h's own history — a
# fixed obstruction depresses one hour's angle to the sun without touching
# the hours right next to it, and unlike a passing cloud, it does this on
# nearly every clear day, not an occasional one.
_OBSTRUCTION_RATIO = 0.60
# A neighbor only counts as a fair "what a normal day looks like" baseline
# if it itself reached close to its own typical that day — otherwise the
# whole day (not just hour h) was cloudy, and that's not evidence of a
# fixed obstruction.
_OBSTRUCTION_NEIGHBOR_NORMAL_RATIO = 0.85
# How much of hour h's history has to fit the pattern before this reads as
# a real, standing obstruction rather than a handful of coincidentally bad
# days. ~18 of 21 days, expressed as a fraction so it scales with a
# different `days` argument.
_OBSTRUCTION_MIN_DAY_FRACTION = 18 / 21
# Need enough "clean" (neighbors-normal) days to trust the pattern at all —
# a handful of clean days out of 21 isn't enough to say anything.
_OBSTRUCTION_MIN_CLEAN_DAYS = 10


def detect_persistent_obstruction(site_id, victron_token, days=21, hour_tolerance=0):
    """
    Looks for an hour that reads persistently low against its OWN
    IMMEDIATE NEIGHBOR HOURS on the same day, across most of the last
    `days` — the signature of a fixed obstruction that predates the whole
    lookback window (see the module comment above for why
    detect_solar_shading can't see this case).

    Real limitations, stated plainly rather than papered over:
    - Works best away from the steep morning/evening ramp, where adjacent
      hours can legitimately differ a lot with no obstruction at all — a
      false positive there (mistaking normal ramp shape for obstruction)
      is the likeliest failure mode of this specific check.
    - Validated so far against exactly ONE real case (RD3439/MU8024,
      2026-09-13) — treat the specific day-count and ratio cutoffs
      (_OBSTRUCTION_RATIO, _OBSTRUCTION_MIN_DAY_FRACTION) as provisional
      until a second confirmed example is checked against them.
    - Not currently wired into any fleet report or Commands-menu button —
      reachable directly for now, pending that second real example.

    Returns (found, detail, confidence, info).
    """
    points = _vrm_pv_history_points(site_id, victron_token, days)
    if not points:
        return None, "No solar-power history available", None, None
    typical_by_hour = _vrm_pv_typical_by_hour(points, hour_tolerance)
    # Neighbors have to be reliably productive on their OWN history
    # (median-based) to serve as a trustworthy same-day reference. The
    # CANDIDATE hour itself deliberately does NOT use this same median
    # gate below — if it's obstructed on a majority of days, its own
    # median is already dragged down by the very thing being detected, so
    # gating candidacy on it would make an obstruction present on >50% of
    # days undetectable by construction. Its own best-ever (ceiling)
    # reading is used for candidacy instead.
    productive_hours = {
        hour for hour, watts in typical_by_hour.items() if watts >= _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS
    }
    ceiling_by_hour, _ = _vrm_pv_ceiling_by_hour(points, hour_tolerance)
    candidate_hours = {
        hour for hour, watts in ceiling_by_hour.items() if watts >= _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS
    }
    if len(candidate_hours) < 3:
        return None, (
            "Not enough productive hours in this trailer's own history to compare hour-to-hour"
        ), None, None

    # This day's reading at each hour — the max, if more than one point
    # landed in the same hour bucket, matching this file's other
    # peak-style day/hour groupings.
    value_by_day_hour = {}
    for t, v in points:
        dt = datetime.utcfromtimestamp(t / 1000)
        day_values = value_by_day_hour.setdefault(dt.date(), {})
        day_values[dt.hour] = max(day_values.get(dt.hour, 0), v)

    best = None  # (hour, obstructed_days, clean_days, avg_ratio)
    for hour in sorted(candidate_hours):
        neighbors = [h for h in (hour - 1, hour + 1) if h in productive_hours]
        if len(neighbors) < 2:
            # Only judge hours with a REAL neighbor on both sides — an
            # edge hour with just one neighbor is too easy to fool with
            # ordinary sunrise/sunset ramp shape.
            continue
        clean_days = 0
        obstructed_days = 0
        ratios = []
        for hours_map in value_by_day_hour.values():
            if hour not in hours_map or any(n not in hours_map for n in neighbors):
                continue
            if not all(
                hours_map[n] >= typical_by_hour[n] * _OBSTRUCTION_NEIGHBOR_NORMAL_RATIO
                for n in neighbors
            ):
                continue  # not a clean comparison day — a neighbor was itself low
            clean_days += 1
            neighbor_avg = sum(hours_map[n] for n in neighbors) / len(neighbors)
            ratio = hours_map[hour] / neighbor_avg if neighbor_avg else 1.0
            ratios.append(ratio)
            if ratio < _OBSTRUCTION_RATIO:
                obstructed_days += 1
        if clean_days < _OBSTRUCTION_MIN_CLEAN_DAYS:
            continue
        if obstructed_days / clean_days < _OBSTRUCTION_MIN_DAY_FRACTION:
            continue
        candidate = (hour, obstructed_days, clean_days, sum(ratios) / len(ratios))
        if best is None or obstructed_days > best[1]:
            best = candidate

    if best is None:
        return False, (
            f"No hour reads persistently low against its own immediate neighbor hours across the "
            f"{days}d window"
        ), None, None

    hour, obstructed_days, clean_days, avg_ratio = best
    confidence = max(30, min(80, round(30 + (obstructed_days / clean_days) * 40 + (1 - avg_ratio) * 20)))
    detail = (
        f"Hour {hour}:00 (UTC) read under {round(_OBSTRUCTION_RATIO * 100)}% of its immediate neighbor "
        f"hours' own same-day output on {obstructed_days} of {clean_days} clean-weather day(s) in the "
        f"last {days}d — consistent with a fixed obstruction at that specific sun angle that predates "
        f"this whole window, not a new or weather-driven dip. Validated against limited real data so "
        f"far — worth a look, not a confirmed diagnosis."
    )
    info = {
        "hour_utc": hour,
        "obstructed_days": obstructed_days,
        "clean_days_observed": clean_days,
        "average_ratio_vs_neighbors": round(avg_ratio, 3),
        "window_days": days,
    }
    return True, detail, confidence, info


def verify_shading_dip_now(unit_key, subject_text, hour_utc, ceiling_days=21):
    """
    Lightweight, single-point re-check for the shading-snapshot scheduler
    (work_tool.shading_snapshots): is this trailer's solar reading, RIGHT
    NOW, still consistent with a dip at hour_utc? A snapshot task already
    knows which hour to aim for (the worst hour from a past
    detect_solar_shading run); before spending a camera fetch on it, this
    confirms the dip is actually happening THIS occurrence too — the
    shading pattern may have moved, cleared, or that specific day may just
    be generally cloudy in a way that isn't really "shading" at all.

    Reuses the same ratio/threshold detect_solar_shading itself uses
    (_SHADE_DEFICIT_RATIO, _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS) so a
    verified "yes" here means the same thing a fresh detection would have
    found, just cheaper (one short recent-history call instead of a full
    ceiling+run search).

    Returns (is_dip, detail, current_watts, typical_watts). is_dip is None
    on a data problem (no credentials, no VRM site, no usable history) —
    never treated as "dip confirmed."
    """
    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error, None, None
    site_id, installation_name, _last_seen, _tz, site_error = _resolve_vrm_site(
        unit_key, subject_text, id_user, victron_token
    )
    if site_error:
        return None, site_error, None, None

    ceiling_points = _vrm_pv_history_points(site_id, victron_token, ceiling_days)
    if not ceiling_points:
        return None, "No solar-power history available to verify against", None, None
    typical_by_hour = _vrm_pv_typical_by_hour(ceiling_points)
    typical = typical_by_hour.get(hour_utc, 0)
    if typical < _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS:
        return None, f"Hour {hour_utc}:00 (UTC) isn't a productive hour in this trailer's own history", None, round(typical)

    recent_points = _vrm_pv_history_points(site_id, victron_token, days=1)
    if not recent_points:
        return None, "No current solar-power reading available", None, round(typical)
    # Prefer a reading whose OWN hour is the one being checked — the
    # scheduler's fetch can land a little early or late relative to the
    # scheduled minute; falling back to the single newest point overall
    # only if nothing landed in the target hour yet.
    same_hour_points = [
        (t, v) for t, v in recent_points if datetime.utcfromtimestamp(t / 1000).hour == hour_utc
    ]
    newest_t, newest_value = max(same_hour_points or recent_points, key=lambda p: p[0])
    is_dip = newest_value < typical * _SHADE_DEFICIT_RATIO
    ratio_pct = round(newest_value / typical * 100) if typical else 0
    detail = (
        f"Current reading {round(newest_value)}W vs this hour's typical {round(typical)}W "
        f"({ratio_pct}%) — {'dip confirmed' if is_dip else 'no dip right now'}"
    )
    return is_dip, detail, round(newest_value), round(typical)


def _vrm_pv_ceiling_and_recent_spike(
    site_id, victron_token, ceiling_days=21, recent_hours=48, margin=1.15, hour_tolerance=1
):
    """
    Fallback AC-power inference for units where the charger device is
    missing or its reading disagreed with AC current — checked live
    against 176 real installations before building this: panel count
    varies per trailer (2/3/4 panels seen) and isn't reliably guessable
    from the unit number, so instead of assuming a wattage, this uses
    what the trailer's own solar has actually produced.

    The ceiling is bucketed by hour-of-day, not one flat all-day number —
    solar at 7am/7pm can't reach anywhere near a midday peak even on a
    perfect day, so comparing an evening reading to the all-day max makes
    the test needlessly insensitive right when a real AC session is most
    likely (early morning/evening service visits). Each hour's ceiling is
    the max PVP seen in that hour +/-hour_tolerance across ceiling_days —
    the tolerance widens the sample per bucket without smearing the
    profile flat. Bucketing is by UTC hour on both the ceiling and the
    recent-window side, so it's internally consistent without needing to
    know the site's actual timezone — a fixed UTC offset cancels out as
    long as both sides use the same one.

    Checks recent_hours of battery charge power (voltage x current)
    against each point's own hour-of-day ceiling. No caching — both
    windows are pulled fresh every call. Returns (status, detail,
    confidence, has_recent_data):
      - ("present", detail, confidence, True) if a qualifying reading was found
      - (None, detail, None, True) if the window had data but nothing
        exceeded its ceiling — real (if soft) evidence, since it means
        this trailer's battery-current telemetry IS currently reporting
        and simply isn't showing an AC-sized draw
      - (None, detail, None, False) if the window had NO data at all in
        the last day — this is NOT evidence of anything; it means VRM
        itself has nothing recent to check, which is a data-freshness
        problem, not a "not plugged in" finding. Callers must not treat
        this the same as the case above (see _vrm_power_snapshot).
    """
    end = int(time.time())
    headers = {"idSite": str(site_id), "X-Authorization": f"Token {victron_token}"}

    pv_points = _vrm_pv_history_points(site_id, victron_token, ceiling_days, end=end)
    if not pv_points:
        return None, None, None, False
    ceiling_by_hour, flat_ceiling = _vrm_pv_ceiling_by_hour(pv_points, hour_tolerance)

    try:
        recent_resp = requests.get(
            f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/stats",
            headers=headers,
            params=[
                ("type", "custom"), ("start", end - recent_hours * 3600), ("end", end),
                ("interval", "15mins"), ("attributeCodes[]", "bc"), ("attributeCodes[]", "bv"),
            ],
            timeout=30,
        )
        recent_payload = recent_resp.json()
    except requests.RequestException:
        return None, None, None, False
    if not recent_payload.get("success"):
        return None, None, None, False
    recent_records = recent_payload.get("records", {})
    bc_series = recent_records.get("bc") or []
    bv_by_t = {
        p[0]: p[1] for p in (recent_records.get("bv") or [])
        if isinstance(p, list) and p[1] is not None
    }
    bc_points = [p for p in bc_series if isinstance(p, list) and p[1] is not None]
    # "Had data in the window" isn't the same as "has current data" — a
    # site that went dark yesterday still has plenty of points inside a
    # 48h window. What actually matters for treating "no spike" as real
    # evidence is whether the telemetry is CURRENTLY flowing, so this
    # checks the newest point's own age against the same stale cutoff
    # _vrm_power_snapshot uses everywhere else.
    newest_point_age = (
        end - max(p[0] for p in bc_points) / 1000 if bc_points else None
    )
    has_recent_data = newest_point_age is not None and newest_point_age <= _VRM_STALE_SEC

    peak_power = None
    peak_time = None
    peak_ceiling = None
    for point in bc_points:
        t, current = point
        voltage = bv_by_t.get(t)
        if voltage is None:
            continue
        power = current * voltage
        hour = datetime.utcfromtimestamp(t / 1000).hour
        local_ceiling = ceiling_by_hour.get(hour, flat_ceiling)
        if power > local_ceiling * margin and (peak_power is None or power > peak_power):
            peak_power, peak_time, peak_ceiling = power, t, local_ceiling

    if peak_power is None:
        if not has_recent_data:
            age_label = _format_age(newest_point_age)
            return None, (
                f"No battery-current data from VRM in the last {recent_hours}h "
                f"(newest point is {age_label} old) — cannot check for a solar-ceiling spike"
            ), None, False
        return None, (
            f"No charge power above this trailer's own hour-of-day solar ceiling "
            f"(observed over {ceiling_days}d, {round(flat_ceiling)}W at peak) in the last {recent_hours}h"
        ), None, True
    # utcfromtimestamp — see detect_solar_shading's identical note; this
    # box's local clock is US Mountain, not UTC, despite sharing today's
    # Pacific-Daylight offset by coincidence.
    when = datetime.utcfromtimestamp(peak_time / 1000).strftime("%Y-%m-%d %H:%M")
    # Confidence scales with how far the reading cleared its own hour's
    # ceiling — a reading right at the margin is weaker evidence than one
    # 40% over it. This is inference, not a direct reading, so it's capped
    # below what a direct charger-state match earns, and floored above
    # pure guessing.
    excess_ratio = peak_power / peak_ceiling if peak_ceiling else 1.0
    confidence = max(60, min(92, round(50 + (excess_ratio - 1) * 100)))
    return "present", (
        f"Charge power reached {round(peak_power)}W at {when} (UTC), above the "
        f"{round(peak_ceiling)}W this trailer's solar has ever produced around that hour "
        f"(observed over {ceiling_days}d) — likely AC-fed"
    ), confidence, True
# cSt (charger "Charge state") values that mean the AC charger is actively
# receiving usable input power, vs. ones that mean it isn't. Not every
# trailer has this device at all — plenty are solar+battery only.
#
# "Fault" is deliberately its own bucket, not lumped with "Off" (an earlier
# version did that, and it was wrong): checked live on a real unit stuck in
# Fault with "Err 20: Bulk time limit reached" — its charger was still
# outputting ~94W to the battery (23.96V x 3.9A on Output 1) while faulted,
# which only happens with real AC input to convert from. A fault means the
# charge attempt failed, not that AC is absent — those are different
# problems with different fixes (a dead/disconnected battery not accepting
# charge vs. a cord that's actually unplugged).
_AC_CHARGER_ACTIVE_STATES = {
    "bulk", "absorption", "float", "storage", "equalize",
    "power supply mode", "passthru",
}
_AC_CHARGER_OFF_STATES = {"off", "low power"}
_AC_CHARGER_FAULT_STATES = {"fault"}
# Minimum charger DC output to count as "real," not standby/quiescent draw
# or measurement noise on the AC-current line. Chosen from what's actually
# been observed: legitimate charging sessions run tens to hundreds of
# watts; a charger sitting idle but electrically connected reads a few
# watts to low tens at most.
_AC_CHARGER_MIN_REAL_WATTS = 30
def _ac_power_status_from_diagnostics(diagnostics_records):
    """
    Best-effort read of whether a trailer is plugged into AC/shore power,
    from the same /diagnostics response callers already fetched for
    Battery SOC — no extra VRM call. Prefers the charger's actual DC
    output watts (Output 1 voltage x current — what's actually reaching
    the battery) over the raw AC-current reading alone, since a bare "AC
    Current > 0.5A" test doesn't distinguish standby draw from real
    charging at different system voltages (0.5A means something very
    different on a 12V system than a 48V one; watts don't have that
    problem).

    Every charger field is checked against its OWN reported "timestamp",
    not just whether /diagnostics returned a value at all — VRM's
    /diagnostics endpoint echoes each field's last-known value forever, it
    does not drop a field just because that sub-device stopped reporting.
    Verified live on a real unit (MU8068): its charger fields (cSt/cI/
    c0V/c0I) were still returning "Absorption, 1A AC, ~65W DC output" —
    every appearance of a real, active charging session — while those
    exact fields' own timestamps were 156 DAYS old. The SAME response's
    battery fields (bs/bv/bc) were 12 minutes old, so the site as a whole
    was reporting fine; only that one sub-device had gone silent. Trusting
    formattedValue without checking timestamp would have confidently
    reported "plugged in, 96% likely" from five-month-old cached data —
    exactly the false-confidence failure mode this whole check exists to
    avoid. Fields older than _VRM_AGING_SEC are treated as unusable for a
    confident verdict and surfaced as "stale" instead (the caller,
    _vrm_power_snapshot, decides whether a fresher fallback signal can
    stand in).

    Returns (status, detail, confidence, charger_data_age_seconds) where
    status is one of "present", "not_detected", "uncertain", "stale",
    "no_charger_hardware", and confidence is a 0-100 "percent likely
    plugged in" — deliberately coarse, since this is telemetry inference,
    not a direct measurement. confidence is None for "stale".
    """
    charge_state = None
    ac_current = None
    dc_output_voltage = None
    dc_output_current = None
    charger_error = None
    charger_field_timestamps = []
    for record in diagnostics_records:
        code = record.get("code")
        if code not in ("cSt", "cI", "c0V", "c0I", "cE"):
            continue
        value_text = str(record.get("formattedValue") or "")
        timestamp = record.get("timestamp")
        if code == "cSt":
            charge_state = value_text.strip()
        elif code == "cI":
            match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value_text)
            if match:
                ac_current = float(match.group(1))
        elif code == "c0V":
            match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value_text)
            if match:
                dc_output_voltage = float(match.group(1))
        elif code == "c0I":
            match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value_text)
            if match:
                dc_output_current = float(match.group(1))
        elif code == "cE":
            charger_error = value_text.strip()
        if timestamp:
            charger_field_timestamps.append(timestamp)

    if charge_state is None and ac_current is None and dc_output_voltage is None:
        # No direct signal at all — not zero evidence either way, so this
        # isn't 50 (that's reserved for "two signals actively disagree")
        # and isn't near-zero (that's reserved for "charger says Off").
        return (
            "no_charger_hardware",
            "No AC charger reported for this trailer (likely solar+battery only)",
            35,
            None,
        )

    charger_data_age_seconds = (
        time.time() - max(charger_field_timestamps) if charger_field_timestamps else None
    )
    if charger_data_age_seconds is not None and charger_data_age_seconds > _VRM_AGING_SEC:
        age_label = _format_age(charger_data_age_seconds)
        return (
            "stale",
            f"Charger last reported {age_label} ago (state was '{charge_state or 'unknown'}') "
            f"— too old to use for a current plugged-in read",
            None,
            charger_data_age_seconds,
        )

    dc_output_watts = (
        dc_output_voltage * dc_output_current
        if dc_output_voltage is not None and dc_output_current is not None
        else None
    )
    has_real_output = dc_output_watts is not None and dc_output_watts > _AC_CHARGER_MIN_REAL_WATTS
    has_current = ac_current is not None and ac_current > 0.5
    has_power_evidence = has_real_output or has_current

    state_lower = charge_state.lower() if charge_state else ""
    is_off_state = state_lower in _AC_CHARGER_OFF_STATES
    is_fault_state = state_lower in _AC_CHARGER_FAULT_STATES
    is_active_state = state_lower in _AC_CHARGER_ACTIVE_STATES
    has_real_error = bool(charger_error) and charger_error.strip().lower() not in ("no error", "")

    detail_parts = [f"charger state: {charge_state or 'unknown'}"]
    if dc_output_watts is not None:
        detail_parts.append(
            f"DC output: {round(dc_output_watts)}W ({dc_output_voltage:g}V x {dc_output_current:g}A)"
        )
    detail_parts.append(f"AC current: {ac_current if ac_current is not None else '?'} A")
    if has_real_error:
        detail_parts.append(f"charger error: {charger_error}")
    detail = ", ".join(detail_parts)

    if is_off_state and has_power_evidence:
        return "uncertain", detail + " (state and current/output disagree)", 50, charger_data_age_seconds
    if is_off_state:
        return "not_detected", detail, 8, charger_data_age_seconds
    if is_fault_state:
        if has_power_evidence:
            # Real output during a fault means AC is very likely present —
            # the fault is a separate problem (battery not accepting
            # charge, timed out, etc.), surfaced in the error text above
            # rather than folded into the plugged-in verdict.
            return (
                "present", detail + " — charger faulted, may not be reaching the battery",
                70, charger_data_age_seconds,
            )
        return "not_detected", detail + " (faulted with no output or current detected)", 20, charger_data_age_seconds
    if is_active_state and has_power_evidence:
        return "present", detail, 96, charger_data_age_seconds
    if is_active_state or has_power_evidence:
        return "present", detail, 85, charger_data_age_seconds
    return "uncertain", detail, 45, charger_data_age_seconds


def _charger_state_from_diagnostics(diagnostics_records):
    """
    Just the charger's reported state string ("Bulk", "Fault", "Off", ...)
    from a /diagnostics records payload. Split out from
    _ac_power_status_from_diagnostics so a caller that already has this
    same records list can cheaply check for the Fault case (see
    _vrm_power_snapshot_for_site's UNPLUGGED_V2 SOC-trend cross-check)
    without re-implementing the parsing or changing that function's
    tested 4-tuple return shape.
    """
    for record in diagnostics_records:
        if record.get("code") == "cSt":
            return str(record.get("formattedValue") or "").strip()
    return None


# UNPLUGGED_V2 (2026-09-13 rule-improvement pass): a Fault-state charger
# with real DC output (_ac_power_status_from_diagnostics's "present, may
# not be reaching the battery" case) is ambiguous on the charger reading
# alone — it can't tell "charging is real and working, fault is cosmetic"
# from "AC is present but the battery genuinely isn't accepting the
# charge." SOC over time settles that: a battery actually charging rises;
# one that isn't, doesn't, regardless of what the charger claims.
_SOC_TREND_LOOKBACK_HOURS = 4
# How much SOC has to visibly RISE over the lookback window to count as
# "really charging" rather than meter jitter/rounding noise.
_SOC_TREND_RISE_THRESHOLD_PCT = 1.0
# How far SOC has to have FALLEN to positively flag "not accepting charge
# despite real output" — kept a soft signal, not a hard contradiction: a
# real load (fridge, inverter) can outpace a modest real charge without
# the charger itself being at fault.
_SOC_TREND_FALL_THRESHOLD_PCT = -2.0


def _soc_trend_verdict(soc_now, soc_earlier):
    """
    Pure comparator for the UNPLUGGED_V2 Fault-state cross-check: given
    current SOC and SOC from _SOC_TREND_LOOKBACK_HOURS ago, says whether
    that supports "charging is real and working" (rising), "battery not
    accepting charge despite real DC output" (falling), or is inconclusive
    ("flat" — a near-full battery has nowhere to rise to, and normal load
    can offset a real but modest charge). Returns (label, delta_pct);
    label is None (with delta also None) if either reading is missing.
    """
    if soc_now is None or soc_earlier is None:
        return None, None
    delta = soc_now - soc_earlier
    if delta >= _SOC_TREND_RISE_THRESHOLD_PCT:
        return "rising", delta
    if delta <= _SOC_TREND_FALL_THRESHOLD_PCT:
        return "falling", delta
    return "flat", delta


def _vrm_soc_points(site_id, victron_token, hours, end=None):
    """
    Hourly Battery SOC (%) points over the last `hours` — same shape and
    failure handling as _vrm_pv_history_points, for the UNPLUGGED_V2
    SOC-trend cross-check: /diagnostics alone only ever gives the current
    instant, and "is the battery actually accepting charge" needs SOC now
    vs. SOC some hours ago.
    """
    end = end if end is not None else int(time.time())
    try:
        response = requests.get(
            f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/stats",
            headers={"idSite": str(site_id), "X-Authorization": f"Token {victron_token}"},
            params=[
                ("type", "custom"), ("start", end - hours * 3600), ("end", end),
                ("interval", "hours"), ("attributeCodes[]", "bs"),
            ],
            timeout=30,
        )
        payload = response.json()
    except requests.RequestException:
        return None
    if not payload.get("success"):
        return None
    series = payload.get("records", {}).get("bs") or []
    points = [(p[0], p[1]) for p in series if isinstance(p, list) and p[1] is not None]
    return points or None


def _soc_trend_for_fault_cross_check(site_id, victron_token, soc_now, end=None):
    """
    Network half of the UNPLUGGED_V2 cross-check: fetches the SOC point
    closest to _SOC_TREND_LOOKBACK_HOURS ago and runs it through
    _soc_trend_verdict against the current reading already on hand (no
    extra call needed for "now" — the caller already has it from
    /diagnostics). Returns (label, delta_pct, soc_earlier); label is None
    (with the others also None) when there's no usable earlier point —
    e.g. a data gap left only much-older or much-newer readings, so
    nothing near the target time is close enough to trust.
    """
    end = end if end is not None else int(time.time())
    points = _vrm_soc_points(site_id, victron_token, _SOC_TREND_LOOKBACK_HOURS + 1, end=end)
    if not points:
        return None, None, None
    target_t = end - _SOC_TREND_LOOKBACK_HOURS * 3600
    closest = min(points, key=lambda p: abs(p[0] / 1000 - target_t))
    if abs(closest[0] / 1000 - target_t) > (_SOC_TREND_LOOKBACK_HOURS * 3600) / 2:
        return None, None, None
    soc_earlier = closest[1]
    label, delta = _soc_trend_verdict(soc_now, soc_earlier)
    return label, delta, soc_earlier


def _vrm_power_snapshot(unit_key, subject_text):
    """
    Shared VRM battery/AC-power read — one installations lookup, one
    diagnostics call, the direct AC-power read, and (only when that read
    is absent, self-contradictory, or too old to trust) the solar-ceiling
    fallback. Used by both unit_battery_weather_outlook (adds weather
    correlation on top) and unit_power_status (the focused
    Diagnostics-menu check) so a fix to one lands in both rather than
    needing to be made twice.

    Two independent freshness signals feed the final verdict, because
    they can disagree — a site can be reporting fine overall while one
    sub-device (its charger) has gone silent, or vice versa:
      - vrm_freshness: how recently the SITE as a whole last reported to
        VRM at all (from _resolve_vrm_site's extended=1 last_timestamp).
      - the charger fields' own timestamps, checked inside
        _ac_power_status_from_diagnostics.
    Neither one is allowed to silently turn into a confident "not plugged
    in" — when the direct charger reading is too old to trust AND the
    solar-ceiling fallback has nothing current either, the final
    ac_power_status is "unknown", not "not_detected". A genuinely
    unreachable-and-unpowered unit and a unit that's simply not talking to
    VRM right now produce identical raw symptoms; only independent
    evidence (Zabbix reachability, a site visit) can tell them apart, and
    this function doesn't have that evidence, so it says so instead of
    guessing.

    Returns (snapshot, error). snapshot is a dict:
      installation_name, battery_soc_percent, soc_error,
      ac_power_status, ac_power_label, ac_power_detail, ac_power_confidence,
      vrm_last_seen_seconds_ago, vrm_freshness
    """
    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error
    site_id, installation_name, vrm_last_seen_seconds_ago, _timezone_name, site_error = _resolve_vrm_site(
        unit_key, subject_text, id_user, victron_token
    )
    if site_error:
        return None, site_error
    return _vrm_power_snapshot_for_site(site_id, installation_name, vrm_last_seen_seconds_ago, victron_token)


def _vrm_power_snapshot_for_site(site_id, installation_name, vrm_last_seen_seconds_ago, victron_token):
    """
    The part of _vrm_power_snapshot that runs once a VRM site is already
    resolved — split out so a fleet-wide pass (fleet_power_status) can
    reuse the exact same diagnostics-read + solar-ceiling-fallback logic
    for every installation from ONE bulk installations call, instead of
    each unit re-fetching that same bulk list just to find its own row in
    it (which is what _resolve_vrm_site does, correctly, for the
    single-unit case, but would be wasteful repeated ~250 times).
    Returns (snapshot, error) — same shape as _vrm_power_snapshot.
    """
    vrm_freshness = _vrm_freshness_tier(vrm_last_seen_seconds_ago)

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

    diagnostics_records = diagnostics_resp.json().get("records") or []
    battery_soc_percent = None
    for record in diagnostics_records:
        if record.get("description") == "Battery SOC":
            match = re.match(r"\s*(\d+(?:\.\d+)?)\s*%", str(record.get("formattedValue") or ""))
            if match:
                battery_soc_percent = float(match.group(1))
            break
    # Not fatal: some architectures (checked live — a Hub-1 system with a
    # 48V/Cerbo GX combo) report battery voltage/current but no percentage
    # SOC at all. Losing SOC shouldn't also lose the AC-power read below,
    # which doesn't depend on it.
    soc_error = None
    if battery_soc_percent is None:
        soc_error = f"VRM diagnostics for {installation_name or unit_key} had no Battery SOC reading"

    ac_power_status, ac_power_detail, ac_power_confidence, charger_age_seconds = (
        _ac_power_status_from_diagnostics(diagnostics_records)
    )

    # UNPLUGGED_V2: the Fault-with-real-output case reads "present" on the
    # charger alone, but that can't distinguish a cosmetic fault from a
    # battery that genuinely isn't accepting the charge — cross-check
    # against the SOC trend, which can. Only fires for that specific case;
    # every other verdict is unaffected.
    charge_state_for_soc_check = _charger_state_from_diagnostics(diagnostics_records)
    if (
        ac_power_status == "present"
        and charge_state_for_soc_check
        and charge_state_for_soc_check.lower() in _AC_CHARGER_FAULT_STATES
        and battery_soc_percent is not None
    ):
        soc_trend_label, soc_trend_delta, soc_earlier = _soc_trend_for_fault_cross_check(
            site_id, victron_token, battery_soc_percent
        )
        if soc_trend_label == "rising":
            ac_power_confidence = max(ac_power_confidence or 0, 90)
            ac_power_detail += (
                f" — SOC rose {round(soc_earlier)}%→{round(battery_soc_percent)}% over the last "
                f"{_SOC_TREND_LOOKBACK_HOURS}h, so the charge is real despite the fault code"
            )
        elif soc_trend_label == "falling":
            ac_power_confidence = min(ac_power_confidence or 100, 55)
            ac_power_detail += (
                f" — SOC fell {round(soc_earlier)}%→{round(battery_soc_percent)}% over the last "
                f"{_SOC_TREND_LOOKBACK_HOURS}h despite the claimed output; battery may not actually be "
                f"accepting the charge (could also be load outpacing a weak charge)"
            )
        # "flat" or missing SOC-trend data: no change — inconclusive either
        # way, and the direct charger reading stands as-is.

    # Fall back to the solar-ceiling inference whenever the direct reading
    # couldn't give a real answer — absent, self-contradictory, or too old
    # to trust (see _ac_power_status_from_diagnostics). This only ever
    # adds evidence on top of what's already known, never overrides a
    # confident direct reading.
    fallback_has_data = True
    if ac_power_status in ("no_charger_hardware", "uncertain", "stale"):
        inferred_status, inferred_detail, inferred_confidence, fallback_has_data = (
            _vrm_pv_ceiling_and_recent_spike(site_id, victron_token)
        )
        if inferred_status:
            ac_power_status = inferred_status
            ac_power_confidence = inferred_confidence
            ac_power_detail = (
                inferred_detail + f" (direct charger reading: {ac_power_detail})"
                if ac_power_detail else inferred_detail
            )
        elif inferred_detail:
            ac_power_detail = (ac_power_detail + " — " if ac_power_detail else "") + inferred_detail

    if ac_power_status == "stale":
        # The charger reading was too old to trust, AND the fallback
        # either wasn't attempted (an inferred_status of None from a
        # source that itself has no current data) or explicitly found
        # nothing current either — there's no fresh evidence in either
        # direction. Say "unknown", not "not plugged in" — this is
        # exactly the failure mode this whole review called out.
        if not fallback_has_data:
            ac_power_status = "unknown"
        elif charger_age_seconds is not None and charger_age_seconds > _VRM_STALE_SEC:
            # Checked live (2026-09-13): ~40% of the fleet has a charger
            # sub-device that last reported WEEKS to MONTHS ago (not just
            # a couple hours) — these are almost certainly solar+battery
            # trailers whose charger registration is a dead leftover, not
            # units with a genuinely ambiguous CURRENT reading. Lumping
            # both under "uncertain" buried the real handful of units
            # worth a look under ~100 that aren't. Once the charger has
            # been silent longer than the same "disconnected" cutoff used
            # everywhere else in this module, treat it the same as never
            # having reported at all — the battery's own solar-only
            # behavior (checked above, no AC-sized spike) is the real,
            # current evidence, same as a true no_charger_hardware case.
            ac_power_status = "no_charger_hardware"
        else:
            # The fallback DID have current battery-current data and found
            # no AC-sized draw — real (if soft) evidence the trailer
            # probably isn't drawing extra power right now even though the
            # charger sub-device itself has gone quiet recently.
            ac_power_status = "uncertain"

    ac_power_labels = {
        "present": "plugged in",
        "not_detected": "not plugged in",
        "uncertain": "AC power status uncertain",
        "no_charger_hardware": "no AC charger on this trailer",
        "unknown": "power state unknown — no current VRM data",
    }
    ac_power_label = ac_power_labels.get(ac_power_status, ac_power_status)

    # A confident-looking direct verdict built on aging (not yet "stale")
    # data still deserves a hedge in the text an operator actually reads —
    # the status/confidence fields stay as computed, only the label picks
    # up the caveat.
    if vrm_freshness == "aging" and ac_power_status in ("present", "not_detected"):
        ac_power_label += f" (VRM data {_format_age(vrm_last_seen_seconds_ago)} old)"

    return {
        "installation_name": installation_name,
        "battery_soc_percent": battery_soc_percent,
        "soc_error": soc_error,
        "ac_power_status": ac_power_status,
        "ac_power_label": ac_power_label,
        "ac_power_detail": ac_power_detail,
        "ac_power_confidence": ac_power_confidence,
        "vrm_last_seen_seconds_ago": vrm_last_seen_seconds_ago,
        "vrm_freshness": vrm_freshness,
    }, None
def unit_power_status(unit, subject=""):
    """
    Focused "is this trailer plugged into AC/shore power" check — the
    Diagnostics-menu answer to a question Battery Outlook could only
    answer as a side effect of its weather correlation, buried under
    Weather where nobody would look for it. No forecast call, and SOC is
    informational rather than required. Returns (info, error).
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None, f"Invalid unit: {unit}"
    subject_text = str(subject or "").strip()

    snapshot, error = _vrm_power_snapshot(unit_key, subject_text)
    if error:
        return None, error
    return _power_status_dict_from_snapshot(unit_key, snapshot)


def _power_status_dict_from_snapshot(unit_key, snapshot):
    """
    The summary/ok-warn-fail enrichment unit_power_status builds on top of
    a raw _vrm_power_snapshot(_for_site) result — split out so
    fleet_power_status can build the exact same shape per installation
    instead of a fleet row silently missing "summary"/"status" (found live
    testing this report: without this split, every fleet row rendered with
    no result text at all — the raw snapshot dict was never enriched).
    """
    # "unknown" is deliberately not "fail" — it means the data needed to
    # tell present from not_detected isn't currently available, which is a
    # different (and less actionable) problem than a confirmed reading.
    status = {
        "present": "ok",
        "no_charger_hardware": "ok",
        "uncertain": "warn",
        "unknown": "warn",
        "not_detected": "fail",
    }.get(snapshot["ac_power_status"], "ok")

    battery_soc_percent = snapshot["battery_soc_percent"]
    ac_power_confidence = snapshot["ac_power_confidence"]
    soc_text = f"{battery_soc_percent:g}%" if battery_soc_percent is not None else "unavailable"
    confidence_text = f" ({ac_power_confidence}% likely)" if ac_power_confidence is not None else ""
    summary = (
        f"{unit_key} ({snapshot['installation_name']}) — {snapshot['ac_power_label']}"
        f"{confidence_text} — battery {soc_text}"
    )

    return {
        "unit": unit_key,
        "installation_name": snapshot["installation_name"],
        "battery_soc_percent": battery_soc_percent,
        "soc_error": snapshot["soc_error"],
        "ac_power_status": snapshot["ac_power_status"],
        "ac_power_label": snapshot["ac_power_label"],
        "ac_power_detail": snapshot["ac_power_detail"],
        "ac_power_confidence": ac_power_confidence,
        "vrm_last_seen_seconds_ago": snapshot["vrm_last_seen_seconds_ago"],
        "vrm_freshness": snapshot["vrm_freshness"],
        "status": status,
        "summary": summary,
    }, None
def unit_shading_status(unit, subject=""):
    """
    "Is this trailer's solar being shaded" check — built from a real ERP
    ticket pattern (issue_subtype "shaded"): the day one such ticket was
    filed (RD3421/MU8064, 2026-08-26), that trailer's own solar output ran
    6-37% of what the SAME trailer produced in those SAME hours on other
    days — see detect_solar_shading for the mechanism and its one real
    blind spot (a broadly overcast day looks the same on telemetry alone).

    Read-only against VRM, same as every other check in this module — one
    installations lookup plus two /stats calls (a multi-day ceiling window,
    a recent window), no writes. Returns (info, error).
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None, f"Invalid unit: {unit}"
    subject_text = str(subject or "").strip()

    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error
    site_id, installation_name, vrm_last_seen_seconds_ago, timezone_name, site_error = _resolve_vrm_site(
        unit_key, subject_text, id_user, victron_token
    )
    if site_error:
        return None, site_error
    return _shading_status_for_site(
        unit_key, site_id, installation_name, vrm_last_seen_seconds_ago, timezone_name, victron_token
    )


def _shading_status_for_site(unit_key, site_id, installation_name, vrm_last_seen_seconds_ago, timezone_name, victron_token):
    """
    The part of unit_shading_status that runs once a VRM site is already
    resolved — split out for the same reason as _vrm_power_snapshot_for_site
    (see its docstring): fleet_shading_status reuses this per installation
    from one bulk installations call instead of each site re-resolving the
    whole list. Returns (snapshot, error) — same shape as unit_shading_status.
    """
    vrm_freshness = _vrm_freshness_tier(vrm_last_seen_seconds_ago)
    found, detail, confidence, window = detect_solar_shading(site_id, victron_token)
    window_label = None
    if window:
        # UTC only, deliberately — this box has no IANA tz database
        # installed (checked: zoneinfo needs the `tzdata` package, which
        # isn't present, and adding a hand-rolled fixed-offset table would
        # get DST wrong for half the year on every zone except Phoenix's).
        # timezone_name is still surfaced separately as a label, not used
        # for conversion, so the window is never silently off by an hour.
        # utcfromtimestamp specifically, not fromtimestamp — this box's own
        # local clock is US Mountain (checked live), not UTC; it only
        # LOOKS right against Pacific installations because -7 happens to
        # match Pacific Daylight Time this month.
        start_label = datetime.utcfromtimestamp(window["start_ts_ms"] / 1000).strftime("%Y-%m-%d %H:%M")
        end_label = datetime.utcfromtimestamp(window["end_ts_ms"] / 1000).strftime("%H:%M")
        window_label = f"{start_label}–{end_label} UTC"

    if found is None:
        status = "unknown"
        label = "cannot check for shading — no usable VRM solar data"
    elif found:
        status = "shaded"
        label = f"possible shading detected, {window_label}" if window_label else "possible shading detected"
    else:
        status = "clear"
        label = "no shading detected"

    confidence_text = f" ({confidence}% confidence)" if confidence is not None else ""
    summary = f"{unit_key} ({installation_name}) — {label}{confidence_text}"
    if timezone_name:
        summary += f" [installation timezone: {timezone_name}]"
    if vrm_freshness not in ("fresh", "aging"):
        summary += f" — VRM data {_format_age(vrm_last_seen_seconds_ago)} old, take with caution"

    # Same ok/warn/fail vocabulary as unit_power_status, for anything (the
    # Shaded Units report) that wants to color a result generically rather
    # than branch on shading_status by name. "shaded" is "fail" — it's the
    # one actionable finding here — "clear" is "ok" (good news: whatever
    # filed the ticket may no longer apply), "unknown" is "warn" (can't
    # confirm either way, not a confirmed problem).
    ui_status = {"shaded": "fail", "clear": "ok", "unknown": "warn"}.get(status, "warn")

    return {
        "unit": unit_key,
        "installation_name": installation_name,
        "shading_status": status,
        "shading_label": label,
        "shading_detail": detail,
        "shading_confidence": confidence,
        "shading_window_utc": window_label,
        "status": ui_status,
        "shading_window_hours_utc": window["hours_utc"] if window else [],
        # The single deepest hour in the dip, not just any hour it
        # touched — what a scheduled snapshot should aim for (see
        # work_tool.shading_snapshots).
        "shading_worst_hour_utc": window["worst_hour_utc"] if window else None,
        "installation_timezone": timezone_name,
        "vrm_last_seen_seconds_ago": vrm_last_seen_seconds_ago,
        "vrm_freshness": vrm_freshness,
        "summary": summary,
    }, None
def _fleet_vrm_installations_with_heads():
    """
    One bulk installations call (site_id/name/last_timestamp for every
    installation) plus one bulk (chunked) ERP crosswalk for their RD/FD
    heads — the shared setup for fleet_power_status and
    fleet_shading_status, so checking the whole fleet for two different
    things only fetches the installation list and resolves the ERP
    crosswalk once between them, not once each.

    Also drops any MU trailer that has no ERP Site linked to its Component
    record — the same "Component {X} has no Site" case resolve_shield_site_id
    treats as unresolvable for a single unit. An MU with no Site is one ERP
    never provisioned a location for (retired, spare, or never finished
    setup), so it's not a real, currently-deployed trailer — including it in
    a fleet report just adds a row nobody can act on. Uses the same bulk
    Component-site lookup resolve_shield_site_id uses for one unit
    (_fetch_erp_component_site_map), not a new call, so this costs one more
    chunked ERP GET alongside the existing head crosswalk, not one per MU.

    Returns (installations, mu_to_heads, error). installations is a list of
    {site_id, installation_name, vrm_last_seen_seconds_ago, timezone_name},
    already filtered down to MUs with a linked Site (non-MU-named
    installations, if any exist, are never filtered — the concept of "no
    Site" only applies to a trailer's own Component).
    """
    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, None, cred_error
    try:
        response = requests.get(
            f"https://vrmapi.victronenergy.com/v2/users/{id_user}/installations",
            headers={"idUser": id_user, "X-Authorization": f"Token {victron_token}"},
            params={"extended": 1},
            timeout=30,
        )
    except requests.RequestException as exc:
        return None, None, f"VRM installations lookup failed: {exc}"
    if response.status_code != 200:
        return None, None, f"VRM installations lookup failed: HTTP {response.status_code}"

    installations = []
    for record in response.json().get("records") or []:
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        last_timestamp = record.get("last_timestamp") or None
        installations.append({
            "site_id": record.get("idSite"),
            "installation_name": name,
            "vrm_last_seen_seconds_ago": (time.time() - last_timestamp) if last_timestamp else None,
            "timezone_name": str(record.get("timezone") or "").strip() or None,
        })

    mu_names = [i["installation_name"] for i in installations if i["installation_name"].upper().startswith("MU")]
    mu_to_heads = {}
    if mu_names:
        mu_to_heads, crosswalk_error = _erp_heads_for_mu_trailers(mu_names)
        mu_to_heads = mu_to_heads or {}
        if crosswalk_error:
            print(f"_fleet_vrm_installations_with_heads: ERP head crosswalk failed: {crosswalk_error}")

    if mu_names:
        site_cache = {}
        try:
            _fetch_erp_component_site_map(
                [_sc_component_name(name) for name in mu_names], site_cache, quiet=True,
            )
        except Exception as exc:
            # Fail open — a broken site lookup should never wipe out an
            # otherwise-working fleet report; every MU just stays included,
            # same as before this filter existed.
            print(f"_fleet_vrm_installations_with_heads: ERP Site lookup failed: {exc}")
            site_cache = None
        if site_cache is not None:
            no_site_mus = {
                name for name in mu_names
                if not (site_cache.get(_sc_component_name(name)) or {}).get("site")
            }
            if no_site_mus:
                print(
                    f"_fleet_vrm_installations_with_heads: {len(no_site_mus)} MU(s) have no "
                    f"ERP Site linked, excluded as inactive: {', '.join(sorted(no_site_mus))}"
                )
                installations = [
                    i for i in installations
                    if i["installation_name"] not in no_site_mus
                ]
    return installations, mu_to_heads, None


def fleet_power_status(max_workers=10):
    """
    AC-power status for every VRM installation in the fleet, concurrently —
    backs the "Units Unplugged" report. Reuses the exact same
    _vrm_power_snapshot_for_site logic (diagnostics read + solar-ceiling
    fallback) a single-unit check uses, so a fleet-wide result and a
    hand-checked single unit can never disagree about how the verdict was
    reached — this function only changes WHERE the installation list and
    ERP crosswalk come from (fetched once, not once per site).

    Cost: ~1-2 setup calls + one VRM request per installation, run
    concurrently. Checked live (2026-09-13): ~250 installations fleet-wide
    — meant for a scheduled background poll (see
    FLEET_POWER_STATUS_REFRESH_SECONDS in flask_endpoints.py), not a live
    button click; a full pass takes on the order of a minute, not seconds.
    Returns (rows, error). Each row has "unit" (the installation/MU name),
    "head_units" (its ERP-linked RD/FD head(s), if any), and every key
    _vrm_power_snapshot_for_site returns (or "error" if that one site's
    check itself failed — the rest of the fleet still comes back).
    """
    installations, mu_to_heads, error = _fleet_vrm_installations_with_heads()
    if error:
        return None, error
    _, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error

    def check_one(installation):
        head_units = mu_to_heads.get(installation["installation_name"].upper(), [])
        row = {"unit": installation["installation_name"], "head_units": head_units}
        snapshot, snap_error = _vrm_power_snapshot_for_site(
            installation["site_id"], installation["installation_name"],
            installation["vrm_last_seen_seconds_ago"], victron_token,
        )
        if snap_error:
            row["error"] = snap_error
        else:
            # The summary text reads as "RD3315(MU8083) — plugged in..."
            # when this trailer's ERP-linked head is known, the same
            # RD####(MU####) shape every ticket subject already uses —
            # not "MU8083 (MU8083)", which is what a bare installation
            # name fed in twice looks like, and is what fleet rows showed
            # before this: nothing here resolves a head on its own, so
            # without it every trailer looked identity-less.
            display_unit = head_units[0] if head_units else installation["installation_name"]
            enriched, _err = _power_status_dict_from_snapshot(display_unit, snapshot)
            row.update(enriched)
            row["unit"] = installation["installation_name"]
        return row

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        rows = list(pool.map(check_one, installations))
    return rows, None


def fleet_shading_status(max_workers=6):
    """
    Shading status for every VRM installation, concurrently — backs the
    "Shaded Units" report. Lower default concurrency than
    fleet_power_status: each site costs TWO /stats calls here (a multi-day
    ceiling window, a recent window) versus one /diagnostics call there,
    so the same worker count would roughly double simultaneous VRM load.
    Same reuse principle as fleet_power_status — see its docstring.
    Returns (rows, error).
    """
    installations, mu_to_heads, error = _fleet_vrm_installations_with_heads()
    if error:
        return None, error
    _, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error

    def check_one(installation):
        head_units = mu_to_heads.get(installation["installation_name"].upper(), [])
        row = {"unit": installation["installation_name"], "head_units": head_units}
        # See fleet_power_status's check_one for why unit_key is the
        # resolved head (RD3315(MU8083), not MU8083 (MU8083)) when known.
        display_unit = head_units[0] if head_units else installation["installation_name"]
        snapshot, snap_error = _shading_status_for_site(
            display_unit, installation["site_id"], installation["installation_name"],
            installation["vrm_last_seen_seconds_ago"], installation["timezone_name"], victron_token,
        )
        if snap_error:
            row["error"] = snap_error
        else:
            row.update(snapshot)
            row["unit"] = installation["installation_name"]
        return row

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        rows = list(pool.map(check_one, installations))
    return rows, None


# A single panel's nominal max output — the one fixed number this whole
# check is built on ("1 panel = up to 300W" per the fleet's own hardware).
# Panel COUNT is never assumed from the unit number (checked earlier this
# session: it isn't reliably guessable — 7000-series usually 2, 8000-series
# usually 4, but real exceptions exist on both, including 3-panel units) —
# only inferred from what a trailer has actually, demonstrably produced.
_PANEL_NOMINAL_WATTS = 300


def _infer_panel_count(historical_peak_watts):
    """
    Best-guess panel count from a trailer's own best-ever-observed solar
    output. Rounds to the nearest multiple of _PANEL_NOMINAL_WATTS, floored
    at 1. Deliberately an estimate, not a lookup — stated plainly where
    it's used: if every panel this trailer has died before the history
    window this checks even begins, the true count is underestimated,
    since there is no install record to check it against instead.

    Peak-wattage inference itself is unaffected by how the panels are
    wired (series vs. parallel doesn't change a healthy array's total
    power) — it's the downstream "how many panels does a shortfall imply"
    math in detect_dead_panel that has to account for wiring; see
    _SERIES_PAIR_WATTS below.
    """
    if historical_peak_watts is None or historical_peak_watts <= 0:
        return None
    return max(1, round(historical_peak_watts / _PANEL_NOMINAL_WATTS))


# 4-panel units are wired as two series-connected PAIRS (2S2P), not four
# independent parallel panels (per-fleet detail, confirmed 2026-09-13).
# That matters for how a shortfall maps to a physical panel count: in a
# series string, the string's current is capped by its weakest panel, so
# one dead panel doesn't just cost its own ~300W — it drags its series
# partner's output down too, costing roughly a whole PAIR's worth (~600W).
# A naive shortfall/300W count would read that as "2 panels missing" and
# overstate the repair. Used only for 4+-panel (even-count) units below;
# 2-panel units aren't known to have this series complication.
_SERIES_PAIR_WATTS = _PANEL_NOMINAL_WATTS * 2

# DEAD_PANEL_V2 (2026-09-13 rule-improvement pass) — four added guards on
# top of the original shortfall check, each closing a specific false-
# positive path found reviewing real data:
#
# 1. _DEAD_PANEL_MIN_HISTORICAL_PEAK_DAYS — the historical peak has to be a
#    real, repeated capability, not a single lucky reading, BEFORE it's
#    trusted to set "expected capacity" at all (previously this only
#    scaled confidence down, never blocked a verdict outright).
_DEAD_PANEL_MIN_HISTORICAL_PEAK_DAYS = 3
# 2. _DEAD_PANEL_MIN_SEPARATION_DAYS — ONLY checked once a shortfall is
#    already on the table (see detect_dead_panel): the historical peak's
#    last occurrence and the recent comparison window need real daylight
#    between them, or the "shortfall" could just be overlapping noise from
#    the same stretch of days. Deliberately NOT a precondition for the
#    healthy verdict too — a healthy unit's own peak routinely recurs
#    inside the recent window (that's what healthy looks like), and an
#    earlier version that checked this before any shortfall existed wrongly
#    returned "unknown" for most of the fleet's genuinely fine units
#    (checked live, 2026-09-13: 149 of 249 installations).
_DEAD_PANEL_MIN_SEPARATION_DAYS = 5
# 3. _DEAD_PANEL_TRAILING_* — "recent capability" comes from the trailing
#    week specifically, not the single best moment anywhere in the wider
#    recent_days window (freshness — a good day from early in a 14-day
#    window shouldn't stand in for "now"), and from that week's SECOND-
#    highest daily peak, not its outright best (persistence — one glitchy
#    high reading, or one unusually good day, shouldn't get to clear an
#    otherwise-persistent shortfall by itself; a real recovery has to show
#    up more than once).
_DEAD_PANEL_TRAILING_WINDOW_DAYS = 7
_DEAD_PANEL_MIN_TRAILING_DAYS_OBSERVED = 5
# 4. _DEAD_PANEL_HOUR_RATIO_STDEV_THRESHOLD — the new signal that actually
#    distinguishes hardware from shading: a dead panel/pair caps output
#    roughly EQUALLY across every productive hour (low stdev in the
#    recent/historical ratio hour-to-hour); shading is hour-specific (high
#    stdev). Checked against a real case (RD3439/MU8024, 2026-09-13): a
#    genuine dead-panel unit held 68.3% +/- 3.1% of typical across all six
#    productive UTC hours (16-21) — comfortably under this threshold.
#    Caveat, stated plainly: validated against that ONE real case so far;
#    treat this specific cutoff as provisional until a second confirmed
#    example is checked.
_DEAD_PANEL_HOUR_RATIO_STDEV_THRESHOLD = 0.10
_DEAD_PANEL_MIN_PRODUCTIVE_HOURS_FOR_STDEV = 4


def detect_dead_panel(site_id, victron_token, history_days=60, recent_days=14, hour_tolerance=1):
    """
    Compares a trailer's best-ever solar output (used to infer how many
    panels it has) against its best RECENT output, looking for a shortfall
    consistent with one or more panels having died or gone dark — the
    same "1 panel ~300W" rule of thumb given for this check: a 2-panel
    unit should clear 300W, a 4-panel unit 600W+, and a sustained failure
    to do so (not just one off day) is worth a look. On a 4-panel unit
    that shortfall shows up in ~600W (one series-pair) increments rather
    than ~300W ones — see _SERIES_PAIR_WATTS — so a single dead panel
    there reads as "1 pair down," not "2 panels missing."

    Uses peak watts, not a hour-of-day baseline like detect_solar_shading —
    a dead panel caps the trailer's ceiling everywhere, all day, so the
    simplest fair comparison is "best it's ever done" vs "best it's done
    lately," not an hour-by-hour profile.

    Real limitations, stated plainly rather than papered over:
    - A panel that died before the history window began is invisible to
      this — the historical peak already reflects the reduced capacity,
      so there is nothing to compare it against.
    - A long cloudy stretch in the recent window suppresses the recent
      peak the same way a dead panel would; this cannot independently
      tell the two apart from telemetry alone, so confidence is capped
      and the detail says so.

    Returns (found, detail, confidence, info). info carries the raw
    numbers (historical/recent peak, inferred panel count, expected
    capacity) for display regardless of the verdict.
    """
    long_points = _vrm_pv_history_points(site_id, victron_token, history_days)
    if not long_points:
        return None, "No solar-power history available", None, None
    historical_peak = max(v for _, v in long_points)
    # How many distinct days actually reached near that peak — a single
    # lucky 15-minute reading shouldn't get to set "expected capacity" on
    # its own.
    near_peak_days = {
        datetime.utcfromtimestamp(t / 1000).date()
        for t, v in long_points if v >= historical_peak * 0.9
    }
    inferred_panels = _infer_panel_count(historical_peak)
    expected_capacity = inferred_panels * _PANEL_NOMINAL_WATTS if inferred_panels else None

    cutoff = int(time.time()) - recent_days * 24 * 3600
    recent_points = [(t, v) for t, v in long_points if t / 1000 >= cutoff]
    if not recent_points:
        return None, "No recent solar-power data available", None, None

    info = {
        "historical_peak_watts": round(historical_peak),
        "historical_peak_days_observed": len(near_peak_days),
        "inferred_panels": inferred_panels,
        "expected_capacity_watts": expected_capacity,
        "history_days": history_days,
        "recent_days": recent_days,
    }

    # DEAD_PANEL_V2 guard 3: "recent capability" comes from the trailing
    # week specifically (freshness — a good day from early in a 14-day
    # recent_days window shouldn't get to stand in for "now"), and from
    # the SECOND-highest daily peak in that week, not the single best
    # moment (persistence — one glitchy high reading, or one unusually
    # good day sandwiched between bad ones, shouldn't get to clear an
    # otherwise-persistent shortfall on its own; the recovery has to show
    # up more than once to count).
    trailing_cutoff = int(time.time()) - _DEAD_PANEL_TRAILING_WINDOW_DAYS * 24 * 3600
    trailing_peak_by_day = {}
    for t, v in recent_points:
        if t / 1000 < trailing_cutoff:
            continue
        day = datetime.utcfromtimestamp(t / 1000).date()
        trailing_peak_by_day[day] = max(trailing_peak_by_day.get(day, 0), v)
    if len(trailing_peak_by_day) < _DEAD_PANEL_MIN_TRAILING_DAYS_OBSERVED:
        return None, (
            f"Only {len(trailing_peak_by_day)} day(s) of solar data in the trailing "
            f"{_DEAD_PANEL_TRAILING_WINDOW_DAYS}d — need at least "
            f"{_DEAD_PANEL_MIN_TRAILING_DAYS_OBSERVED} to confirm a shortfall holds across the week "
            f"rather than reflecting a single day's reading"
        ), None, info
    sorted_trailing_peaks = sorted(trailing_peak_by_day.values(), reverse=True)
    recent_peak = sorted_trailing_peaks[1] if len(sorted_trailing_peaks) >= 2 else sorted_trailing_peaks[0]
    info["recent_peak_watts"] = round(recent_peak)

    if len(near_peak_days) < _DEAD_PANEL_MIN_HISTORICAL_PEAK_DAYS:
        # DEAD_PANEL_V2 guard 1: a hard gate, not just a confidence
        # penalty — an under-observed "peak" isn't trustworthy enough to
        # build an expected-capacity comparison on at all.
        return None, (
            f"Historical peak {round(historical_peak)}W was only seen on {len(near_peak_days)} day(s) "
            f"in the last {history_days}d — need at least {_DEAD_PANEL_MIN_HISTORICAL_PEAK_DAYS} to "
            f"trust it as this trailer's real capability rather than a fluke reading"
        ), None, info

    if not expected_capacity or expected_capacity <= _PANEL_NOMINAL_WATTS:
        # A 1-panel-inferred trailer has nothing to compare against — there
        # is no "missing panel" question when only one was ever expected.
        return False, (
            f"Best-ever output {round(historical_peak)}W is consistent with a single panel "
            f"— nothing to compare a shortfall against"
        ), None, info

    shortfall = expected_capacity - recent_peak
    # A shortfall has to be close to a full panel's worth to count — small
    # gaps (dust, panel angle, a slightly hazy week) are normal and
    # shouldn't read as a hardware failure.
    if shortfall < _PANEL_NOMINAL_WATTS * 0.7:
        return False, (
            f"Recent peak {round(recent_peak)}W is within normal range of the "
            f"{expected_capacity}W expected from an inferred {inferred_panels}-panel array"
        ), None, info

    # DEAD_PANEL_V2 guard 2: only gates CONFIRMING a shortfall as a dead
    # panel, not the healthy verdict above — a healthy unit's own peak
    # routinely recurs inside the recent window (that's what "healthy"
    # looks like), so requiring separation before EVERY verdict wrongly
    # returned "unknown" for most of the fleet's genuinely fine units
    # (checked live, 2026-09-13: 149 of 249 installations, the single
    # biggest cause of the report showing far fewer rows than it should).
    # Once there IS an apparent shortfall, though, the historical evidence
    # and the recent comparison window still need real daylight between
    # them, or the "shortfall" could just be the SAME stretch of ordinary
    # day-to-day variance measured against itself.
    last_peak_date = max(near_peak_days)
    recent_window_start_date = datetime.utcfromtimestamp(cutoff).date()
    separation_days = (recent_window_start_date - last_peak_date).days
    if separation_days < _DEAD_PANEL_MIN_SEPARATION_DAYS:
        return None, (
            f"Recent peak {round(recent_peak)}W looks short of the {expected_capacity}W expected, but "
            f"this trailer's historical peak was last seen only {separation_days} day(s) before the "
            f"recent {recent_days}d comparison window starts — need at least "
            f"{_DEAD_PANEL_MIN_SEPARATION_DAYS} day(s) of separation to trust the shortfall as real "
            f"rather than the same stretch of days compared against itself"
        ), None, info

    # For 4+-panel (even) arrays, count the shortfall in series-PAIR units
    # (see _SERIES_PAIR_WATTS) rather than single-panel units — a dead
    # panel there costs its whole pair, so dividing by one panel's wattage
    # would double-count the pair's healthy partner as also missing.
    wired_in_series_pairs = inferred_panels >= 4 and inferred_panels % 2 == 0
    loss_unit_watts = _SERIES_PAIR_WATTS if wired_in_series_pairs else _PANEL_NOMINAL_WATTS
    max_units = (inferred_panels // 2) if wired_in_series_pairs else inferred_panels
    missing_units = max(1, min(round(shortfall / loss_unit_watts), max_units))
    # Confidence: higher when the historical peak was reached on several
    # different days (a real, repeatable capability, not a fluke reading)
    # and when the shortfall lines up cleanly with a whole number of
    # panels (or pairs) rather than an odd fraction more consistent with
    # cloud cover.
    consistency_score = min(1.0, len(near_peak_days) / 3)
    cleanliness = 1.0 - min(1.0, abs((shortfall / loss_unit_watts) - missing_units))
    confidence = max(30, min(90, round(40 + consistency_score * 25 + cleanliness * 25)))
    if wired_in_series_pairs:
        missing_panels = missing_units  # 1 dead panel per affected pair, not 2
        shortfall_phrase = (
            f"roughly {missing_units} series pair('s) worth short — on this wiring (2 panels per "
            f"series string) that's consistent with {missing_units} physically dead panel(s) each "
            f"dragging its series partner down, not {missing_units * 2}"
        )
    else:
        missing_panels = missing_units
        shortfall_phrase = f"roughly {missing_units} panel('s) worth short"
    detail = (
        f"Best-ever output {round(historical_peak)}W (seen on {len(near_peak_days)} day(s) in the last "
        f"{history_days}d) implies {inferred_panels} panel(s), ~{expected_capacity}W expected — recent "
        f"best is only {round(recent_peak)}W in the last {recent_days}d, {shortfall_phrase}. Could also "
        f"be a stretch of cloudy weather rather than a dead panel — check the trend over more days "
        f"before assuming hardware."
    )
    info["missing_panels"] = missing_panels
    info["wired_in_series_pairs"] = wired_in_series_pairs

    # DEAD_PANEL_V2 guard 4 / new signal: does the loss hold roughly
    # EQUALLY across every productive hour (hardware — a dead panel caps
    # output the same amount at 10am and at 2pm) or does it vary a lot by
    # hour (more consistent with sun-angle-specific shading)? Reuses the
    # exact hour-of-day typical machinery detect_solar_shading already
    # has, just comparing the recent window's own typical against the
    # historical window's, hour by hour.
    # The "historical" side of this comparison must exclude the recent
    # window itself, or a trailer whose recent data happens to be part of
    # long_points (it always is — recent_points is a subset) would be
    # compared partly against itself.
    older_points = [(t, v) for t, v in long_points if t / 1000 < cutoff]
    historical_typical_by_hour = _vrm_pv_typical_by_hour(older_points, hour_tolerance)
    recent_typical_by_hour = _vrm_pv_typical_by_hour(recent_points, hour_tolerance)
    hour_ratios = [
        recent_typical_by_hour[hour] / historical_typical_by_hour[hour]
        for hour in historical_typical_by_hour
        if historical_typical_by_hour[hour] >= _SHADE_MIN_PRODUCTIVE_TYPICAL_WATTS
        and hour in recent_typical_by_hour
    ]
    if len(hour_ratios) >= _DEAD_PANEL_MIN_PRODUCTIVE_HOURS_FOR_STDEV:
        from statistics import pstdev, mean
        ratio_stdev = pstdev(hour_ratios)
        ratio_mean = mean(hour_ratios)
        info["hour_ratio_stdev"] = round(ratio_stdev, 3)
        info["hour_ratio_mean"] = round(ratio_mean, 3)
        info["productive_hours_compared"] = len(hour_ratios)
        if ratio_stdev >= _DEAD_PANEL_HOUR_RATIO_STDEV_THRESHOLD:
            # Loss is hour-specific, not proportional — route to shading
            # rather than confidently calling this hardware. Validated
            # against only one real case so far (see the constant's
            # comment); this is a soft rejection, not a confident "no."
            return False, (
                f"Power loss varies by hour ({round(ratio_mean * 100)}% of typical +/- "
                f"{round(ratio_stdev * 100)}pp across {len(hour_ratios)} productive hours) rather than "
                f"holding steady — more consistent with sun-angle-specific shading than a hardware "
                f"fault that would cap output equally all day; check solar-shading status instead"
            ), None, info
        confidence = min(95, confidence + 5)
        detail += (
            f" Loss is proportional across {len(hour_ratios)} productive hours ({round(ratio_mean * 100)}% "
            f"of typical +/- {round(ratio_stdev * 100)}pp) — consistent with hardware, not shading."
        )

    return True, detail, confidence, info


def unit_dead_panel_status(unit, subject=""):
    """
    Diagnostics-menu / on-demand version of detect_dead_panel for one
    unit. Returns (info, error) — same summary/status/confidence shape as
    unit_power_status and unit_shading_status.
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None, f"Invalid unit: {unit}"
    subject_text = str(subject or "").strip()

    id_user, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error
    site_id, installation_name, vrm_last_seen_seconds_ago, timezone_name, site_error = _resolve_vrm_site(
        unit_key, subject_text, id_user, victron_token
    )
    if site_error:
        return None, site_error
    return _dead_panel_status_for_site(
        unit_key, installation_name, vrm_last_seen_seconds_ago, site_id, victron_token
    )


def _dead_panel_status_for_site(unit_key, installation_name, vrm_last_seen_seconds_ago, site_id, victron_token):
    """The part of unit_dead_panel_status that runs once a VRM site is
    already resolved — see _vrm_power_snapshot_for_site's docstring for
    why this split exists (fleet_dead_panel_status reuses it per site from
    one bulk installations call)."""
    vrm_freshness = _vrm_freshness_tier(vrm_last_seen_seconds_ago)
    found, detail, confidence, info = detect_dead_panel(site_id, victron_token)

    # A site that has stopped reporting looks IDENTICAL to a dead panel on
    # this metric — both show "no recent peak worth mentioning" — but they
    # are different problems with different fixes (a comms issue vs a
    # hardware one). Checked live (2026-09-13): two real installations
    # flagged "dead panel" with a 14-day recent peak of 11W and 0W were
    # both actually VRM-disconnected for 3.5+ and 10+ days respectively —
    # not a panel failure, just no data to measure one. Don't let a
    # confident hardware verdict stand on stale evidence; downgrade to
    # "unknown" instead, same principle as _vrm_power_snapshot's "unknown".
    if found and vrm_freshness in ("stale", "disconnected"):
        found = None
        detail = (
            f"VRM data for this site is {vrm_freshness} ({_format_age(vrm_last_seen_seconds_ago)} old) — "
            f"a low recent peak here is at least as likely to mean the site isn't reporting as it is a "
            f"dead panel; {detail}"
        )
        confidence = None

    if found is None:
        status = "unknown"
        label = "cannot check for a dead panel — no usable/current VRM solar data"
    elif found:
        status = "dead_panel"
        panels = (info or {}).get("inferred_panels")
        label = f"possible dead/underperforming panel (of ~{panels} inferred)" if panels else "possible dead/underperforming panel"
    else:
        status = "ok"
        label = "solar output consistent with a healthy array"

    confidence_text = f" ({confidence}% confidence)" if confidence is not None else ""
    summary = f"{unit_key} ({installation_name}) — {label}{confidence_text}"
    if vrm_freshness not in ("fresh", "aging"):
        summary += f" — VRM data {_format_age(vrm_last_seen_seconds_ago)} old, take with caution"

    ui_status = {"dead_panel": "fail", "ok": "ok", "unknown": "warn"}.get(status, "warn")

    return {
        "unit": unit_key,
        "installation_name": installation_name,
        "dead_panel_status": status,
        "dead_panel_label": label,
        "dead_panel_detail": detail,
        "dead_panel_confidence": confidence,
        "dead_panel_info": info,
        "status": ui_status,
        "vrm_last_seen_seconds_ago": vrm_last_seen_seconds_ago,
        "vrm_freshness": vrm_freshness,
        "summary": summary,
    }, None


def fleet_dead_panel_status(max_workers=10):
    """
    Dead-panel status for every VRM installation, concurrently — backs a
    "Dead Panels" report the same way fleet_power_status/
    fleet_shading_status back theirs. One /stats call per site (a single
    ~60-day peak-watts pull covers both the historical and recent windows
    detect_dead_panel needs), so this is closer to fleet_power_status's
    cost than fleet_shading_status's. Returns (rows, error).
    """
    installations, mu_to_heads, error = _fleet_vrm_installations_with_heads()
    if error:
        return None, error
    _, victron_token, cred_error = _vrm_credentials()
    if cred_error:
        return None, cred_error

    def check_one(installation):
        head_units = mu_to_heads.get(installation["installation_name"].upper(), [])
        row = {"unit": installation["installation_name"], "head_units": head_units}
        # See fleet_power_status's check_one for why unit_key is the
        # resolved head when known.
        display_unit = head_units[0] if head_units else installation["installation_name"]
        snapshot, snap_error = _dead_panel_status_for_site(
            display_unit, installation["installation_name"],
            installation["vrm_last_seen_seconds_ago"], installation["site_id"], victron_token,
        )
        if snap_error:
            row["error"] = snap_error
        else:
            row.update(snapshot)
            row["unit"] = installation["installation_name"]
        return row

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        rows = list(pool.map(check_one, installations))
    return rows, None


def fleet_vrm_freshness_status():
    """
    VRM data freshness for every installation, fleet-wide — backs a "VRM
    Disconnected" report. Unlike the other three fleet_* checks, this
    needs no per-site follow-up call at all: freshness comes straight off
    the one bulk installations call's last_timestamp (see
    _fleet_vrm_installations_with_heads), so it's the cheapest of the
    fleet reports by a wide margin — safe to refresh far more often, and
    the one report here that could reasonably run live on a button click
    instead of waiting on a scheduled poll.
    Returns (rows, error).
    """
    installations, mu_to_heads, error = _fleet_vrm_installations_with_heads()
    if error:
        return None, error
    rows = []
    for installation in installations:
        freshness = _vrm_freshness_tier(installation["vrm_last_seen_seconds_ago"])
        age = installation["vrm_last_seen_seconds_ago"]
        age_label = f"last seen {_format_age(age)} ago" if age is not None else "never reported"
        head_units = mu_to_heads.get(installation["installation_name"].upper(), [])
        # RD3315(MU8083), not MU8083 — see fleet_power_status's check_one
        # for why: this trailer's ERP-linked head is the identifier a
        # ticket would actually use, when one is known.
        display_unit = (
            f"{head_units[0]}({installation['installation_name']})" if head_units
            else installation["installation_name"]
        )
        rows.append({
            "unit": installation["installation_name"],
            "head_units": head_units,
            "vrm_last_seen_seconds_ago": age,
            "vrm_freshness": freshness,
            "status": {
                "fresh": "ok", "aging": "ok", "stale": "warn",
                "disconnected": "fail", "unknown": "warn",
            }.get(freshness, "warn"),
            "summary": f"{display_unit} — VRM {freshness} ({age_label})",
        })
    return rows, None


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

    snapshot, error = _vrm_power_snapshot(unit_key, subject_text)
    if error:
        return None, error
    installation_name = snapshot["installation_name"]
    battery_soc_percent = snapshot["battery_soc_percent"]
    soc_error = snapshot["soc_error"]
    ac_power_status = snapshot["ac_power_status"]
    ac_power_label = snapshot["ac_power_label"]
    ac_power_detail = snapshot["ac_power_detail"]
    ac_power_confidence = snapshot["ac_power_confidence"]
    vrm_freshness = snapshot["vrm_freshness"]

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
    # A risk verdict built on a stale SOC reading is just as misleading as
    # a stale plugged-in verdict — "45% heading into 3 cloudy days" means
    # nothing if that 45% is two days old. Require at least "aging"
    # freshness (VRM heard from this site within the last 2h) before
    # computing one at all.
    if battery_soc_percent is not None and forecast and vrm_freshness in ("fresh", "aging"):
        if battery_soc_percent < 40 and cloudy_days >= 3:
            risk = "high"
        elif battery_soc_percent < 60 and cloudy_days >= 2:
            risk = "elevated"
        else:
            risk = "low"

    summary_parts = (
        [f"Battery SOC {battery_soc_percent:g}%"] if battery_soc_percent is not None
        else ["Battery SOC unavailable"]
    )
    if forecast:
        summary_parts.append(f"{cloudy_days}/{total_days} cloudy day(s) ahead at {location_label}")
    if risk:
        summary_parts.append(f"risk: {risk}")
    elif battery_soc_percent is not None and vrm_freshness not in ("fresh", "aging"):
        summary_parts.append(f"risk: unknown — VRM data {_format_age(snapshot['vrm_last_seen_seconds_ago'])} old")
    confidence_text = f" ({ac_power_confidence}% likely)" if ac_power_confidence is not None else ""
    summary_parts.append(ac_power_label + confidence_text)
    summary = f"{unit_key} — " + ", ".join(summary_parts)

    # "not_detected" is the one that matters most operationally — it's the
    # same condition ERP tickets get filed under as "unplugged" — so it
    # gets the status that stays on screen until dismissed, not a fading
    # toast (see appendDiagnosticButton's status->notify mapping). "unknown"
    # gets "warn", not "fail" — it means the data needed to call it either
    # way isn't there, which is a different problem than a confirmed read.
    status = {
        "present": "ok",
        "no_charger_hardware": "ok",
        "uncertain": "warn",
        "unknown": "warn",
        "not_detected": "fail",
    }.get(ac_power_status, "ok")

    return {
        "unit": unit_key,
        "installation_name": installation_name,
        "battery_soc_percent": battery_soc_percent,
        "soc_error": soc_error,
        "location": location_label,
        "forecast": forecast,
        "cloudy_days": cloudy_days,
        "forecast_days": total_days,
        "risk": risk,
        "weather_error": weather_error,
        "ac_power_status": ac_power_status,
        "ac_power_label": ac_power_label,
        "ac_power_detail": ac_power_detail,
        "ac_power_confidence": ac_power_confidence,
        "vrm_last_seen_seconds_ago": snapshot["vrm_last_seen_seconds_ago"],
        "vrm_freshness": vrm_freshness,
        "status": status,
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
    # Resets to 0 at local midnight and accumulates through the day, so this
    # is a sawtooth over multi-day windows by design — that ramp is the point
    # (how much each day actually harvested), not a bug to smooth out.
    "yield_today": {"code": "YT", "label": "Solar Yield (Today)", "unit": "kWh"},
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
    site_id, installation_name, vrm_last_seen_seconds_ago, _timezone_name, site_error = _resolve_vrm_site(
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
        "vrm_last_seen_seconds_ago": vrm_last_seen_seconds_ago,
        "vrm_freshness": _vrm_freshness_tier(vrm_last_seen_seconds_ago),
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
