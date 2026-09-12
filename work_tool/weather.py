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
