"""
Per-unit busy/lock registry and the shared per-unit notes.

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
import shutil
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


_unit_busy = {}
_unit_busy_lock = threading.Lock()
_UNIT_BUSY_LOG_MAX = 200
def unit_busy_status(unit):
    """Return a copy of the current busy-state dict for a unit, or None if free."""
    unit = str(unit or "").strip()
    with _unit_busy_lock:
        info = _unit_busy.get(unit)
        return dict(info) if info else None
def unit_busy_start(unit, action, version=None):
    """
    Try to mark a unit busy with the given action.
    Returns (ok, token_or_None, existing_info_or_None). On success the caller
    gets an ownership token that must be presented to touch/end the job.
    """
    unit = str(unit or "").strip()
    with _unit_busy_lock:
        existing = _unit_busy.get(unit)
        if existing:
            return False, None, dict(existing)
        token = uuid.uuid4().hex
        _unit_busy[unit] = {
            "unit": unit,
            "action": action,
            "token": token,
            "phase": "start",
            "version": version,
            "log": [],
            "started_at": time.time(),
        }
        return True, token, None
def unit_busy_touch(unit, token, phase=None, version=None, log_line=None):
    """Update phase/version and optionally append a log line. Returns True if applied."""
    unit = str(unit or "").strip()
    with _unit_busy_lock:
        info = _unit_busy.get(unit)
        if not info or info.get("token") != token:
            return False
        if phase is not None:
            info["phase"] = phase
        if version is not None:
            info["version"] = version
        if log_line:
            info.setdefault("log", []).append(str(log_line))
            info["log"] = info["log"][-_UNIT_BUSY_LOG_MAX:]
        return True
def unit_busy_end(unit, token):
    """Release a unit's busy state if the token matches. Returns True if cleared."""
    unit = str(unit or "").strip()
    with _unit_busy_lock:
        info = _unit_busy.get(unit)
        if not info or info.get("token") != token:
            return False
        del _unit_busy[unit]
        return True
def unit_busy_force_clear(unit):
    """Force-clear a unit's busy state regardless of token — escape hatch for a stuck lock."""
    unit = str(unit or "").strip()
    with _unit_busy_lock:
        return _unit_busy.pop(unit, None) is not None
def list_busy_units():
    """Return a list of {unit, action, phase, started_at} for every currently busy unit."""
    with _unit_busy_lock:
        return [
            {
                "unit": info.get("unit"),
                "action": info.get("action"),
                "phase": info.get("phase"),
                "started_at": info.get("started_at"),
            }
            for info in _unit_busy.values()
        ]
# ---- Default data dir ------------------------------------------------------
# These paths used to be built from __file__, which was the repo root while
# this was work_tool.py. The package split moved __file__ into work_tool/, so
# the default quietly became work_tool/data/live/ instead of the data/live/
# that unit_history, tech_stats and shading_snapshots all use. The default is
# pinned to the repo root again, and _adopt_legacy_data_file carries over
# whatever was written to the package-local dir in the meantime.
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGACY_PACKAGE_DATA_DIR = os.path.join(_PACKAGE_DIR, "data", "live")
_legacy_adopt_lock = threading.Lock()
def _default_data_dir():
    data_dir = (os.getenv("WORK_TOOL_DATA_DIR") or "").strip()
    if not data_dir:
        data_dir = os.path.join(os.path.dirname(_PACKAGE_DIR), "data", "live")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir
def _merge_entries_by_updated_at(current, legacy):
    """Merge two {key: {..., "updated_at": iso}} dicts, keeping the newer
    entry per key. ISO timestamps from isoformat() sort as strings."""
    merged = dict(current)
    for key, entry in legacy.items():
        mine = merged.get(key)
        if not isinstance(mine, dict) or str((entry or {}).get("updated_at") or "") > str(mine.get("updated_at") or ""):
            merged[key] = entry
    return merged
def _adopt_legacy_data_file(name, merge_json=False):
    """
    Move work_tool/data/live/<name> into the default data dir, once. JSON
    stores are merged entry by entry (newer updated_at wins) so neither
    copy's notes or ticket flags are lost; anything else is taken only if
    it is newer than the copy already there. The old file is renamed to
    <name>.migrated rather than deleted. Fails soft: on any error the old
    file stays put and the next call tries again.
    """
    if (os.getenv("WORK_TOOL_DATA_DIR") or "").strip():
        return
    legacy = os.path.join(_LEGACY_PACKAGE_DATA_DIR, name)
    if not os.path.isfile(legacy):
        return
    with _legacy_adopt_lock:
        if not os.path.isfile(legacy):
            return
        target = os.path.join(_default_data_dir(), name)
        try:
            if merge_json and os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    current = json.load(f)
                with open(legacy, "r", encoding="utf-8") as f:
                    old = json.load(f)
                merged = _merge_entries_by_updated_at(current, old)
                tmp_path = target + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(merged, f, indent=2, sort_keys=True)
                os.replace(tmp_path, target)
            elif not os.path.isfile(target) or os.path.getmtime(legacy) > os.path.getmtime(target):
                shutil.copy2(legacy, target)
            os.replace(legacy, legacy + ".migrated")
        except (OSError, ValueError) as exc:
            print(f"Could not move {legacy} into {target}: {exc}")
_unit_notes_lock = threading.Lock()
def _unit_notes_path():
    _adopt_legacy_data_file("unit_notes.json", merge_json=True)
    return os.path.join(_default_data_dir(), "unit_notes.json")
def _load_unit_notes():
    try:
        with open(_unit_notes_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
def get_unit_note(unit):
    """Return (text, updated_at) for a unit's saved note (empty strings if none)."""
    unit = str(unit or "").strip()
    with _unit_notes_lock:
        notes = _load_unit_notes()
    entry = notes.get(unit) or {}
    return entry.get("text", ""), entry.get("updated_at", "")
def set_unit_note(unit, text):
    """Save (or clear, if text is blank) a unit's note. Returns the new updated_at."""
    unit = str(unit or "").strip()
    text = str(text or "")
    with _unit_notes_lock:
        path = _unit_notes_path()
        notes = _load_unit_notes()
        if text.strip():
            notes[unit] = {
                "text": text,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        else:
            notes.pop(unit, None)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
        return notes.get(unit, {}).get("updated_at", "")

# ---- Shared ticket triage state (Worked / Skipped) -------------------------
# Worked/Skipped used to live only in each browser's localStorage, so one
# tech's triage was invisible to anyone else looking at the same dashboard.
# This mirrors the unit-notes pattern above (one JSON file, same lock/atomic-
# write discipline) but keyed by ERP issue_id instead of unit. An entry is
# dropped once both flags are false, so the file stays bounded by however
# many tickets are actively marked right now, not by history.
_ticket_state_lock = threading.Lock()
def _ticket_state_path():
    _adopt_legacy_data_file("ticket_state.json", merge_json=True)
    return os.path.join(_default_data_dir(), "ticket_state.json")
def _load_ticket_state():
    try:
        with open(_ticket_state_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
def get_ticket_states():
    """Return {issue_id: {"worked": bool, "skipped": bool, "updated_at": str}} for
    every ticket currently marked worked and/or skipped, shared across everyone
    on the dashboard."""
    with _ticket_state_lock:
        return dict(_load_ticket_state())
def set_ticket_state(issue_id, worked=None, skipped=None):
    """Merge worked/skipped flags for one ticket; a field left None is unchanged.
    Returns the resulting entry (or None if the ticket ends up untouched)."""
    issue_id = str(issue_id or "").strip()
    if not issue_id:
        return None
    with _ticket_state_lock:
        path = _ticket_state_path()
        states = _load_ticket_state()
        entry = dict(states.get(issue_id) or {"worked": False, "skipped": False})
        if worked is not None:
            entry["worked"] = bool(worked)
        if skipped is not None:
            entry["skipped"] = bool(skipped)
        if entry.get("worked") or entry.get("skipped"):
            entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
            states[issue_id] = entry
        else:
            states.pop(issue_id, None)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(states, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
        return states.get(issue_id)
def clear_ticket_states(issue_ids=None):
    """Clear worked/skipped for the given issue_ids, or every ticket when None
    (the "Clear checkboxes" escape hatch — shared, so it clears for everyone)."""
    with _ticket_state_lock:
        path = _ticket_state_path()
        if issue_ids is None:
            states = {}
        else:
            states = _load_ticket_state()
            wanted = {str(i or "").strip() for i in issue_ids if str(i or "").strip()}
            for issue_id in wanted:
                states.pop(issue_id, None)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(states, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
        return states
