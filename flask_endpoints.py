from flask import Flask, request, jsonify, render_template, Response, redirect, url_for
from werkzeug.utils import secure_filename
import os
import copy
import re
import requests
import work_tool
from datetime import datetime, timedelta, timezone
import time
import json
import io
import sys
import uuid
import threading
import queue
import socket
import paramiko
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

WORK_TOOL_ENV = str(os.getenv("WORK_TOOL_ENV") or "live").strip().lower()
if WORK_TOOL_ENV not in ("live", "sandbox"):
    WORK_TOOL_ENV = "live"
WORK_TOOL_PORT = int(str(os.getenv("WORK_TOOL_PORT") or "5000").strip() or "5000")

def work_tool_data_dir():
    override = str(os.getenv("WORK_TOOL_DATA_DIR") or "").strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(BASE_DIR, override)
    if WORK_TOOL_ENV == "sandbox":
        return os.path.join(BASE_DIR, "data", "sandbox")
    return BASE_DIR

DATA_DIR = work_tool_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)


@app.context_processor
def inject_work_tool_runtime():
    return {
        "work_tool_env": WORK_TOOL_ENV,
        "work_tool_port": WORK_TOOL_PORT,
        "is_sandbox": WORK_TOOL_ENV == "sandbox",
    }


def _env_int(name, default):
    """
    int(os.getenv(name)) with a fallback, tolerating an empty or
    whitespace-only value the same way every REFRESH_SECONDS/KEEP_DAYS
    constant in this file used to hand-roll individually:
    `int((os.getenv(name) or str(default)).strip() or str(default))`.
    Collapses ~9 near-identical 3-line blocks into one-liners — same
    behavior, one place to get the fallback-of-a-fallback logic right.
    """
    raw = (os.getenv(name) or "").strip()
    return int(raw) if raw else int(default)


def _error(message, status=400):
    """
    Shared shape for the plain {"ok": False, "error": message} JSON error
    response every route in this file used to hand-type individually (92
    call sites collapsed onto this one helper) — one place to change if
    that shape ever needs a new field, and no risk of a typo'd key
    breaking a JS `.then()` chain that expects `data.error`. Routes that
    need extra fields alongside "error" (a handful do) still build their
    own dict; this only covers the plain, no-extra-fields case.
    """
    return jsonify({"ok": False, "error": message}), status


def automated_tasks_paused():
    """True when sandbox, or PAUSE_AUTOMATED_TASKS is set in .env (reloads each check)."""
    if WORK_TOOL_ENV == "sandbox":
        return True
    load_dotenv(ENV_PATH, override=True)
    value = str(os.getenv("PAUSE_AUTOMATED_TASKS") or "").strip().lower()
    return value in ("1", "true", "yes", "on")


def erp_writes_disabled():
    """
    When True, ERP-mutating dashboard actions stay visible but disabled,
    and matching POST routes return 403.
    Controlled by DISABLE_ERP_WRITES in .env (default: disabled / "1").
    Set DISABLE_ERP_WRITES=0 to allow writes.
    """
    load_dotenv(ENV_PATH, override=True)
    value = str(os.getenv("DISABLE_ERP_WRITES", "1")).strip().lower()
    return value in ("1", "true", "yes", "on", "")


def _erp_writes_blocked_response():
    return jsonify({
        "ok": False,
        "error": "ERP writes are disabled (set DISABLE_ERP_WRITES=0 in .env to enable).",
    }), 403

UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Recovery-email uploads are deleted once their job finishes, but a Windows
# file lock (or a crash mid-job) leaves the spreadsheet behind, and those
# accumulate silently. Sweep anything older than a day at startup.
UPLOAD_RETENTION_SECONDS = 24 * 60 * 60


def _sweep_stale_uploads():
    try:
        entries = os.listdir(UPLOAD_FOLDER)
    except OSError:
        return
    cutoff = time.time() - UPLOAD_RETENTION_SECONDS
    removed = 0
    for name in entries:
        path = os.path.join(UPLOAD_FOLDER, name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            # Still locked, or gone already — try again next start.
            pass
    if removed:
        print(f"Removed {removed} stale upload(s) from {UPLOAD_FOLDER}")


_sweep_stale_uploads()

# Validation history is append-only. Ninety days is well past what the flap
# report needs and keeps the file to a few MB on a storage-tight workstation;
# prune() also enforces a hard row ceiling and reclaims the freed space.
UNIT_HISTORY_KEEP_DAYS = _env_int("UNIT_HISTORY_KEEP_DAYS", 90)
import unit_history
try:
    unit_history.prune(keep_days=UNIT_HISTORY_KEEP_DAYS)
except Exception as _history_exc:  # never block startup on history
    print(f"Unit history prune skipped: {_history_exc}")

# Same retention window as unit_history, same reasoning — see
# alarm_history.py's module docstring for why its row growth is nowhere
# near unit_history's despite tracking a much larger live alarm count.
ALARM_HISTORY_KEEP_DAYS = _env_int("ALARM_HISTORY_KEEP_DAYS", 90)
import alarm_history
try:
    alarm_history.prune(keep_days=ALARM_HISTORY_KEEP_DAYS)
except Exception as _alarm_history_exc:  # never block startup on history
    print(f"Alarm history prune skipped: {_alarm_history_exc}")

# Scheduled "photograph the panels while they're actually shaded" tasks —
# see shading_snapshots.py's module docstring. One week is plenty of time
# for someone to have looked at a captured photo.
SHADING_SNAPSHOT_RETENTION_DAYS = int(
    (os.getenv("SHADING_SNAPSHOT_RETENTION_DAYS") or "7").strip() or "7"
)
import shading_snapshots
try:
    shading_snapshots.prune_old(retention_days=SHADING_SNAPSHOT_RETENTION_DAYS)
except Exception as _shading_snapshot_exc:  # never block startup on history
    print(f"Shading snapshot prune skipped: {_shading_snapshot_exc}")

# Per-tech ticket stats (resolved/worked/skipped counts) — see
# tech_stats.py's module docstring. Years of retention by default since a
# tech may genuinely want their all-time count, not just a recent window.
TECH_STATS_KEEP_DAYS = _env_int("TECH_STATS_KEEP_DAYS", 730)
import tech_stats
try:
    tech_stats.prune(keep_days=TECH_STATS_KEEP_DAYS)
except Exception as _tech_stats_exc:  # never block startup on history
    print(f"Tech stats prune skipped: {_tech_stats_exc}")

issue_jobs = {}
stream_jobs = issue_jobs  # shared job store for streamed validations
issues_validation_lock = threading.Lock()
shared_issue_job_lock = threading.Lock()
SHARED_ISSUES_JOB_ID = "shared"
ISSUE_STATE_EVENT_BATCH_SIZE = 500
RESOLVED_TRACKER_PATH = os.path.join(DATA_DIR, "resolved_today.json")
resolved_tracker_lock = threading.Lock()
ERP_POLL_INTERVAL_SECONDS = 30 * 60
ERP_POLL_THROTTLE_SECONDS = 29.5 * 60

# Cache for the scheduled Zabbix/VRM alerts poll below — the live endpoint
# (/issues/power-infra-alerts) calls both APIs fresh and takes ~7s, too slow
# for the dashboard to poll every row's warning glyph against. This cache is
# what the frontend actually polls; the scheduled loop is what keeps it warm.
_power_infra_cache = {"rows": [], "fetched_at": None, "zabbix_error": None, "vrm_error": None}
_power_infra_cache_lock = threading.Lock()

# Same shape, x4, for the fleet-wide VRM checks behind the Reports menu's
# Units Unplugged / Shaded Units / Dead Panels / VRM Disconnected reports,
# plus the Battery Outlook and Up Steady Power vs Cell checks below them.
# Each covers every VRM installation the fleet has, not just units with a
# matching open ticket (an earlier version of the first two reports only
# checked ticket-scoped units; broadened on request). In-memory only, by
# design — the ask was "keep these up to date without refreshing too often,
# without taking up a lot of space," and a plain dict refreshed on a timer
# costs zero disk and answers exactly that, the same way _power_infra_cache
# already does for Zabbix/VRM alerts. If per-unit HISTORY (not just current
# state) is wanted later, that's a different, bigger ask — see
# alarm_history.py's episode model for the precedent.
#
# The six caches/locks themselves, their /live + /cached routes, and their
# background poll loops are all built by make_fleet_report(), one call per
# report, near the bottom of this file (after the REFRESH_SECONDS constants
# they need) — not declared here. _fleet_shading_status_cache and its lock
# specifically are still read directly by issues_schedule_shading_snapshot_bulk
# further down, exactly as before the factory existed.

ISSUE_RESULT_KEYS = (
    "false_positives",
    "nuc_down",
    "stale_vpn",
    "truly_down",
    "scrypted_outage",
    "speaker_outage",
    "camera_outage",
    "panel_issues",
    "camera_view",
    "on_hold",
    "monitoring_hours",
    "termination",
    "relocation",
    "footage_request",
    "discarded_tickets",
)
ARIZONA_TZ = timezone(timedelta(hours=-7))
ARIZONA_VALIDATION_HOURS = (4,)
ARIZONA_VALIDATION_MINUTE = 0
ARIZONA_MISSING_COMPONENTS_HOUR = 4
ARIZONA_MISSING_COMPONENTS_MINUTE = 5
ARIZONA_NETSHEET_SYNC_HOUR = 4
ARIZONA_NETSHEET_SYNC_MINUTE = 10

PROJECT_RESULT_KEYS = (
    "projects_open",
    "projects_in_progress",
    "projects_prep",
)

CAMERA_FIELD_PRESET_IDS = frozenset({
    "camera_adjustment",
    "dark_views",
    "blurry_cameras",
    "dirty_cameras",
})

NUC_DOWN_FIELD_PRESET_IDS = frozenset({
    "nuc_down",
})

def _empty_issue_results():
    results = {key: [] for key in ISSUE_RESULT_KEYS}
    for key in PROJECT_RESULT_KEYS:
        results[key] = []
    return results

def _issue_results_dict(result_tuple):
    results = dict(zip(ISSUE_RESULT_KEYS, result_tuple))
    for key in PROJECT_RESULT_KEYS:
        results.setdefault(key, [])
    return results

def _issue_ids_from_results(results):
    """Issue ids that landed on the dashboard or Miscellaneous after validation."""
    ids = set()
    for key in ISSUE_RESULT_KEYS:
        for item in (results or {}).get(key) or []:
            issue_id = str((item or {}).get("issue_id") or "").strip()
            if issue_id:
                ids.add(issue_id)
    return ids

def _split_project_entries(project_entries):
    open_entries = []
    in_progress_entries = []
    for entry in project_entries or []:
        status = str((entry or {}).get("erp_status") or "").strip().lower()
        percent_raw = (entry or {}).get("percent_complete")
        try:
            percent_value = (
                float(percent_raw)
                if percent_raw not in (None, "")
                else 0.0
            )
        except (TypeError, ValueError):
            percent_value = 0.0
        # ERP often leaves status as "Open" and uses percent_complete for progress.
        if status == "in progress" or percent_value > 0:
            in_progress_entries.append(entry)
        else:
            open_entries.append(entry)
    return open_entries, in_progress_entries

def _attach_projects_results(results, project_entries, prep_entries=None):
    if results is None:
        results = _empty_issue_results()
    open_entries, in_progress_entries = _split_project_entries(project_entries)
    results["projects_open"] = open_entries
    results["projects_in_progress"] = in_progress_entries
    if prep_entries is not None:
        results["projects_prep"] = list(prep_entries or [])
    else:
        results.setdefault("projects_prep", [])
    results.pop("projects", None)
    return results

def _project_entry_count(results):
    return sum(len((results or {}).get(key) or []) for key in PROJECT_RESULT_KEYS)

def _today_key():
    return datetime.now().date().isoformat()

def _empty_resolved_tracker():
    return {"date": _today_key(), "issue_ids": []}

def _load_resolved_tracker():
    tracker = _empty_resolved_tracker()
    try:
        with open(RESOLVED_TRACKER_PATH, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
        if stored.get("date") == tracker["date"] and isinstance(stored.get("issue_ids"), list):
            tracker["issue_ids"] = [
                str(issue_id).strip()
                for issue_id in stored["issue_ids"]
                if str(issue_id).strip()
            ]
    except (OSError, ValueError, TypeError):
        pass
    return tracker

def _save_resolved_tracker(tracker):
    tmp_path = RESOLVED_TRACKER_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(tracker, handle)
    os.replace(tmp_path, RESOLVED_TRACKER_PATH)

def _resolved_stats():
    with resolved_tracker_lock:
        tracker = _load_resolved_tracker()
        if tracker["date"] != _today_key():
            tracker = _empty_resolved_tracker()
            _save_resolved_tracker(tracker)
        issue_ids = list(dict.fromkeys(tracker["issue_ids"]))
        return {
            "date": tracker["date"],
            "count": len(issue_ids),
            "issue_ids": issue_ids,
        }

def _mark_issue_resolved(issue_id):
    issue_id = str(issue_id or "").strip()
    if not issue_id:
        return _resolved_stats(), False
    with resolved_tracker_lock:
        tracker = _load_resolved_tracker()
        if tracker["date"] != _today_key():
            tracker = _empty_resolved_tracker()
        added = issue_id not in tracker["issue_ids"]
        if added:
            tracker["issue_ids"].append(issue_id)
            _save_resolved_tracker(tracker)
        stats = {
            "date": tracker["date"],
            "count": len(tracker["issue_ids"]),
            "issue_ids": list(tracker["issue_ids"]),
        }
    return stats, added

def _unmark_resolved_issue_ids(issue_ids):
    issue_ids = {
        str(issue_id or "").strip()
        for issue_id in (issue_ids or [])
        if str(issue_id or "").strip()
    }
    if not issue_ids:
        return _resolved_stats(), set()
    with resolved_tracker_lock:
        tracker = _load_resolved_tracker()
        if tracker["date"] != _today_key():
            tracker = _empty_resolved_tracker()
            _save_resolved_tracker(tracker)
            return {
                "date": tracker["date"],
                "count": 0,
                "issue_ids": [],
            }, set()
        remaining = [
            issue_id for issue_id in tracker["issue_ids"]
            if issue_id not in issue_ids
        ]
        restored = set(tracker["issue_ids"]) - set(remaining)
        if restored:
            tracker["issue_ids"] = remaining
            _save_resolved_tracker(tracker)
        stats = {
            "date": tracker["date"],
            "count": len(tracker["issue_ids"]),
            "issue_ids": list(tracker["issue_ids"]),
        }
    return stats, restored

def _item_issue_id(item):
    if isinstance(item, dict):
        return str(item.get("issue_id") or "").strip()
    return ""

def _listed_issue_ids(results):
    listed = set()
    for key, items in (results or {}).items():
        if key == "projects" or key in PROJECT_RESULT_KEYS:
            continue
        for item in items or []:
            issue_id = _item_issue_id(item)
            if issue_id:
                listed.add(issue_id)
    return listed

def _result_item_key(item):
    return (
        str((item or {}).get("issue_id") or "").strip(),
        str((item or {}).get("unit") or "").strip(),
        str((item or {}).get("camera_target") or "").strip(),
    )

def _find_result_item(items, issue_id, unit, camera_target=""):
    want = (
        str(issue_id or "").strip(),
        str(unit or "").strip(),
        str(camera_target or "").strip(),
    )
    for item in items or []:
        if _result_item_key(item) == want:
            return item
    return None

def _remove_issue_ids_from_results(results, issue_ids):
    removed = 0
    for key in ISSUE_RESULT_KEYS:
        before = len(results.get(key) or [])
        results[key] = [
            item for item in (results.get(key) or [])
            if _item_issue_id(item) not in issue_ids
        ]
        removed += before - len(results[key])
    return removed

def _issue_class_key(issue):
    """
    The fields that decide whether a listed ticket needs to be dropped and
    freshly revalidated on the next poll — Issue Type/Subtype, same as
    always, plus Subject. A subject edit isn't just cosmetic: unit, region,
    and even which list a ticket belongs in are all parsed FROM the
    subject during validation, so a changed subject needs the exact same
    remove-then-revalidate treatment a type/subtype change gets, not a
    quiet text swap that leaves a stale unit/region/list behind it.
    """
    issue = issue or {}
    return (
        str(issue.get("issue_type") or "").strip().lower(),
        str(issue.get("issue_subtype") or "").strip().lower(),
        str(issue.get("subject") or "").strip(),
    )

def _item_class_differs(item, issue):
    """True if the listed row's Issue Type, Subtype, or Subject does not match ERP."""
    item = item or {}
    issue = issue or {}
    if item.get("reason") and "issue_subtype" not in item and "undiagnosed" not in item:
        return False
    erp_type, erp_subtype, erp_subject = _issue_class_key(issue)
    item_subject = str(item.get("subject") or "").strip()
    if item_subject and erp_subject and item_subject != erp_subject:
        return True
    item_type = str(item.get("issue_type") or "").strip().lower()
    item_subtype = str(item.get("issue_subtype") or "").strip().lower()
    if item_type:
        return item_type != erp_type or item_subtype != erp_subtype
    item_outage = str(item.get("outage_type") or "").strip().lower()
    erp_outage = work_tool._parse_outage_kind(issue.get("issue_type")).lower()
    item_undiagnosed = bool(item.get("undiagnosed"))
    erp_undiagnosed = not bool(erp_subtype)
    return (
        item_subtype != erp_subtype
        or item_outage != erp_outage
        or item_undiagnosed != erp_undiagnosed
    )

def _find_classification_changed_records(
    current_records, known_ids, results, classifications, exclude_ids
):
    current_by_id = {
        issue["issue_id"]: issue
        for issue in current_records
        if issue.get("issue_id")
    }
    exclude_ids = exclude_ids or set()
    classifications = classifications or {}
    updated = []
    seen = set()
    for issue_id, issue in current_by_id.items():
        if issue_id not in known_ids or issue_id in exclude_ids or issue_id in seen:
            continue
        stored = classifications.get(issue_id)
        if stored is not None and stored != _issue_class_key(issue):
            updated.append(issue)
            seen.add(issue_id)
    for items in (results or {}).values():
        for item in items or []:
            issue_id = _item_issue_id(item)
            if (
                not issue_id
                or issue_id in seen
                or issue_id in exclude_ids
                or issue_id not in known_ids
            ):
                continue
            issue = current_by_id.get(issue_id)
            if issue and _item_class_differs(item, issue):
                updated.append(issue)
                seen.add(issue_id)
    return updated

def _erp_row_fields(issue):
    issue_type = str((issue or {}).get("issue_type") or "").strip()
    issue_subtype = str((issue or {}).get("issue_subtype") or "").strip()
    subject = str((issue or {}).get("subject") or "").strip()
    site = str((issue or {}).get("site") or "").strip()
    fields = {
        "issue_type": issue_type,
        "outage_type": work_tool._parse_outage_kind(issue_type),
        "issue_subtype": issue_subtype,
        "undiagnosed": not bool(issue_subtype),
    }
    if subject:
        fields["subject"] = subject
    if site:
        fields["site"] = site
    return fields


def _patch_issue_class_on_results(results, issue):
    """Write current ERP type/subtype onto every listed row for this ticket."""
    fields = _erp_row_fields(issue)
    issue_id = str((issue or {}).get("issue_id") or "").strip()
    patched = []
    if not issue_id:
        return patched
    site = str(fields.get("site") or "").strip()
    for key in ISSUE_RESULT_KEYS:
        for item in (results or {}).get(key) or []:
            if _item_issue_id(item) == issue_id:
                item.update(fields)
                if site:
                    unit = str(item.get("unit") or "").strip()
                    subject = str(item.get("subject") or fields.get("subject") or "").strip()
                    if unit:
                        work_tool._store_site_id_cache(unit, subject, site)
                patched.append((key, item))
    return patched

def _snapshot_items_by_issue_id(results, issue_ids):
    snapshot = {}
    for key in ISSUE_RESULT_KEYS:
        for item in (results or {}).get(key) or []:
            issue_id = _item_issue_id(item)
            if issue_id in issue_ids:
                snapshot.setdefault(issue_id, []).append(item)
    return snapshot

def _preserve_result_item_state(old_item, new_item):
    # Any field a route patches directly into job["results"] (see
    # _patch_shared_issue_fields and the routes that write compute_label/
    # connectivity_kind below) must be listed here, or the next routine
    # ERP poll — which rebuilds results from scratch — silently reverts it
    # with no error. Caught live, 2026-09-23: compute_label (set by
    # /issues/ping-compute) and connectivity_kind (set by /issues/set-fields)
    # were both missing, so a tech's own classification could vanish on
    # the next 30-minute poll — the same failure shape as the move_to and
    # subject-detection bugs found and fixed earlier this session.
    if not old_item or not new_item:
        return new_item
    for field in (
        "led_status",
        "speaker_up",
        "camera_up",
        "panel_fisheye_up",
        "camera_view_status",
        "hold_kind",
        "erp_status",
        "compute_label",
        "connectivity_kind",
    ):
        if old_item.get(field) is not None:
            new_item[field] = old_item[field]
    if "is_new" in old_item:
        new_item["is_new"] = old_item["is_new"]
    return new_item

def _apply_preserved_state_to_results(new_results, old_items):
    old_by_key = {_result_item_key(item): item for item in old_items}
    for key in ISSUE_RESULT_KEYS:
        for item in new_results.get(key) or []:
            old_item = old_by_key.get(_result_item_key(item))
            if old_item is None and item.get("issue_id"):
                issue_id = _item_issue_id(item)
                old_item = next(
                    (
                        candidate
                        for candidate in old_items
                        if _item_issue_id(candidate) == issue_id
                    ),
                    None,
                )
            _preserve_result_item_state(old_item, item)
    return new_results

def _new_validation_run_id():
    return uuid.uuid4().hex

def _patch_shared_issue_fields(unit, fields, camera_target=None, result_keys=None):
    """Keep pinged LED/status fields on the shared job so ERP polls do not revert them."""
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if not job or not job.get("results") or not fields:
        return
    unit = str(unit or "").strip()
    if not unit:
        return
    camera_target = None if camera_target is None else str(camera_target)
    keys = result_keys or (
        [key for key in ISSUE_RESULT_KEYS if key != "discarded_tickets"]
        + list(PROJECT_RESULT_KEYS)
    )
    with job["state_lock"]:
        for key in keys:
            for item in job["results"].get(key) or []:
                if str(item.get("unit") or "").strip() != unit:
                    continue
                if (
                    camera_target is not None
                    and str(item.get("camera_target") or "") != camera_target
                ):
                    continue
                item.update(fields)

def _move_shared_issue_to_list(results, issue_id, unit, from_key, to_key, extra_fields=None):
    """Move every shared-job issue row for (issue_id, unit) from from_key to to_key.

    A camera-outage ticket with no camera named in its subject fans out into
    several rows sharing the same issue_id+unit (one per camera — see
    work_tool._core's generic camera-outage fan-out). Moving only the first/
    last match here silently dropped the other rows on reclassify.
    """
    issue_id = str(issue_id or "").strip()
    unit = str(unit or "").strip()
    if not issue_id or not unit or from_key == to_key:
        return False
    if from_key not in results or to_key not in results:
        return False
    moved_items = []
    remaining = []
    for item in results.get(from_key) or []:
        if (
            _item_issue_id(item) == issue_id
            and str((item or {}).get("unit") or "").strip() == unit
        ):
            moved_items.append(item)
        else:
            remaining.append(item)
    if not moved_items:
        return False
    results[from_key] = remaining
    if extra_fields:
        for item in moved_items:
            item.update(extra_fields)
    results.setdefault(to_key, []).extend(moved_items)
    return True

def _sync_shared_validate_result(unit, issue_id, source_list_id, to_list_id, extra_fields):
    """
    Keep the shared job's own copy of a ticket in sync with a Validate
    (Quick/Full) result. Without this, Validate only ever updated the
    calling browser's own view — the next shared-state snapshot
    (pollSharedReportState -> fillList on the frontend, which fully
    replaces each list from server truth whenever results change) would
    silently revert the row back to whatever category/LED the server
    still had, since the server was never told what Validate just found.
    Caught live: "ran validate on RD3059 and it returned down full but
    stayed in up steady list, with LED light green" — RD3059 really was
    down; the server's own copy just never learned that.

    Requires both issue_id and source_list_id (the caller's own current
    list) to do anything — Unit Tools' ad-hoc validates send neither (no
    shared job entry to sync for those), and skipping there is
    deliberate: patching by unit alone risks touching a different,
    unrelated open ticket for the same unit.
    """
    issue_id = str(issue_id or "").strip()
    source_list_id = str(source_list_id or "").strip()
    if not issue_id or not source_list_id:
        return
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or job.get("results") is None:
        return
    with job["state_lock"]:
        results = job["results"]
        if source_list_id not in results:
            return
        moved = False
        if to_list_id and to_list_id != source_list_id and to_list_id in results:
            moved = _move_shared_issue_to_list(
                results, issue_id, unit, source_list_id, to_list_id, extra_fields
            )
        if not moved and extra_fields:
            unit_norm = str(unit or "").strip()
            # No `break` — a fanned-out camera-outage ticket has several rows
            # sharing this issue_id+unit (one per camera); all of them need
            # the same patch, not just whichever came first.
            for item in results.get(source_list_id) or []:
                if (
                    _item_issue_id(item) == issue_id
                    and str((item or {}).get("unit") or "").strip() == unit_norm
                ):
                    item.update(extra_fields)
                    moved = True
        if moved:
            job["version"] += 1

def _publish_job_event(job_id, event):
    job = stream_jobs.get(job_id)
    if job is None:
        return
    job["queue"].put(event)
    event_lock = job.get("event_lock")
    if event_lock is not None:
        with event_lock:
            history_event = copy.deepcopy(event)
            if history_event.get("type") == "done":
                history_event.pop("results", None)
            job["events"].append(history_event)

def _create_issue_job(job_id):
    stream_jobs[job_id] = {
        "queue": queue.Queue(),
        "done": False,
        "results": None,
        "known_issue_ids": set(),
        "issue_classifications": {},
        "poll_lock": threading.Lock(),
        "state_lock": threading.RLock(),
        "events": [],
        "event_lock": threading.Lock(),
        "version": 0,
        "validation_run_id": "",
        "last_poll_at": 0.0,
        "last_projects_poll_at": 0.0,
    }
    thread = threading.Thread(
        target=_run_issues_validation,
        args=(job_id,),
        daemon=True,
    )
    thread.start()
    return job_id

def _ensure_shared_issue_job():
    with shared_issue_job_lock:
        if SHARED_ISSUES_JOB_ID not in stream_jobs:
            _create_issue_job(SHARED_ISSUES_JOB_ID)
    return SHARED_ISSUES_JOB_ID

def dedupe(lst):
    return list(dict.fromkeys(lst))

def _safe_stream_write(stream, text):
    """Write text to a console stream without crashing on unsupported Unicode."""
    if not stream:
        return
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        stream.write(text.encode(encoding, errors="replace").decode(encoding))

# Every job/poll function below used to redirect print() output by
# reassigning the bare `sys.stdout = <capture>` global directly, then
# restoring it in a `finally`. That's safe only as long as exactly one such
# function is ever mid-run at a time — true back when the shared ticket
# queue only ever got touched by one HTTP request at a time, false since
# the ERP ticket/project poll (and other background loops) started running
# on their own scheduled threads concurrently with a tech's own manual
# Refresh/Revalidate clicks: two threads racing to set/restore the same
# global `sys.stdout` can leave one job's print() lines landing in
# another job's captured buffer (or the console) instead of its own.
#
# Fix: `sys.stdout` is reassigned exactly ONCE, at import time, to this
# dispatcher. Every capture site below then pushes/pops its own
# destination on a per-THREAD stack (via threading.local, not a bare
# global) instead of touching sys.stdout itself — two threads each pushing
# their own capture never see each other's, no lock required.
_true_stdout = sys.stdout
_stdout_capture_local = threading.local()

def _push_stdout_capture(target):
    stack = getattr(_stdout_capture_local, "stack", None)
    if stack is None:
        stack = []
        _stdout_capture_local.stack = stack
    stack.append(target)

def _pop_stdout_capture():
    stack = getattr(_stdout_capture_local, "stack", None)
    if stack:
        stack.pop()

class _ThreadLocalStdoutDispatcher:
    """Installed as sys.stdout exactly once (see _true_stdout above).
    Routes print() to whatever the CURRENT THREAD last pushed via
    _push_stdout_capture, falling back to the real console when nothing
    has. `.original` always means the real console, never "whatever
    sys.stdout happened to be" — JobStdout instances below echo to it
    directly so their own writes don't recurse back through this
    dispatcher."""
    def __init__(self, original):
        self.original = original

    def _current(self):
        stack = getattr(_stdout_capture_local, "stack", None)
        return stack[-1] if stack else None

    def write(self, text):
        target = self._current()
        if target is not None:
            return target.write(text)
        return self.original.write(text)

    def flush(self):
        target = self._current()
        if target is not None and hasattr(target, "flush"):
            try:
                target.flush()
            except Exception:
                pass
        self.original.flush()

sys.stdout = _ThreadLocalStdoutDispatcher(_true_stdout)

class JobStdout:
    """Tee stdout into a per-job queue so the browser can stream it. This endpoint was created by Cursor reusing code I wrote from work tool"""
    def __init__(self, job_id, original):
        self.job_id = job_id
        self.original = original
        self._buf = ""

    def write(self, text):
        _safe_stream_write(self.original, text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            job = stream_jobs.get(self.job_id)
            if job is None:
                continue
            if line.startswith("__PROGRESS__ "):
                parts = line.split(" ", 3)
                try:
                    current = int(parts[1])
                    total = int(parts[2])
                except (IndexError, ValueError):
                    continue
                unit = parts[3] if len(parts) > 3 else ""
                _publish_job_event(self.job_id, {
                    "type": "progress",
                    "current": current,
                    "total": total,
                    "unit": unit,
                })
                continue
            _publish_job_event(self.job_id, {"type": "log", "line": line})
        return len(text)

    def flush(self):
        if self.original:
            self.original.flush()

# The background pollers (fleet reports, Power & Infra Alerts, the ERP
# ticket/project pull, the ART report) never pushed a stdout capture of
# their own, so every print() they made — including the startup-sequence
# lines added alongside this ("first pass in Ns", "poll starting...")  —
# went straight to _true_stdout: the real process console (a service log
# file on the live instance), never the shared job's own stream the
# dashboard's Stdout pane and progress bar actually read from. A tech
# watching the browser right after a restart saw nothing, no matter how
# much detail those prints carried — this is why. Tee'ing them into the
# SAME shared-job stream _run_issues_validation already uses fixes that
# with no new UI: they show up as ordinary lines in the pane that's
# already there.
def _with_shared_job_stdout_capture(fn):
    """Run fn() with print() output also tee'd into the shared issues
    job's console stream. Safe before that job exists yet — JobStdout
    itself no-ops (after still echoing to the real console) if the job
    isn't found."""
    job_id = _ensure_shared_issue_job()
    _push_stdout_capture(JobStdout(job_id, _true_stdout))
    try:
        return fn()
    finally:
        _pop_stdout_capture()

def _shared_console_print(text):
    """One-off status line (e.g. a loop's "first pass in Ns" announcement)
    routed the same way — see _with_shared_job_stdout_capture."""
    _with_shared_job_stdout_capture(lambda: print(text))

def _run_issues_validation(job_id, scheduled=False):
    if scheduled and automated_tasks_paused():
        print(
            "Scheduled ticket-queue validation skipped — "
            "PAUSE_AUTOMATED_TASKS is enabled"
        )
        return
    job = stream_jobs[job_id]
    poll_lock = job["poll_lock"]
    poll_lock.acquire()
    try:
        with issues_validation_lock:
            _push_stdout_capture(JobStdout(job_id, _true_stdout))
            try:
                if scheduled:
                    when = _arizona_now()
                    print(
                        "Scheduled 4:00 AM AZ ticket-queue revalidation started "
                        f"({when.strftime('%Y-%m-%d %H:%M %Z')})"
                    )
                work_tool.generate_net_array()
                issue_records = work_tool.fetch_erp_issues()
                project_records = work_tool.fetch_erp_projects()
                prep_records = work_tool.fetch_erp_prep_projects()
                with job["state_lock"]:
                    job["issue_classifications"] = {
                        issue["issue_id"]: _issue_class_key(issue)
                        for issue in issue_records
                        if issue.get("issue_id")
                    }
                print(
                    f"Fetched {len(issue_records)} Open/Monitoring/On Hold issues from ERP"
                )
                print(
                    f"Fetched {len(project_records)} Open/In Progress NOC projects from ERP"
                )
                print(
                    f"Fetched {len(prep_records)} Open/In Progress Prep projects from ERP"
                )
                results = _issue_results_dict(
                    work_tool.validate_issue_records(issue_records)
                )
                _attach_projects_results(
                    results,
                    work_tool.validate_project_records(project_records),
                    work_tool.build_prep_project_entries(prep_records),
                )
                resolved_ids = set(_resolved_stats()["issue_ids"])
                if resolved_ids:
                    _remove_issue_ids_from_results(results, resolved_ids)
                with job["state_lock"]:
                    job["results"] = results
                    job["known_issue_ids"] = _issue_ids_from_results(results)
                    job["validation_run_id"] = _new_validation_run_id()
                    job["version"] += 1
                    job["last_poll_at"] = time.time()
            finally:
                _pop_stdout_capture()
        _publish_job_event(job_id, {"type": "done", "results": job["results"]})
    except Exception as e:
        _publish_job_event(job_id, {"type": "log", "line": f"ERROR: {e}"})
        with job["state_lock"]:
            job["results"] = _empty_issue_results()
            job["validation_run_id"] = _new_validation_run_id()
            job["version"] += 1
        _publish_job_event(job_id, {"type": "done", "results": job["results"]})
    finally:
        job["done"] = True
        poll_lock.release()

def _run_recovery_email_check(job_id, report_path, delete_after=True):
    job = stream_jobs[job_id]
    _push_stdout_capture(JobStdout(job_id, _true_stdout))
    try:
        work_tool.generate_false_mu()
        work_tool.generate_net_array()
        recovery_errors = []
        needs_recovery_email, needs_initial_email, potential_false_positive, pending_recovery, email_status_up_to_date = work_tool.check_missing_recovery_emails(report_path, errors=recovery_errors)
        if recovery_errors:
            # Routes into the except block below, reusing its already-correct
            # "ERROR: ..." log line + empty-results handling instead of
            # silently publishing a "done" event that looks like a clean,
            # fully-up-to-date fleet.
            raise RuntimeError(recovery_errors[0])
        job["results"] = {
            "needs_recovery_email": needs_recovery_email,
            "needs_initial_email": needs_initial_email,
            "potential_false_positive": potential_false_positive,
            "pending_recovery": pending_recovery,
            "email_status_up_to_date": email_status_up_to_date,
        }
        job["queue"].put({"type": "done", "results": job["results"]})
    except Exception as e:
        job["queue"].put({"type": "log", "line": f"ERROR: {e}"})
        job["queue"].put({"type": "done", "results": {
            "needs_recovery_email": [],
            "needs_initial_email": [],
            "potential_false_positive": [],
            "pending_recovery": [],
            "email_status_up_to_date": [],
        }})
    finally:
        _pop_stdout_capture()
        if delete_after:
            try:
                os.remove(report_path)
            except Exception as e:
                print(f"Failed to remove upload: {e}")
        job["done"] = True

def _sse_stream(job_id):
    job = stream_jobs.get(job_id)
    if job is None:
        return "Unknown job", 404

    def event_stream():
        while True:
            try:
                event = job["queue"].get(timeout=1)
            except queue.Empty:
                if job["done"]:
                    break
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "done":
                break

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

def _static_asset_version(filename):
    """
    mtime of a static file, for a `?v=` cache-bust query param — so a
    JS/CSS edit takes effect on the next page load (after the usual
    service restart) without anyone needing to hard-refresh. Flask's
    plain url_for('static', ...) carries no version of its own; a NOC
    tech who just does a normal refresh would otherwise keep the
    browser's cached copy of issues_results.js/css indefinitely. Falls
    back to "0" (still a valid, just non-cache-busting, query value) if
    the file can't be stat'd, rather than raising into a page render.
    """
    try:
        path = os.path.join(app.static_folder, filename)
        return str(int(os.path.getmtime(path)))
    except OSError:
        return "0"


def _render_issues_dashboard(job_id=None):
    """Shared Issues Dashboard UI (home page)."""
    if job_id is None:
        job_id = _ensure_shared_issue_job()
    elif job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template(
        "issues_results.html",
        job_id=job_id,
        work_tld=work_tool.work_tld(),
        mesh_base_url=work_tool.meshcentral_base_url(),
        raindance_base_url=work_tool.raindance_base_url(),
        automation_paused=automated_tasks_paused(),
        erp_writes_disabled=erp_writes_disabled(),
        js_version=_static_asset_version("issues_results.js"),
        css_version=_static_asset_version("issues_results.css"),
    )


def _page_moved(old_name, new_url="/", new_name="Issues Dashboard"):
    return render_template(
        "page_moved.html",
        old_name=old_name,
        new_url=new_url,
        new_name=new_name,
    )


@app.route("/", methods=["GET"])
def home():
    return _render_issues_dashboard()


@app.route("/victron", methods=["GET"])
@app.route("/victron/results", methods=["GET", "POST"])
def victron_form():
    return _page_moved("Victron VRM Checker")


@app.route("/outage_filter", methods=["GET"])
@app.route("/outage_filter/results", methods=["GET", "POST"])
def outage_form():
    return _page_moved("Outage Filter")


@app.route("/linux", methods=["GET"])
@app.route("/linux/results", methods=["GET", "POST"])
@app.route("/linux/watch/<job_id>", methods=["GET"])
def linux_form(job_id=None):
    return _page_moved("Linux Diagnostic Tool")


@app.route("/zabbix", methods=["GET"])
def zabbix_form():
    return _page_moved("Zabbix Monitor")


@app.route("/issues", methods=["GET"])
def issues_form():
    return _page_moved("Unit Outage Verification Tool (/issues)")


@app.route("/issues/results", methods=["POST"])
def issues_results():
    _ensure_shared_issue_job()
    return redirect(url_for("home"))


@app.route("/issues/watch", methods=["GET"])
def issues_watch_shared():
    return _page_moved("Issues watch (/issues/watch)")


@app.route("/issues/watch/<job_id>", methods=["GET"])
def issues_watch(job_id):
    return _render_issues_dashboard(job_id=job_id)

@app.route("/issues/stream/<job_id>", methods=["GET"])
def issues_stream(job_id):
    return _sse_stream(job_id)

@app.route("/issues/state/<job_id>", methods=["GET"])
def issues_state(job_id):
    job = stream_jobs.get(job_id)
    if job is None:
        return _error("Unknown job", 404)
    try:
        cursor = max(0, int(request.args.get("cursor", 0)))
        client_version = max(0, int(request.args.get("version", 0)))
    except (TypeError, ValueError):
        return _error("Invalid state cursor")

    with job["event_lock"]:
        next_cursor = min(
            cursor + ISSUE_STATE_EVENT_BATCH_SIZE,
            len(job["events"]),
        )
        events = copy.deepcopy(job["events"][cursor:next_cursor])
    with job["state_lock"]:
        version = job["version"]
        validation_run_id = job.get("validation_run_id") or ""
        results = (
            copy.deepcopy(job["results"])
            if job.get("results") is not None and client_version != version
            else None
        )
    resolved = _resolved_stats()
    with _recovery_email_status_lock:
        email_status_rev = _recovery_email_status_cache["rev"]
    return jsonify({
        "ok": True,
        "events": events,
        "cursor": next_cursor,
        "done": job["done"],
        "version": version,
        "validation_run_id": validation_run_id,
        "results": results,
        "resolved_today": resolved,
        "email_status_rev": email_status_rev,
    })

def _poll_shared_issue_queue(job_id, scope="issues", force=False, manual=False):
    """
    One incremental ERP poll pass for the shared ticket-queue job — new/
    removed/restored/updated tickets for scope="issues", or a fresh
    Open/In Progress project pull for scope="projects". Split out of the
    /issues/poll route itself so a scheduled background loop can call the
    exact same logic the manual "Pull Issues"/"Pull Projects" buttons do,
    not a re-implementation that could drift from it (see
    _erp_ticket_project_poll_loop). Returns (response_dict, http_status) —
    http_status is None for the normal 200 case, matching how the route
    itself used to build its response before this was split out.

    Deliberately does NOT check automated_tasks_paused() at all — ticket/
    project pull is a named exception to that flag now (Andrew's own
    request, 2026-09-15: resume it specifically, while the 4am Add-
    Missing-Components/netsheet-sync jobs stay paused), same pattern as
    the fleet-report polls and Power & Infra Alerts, which never
    consulted that flag either. This is what lets BOTH the client's own
    30-min auto-poll and the server-side scheduled loop
    (_erp_ticket_project_poll_loop) actually pull, not just one of them.
    """
    job = stream_jobs.get(job_id)
    if job is None:
        return {"ok": False, "error": "Unknown job"}, 404
    if not job["done"]:
        return {"ok": False, "error": "Initial validation is still running"}, 409
    if scope not in ("issues", "projects"):
        scope = "issues"
    poll_at_key = "last_poll_at" if scope == "issues" else "last_projects_poll_at"
    if not force:
        with job["state_lock"]:
            if time.time() - float(job.get(poll_at_key) or 0.0) < ERP_POLL_THROTTLE_SECONDS:
                return {
                    "ok": True,
                    "skipped": True,
                    "scope": scope,
                    "new_count": 0,
                    "removed_count": 0,
                    "restored_count": 0,
                    "updated_count": 0,
                    "project_count": 0,
                    "results": _empty_issue_results(),
                    "logs": [],
                    "resolved_today": _resolved_stats(),
                }, None
    if not job["poll_lock"].acquire(blocking=False):
        return {
            "ok": True,
            "busy": True,
            "scope": scope,
            "new_count": 0,
            "removed_count": 0,
            "restored_count": 0,
            "updated_count": 0,
            "project_count": 0,
            "results": _empty_issue_results(),
            "logs": [],
            "resolved_today": _resolved_stats(),
        }, None

    captured_stdout = io.StringIO()
    new_records = []
    missing_ids = set()
    restored_ids = set()
    updated_records = []
    project_count = 0
    fetched_count = None
    try:
        with issues_validation_lock:
            _push_stdout_capture(captured_stdout)
            try:
                incremental_results = _empty_issue_results()
                snapshot = None
                if scope == "projects":
                    project_records = work_tool.fetch_erp_projects()
                    prep_records = work_tool.fetch_erp_prep_projects()
                    print(
                        f"ERP project refresh found {len(project_records)} Open/In Progress NOC project"
                        f"{'' if len(project_records) == 1 else 's'}"
                    )
                    print(
                        f"ERP Prep refresh found {len(prep_records)} Open/In Progress Prep project"
                        f"{'' if len(prep_records) == 1 else 's'}"
                    )
                    project_entries = work_tool.validate_project_records(project_records)
                    prep_entries = work_tool.build_prep_project_entries(prep_records)
                    project_count = len(project_entries) + len(prep_entries)
                    with job["state_lock"]:
                        if job["results"] is None:
                            job["results"] = _empty_issue_results()
                        _attach_projects_results(
                            job["results"],
                            project_entries,
                            prep_entries,
                        )
                        for key in PROJECT_RESULT_KEYS:
                            incremental_results[key] = list(
                                (job["results"] or {}).get(key) or []
                            )
                        job["version"] += 1
                        snapshot = copy.deepcopy(job["results"])
                        job["last_projects_poll_at"] = time.time()
                else:
                    current_records = work_tool.fetch_erp_issues()
                    fetched_count = len(current_records)
                    print(
                        f"ERP refresh fetched {fetched_count} Open/Monitoring/On Hold ticket"
                        f"{'' if fetched_count == 1 else 's'} from ERP"
                    )
                    current_ids = {
                        issue["issue_id"] for issue in current_records if issue.get("issue_id")
                    }
                    resolved_ids = set(_resolved_stats()["issue_ids"])
                    new_records = [
                        issue for issue in current_records
                        if issue["issue_id"] not in job["known_issue_ids"]
                    ]
                    if force and manual:
                        with job["state_lock"]:
                            listed_ids_pre = _listed_issue_ids(job["results"])
                        retry_ids = current_ids - listed_ids_pre - resolved_ids
                        new_record_ids = {
                            issue["issue_id"] for issue in new_records if issue.get("issue_id")
                        }
                        retry_records = [
                            issue for issue in current_records
                            if issue.get("issue_id") in retry_ids
                            and issue["issue_id"] not in new_record_ids
                        ]
                        if retry_records:
                            print(
                                f"Manual ERP refresh re-validating {len(retry_records)} ticket"
                                f"{'' if len(retry_records) == 1 else 's'} "
                                f"in ERP but not on the dashboard"
                            )
                            new_records.extend(retry_records)
                    print(
                        f"ERP refresh found {len(new_records)} new ticket"
                        f"{'' if len(new_records) == 1 else 's'}"
                    )
                    with job["state_lock"]:
                        if job["results"] is None:
                            job["results"] = _empty_issue_results()
                        listed_ids = _listed_issue_ids(job["results"])
                        missing_ids = listed_ids - current_ids
                        restored_ids = (resolved_ids & current_ids) - listed_ids
                        changed = False
                        if missing_ids:
                            removed = _remove_issue_ids_from_results(
                                job["results"], missing_ids
                            )
                            job["known_issue_ids"] -= missing_ids
                            print(
                                f"Removed {len(missing_ids)} ticket"
                                f"{'' if len(missing_ids) == 1 else 's'} "
                                f"no longer Open/Monitoring/On Hold ({removed} list rows)"
                            )
                            changed = True
                        if restored_ids:
                            restore_records = [
                                issue for issue in current_records
                                if issue["issue_id"] in restored_ids
                            ]
                            print(
                                f"Re-adding {len(restore_records)} still-open ticket"
                                f"{'' if len(restore_records) == 1 else 's'} "
                                f"previously marked resolved"
                            )
                            restored_results = _issue_results_dict(
                                work_tool.validate_issue_records(restore_records)
                            )
                            for key, items in restored_results.items():
                                if key == "projects" or key in PROJECT_RESULT_KEYS:
                                    continue
                                incremental_results[key].extend(items)
                                job["results"][key].extend(items)
                            _unmark_resolved_issue_ids(restored_ids)
                            changed = True
                        if new_records:
                            new_results = _issue_results_dict(
                                work_tool.validate_issue_records(new_records)
                            )
                            for key, items in new_results.items():
                                if key == "projects" or key in PROJECT_RESULT_KEYS:
                                    continue
                                for item in items:
                                    item["is_new"] = True
                                incremental_results[key].extend(items)
                                job["results"][key].extend(items)
                            job["known_issue_ids"].update(
                                _issue_ids_from_results(new_results)
                            )
                            changed = True
                        remaining_listed_ids = listed_ids - missing_ids
                        updated_records = _find_classification_changed_records(
                            current_records,
                            remaining_listed_ids,
                            job["results"],
                            job.get("issue_classifications"),
                            restored_ids,
                        )
                        if updated_records:
                            updated_ids = {
                                issue["issue_id"] for issue in updated_records
                            }
                            print(
                                f"Updating {len(updated_records)} ticket"
                                f"{'' if len(updated_records) == 1 else 's'} "
                                f"with changed Issue Type/Subtype"
                            )
                            classifications = job.get("issue_classifications") or {}
                            for issue in updated_records:
                                issue_id = issue.get("issue_id") or ""
                                old_type, old_subtype, old_subject = classifications.get(
                                    issue_id, ("", "", "")
                                )
                                new_type, new_subtype, new_subject = _issue_class_key(issue)
                                print(
                                    f"{issue_id} type/subtype "
                                    f"{old_type or '(none)'}/"
                                    f"{old_subtype or '(undiagnosed)'} -> "
                                    f"{new_type or '(none)'}/"
                                    f"{new_subtype or '(undiagnosed)'}"
                                    + (
                                        f"; subject changed: {old_subject!r} -> {new_subject!r}"
                                        if old_subject and new_subject and old_subject != new_subject
                                        else ""
                                    )
                                )
                                _patch_issue_class_on_results(job["results"], issue)
                            old_items = []
                            for items in _snapshot_items_by_issue_id(
                                job["results"], updated_ids
                            ).values():
                                old_items.extend(items)
                            _remove_issue_ids_from_results(job["results"], updated_ids)
                            updated_results = _apply_preserved_state_to_results(
                                _issue_results_dict(
                                    work_tool.validate_issue_records(updated_records)
                                ),
                                old_items,
                            )
                            for key, items in updated_results.items():
                                if key == "projects" or key in PROJECT_RESULT_KEYS:
                                    continue
                                incremental_results[key].extend(items)
                                job["results"][key].extend(items)
                            changed = True
                        job["issue_classifications"] = {
                            issue["issue_id"]: _issue_class_key(issue)
                            for issue in current_records
                            if issue.get("issue_id")
                        }
                        if changed:
                            job["version"] += 1
                            snapshot = copy.deepcopy(job["results"])
                        job["last_poll_at"] = time.time()
            finally:
                _pop_stdout_capture()
        captured_output = captured_stdout.getvalue()
        if captured_output:
            JobStdout(job_id, None).write(
                captured_output + ("" if captured_output.endswith("\n") else "\n")
            )
        response = {
            "ok": True,
            "scope": scope,
            "new_count": len(new_records),
            "removed_count": len(missing_ids),
            "restored_count": len(restored_ids),
            "updated_count": len(updated_records),
            "project_count": project_count,
            "results": incremental_results,
            "snapshot": snapshot,
            "logs": captured_output.splitlines(),
            "resolved_today": _resolved_stats(),
        }
        if fetched_count is not None:
            response["fetched_count"] = fetched_count
        return response, None
    except Exception as exc:
        captured_output = captured_stdout.getvalue()
        if captured_output:
            JobStdout(job_id, None).write(
                captured_output + ("" if captured_output.endswith("\n") else "\n")
            )
        _publish_job_event(job_id, {
            "type": "log",
            "line": f"ERP refresh failed: {exc}",
        })
        return {
            "ok": False,
            "scope": scope,
            "error": str(exc),
            "logs": captured_output.splitlines(),
        }, 502
    finally:
        job["poll_lock"].release()


@app.route("/issues/poll/<job_id>", methods=["POST"])
def issues_poll(job_id):
    payload = request.get_json(silent=True) or {}
    force = bool(payload.get("force"))
    manual = bool(payload.get("manual"))
    scope = str(payload.get("scope") or "issues").strip().lower()
    response, status = _poll_shared_issue_queue(job_id, scope=scope, force=force, manual=manual)
    return (jsonify(response), status) if status else jsonify(response)


@app.route("/issues/resolved", methods=["GET", "POST"])
def issues_resolved():
    if request.method == "GET":
        stats = _resolved_stats()
        stats["ok"] = True
        return jsonify(stats)

    payload = request.get_json(silent=True) or {}
    issue_id = str(payload.get("issue_id") or "").strip()
    if not issue_id:
        return _error("Missing issue_id")
    stats, added = _mark_issue_resolved(issue_id)
    tech = str(payload.get("tech") or "").strip()
    if added and tech:
        tech_stats.record(
            tech, issue_id, "resolved",
            unit=payload.get("unit"), ip=request.remote_addr,
        )
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job and job.get("results") is not None:
        with job["state_lock"]:
            if _remove_issue_ids_from_results(job["results"], {issue_id}):
                job["version"] += 1
    _publish_job_event(SHARED_ISSUES_JOB_ID, {
        "type": "log",
        "line": (
            f"Marked {issue_id} resolved"
            if added else f"{issue_id} already counted as resolved today"
        ),
    })
    stats["ok"] = True
    stats["added"] = added
    return jsonify(stats)

@app.route("/issues/cameras/<unit>", methods=["GET"])
def issues_list_cameras(unit):
    cameras, error = work_tool.list_unit_cameras(unit)
    if error:
        return _error(error, 404)
    return jsonify({
        "ok": True,
        "unit": unit,
        "cameras": cameras or [],
    })

@app.route("/issues/cameras-launch/<unit>", methods=["GET"])
def issues_cameras_launch(unit):
    info, error = work_tool.cameras_launch_info(unit)
    if error:
        return render_template(
            "camera_launch.html",
            unit=unit,
            cameras=[],
            direct_urls=[],
            count=0,
            vendor="dahua",
            error=error,
        ), 404
    return render_template(
        "camera_launch.html",
        unit=info["unit"],
        cameras=info["cameras"],
        direct_urls=[row["direct_url"] for row in info["cameras"]],
        count=info["count"],
        vendor=info.get("vendor") or "dahua",
        error=None,
    )

@app.route("/issues/open-camera-urls", methods=["POST"])
def issues_open_camera_urls():
    payload = request.get_json(silent=True) or {}
    urls = payload.get("urls") or []
    ie_mode = payload.get("ie_mode")
    if ie_mode is None:
        ie_mode = True
    result, error = work_tool.open_camera_urls(urls, ie_mode=bool(ie_mode))
    if error:
        return _error(error)
    return jsonify(result)

@app.route("/issues/fd-cameras/<unit>", methods=["POST"])
def issues_fd_cameras(unit):
    # Read-only: the FD router's DHCP leases plus a ping of each camera
    # (see work_tool/fd_cameras.py). Cached an hour; {"refresh": true} rereads.
    payload = request.get_json(silent=True) or {}
    cameras, error = work_tool.fd_router_cameras_with_ping(unit, refresh=bool(payload.get("refresh")))
    if error:
        return _error(error)
    down = [c for c in cameras if not c["up"]]
    return jsonify({
        "ok": True,
        "unit": unit,
        "cameras": cameras,
        "status": "warn" if down else "ok",
        "summary": f"{unit}: {len(cameras)} camera(s) on the router, "
                   + (f"{len(down)} not answering" if down else "all answering"),
    })

@app.route("/issues/camera-snapshot/<unit>/<target>", methods=["GET"])
def issues_camera_snapshot(unit, target):
    image, error = work_tool.camera_snapshot(unit, target)
    if error:
        return error, 502
    response = Response(image, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

@app.route("/issues/camera-sky-snapshot/<unit>/<target>", methods=["GET"])
def issues_camera_sky_snapshot(unit, target):
    """Tilt this camera up toward the sky, snapshot, then return it to its
    saved preset — see work_tool.camera_sky_snapshot. Falls back to a plain
    in-place snapshot when the camera has no PTZ channel."""
    image, was_tilted, was_restored, error = work_tool.camera_sky_snapshot(unit, target)
    if error:
        return error, 502
    response = Response(image, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["X-Camera-Tilted"] = "1" if was_tilted else "0"
    response.headers["X-Camera-Restored"] = "1" if was_restored else "0"
    return response

@app.route("/issues/camera-outage-ping/<unit>", methods=["POST"])
def issues_camera_outage_ping(unit):
    """Ping-sweep this unit's cameras to try naming which one explains a camera-outage alert — see work_tool.unit_camera_outage_ping_check."""
    info, error = work_tool.unit_camera_outage_ping_check(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/camera-test-email/<unit>/<target>", methods=["POST"])
def issues_camera_test_email(unit, target):
    """Trigger the camera's own test-email action against its already-configured SMTP settings — see work_tool.camera_send_test_email."""
    message, error = work_tool.camera_send_test_email(unit, target)
    if error:
        return _error(error)
    return jsonify({"ok": True, "message": message})

@app.route("/issues/camera-rooms/<unit>", methods=["POST"])
def issues_camera_rooms(unit):
    """Each Dahua camera's configured room (from its SMTP Sender) — see work_tool.camera_rooms."""
    rows, error = work_tool.camera_rooms(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, "unit": unit, "cameras": rows})

@app.route("/issues/camera-test-email-loop/<unit>", methods=["POST"])
def issues_camera_test_email_loop_start(unit):
    """Start the 'Test All Emails' background loop — see work_tool.start_camera_test_email_loop."""
    info, error = work_tool.start_camera_test_email_loop(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/camera-test-email-loop/<job_id>/stream", methods=["GET"])
def issues_camera_test_email_loop_stream(job_id):
    def generate():
        for chunk in work_tool.iter_camera_test_email_loop_output(job_id):
            yield chunk

    return Response(
        generate(),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/issues/camera-test-email-loop/<job_id>/stop", methods=["POST"])
def issues_camera_test_email_loop_stop(job_id):
    ok, message, info = work_tool.stop_camera_test_email_loop(job_id, reason="cancelled")
    if not ok:
        return _error(message, 404)
    payload = {"ok": True, "message": message}
    if info:
        payload.update(info)
    return jsonify(payload)

@app.route("/issues/camera/<unit>/<target>", methods=["GET"])
def issues_camera(unit, target):
    info, error = work_tool.camera_login_info(unit, target)
    if error:
        return error, 404
    return render_template("camera_redirect.html", **info)

@app.route(
    "/issues/camera-proxy/<unit>/<target>/",
    defaults={"subpath": ""},
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
@app.route(
    "/issues/camera-proxy/<unit>/<target>/<path:subpath>",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
def issues_camera_proxy(unit, target, subpath):
    status, headers, content, error = work_tool.proxy_camera_http(
        unit,
        target,
        subpath,
        method=request.method,
        query_string=request.query_string,
        headers={key: value for key, value in request.headers if key.lower() != "host"},
        body=request.get_data() or None,
    )
    if error:
        return error, 502
    response = Response(content if request.method != "HEAD" else b"", status=status or 502)
    for key, value in (headers or {}).items():
        if key.lower() == "set-cookie":
            values = value if isinstance(value, (list, tuple)) else [value]
            for item in values:
                if item:
                    response.headers.add(key, item)
        else:
            response.headers[key] = value
    return response

@app.errorhandler(404)
def camera_proxy_root_fallback(error):
    """
    Send stray camera-app requests back through their proxy.

    The camera UI builds some URLs (its video decoder worker, image assets) at runtime
    from a public path of "/", so they land on the dashboard root instead of the camera.
    The referring page tells us which camera asked.
    """
    referrer = request.referrer or ""
    match = re.search(r"/issues/camera-proxy/([^/]+)/([^/]+)/", referrer)
    if not match or request.path.startswith("/issues/camera-proxy/"):
        return error
    location = f"/issues/camera-proxy/{match.group(1)}/{match.group(2)}{request.path}"
    if request.query_string:
        location = f"{location}?{request.query_string.decode('utf-8', 'replace')}"
    return redirect(location)

@app.route("/issues/fisheye/<unit>", methods=["GET"])
def issues_fisheye(unit):
    data, error = work_tool.fetch_fisheye_snapshot(unit)
    if error:
        return error, 502
    return Response(data, mimetype="image/jpeg")

@app.route("/issues/ping-speaker/<unit>", methods=["POST"])
def issues_ping_speaker(unit):
    speaker_up, output, error = work_tool.ping_speaker_status(unit)
    if error:
        return _error(error, 404)
    _patch_shared_issue_fields(
        unit,
        {"speaker_up": speaker_up},
        result_keys=("speaker_outage",),
    )
    return jsonify({
        "ok": True,
        "unit": unit,
        "speaker_up": speaker_up,
        "output": output,
    })

@app.route("/issues/bounce-switch/<unit>", methods=["POST"])
def issues_bounce_switch(unit):
    result, error = work_tool.bounce_switch(unit)
    if error:
        return _error(error, 500)
    return _bounce_output_response(result, "Bounce Switch", "relay")

@app.route("/issues/robofiber-uptime/<unit>", methods=["POST"])
def issues_robofiber_uptime(unit):
    result, error = work_tool.get_robofiber_uptime(unit)
    if error:
        return _error(error)
    # Feeds the same switch-uptime cache unit_power_vs_cell_outage reads
    # (_store_switch_up_since/_cached_switch_up_since in work_tool._core)
    # — without this, a fresh manual check here (e.g. right after a
    # switch reboot) never reached that cache, so the next power-vs-cell
    # check (scheduled or on-demand) kept whatever pre-reboot uptime it
    # already had instead of picking up the real one. Also handed back in
    # the response so the command menu's own uptime line can update
    # immediately without a second round trip.
    uptime_seconds = work_tool._parse_switch_uptime_seconds(result.get("uptime") or "")
    if uptime_seconds is not None:
        switch_up_since = time.time() - uptime_seconds
        work_tool._store_switch_up_since(unit, switch_up_since, result.get("uptime") or "")
        result["switch_uptime_seconds"] = uptime_seconds
        result["switch_up_since"] = switch_up_since
        # Also patch this unit's row in the fleet power-vs-cell cache, if
        # it already has one — without this, the fresh reading only ever
        # lived in the calling browser's own state; the client's own 60s
        # poll of /fleet-power-vs-cell-outage/cached (pollPowerVsCellCache)
        # would silently revert it back to whatever the last full sweep
        # (up to 30 min stale) had, well before the NEXT sweep could pick
        # up the real number itself. Caught live, 2026-09-28: refreshed
        # switch uptime showed the correct "1m" for a moment, then reverted
        # to the pre-reboot "119d" within about a minute.
        unit_key = str(unit or "").strip().upper()
        with _power_vs_cell_cache_lock:
            for row in _power_vs_cell_cache.get("rows") or []:
                if str(row.get("unit") or "").strip().upper() == unit_key:
                    row["switch_uptime_seconds"] = uptime_seconds
                    row["switch_up_since"] = switch_up_since
                    row["switch_uptime_text"] = result.get("uptime") or row.get("switch_uptime_text")
                    row["checked_at"] = time.time()
    return jsonify({"ok": True, **result})

@app.route("/issues/robofiber-logs-link/<unit>", methods=["POST"])
def issues_robofiber_logs_link(unit):
    result, error = work_tool.get_robofiber_logs_link_events(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **result})

@app.route("/issues/robofiber-logs-month/<unit>", methods=["POST"])
def issues_robofiber_logs_month(unit):
    result, error = work_tool.get_robofiber_logs_last_month(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **result})

@app.route("/issues/bounce-speaker/<unit>", methods=["POST"])
def issues_bounce_speaker(unit):
    result, error = work_tool.bounce_speaker(unit)
    if error:
        return _error(error, 500)
    return _bounce_output_response(result, "Bounce Speaker", "speaker")

def _bounce_output_response(result, action_label, endpoint_label):
    """Stream a bounce utility's combined stdout/stderr to the browser."""
    process = result["process"]

    def generate():
        yield (
            f"{action_label} started for {result['unit']} using "
            f"{endpoint_label} IP {result['ip']}\n"
        )
        if process.stdout is not None:
            for line in process.stdout:
                yield line
            process.stdout.close()
        return_code = process.wait()
        yield f"{action_label} finished with exit code {return_code}\n"

    return Response(
        generate(),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/issues/ping-router/<unit>", methods=["POST"])
def issues_ping_router(unit):
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode") or request.args.get("mode") or "quick").strip()
    info, error = work_tool.ping_router_status(unit, mode=mode)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/ping-router-long/<unit>", methods=["POST"])
def issues_ping_router_long_start(unit):
    info, error = work_tool.start_router_long_ping(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/ping-nuc-long/<unit>", methods=["POST"])
def issues_ping_nuc_long_start(unit):
    info, error = work_tool.start_nuc_long_ping(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/ping-pve-long/<unit>", methods=["POST"])
def issues_ping_pve_long_start(unit):
    info, error = work_tool.start_pve_long_ping(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/ping-camera-long/<unit>/<target>", methods=["POST"])
def issues_ping_camera_long_start(unit, target):
    info, error = work_tool.start_camera_long_ping(unit, target)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

# The stream/stop routes above are job_id-keyed and kind-agnostic (see
# _start_long_ping) — NUC/PVE/camera long pings started above are read
# back and stopped through these same two routes, not separate copies.
@app.route("/issues/ping-router-long/<job_id>/stream", methods=["GET"])
def issues_ping_router_long_stream(job_id):
    def generate():
        for chunk in work_tool.iter_router_long_ping_output(job_id):
            yield chunk

    return Response(
        generate(),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/issues/ping-router-long/<job_id>/stop", methods=["POST"])
def issues_ping_router_long_stop(job_id):
    ok, message, info = work_tool.stop_router_long_ping(job_id, reason="cancelled")
    if not ok:
        return _error(message, 404)
    payload = {"ok": True, "message": message}
    if info:
        payload.update(info)
    return jsonify(payload)

@app.route("/issues/ping-camera/<unit>/<target>", methods=["POST"])
def issues_ping_camera(unit, target):
    camera_up, output, error = work_tool.ping_camera_status(unit, target)
    if error:
        return _error(error, 404)
    _patch_shared_issue_fields(
        unit,
        {"camera_up": camera_up},
        camera_target=target,
        result_keys=("camera_outage",),
    )
    return jsonify({
        "ok": True,
        "unit": unit,
        "target": target,
        "camera_up": camera_up,
        "output": output,
    })

@app.route("/issues/ping-compute/<unit>", methods=["POST"])
def issues_ping_compute(unit):
    compute_up, label, output, error = work_tool.ping_compute_status(unit)
    if error:
        return _error(error, 404)
    _patch_shared_issue_fields(
        unit,
        {
            "led_status": "green" if compute_up else "yellow",
            "compute_label": label,
        },
        result_keys=("nuc_down", "truly_down", "false_positives"),
    )
    return jsonify({
        "ok": True,
        "unit": unit,
        "label": label,
        "compute_up": compute_up,
        "output": output,
    })

@app.route("/issues/ping-scrypted/<unit>", methods=["POST"])
def issues_ping_scrypted(unit):
    scrypted_up, output, error = work_tool.ping_scrypted_status(unit)
    if error:
        return _error(error, 404)
    _patch_shared_issue_fields(
        unit,
        {
            "led_status": "green" if scrypted_up else "yellow",
        },
        result_keys=("scrypted_outage",),
    )
    return jsonify({
        "ok": True,
        "unit": unit,
        "scrypted_up": scrypted_up,
        "output": output,
    })

@app.route("/issues/scrypted-no-audio/<unit>", methods=["POST"])
def issues_scrypted_no_audio(unit):
    result, error = work_tool.set_scrypted_no_audio(unit)
    if error:
        return _error(error)
    result["ok"] = True
    return jsonify(result)

@app.route("/issues/scrypted-ram-folder/<unit>", methods=["POST"])
def issues_scrypted_ram_folder(unit):
    result, error = work_tool.scrypted_ram_folder_status(unit)
    if error:
        return _error(error)
    result["ok"] = True
    return jsonify(result)

@app.route("/issues/scrypted-ram-folder-stream/<unit>", methods=["POST"])
def issues_scrypted_ram_folder_stream(unit):
    """Live output from the RAM folder check — see work_tool.stream_scrypted_ram_folder_status."""
    def generate():
        for chunk in work_tool.stream_scrypted_ram_folder_status(unit):
            yield chunk

    return Response(
        generate(),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/issues/ping-pve/<unit>", methods=["POST"])
def issues_ping_pve(unit):
    pve_up, output, error = work_tool.ping_pve_status(unit)
    if error:
        return _error(error, 404)
    return jsonify({
        "ok": True,
        "unit": unit,
        "pve_up": pve_up,
        "output": output,
    })

@app.route("/issues/set-fields/<preset_id>/<issue_id>", methods=["POST"])
def issues_set_fields(preset_id, issue_id):
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    unit = str(payload.get("unit") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    source_list_id = str(payload.get("source_list_id") or "").strip()
    result, error = work_tool.set_issue_preset_fields(
        preset_id, issue_id, unit, subject=subject
    )
    if error:
        return _error(error)
    list_id = result.get("list_id") or ""
    move_to_list = ""
    field_updates = {
        "issue_type": result.get("issue_type") or "",
        "outage_type": result.get("outage_type") or "",
        "issue_subtype": result.get("issue_subtype") or "",
        "undiagnosed": bool(result.get("undiagnosed")),
    }
    if (
        source_list_id == "false_positives"
        and str(preset_id or "").strip() in CAMERA_FIELD_PRESET_IDS
    ):
        move_to_list = "camera_view"
        field_updates.update({
            "is_camera_view": True,
            "camera_view_status": "green",
            "led_status": "green",
        })
    elif (
        source_list_id in ("false_positives", "truly_down")
        and str(preset_id or "").strip() in NUC_DOWN_FIELD_PRESET_IDS
    ):
        move_to_list = "nuc_down"
        field_updates.update({
            "is_nuc_down": True,
            "connectivity_kind": "nuc_down",
            "led_status": "yellow",
        })
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job and job.get("results") is not None:
        with job["state_lock"]:
            if move_to_list:
                from_list = (
                    "false_positives"
                    if move_to_list == "camera_view"
                    else source_list_id
                )
                _move_shared_issue_to_list(
                    job["results"],
                    issue_id,
                    unit,
                    from_list,
                    move_to_list,
                    field_updates,
                )
                job["version"] += 1
            elif list_id:
                # Patch even when set_fields is empty so subtype/type refresh
                # still lands on the shared job without nested-lock hangs.
                for key in (list_id,):
                    for item in job["results"].get(key) or []:
                        if str(item.get("unit") or "").strip() != unit:
                            continue
                        if _item_issue_id(item) != str(issue_id or "").strip():
                            continue
                        item.update(field_updates)
                if result.get("set_fields"):
                    job["version"] += 1
    result["ok"] = True
    result["move_to_list"] = move_to_list
    return jsonify(result)

def _listed_tickets_with_units(results):
    tickets = []
    seen = set()
    for key in ISSUE_RESULT_KEYS:
        for item in (results or {}).get(key) or []:
            issue_id = _item_issue_id(item)
            subject = str((item or {}).get("subject") or "").strip()
            unit = str((item or {}).get("unit") or "").strip()
            if not unit:
                unit = work_tool._head_unit_from_subject(subject)
            if not issue_id or not unit or issue_id in seen:
                continue
            seen.add(issue_id)
            tickets.append({
                "issue_id": issue_id,
                "unit": unit,
                "subject": subject,
            })
    return tickets

def _add_missing_components_log_lines(result, scheduled=False):
    prefix = (
        "Scheduled Add Missing Components/Sites"
        if scheduled
        else "Add Missing Components/Sites"
    )
    updated = result.get("updated") or []
    skipped = result.get("skipped") or []
    errors = result.get("errors") or []
    component_set = result.get("component_set") or 0
    site_set = result.get("site_set") or 0
    lines = [
        prefix
        + " — checked "
        + str(result.get("checked") or 0)
        + ", component set "
        + str(component_set)
        + ", site set "
        + str(site_set)
        + ", skipped "
        + str(len(skipped))
        + (f", {len(errors)} errors" if errors else "")
    ]
    for item in updated:
        parts = []
        if item.get("component"):
            parts.append("component " + str(item.get("component")))
        if item.get("site"):
            parts.append("site " + str(item.get("site")))
        if parts:
            lines.append(
                "Set " + " and ".join(parts) + " on " + str(item.get("issue_id") or "")
            )
    for line in errors:
        if line:
            lines.append(prefix + " warning: " + str(line))
    return lines


def _run_add_missing_components(job, scheduled=False):
    if erp_writes_disabled():
        print(
            "Add Missing Components/Sites skipped — "
            "DISABLE_ERP_WRITES is enabled"
        )
        return {"checked": 0, "updated": [], "skipped": [], "errors": []}
    if scheduled and automated_tasks_paused():
        print(
            "Scheduled Add Missing Components/Sites skipped — "
            "PAUSE_AUTOMATED_TASKS is enabled"
        )
        return {"checked": 0, "updated": [], "skipped": [], "errors": []}
    with job["state_lock"]:
        tickets = _listed_tickets_with_units(job["results"])
    _push_stdout_capture(JobStdout(SHARED_ISSUES_JOB_ID, _true_stdout))
    try:
        if scheduled:
            when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
            print(
                f"Daily 4:05 AM AZ Add Missing Components/Sites starting ({when})..."
            )
        else:
            print(
                f"Add Missing Components/Sites starting ({len(tickets)} listed tickets)..."
            )
        result = work_tool.add_missing_issue_components(tickets)
        for line in _add_missing_components_log_lines(result, scheduled=scheduled):
            print(line)
        return result
    finally:
        _pop_stdout_capture()


@app.route("/issues/add-missing-components", methods=["POST"])
def issues_add_missing_components():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        return _error("Shared report is not ready", 409)
    if not job["poll_lock"].acquire(blocking=False):
        return _error("Another ERP update is already running", 409)
    try:
        result = _run_add_missing_components(job, scheduled=False)
        result["ok"] = True
        return jsonify(result)
    except Exception as exc:
        return _error(str(exc), 502)
    finally:
        job["poll_lock"].release()

def _units_from_shared_results(results):
    units = []
    seen = set()
    for entries in (results or {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            unit = str(entry.get("unit") or "").strip()
            if not unit:
                continue
            key = unit.upper()
            if key in seen:
                continue
            seen.add(key)
            units.append(unit)
    return units

def _netsheet_sync_log_lines(result, scheduled=False):
    prefix = (
        "Daily 4:10 AM AZ Sync netsheet from v19"
        if scheduled
        else "Sync netsheet from v19"
    )
    lines = [
        f"{prefix} — checked {result.get('checked', 0)}, "
        f"added {result.get('added', 0)}, "
        f"backfilled {result.get('backfilled', 0)}, "
        f"unchanged {result.get('unchanged', 0)}, "
        f"failed {result.get('failed', 0)}"
    ]
    for unit in result.get("updated_units") or []:
        lines.append(f"Netsheet updated: {unit}")
    for error in result.get("errors") or []:
        if error:
            lines.append(f"Netsheet sync warning: {error}")
    return lines

def _run_netsheet_sync(job=None, scheduled=False):
    if scheduled and automated_tasks_paused():
        print(
            "Scheduled Sync netsheet from v19 skipped — "
            "PAUSE_AUTOMATED_TASKS is enabled"
        )
        return {
            "checked": 0,
            "added": 0,
            "backfilled": 0,
            "unchanged": 0,
            "failed": 0,
            "errors": [],
            "updated_units": [],
        }
    _push_stdout_capture(io.StringIO())
    try:
        units = []
        if job and isinstance(job.get("results"), dict):
            units = _units_from_shared_results(job.get("results"))
        when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
        if scheduled:
            print(f"Daily 4:10 AM AZ Sync netsheet from v19 starting ({when})...")
        else:
            print(f"Sync netsheet from v19 starting ({len(units)} listed units)...")
        result = work_tool.sync_netsheet_from_erp(
            units=units,
            include_sparse_sheet_rows=True,
            max_units=200,
        )
        for line in _netsheet_sync_log_lines(result, scheduled=scheduled):
            print(line)
        return result
    finally:
        _pop_stdout_capture()

@app.route("/issues/sync-netsheet", methods=["POST"])
def issues_sync_netsheet():
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        return _error("Shared report is not ready", 409)
    if not job["poll_lock"].acquire(blocking=False):
        return _error("Another ERP update is already running", 409)
    try:
        result = _run_netsheet_sync(job, scheduled=False)
        result["ok"] = True
        return jsonify(result)
    except Exception as exc:
        return _error(str(exc), 502)
    finally:
        job["poll_lock"].release()

@app.route("/issues/check-patch/<unit>", methods=["POST"])
def issues_check_patch(unit):
    info, error = work_tool.get_unit_patch_version(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/pve-nvme-health/<unit>", methods=["POST"])
def issues_pve_nvme_health(unit):
    """Read-only NVMe SMART health from the unit's PVE host (smartctl -a)."""
    payload = request.get_json(silent=True) or {}
    device = (payload.get("device") or request.args.get("device") or "").strip()
    info, error = work_tool.pve_nvme_health(unit, device=device or None)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/pve-kernel-io-errors/<unit>", methods=["POST"])
def issues_pve_kernel_io_errors(unit):
    """Read-only dmesg + journalctl -k grep for storage I/O/NVMe/ATA/filesystem error signatures."""
    payload = request.get_json(silent=True) or {}
    journal_days = payload.get("journal_days") or request.args.get("journal_days")
    info, error = work_tool.pve_kernel_io_errors(unit, journal_days=journal_days or 30)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/pve-boot-errors/<unit>", methods=["POST"])
def issues_pve_boot_errors(unit):
    """Read-only journalctl -b -p err — every error-or-worse journal entry since the PVE host's last boot."""
    info, error = work_tool.pve_boot_errors(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/pve-filesystem-health/<unit>", methods=["POST"])
def issues_pve_filesystem_health(unit):
    """Read-only findmnt/lsblk check for a filesystem already mounted read-only on the PVE host."""
    info, error = work_tool.pve_filesystem_health(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/pve-link-stats/<unit>", methods=["POST"])
def issues_pve_link_stats(unit):
    """Read-only `ip -s link` on the PVE host — flags any interface with dropped packets or errors."""
    info, error = work_tool.pve_link_stats(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/service-status/<unit>", methods=["POST"])
def issues_service_status(unit):
    """Which platform services are actually active on the Scrypted box (read-only)."""
    info, error = work_tool.scrypted_service_status(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/pve-resources/<unit>", methods=["POST"])
def issues_pve_resources(unit):
    """Memory, disk, load and VM 101 state on the PVE host (read-only)."""
    info, error = work_tool.pve_host_resources(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/nuc-resources/<unit>", methods=["POST"])
def issues_nuc_resources(unit):
    """Memory, disk and CPU load on the unit's Windows NUC (read-only)."""
    info, error = work_tool.nuc_host_resources(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/nuc-disk-health/<unit>", methods=["POST"])
def issues_nuc_disk_health(unit):
    """Drive health, SMART counters and disk-failure events on the unit's Windows NUC (read-only)."""
    info, error = work_tool.nuc_disk_health(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/camera-matrix/<unit>", methods=["POST"])
def issues_camera_matrix(unit):
    """Reach every camera, fisheye and speaker for a unit in one pass."""
    info, error = work_tool.camera_reachability_matrix(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/camera-analytics/<unit>", methods=["POST"])
def issues_camera_analytics(unit):
    """Field/Line Detection rule state on a Hikvision unit's cameras (read-only)."""
    info, error = work_tool.hikvision_analytics_status(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/run-diagnostics/<unit>", methods=["POST"])
def issues_run_diagnostics(unit):
    """Every read-only check for a unit, in one call. Individual checks may fail independently."""
    info, error = work_tool.run_unit_diagnostics(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/unit-history/<unit>", methods=["GET"])
def issues_unit_history(unit):
    """Recorded validation history for a unit, plus its recent flap summary."""
    try:
        days = int(request.args.get("days") or 30)
        limit = int(request.args.get("limit") or 200)
    except ValueError:
        return _error("days and limit must be integers")
    info, error = work_tool.unit_history_entries(unit, days=days, limit=limit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/flap-report", methods=["GET"])
def issues_flap_report():
    """Units flapping most in the window — fleet-wide view over recorded history."""
    try:
        days = int(request.args.get("days") or 7)
        min_transitions = int(request.args.get("min_transitions") or 3)
    except ValueError:
        return _error("days and min_transitions must be integers")
    info, error = work_tool.fleet_flap_report(days=days, min_transitions=min_transitions)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/zabbix-flap-report", methods=["GET"])
def issues_zabbix_flap_report():
    """Units flapping most in the window, read straight from Zabbix's own Router/Switch trigger history — see work_tool.fleet_zabbix_flap_report."""
    try:
        days = int(request.args.get("days") or 7)
        min_transitions = int(request.args.get("min_transitions") or 3)
    except ValueError:
        return _error("days and min_transitions must be integers")
    units, error = work_tool.fleet_zabbix_flap_report(days=days, min_transitions=min_transitions)
    if error:
        return _error(error)
    return jsonify({"ok": True, "days": days, "min_transitions": min_transitions, "units": units})


@app.route("/issues/camera-outage-report", methods=["GET"])
def issues_camera_outage_report():
    """Fleet-wide units with the SNUC-Watch camera image buffer alert open — see work_tool.fleet_camera_outage_report."""
    rows, error = work_tool.fleet_camera_outage_report()
    if error:
        return _error(error)
    return jsonify({"ok": True, "units": rows})


@app.route("/issues/history-stats", methods=["GET"])
def issues_history_stats():
    """Size and row count of the validation-history database."""
    return jsonify(unit_history.stats())


@app.route("/issues/power-infra-alerts", methods=["GET"])
def issues_power_infra_alerts():
    """
    Experimental: Zabbix active problems x VRM active battery alarms,
    merged by unit, fleet-wide. Read-only against both APIs. Live — takes
    a few seconds; use the /cached variant for anything polled frequently.
    """
    info, error = work_tool.combined_power_infra_alerts()
    if error:
        return _error(error)
    rows = info.get("rows") or []
    with _power_infra_cache_lock:
        _power_infra_cache["rows"] = rows
        _power_infra_cache["fetched_at"] = time.time()
        _power_infra_cache["zabbix_error"] = info.get("zabbix_error")
        _power_infra_cache["vrm_error"] = info.get("vrm_error")
    # Recorded here too, not just from the scheduled poll below — a manual
    # Refresh is a real data point and costs nothing extra to keep, same as
    # unit_history piggybacking on validations that were happening anyway.
    try:
        alarm_history.record_snapshot(rows)
    except Exception as exc:
        print(f"Alarm history record (manual refresh) skipped: {exc}")
    return jsonify({"ok": True, **info})


@app.route("/issues/power-infra-alerts/cached", methods=["GET"])
def issues_power_infra_alerts_cached():
    """
    Instant read of the last poll (scheduled, every
    POWER_INFRA_ALERTS_REFRESH_SECONDS when PAUSE_AUTOMATED_TASKS is off, or
    whatever the panel's own Refresh last fetched). This is what the
    dashboard polls to light up a unit's warning glyph — never calls Zabbix
    or VRM itself, so it's cheap enough to poll often.
    """
    with _power_infra_cache_lock:
        snapshot = dict(_power_infra_cache)
    return jsonify({
        "ok": True,
        "rows": snapshot.get("rows") or [],
        "fetched_at": snapshot.get("fetched_at"),
        "zabbix_error": snapshot.get("zabbix_error"),
        "vrm_error": snapshot.get("vrm_error"),
    })


def _fleet_cache_route(check_fn, cache, cache_lock, augment_fn=None):
    """Shared body for a fleet-wide report's live (POST-style semantics,
    GET verb — read-only, matches the Power & Infra Alerts precedent)
    endpoint: run the check now, refresh the cache, return the result.
    `augment_fn`, if given, runs on the rows AFTER caching but before the
    response — for data that changes independently of the fleet check
    itself (see _augment_shading_rows_with_snapshot_tasks), so it's never
    baked into the stored cache and always reflects the current state."""
    rows, error = check_fn()
    if error:
        return _error(error)
    with cache_lock:
        cache["rows"] = rows or []
        cache["fetched_at"] = time.time()
        cache["error"] = None
    out_rows = augment_fn(rows or []) if augment_fn else (rows or [])
    return jsonify({"ok": True, "rows": out_rows, "fetched_at": cache["fetched_at"]})


def _fleet_cached_route(cache, cache_lock, augment_fn=None):
    """Shared body for a fleet-wide report's instant cached read — never
    calls VRM itself, backed by the scheduled poll (or the last live
    Refresh)."""
    with cache_lock:
        snapshot = dict(cache)
    rows = snapshot.get("rows") or []
    return jsonify({
        "ok": True,
        "rows": augment_fn(rows) if augment_fn else rows,
        "fetched_at": snapshot.get("fetched_at"),
        "error": snapshot.get("error"),
    })


def _power_vs_cell_sweep_units():
    """
    Current Up Steady (false_positives) + Offline compute (nuc_down) +
    Scrypted outage (scrypted_outage) units from
    the shared ERP-pull job, plus a {unit: issue_id} map — real ERP
    tickets too, so their issue_id rides along for
    fleet_power_vs_cell_outage_status to pass into
    unit_power_vs_cell_outage (it prefers whichever loss window matches
    the ticket's own creation time; see that function's docstring).

    Andrew's own request, 2026-09-18 (extended same day after reporting a
    Down Full ticket, RD3421, missing its switch-uptime line): this used
    to be Up Steady only, but a switch reboot correlating with when
    compute/Scrypted/the router itself also went down is the same signal
    everywhere. Down Full is arguably the sharpest case of all — the
    switch is a separate device from the router/compute, so whether IT
    also rebooted is exactly what tells a real power event apart from a
    router/compute-specific failure with the switch (and power) still up.
    Down Full was dropped again on 2026-10-13 (Andrew's request): the
    check needs the switch reachable, which it never is while the unit
    is down. A Down Full ticket that revalidates into Up Steady gets the
    check then instead (_recheck_power_vs_cell_for_units).
    Unlike the VRM fleet checks above, this diagnostic has no
    VRM-installation-wide "everything" source of its own — these three
    only exist as categories inside the live dashboard's own shared
    ticket-queue pull (see ISSUE_RESULT_KEYS) — so it rides on whatever
    that job's results currently hold.

    Returns (None, None) when the job doesn't exist yet or is mid-run, so
    the caller can tell "genuinely zero qualifying tickets right now"
    apart from "nothing to check yet." Where more than one ticket names
    the same unit (including across these three lists), whichever is seen
    first wins the mapping — one is enough to give the window-matching
    something to work with.
    """
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if not job or not job.get("done"):
        return None, None
    results = job.get("results") or {}
    unit_issue_ids = {}
    for list_id in ("false_positives", "nuc_down", "scrypted_outage"):
        for entry in results.get(list_id) or []:
            unit = str((entry or {}).get("unit") or "").strip().upper()
            issue_id = str((entry or {}).get("issue_id") or "").strip()
            if unit and unit not in unit_issue_ids:
                unit_issue_ids[unit] = issue_id
    return sorted(unit_issue_ids), unit_issue_ids


def _power_vs_cell_check_fn():
    """check_fn adapter so this fits _run_fleet_check/_fleet_cache_route's
    zero-arg contract — fleet_power_vs_cell_outage_status itself needs an
    explicit unit list (it has no fleet-wide source of its own), supplied
    here from the shared job's current Up Steady/Offline compute/Scrypted
    outage categories."""
    units, unit_issue_ids = _power_vs_cell_sweep_units()
    if units is None:
        return None, "Shared ticket-queue pull hasn't completed a run yet — nothing to check"
    if not units:
        return [], None
    return work_tool.fleet_power_vs_cell_outage_status(units, unit_issue_ids=unit_issue_ids)


def _recheck_power_vs_cell_for_units(units):
    """
    Run the cell/power check for just these units, in the background, and
    merge the rows into the fleet power-vs-cell cache the row badges read.
    Called when a revalidate moves a Down Full ticket to Up Steady (Andrew's
    request, 2026-10-13): the check needs the switch reachable, so it's
    useless while the unit is down and only worth running once it's back.
    """
    unit_keys = sorted({str(u or "").strip().upper() for u in units or [] if str(u or "").strip()})
    if not unit_keys:
        return
    _units, unit_issue_ids = _power_vs_cell_sweep_units()
    issue_ids = {u: (unit_issue_ids or {}).get(u) for u in unit_keys}

    def run():
        names = ", ".join(unit_keys)
        try:
            rows, error = work_tool.fleet_power_vs_cell_outage_status(
                unit_keys, unit_issue_ids=issue_ids
            )
        except Exception as exc:
            rows, error = None, str(exc)
        if error:
            _shared_console_print(f"Cell/power check for {names} failed: {error}")
            return
        fresh = {str(row.get("unit") or "").strip().upper(): row for row in rows or []}
        with _power_vs_cell_cache_lock:
            kept = [
                row for row in (_power_vs_cell_cache.get("rows") or [])
                if str(row.get("unit") or "").strip().upper() not in fresh
            ]
            _power_vs_cell_cache["rows"] = kept + list(fresh.values())
        lines = [f"Cell/power check after moving to Up Steady ({names}):"]
        for unit, row in sorted(fresh.items()):
            result = row.get("error") or row.get("summary") or row.get("verdict") or "no verdict"
            lines.append(f"  {unit}: {result}")
        _shared_console_print("\n".join(lines))

    threading.Thread(target=run, name="power-vs-cell-recheck", daemon=True).start()


def _snapshot_task_public(task):
    """Trim a shading_snapshots task row to what the UI needs — no internal
    subject text, just enough to render a status line + thumbnail link."""
    if not task:
        return None
    return {
        "id": task["id"],
        "status": task["status"],
        "camera_target": task["camera_target"],
        "peak_hour_utc": task["peak_hour_utc"],
        "attempts_used": task["attempts_used"],
        "attempts_total": task["attempts_total"],
        "next_attempt_at": task["next_attempt_at"],
        "captured_at": task["captured_at"],
        "last_note": task["last_note"],
        "has_image": bool(task["image_filename"]),
    }


def _augment_shading_rows_with_snapshot_tasks(rows):
    """Attach each row's own most recent shading-snapshot task (if any) —
    read fresh every time, since a task's status can change between fleet
    shading polls (they're on different, independent clocks)."""
    units = [row.get("unit") for row in rows if row.get("unit")]
    tasks_by_unit = shading_snapshots.latest_tasks_by_unit(units) if units else {}
    for row in rows:
        task = tasks_by_unit.get(str(row.get("unit") or "").strip().upper())
        row["snapshot_task"] = _snapshot_task_public(task)
    return rows


# The /issues/fleet-* live+cached route pairs (Units Unplugged, Shaded
# Units, Dead Panels, VRM Disconnected, Battery Outlook, Up Steady Power vs
# Cell) are registered by make_fleet_report() near the bottom of this file,
# not declared here — see that function's docstring for what each one backs.


@app.route("/issues/network-latency-history/<unit>", methods=["POST"])
def issues_network_latency_history(unit):
    """Experimental: Router/Switch ICMP ping response time & loss over time, from Zabbix."""
    payload = request.get_json(silent=True) or {}
    hours = payload.get("hours") or request.args.get("hours") or 24
    info, error = work_tool.unit_network_latency_history(unit, hours)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/power-vs-cell-outage/<unit>", methods=["POST"])
def issues_power_vs_cell_outage(unit):
    """
    Experimental: power outage vs. cell/carrier outage — compares the
    switch's own uptime against the router's most recent ~100% ICMP
    ping-loss window from Zabbix. Read-only (see
    work_tool.unit_power_vs_cell_outage).
    """
    payload = request.get_json(silent=True) or {}
    hours = payload.get("hours") or request.args.get("hours")
    # Only override when the caller actually asked for a different window
    # — otherwise let unit_power_vs_cell_outage's own default (2 weeks)
    # apply rather than pinning this route to a stale, shorter one.
    kwargs = {"hours": hours} if hours else {}
    # issue_id is optional — when the ticket's own ERP id is known, it
    # lets unit_power_vs_cell_outage pick the loss window matching when
    # the ticket was actually opened, rather than falling straight to its
    # longest-duration fallback (see that function's docstring).
    issue_id = payload.get("issue_id") or request.args.get("issue_id")
    if issue_id:
        kwargs["issue_id"] = issue_id
    info, error = work_tool.unit_power_vs_cell_outage(unit, **kwargs)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/zabbix-alerts/<unit>", methods=["POST"])
def issues_zabbix_alerts(unit):
    """Active Zabbix problems for one unit's Router/Switch/NUC/Speaker/SNUC hosts."""
    by_unit, error = work_tool.zabbix_active_problems_by_unit()
    if error:
        return _error(error)
    problems = (by_unit or {}).get(str(unit or "").strip().upper()) or []
    problems = sorted(problems, key=lambda p: -p["severity"])
    return jsonify({
        "ok": True,
        "unit": unit,
        "problems": problems,
        "summary": (
            f"{len(problems)} active Zabbix problem(s) on {unit}"
            if problems else f"No active Zabbix problems on {unit}"
        ),
    })


@app.route("/issues/history-compact", methods=["POST"])
def issues_history_compact():
    """
    Prune history to the retention window and hand the freed disk back to the
    OS. Runs at startup too; this is the on-demand version.
    """
    deleted = unit_history.prune(keep_days=UNIT_HISTORY_KEEP_DAYS)
    result = unit_history.compact()
    if not result.get("ok"):
        return _error(result.get("error"), 500)
    return jsonify({
        "ok": True,
        "deleted": deleted,
        "freed_bytes": result["freed_bytes"],
        "freed_mb": round(result["freed_bytes"] / (1024 * 1024), 2),
        **unit_history.stats(),
    })


@app.route("/issues/alarm-history-stats", methods=["GET"])
def issues_alarm_history_stats():
    """Size, episode count, and open/closed split of the alarm-history database."""
    return jsonify(alarm_history.stats())


@app.route("/issues/alarm-history-compact", methods=["POST"])
def issues_alarm_history_compact():
    """Prune alarm history to the retention window and reclaim disk. On-demand
    version of the startup prune — see unit_history's identical sibling route."""
    deleted = alarm_history.prune(keep_days=ALARM_HISTORY_KEEP_DAYS)
    result = alarm_history.compact()
    if not result.get("ok"):
        return _error(result.get("error"), 500)
    return jsonify({
        "ok": True,
        "deleted": deleted,
        "freed_bytes": result["freed_bytes"],
        "freed_mb": round(result["freed_bytes"] / (1024 * 1024), 2),
        **alarm_history.stats(),
    })


@app.route("/issues/alarm-history/<unit>", methods=["GET"])
def issues_alarm_history(unit):
    """
    Every recorded Zabbix/VRM alarm episode for a unit — "has this happened
    before," not just "is something active right now." days defaults to 30;
    pass ?days= to widen it (bounded by ALARM_HISTORY_KEEP_DAYS regardless,
    since nothing older survives pruning).
    """
    try:
        days = int(request.args.get("days") or 30)
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, ALARM_HISTORY_KEEP_DAYS))
    unit = str(unit or "").strip().upper()
    episodes = alarm_history.unit_alarm_history(unit, days=days)
    recurrence = alarm_history.unit_alarm_recurrence(unit, days=days)
    return jsonify({
        "ok": True,
        "unit": unit,
        "days": days,
        "episodes": episodes,
        "recurrence": recurrence,
    })


@app.route("/issues/alarm-frequency", methods=["GET"])
def issues_alarm_frequency():
    """
    Fleet-wide "repeat offenders" — units with the most alarm episodes in
    the window, the alarm-history equivalent of unit_history's flap report.
    """
    try:
        days = int(request.args.get("days") or 7)
    except (TypeError, ValueError):
        days = 7
    days = max(1, min(days, ALARM_HISTORY_KEEP_DAYS))
    try:
        min_episodes = int(request.args.get("min_episodes") or 2)
    except (TypeError, ValueError):
        min_episodes = 2
    rows = alarm_history.fleet_alarm_frequency(days=days, min_episodes=min_episodes)
    return jsonify({"ok": True, "days": days, "min_episodes": min_episodes, "rows": rows})


@app.route("/issues/carrier/<unit>", methods=["POST"])
def issues_carrier(unit):
    info, error = work_tool.get_unit_carriers(unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/weather/<unit>", methods=["POST"])
def issues_weather(unit):
    payload = request.get_json(silent=True) or {}
    subject = str(
        payload.get("subject")
        or request.args.get("subject")
        or ""
    ).strip()
    info, error = work_tool.get_unit_weather(unit, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/battery-outlook/<unit>", methods=["POST"])
def issues_battery_outlook(unit):
    """Experimental: VRM battery SOC x multi-day cloud outlook (read-only)."""
    payload = request.get_json(silent=True) or {}
    subject = str(
        payload.get("subject")
        or request.args.get("subject")
        or ""
    ).strip()
    info, error = work_tool.unit_battery_weather_outlook(unit, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/weather-forecast/<unit>", methods=["POST"])
def issues_weather_forecast(unit):
    """Multi-day cloud outlook only, no VRM call — see work_tool.unit_weather_forecast."""
    payload = request.get_json(silent=True) or {}
    subject = str(
        payload.get("subject")
        or request.args.get("subject")
        or ""
    ).strip()
    info, error = work_tool.unit_weather_forecast(unit, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/power-status/<unit>", methods=["POST"])
def issues_power_status(unit):
    """Experimental: focused "is this trailer plugged into AC/shore power" check (read-only)."""
    payload = request.get_json(silent=True) or {}
    subject = str(
        payload.get("subject")
        or request.args.get("subject")
        or ""
    ).strip()
    info, error = work_tool.unit_power_status(unit, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/shading-status/<unit>", methods=["POST"])
def issues_shading_status(unit):
    """
    Experimental: is this trailer's solar being shaded — built from a real
    ERP "shaded" ticket pattern (see work_tool.detect_solar_shading).
    Read-only against VRM.
    """
    payload = request.get_json(silent=True) or {}
    subject = str(
        payload.get("subject")
        or request.args.get("subject")
        or ""
    ).strip()
    info, error = work_tool.unit_shading_status(unit, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/dead-panel-status/<unit>", methods=["POST"])
def issues_dead_panel_status(unit):
    """
    Experimental: is this trailer likely down a solar panel — built from
    a peak-output-over-time comparison (see work_tool.detect_dead_panel).
    Read-only against VRM.
    """
    payload = request.get_json(silent=True) or {}
    subject = str(
        payload.get("subject")
        or request.args.get("subject")
        or ""
    ).strip()
    info, error = work_tool.unit_dead_panel_status(unit, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/schedule-shading-snapshot/<unit>", methods=["POST"])
def issues_schedule_shading_snapshot(unit):
    """
    Schedule a snapshot task aimed at this trailer's own worst shading
    hour — requires shading to be CURRENTLY detected (runs the check
    fresh); there's no "peak hour" to aim at otherwise. The task itself
    doesn't fire until the following day, and only after re-confirming
    the dip is still happening — see shading_snapshots.py's module
    docstring and work_tool.verify_shading_dip_now.
    """
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or request.args.get("subject") or "").strip()
    camera_target = str(payload.get("camera_target") or "fisheye").strip() or "fisheye"

    info, error = work_tool.unit_shading_status(unit, subject)
    if error:
        return _error(error)
    if info.get("shading_status") != "shaded" or info.get("shading_worst_hour_utc") is None:
        return jsonify({
            "ok": False,
            "error": (
                "No active shading detected right now for this unit — run \"Check Shade\" first, "
                "or try again once a dip shows up."
            ),
        }), 400

    task_id, created, next_attempt_at = shading_snapshots.schedule_task(
        info["unit"], subject, camera_target, info["shading_worst_hour_utc"],
        verify_mode=info.get("shading_source") or "dip",
        window_start_minutes_utc=info.get("shading_window_start_minutes_utc"),
        window_end_minutes_utc=info.get("shading_window_end_minutes_utc"),
    )
    if task_id is None:
        return _error("Could not schedule the snapshot task", 500)
    return jsonify({
        "ok": True,
        "task_id": task_id,
        "created": created,
        "unit": info["unit"],
        "camera_target": camera_target,
        "peak_hour_utc": info["shading_worst_hour_utc"],
        "next_attempt_at": next_attempt_at,
    })


@app.route("/issues/schedule-shading-snapshot-bulk", methods=["POST"])
def issues_schedule_shading_snapshot_bulk():
    """
    Same as issues_schedule_shading_snapshot, but for every unit the
    Shaded Units report CURRENTLY lists as "shaded" — reads the cached
    fleet shading rows (whatever's already on screen), it does not
    re-check the whole fleet live. Units already carrying a pending task
    are left alone (schedule_task's own de-dup), so re-clicking this
    doesn't pile up repeats.
    """
    payload = request.get_json(silent=True) or {}
    camera_target = str(payload.get("camera_target") or "fisheye").strip() or "fisheye"

    with _fleet_shading_status_cache_lock:
        rows = list(_fleet_shading_status_cache.get("rows") or [])

    scheduled, already_pending, skipped = [], [], []
    for row in rows:
        if row.get("shading_status") != "shaded":
            continue
        unit = row.get("unit")
        worst_hour = row.get("shading_worst_hour_utc")
        if not unit or worst_hour is None:
            skipped.append(unit or "(unknown)")
            continue
        task_id, created, next_attempt_at = shading_snapshots.schedule_task(
            unit, "", camera_target, worst_hour,
            verify_mode=row.get("shading_source") or "dip",
            window_start_minutes_utc=row.get("shading_window_start_minutes_utc"),
            window_end_minutes_utc=row.get("shading_window_end_minutes_utc"),
        )
        if task_id is None:
            skipped.append(unit)
        elif created:
            scheduled.append({"unit": unit, "task_id": task_id, "next_attempt_at": next_attempt_at})
        else:
            already_pending.append(unit)

    return jsonify({
        "ok": True,
        "scheduled": scheduled,
        "already_pending": already_pending,
        "skipped": skipped,
    })


@app.route("/issues/shading-snapshot-task/<unit>", methods=["GET"])
def issues_shading_snapshot_task(unit):
    """Latest snapshot task (if any) for one unit — for the Diagnostics panel."""
    tasks = shading_snapshots.latest_tasks_by_unit([unit])
    task = tasks.get(str(unit or "").strip().upper())
    return jsonify({"ok": True, "task": _snapshot_task_public(task)})


@app.route("/issues/shading-snapshot-image/<int:task_id>", methods=["GET"])
def issues_shading_snapshot_image(task_id):
    path = shading_snapshots.image_path_for(task_id)
    if not path:
        return "No image for this task", 404
    with open(path, "rb") as fh:
        image = fh.read()
    response = Response(image, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.route("/issues/cancel-shading-snapshot/<int:task_id>", methods=["POST"])
def issues_cancel_shading_snapshot(task_id):
    ok = shading_snapshots.cancel_task(task_id)
    return jsonify({"ok": ok})


@app.route("/issues/outage-pattern/<unit>", methods=["POST"])
def issues_outage_pattern(unit):
    """
    Experimental, newer and less field-validated than the VRM-based
    plug/shading/dead-panel checks: for a unit with no VRM trailer to
    check directly, looks in Zabbix's own event history for a recurring
    early-morning-unreachable / mid-morning-recovered pattern — see
    work_tool.detect_early_morning_outage_pattern for the reasoning and
    its explicit limitations (can't tell shading from a dead panel from
    an undersized array, and needs a resolvable region for local time).
    Read-only against Zabbix.
    """
    payload = request.get_json(silent=True) or {}
    subject = str(
        payload.get("subject")
        or request.args.get("subject")
        or ""
    ).strip()
    days = payload.get("days") or request.args.get("days") or 21
    region = work_tool.region_code_from_subject(subject)
    found, detail, confidence, matching_days = work_tool.detect_early_morning_outage_pattern(
        unit, region, days=int(days)
    )
    unit_key = str(unit or "").strip().upper()
    if found is None:
        status, label = "warn", "cannot check — " + detail
    elif found:
        status, label = "fail", "recurring early-morning outage pattern detected"
    else:
        status, label = "ok", "no recurring early-morning outage pattern found"
    confidence_text = f" ({confidence}% confidence)" if confidence is not None else ""
    summary = f"{unit_key} — {label}{confidence_text}"
    return jsonify({
        "ok": True,
        "unit": unit_key,
        "region": region,
        "found": found,
        "detail": detail,
        "confidence": confidence,
        "matching_days": matching_days,
        "status": status,
        "summary": summary,
    })


@app.route("/issues/battery-history/<unit>", methods=["POST"])
def issues_battery_history(unit):
    """Experimental: VRM voltage/SOC/current/solar time-series (read-only)."""
    payload = request.get_json(silent=True) or {}
    hours = payload.get("hours") or request.args.get("hours") or 24
    subject = payload.get("subject") or request.args.get("subject") or ""
    info, error = work_tool.unit_battery_history(unit, hours, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})


@app.route("/issues/weather-bulk", methods=["POST"])
def issues_weather_bulk():
    """
    Retained for region_code_from_subject's OTHER use (resolving local
    time for detect_early_morning_outage_pattern) — the ticket weather
    icon itself no longer calls this; see /issues/weather-bulk-units.
    """
    payload = request.get_json(silent=True) or {}
    regions = payload.get("regions") or []
    if not isinstance(regions, list):
        return _error("regions must be a list")
    force = bool(payload.get("force"))
    info, error = work_tool.get_weather_for_regions(regions, force=force)
    if error:
        return _error(error)
    return jsonify({"ok": True, "regions": info})


@app.route("/issues/weather-bulk-units", methods=["POST"])
def issues_weather_bulk_units():
    """
    Per-ticket weather icon data source (WEATHER_V2, 2026-09-15) — each
    unit's own trailer/site GPS via work_tool.get_weather_for_units,
    not a shared per-region metro coordinate. `units` is a list of
    {"unit": ..., "subject": ...} objects.
    """
    payload = request.get_json(silent=True) or {}
    units = payload.get("units") or []
    if not isinstance(units, list):
        return _error("units must be a list")
    force = bool(payload.get("force"))
    info, error = work_tool.get_weather_for_units(units, force=force)
    if error:
        return _error(error)
    return jsonify({"ok": True, "units": info})

def _unit_busy_response(unit, existing):
    existing = existing or {}
    return jsonify({
        "ok": False,
        "error": "%s is busy: %s" % (unit, existing.get("action") or "another action"),
        "busy": True,
        "action": existing.get("action"),
        "phase": existing.get("phase"),
    }), 409


def _run_locked_quick_action(unit, action_label, fn, *, token=None):
    """
    Run a one-shot action (reboot, restart services) under the per-unit lock.
    If `token` is given, it must match an in-flight job (e.g. the security fix
    wizard handing off its final step) instead of acquiring a fresh lock.
    """
    if token:
        info = work_tool.unit_busy_status(unit)
        if not info or info.get("token") != token:
            return jsonify({
                "ok": False,
                "error": "Security fix session expired or unit lock lost — refresh and check unit status",
            }), 409
        ok, message = fn()
        work_tool.unit_busy_end(unit, token)
        if not ok:
            return _error(message)
        return jsonify({"ok": True, "unit": unit, "message": message})

    started, new_token, existing = work_tool.unit_busy_start(unit, action_label)
    if not started:
        return _unit_busy_response(unit, existing)
    try:
        ok, message = fn()
    finally:
        work_tool.unit_busy_end(unit, new_token)
    if not ok:
        return _error(message)
    return jsonify({"ok": True, "unit": unit, "message": message})


def _require_unit_token(unit):
    """Validate the token in the request against the unit's in-flight job. Returns (token, error_response)."""
    payload = request.get_json(silent=True) or {}
    token = payload.get("token") or request.args.get("token")
    info = work_tool.unit_busy_status(unit)
    if not token or not info or info.get("token") != token:
        return None, (jsonify({
            "ok": False,
            "error": "Security fix session expired or unit lock lost — refresh and check unit status",
        }), 409)
    return token, None


@app.route("/issues/unit-status/<unit>", methods=["GET"])
def issues_unit_status(unit):
    info = work_tool.unit_busy_status(unit)
    token = request.args.get("token") or ""
    note_text, note_updated_at = work_tool.get_unit_note(unit)
    result = {"ok": True, "busy": bool(info), "note": note_text, "note_updated_at": note_updated_at}
    if info:
        result.update({
            "action": info.get("action"),
            "phase": info.get("phase"),
            "version": info.get("version"),
            "started_at": info.get("started_at"),
            "log": info.get("log", []),
            "is_owner": bool(token) and token == info.get("token"),
        })
    return jsonify(result)


@app.route("/issues/unit-lock/<unit>/clear", methods=["POST"])
def issues_unit_lock_clear(unit):
    cleared = work_tool.unit_busy_force_clear(unit)
    return jsonify({"ok": True, "cleared": cleared})


@app.route("/issues/busy-units", methods=["GET"])
def issues_busy_units():
    return jsonify({"ok": True, "units": work_tool.list_busy_units()})


@app.route("/issues/unit-note/<unit>", methods=["GET"])
def issues_unit_note_get(unit):
    text, updated_at = work_tool.get_unit_note(unit)
    return jsonify({"ok": True, "unit": unit, "text": text, "updated_at": updated_at})


@app.route("/issues/unit-note/<unit>", methods=["POST"])
def issues_unit_note_set(unit):
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    updated_at = work_tool.set_unit_note(unit, text)
    return jsonify({"ok": True, "unit": unit, "updated_at": updated_at})


# Worked/Skipped, shared across every browser looking at this dashboard —
# see work_tool/locks.py for why this exists (it didn't used to be shared).
@app.route("/issues/ticket-state", methods=["GET"])
def issues_ticket_state_get():
    return jsonify({"ok": True, "states": work_tool.get_ticket_states()})


@app.route("/issues/ticket-state", methods=["POST"])
def issues_ticket_state_set():
    payload = request.get_json(silent=True) or {}
    issue_id = str(payload.get("issue_id") or "").strip()
    if not issue_id:
        return _error("issue_id is required")
    worked = payload.get("worked")
    skipped = payload.get("skipped")
    entry = work_tool.set_ticket_state(
        issue_id,
        worked=bool(worked) if worked is not None else None,
        skipped=bool(skipped) if skipped is not None else None,
    )
    tech = str(payload.get("tech") or "").strip()
    if tech:
        unit = payload.get("unit")
        ip = request.remote_addr
        if worked is not None:
            if worked:
                tech_stats.record(tech, issue_id, "worked", unit=unit, ip=ip)
            else:
                tech_stats.clear(tech, issue_id, "worked")
        if skipped is not None:
            if skipped:
                tech_stats.record(tech, issue_id, "skipped", unit=unit, ip=ip)
            else:
                tech_stats.clear(tech, issue_id, "skipped")
    return jsonify({"ok": True, "issue_id": issue_id, "state": entry or {"worked": False, "skipped": False}})


@app.route("/issues/tech-stats", methods=["GET"])
def issues_tech_stats():
    """Week/month/year/all-time resolved+worked+skipped counts for one tech name."""
    tech = str(request.args.get("tech") or "").strip()
    if not tech:
        return _error("tech is required")
    return jsonify({"ok": True, **tech_stats.summary(tech)})


@app.route("/issues/tech-stats/techs", methods=["GET"])
def issues_tech_stats_techs():
    """Every tech name with recorded stats, most active first — for a "whose stats?" picker."""
    return jsonify({"ok": True, "techs": tech_stats.known_techs()})


@app.route("/issues/ticket-state/clear", methods=["POST"])
def issues_ticket_state_clear():
    payload = request.get_json(silent=True) or {}
    issue_ids = payload.get("issue_ids")
    states = work_tool.clear_ticket_states(issue_ids if isinstance(issue_ids, list) else None)
    return jsonify({"ok": True, "states": states})


@app.route("/issues/reboot-scrypted/<unit>", methods=["POST"])
@app.route("/issues/reboot-snuc/<unit>", methods=["POST"])
def issues_reboot_scrypted(unit):
    return _run_locked_quick_action(unit, "Reboot Scrypted", lambda: work_tool.reboot_scrypted(unit))

@app.route("/issues/reboot-pve/<unit>", methods=["POST"])
def issues_reboot_pve(unit):
    return _run_locked_quick_action(unit, "Reboot PVE", lambda: work_tool.reboot_pve(unit))

def _plain_stream(lines):
    return Response(
        lines,
        content_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.route("/issues/camera-dst-fix-stream/<unit>", methods=["POST"])
def issues_camera_dst_fix_stream(unit):
    """Live output from the Camera DST Fix — see work_tool.stream_camera_dst_fix. Takes the unit lock itself."""
    return _plain_stream(work_tool.stream_camera_dst_fix(unit))

@app.route("/issues/camera-dst-fix-all-stream", methods=["POST"])
def issues_camera_dst_fix_all_stream():
    """Camera DST Fix on every Camera Outage Report unit, one at a time — see work_tool.stream_camera_dst_fix_all."""
    return _plain_stream(work_tool.stream_camera_dst_fix_all())

@app.route("/issues/security-update-fix/step1/<unit>", methods=["POST"])
def issues_security_fix_step1(unit):
    started, token, existing = work_tool.unit_busy_start(unit, "Security Update Fix")
    if not started:
        return _unit_busy_response(unit, existing)
    ok, message, version = work_tool.security_update_web_step1(unit)
    if not ok:
        work_tool.unit_busy_end(unit, token)
        return _error(message)
    work_tool.unit_busy_touch(unit, token, phase="step1_done", version=version, log_line=message)
    return jsonify({"ok": True, "unit": unit, "version": version, "message": message, "token": token})

@app.route("/issues/security-update-fix/step2/<unit>", methods=["POST"])
def issues_security_fix_step2(unit):
    token, err = _require_unit_token(unit)
    if err:
        return err
    ok, message = work_tool.security_update_web_step2(unit)
    work_tool.unit_busy_touch(unit, token, phase="step2_done" if ok else "step2_failed", log_line=message)
    if not ok:
        return _error(message)
    return jsonify({"ok": True, "unit": unit, "message": message})

@app.route("/issues/security-update-fix/shutdown/<unit>", methods=["POST"])
def issues_security_fix_shutdown(unit):
    token, err = _require_unit_token(unit)
    if err:
        return err
    ok, message = work_tool.security_update_web_shutdown(unit)
    work_tool.unit_busy_touch(unit, token, phase="shutdown_done" if ok else "shutdown_failed", log_line=message)
    if not ok:
        return _error(message)
    return jsonify({"ok": True, "unit": unit, "message": message})

@app.route("/issues/security-update-fix/finish/<unit>", methods=["POST"])
def issues_security_fix_finish(unit):
    token, err = _require_unit_token(unit)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    version = payload.get("version") or request.args.get("version")
    if not version:
        # Browser refresh may have lost its in-memory copy — fall back to the
        # version step 1 saved server-side for this job.
        info = work_tool.unit_busy_status(unit)
        version = info.get("version") if info else None
    ok, message = work_tool.security_update_web_finish(unit, version)
    work_tool.unit_busy_touch(unit, token, phase="finish_done" if ok else "finish_failed", log_line=message)
    if not ok:
        return _error(message)
    return jsonify({"ok": True, "unit": unit, "message": message})

@app.route("/issues/security-update-fix/verify/<unit>", methods=["POST"])
def issues_security_fix_verify(unit):
    token, err = _require_unit_token(unit)
    if err:
        return err
    ok, message, drivers_loaded, counts = work_tool.security_update_web_verify(unit)
    phase = "verify_done" if (ok and drivers_loaded) else ("verify_warning" if ok else "verify_failed")
    work_tool.unit_busy_touch(unit, token, phase=phase, log_line=message)
    if not ok:
        return _error(message)
    return jsonify({
        "ok": True, "unit": unit, "message": message, "drivers_loaded": drivers_loaded,
        "token": token, **counts,
    })

@app.route("/issues/restart-services/<unit>", methods=["POST"])
def issues_restart_services(unit):
    payload = request.get_json(silent=True) or {}
    token = payload.get("token") or request.args.get("token")
    return _run_locked_quick_action(
        unit, "Restart All Services", lambda: work_tool.restart_platform_services(unit), token=token
    )

@app.route("/issues/reboot-nuc/<unit>", methods=["POST"])
def issues_reboot_nuc(unit):
    ok, message = work_tool.reboot_nuc(unit)
    if not ok:
        return _error(message or "Reboot NUC failed")
    return jsonify({"ok": True, "unit": unit, "message": message or "Restarting"})

@app.route("/issues/nuc-uptime/<unit>", methods=["POST"])
def issues_nuc_uptime(unit):
    ok, message, output = work_tool.nuc_uptime(unit)
    if not ok:
        return _error(message or "NUC uptime failed")
    return jsonify({
        "ok": True,
        "unit": unit,
        "message": message or "OK",
        "output": output or "",
    })

@app.route("/issues/chkdsk/<unit>", methods=["POST"])
def issues_chkdsk(unit):
    payload = request.get_json(silent=True) or {}
    drive = payload.get("drive") or request.args.get("drive") or ""
    ok, message, output = work_tool.chkdsk(unit, drive, read_only=True)
    if not ok:
        return jsonify({
            "ok": False,
            "error": message or "chkdsk failed",
            "output": output or "",
        }), 400
    return jsonify({
        "ok": True,
        "unit": unit,
        "drive": str(drive or "").strip().upper()[:1],
        "message": message or "OK",
        "output": output or "",
    })

@app.route("/issues/update-patch-stream/<unit>", methods=["POST"])
def issues_update_patch_stream(unit):
    """Live output from a patch update — see work_tool.stream_update_unit_patch_version."""
    def generate():
        for chunk in work_tool.stream_update_unit_patch_version(unit):
            yield chunk

    return Response(
        generate(),
        content_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/issues/update-patch/<unit>", methods=["POST"])
def issues_update_patch(unit):
    result, error = work_tool.update_unit_patch_version(unit)
    if error:
        payload = {"ok": False, "error": error}
        if isinstance(result, dict):
            if result.get("output"):
                payload["output"] = result["output"]
            if result.get("stderr"):
                payload["stderr"] = result["stderr"]
            if result.get("exit_code") is not None:
                payload["exit_code"] = result["exit_code"]
            if result.get("host"):
                payload["host"] = result["host"]
        return jsonify(payload), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/create-deployment-project", methods=["POST"])
def issues_create_deployment_project():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("project_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    created, error = work_tool.create_noc_deployment_project(
        project_id,
        prep_subject=subject or None,
    )
    if error:
        return _error(error)
    return jsonify({"ok": True, **created})

@app.route("/issues/create-termination-project", methods=["POST"])
def issues_create_termination_project():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    issue_id = str(payload.get("issue_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    created, error = work_tool.create_noc_termination_project(
        issue_id,
        issue_subject=subject or None,
    )
    if error:
        return _error(error)
    return jsonify({"ok": True, **created})

@app.route("/issues/create-relocation-project", methods=["POST"])
def issues_create_relocation_project():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    issue_id = str(payload.get("issue_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    created, error = work_tool.create_noc_relocation_project(
        issue_id,
        issue_subject=subject or None,
    )
    if error:
        return _error(error)
    return jsonify({"ok": True, **created})

@app.route("/issues/lookup-site", methods=["POST"])
def issues_lookup_site():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    if action not in ("terminate", "activate"):
        return _error("action must be terminate or activate")
    site, error = work_tool.lookup_erp_site_for_project_action(subject, action)
    if error:
        return _error(error)
    return jsonify({"ok": True, **site})

@app.route("/issues/terminate-site", methods=["POST"])
def issues_terminate_site():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    site_id = str(payload.get("site_id") or "").strip()
    result, error = work_tool.terminate_erp_site_from_project(
        subject,
        site_id=site_id or None,
    )
    if error:
        return _error(error)
    return jsonify({"ok": True, **result})

@app.route("/issues/activate-site", methods=["POST"])
def issues_activate_site():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    site_id = str(payload.get("site_id") or "").strip()
    result, error = work_tool.activate_erp_site_from_project(
        subject,
        site_id=site_id or None,
    )
    if error:
        return _error(error)
    return jsonify({"ok": True, **result})

@app.route("/issues/clear-mu-coordinates", methods=["POST"])
def issues_clear_mu_coordinates():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    mu = str(payload.get("mu") or "").strip()
    if mu:
        result, error = work_tool.clear_mu_coordinates(mu)
    else:
        result, error = work_tool.clear_mu_coordinates_from_subject(subject, unit=unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **result})

@app.route("/issues/clear-mu-site", methods=["POST"])
def issues_clear_mu_site():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    mu = str(payload.get("mu") or "").strip()
    if mu:
        result, error = work_tool.clear_mu_site(mu)
    else:
        result, error = work_tool.clear_mu_site_from_subject(subject, unit=unit)
    if error:
        return _error(error)
    return jsonify({"ok": True, **result})

@app.route("/issues/refurbish-projects/preview", methods=["POST"])
def issues_refurbish_projects_preview():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    preview, error = work_tool.preview_refurbish_projects_from_termination(
        subject,
        unit=unit or None,
    )
    if error:
        return _error(error)
    return jsonify({"ok": True, **preview})

@app.route("/issues/refurbish-projects", methods=["POST"])
def issues_refurbish_projects():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    created, error = work_tool.create_refurbish_projects_from_termination(
        subject,
        unit=unit or None,
    )
    if error:
        return _error(error)
    return jsonify({"ok": True, **created})

@app.route("/issues/tech-checks/preview", methods=["POST"])
def issues_tech_checks_preview():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("project_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    if not project_id:
        return _error("Missing project id")
    if not work_tool._is_noc_deployment_project_subject(subject):
        return jsonify({
            "ok": False,
            "error": "Tech Checks is only available for NOC Deployment projects",
        }), 400
    preview, error = work_tool.preview_project_tech_checks(project_id, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **preview})

@app.route("/issues/tech-checks", methods=["POST"])
def issues_tech_checks():
    if erp_writes_disabled():
        return _erp_writes_blocked_response()
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("project_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    if not project_id:
        return _error("Missing project id")
    if not work_tool._is_noc_deployment_project_subject(subject):
        return jsonify({
            "ok": False,
            "error": "Tech Checks is only available for NOC Deployment projects",
        }), 400
    result, error = work_tool.complete_project_tech_checks(project_id, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **result})

# Quick Validate only ever pings router/compute/Scrypted — it has no idea
# whether a ticket's actual complaint is the speaker, a camera, or a panel,
# so "router+compute are up" is not evidence any of THOSE are fixed. Caught
# live, 2026-09-28 (RD3523, "Unit Outage Partial - Speaker"): Quick Validate
# moved it straight to Up Steady on router/compute alone while the row's own
# data still read "speaker down". These four lists already have correct,
# speaker/camera/panel-aware per-entry logic in revalidate_list_entry (the
# same thing the bulk "Revalidate list" button uses) — route Quick Validate
# through that instead of the blind connectivity check when the ticket is
# currently sitting in one of them.
SPECIALIZED_VALIDATE_LISTS = {"speaker_outage", "camera_outage", "panel_issues", "camera_view"}

@app.route("/issues/validate-unit/<unit>", methods=["POST"])
def issues_validate_unit(unit):
    payload = request.get_json(silent=True) or {}
    issue_id = payload.get("issue_id")
    source_list_id = payload.get("source_list_id")
    camera_target = payload.get("camera_target") or ""

    if source_list_id in SPECIALIZED_VALIDATE_LISTS:
        job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
        if job is None or job.get("results") is None:
            return _error("Shared report is not ready", 409)
        with job["state_lock"]:
            item = _find_result_item(
                job["results"].get(source_list_id) or [], issue_id, unit, camera_target,
            )
            item_copy = copy.deepcopy(item) if item else None
        if item_copy is None:
            return _error(f"{unit} is no longer in {source_list_id.replace('_', ' ')}")
        category, fields, output, error = work_tool.revalidate_list_entry(source_list_id, item_copy)
        if error:
            return _error(error)
        destination = category or source_list_id
        if destination not in ISSUE_RESULT_KEYS or destination in (
            "discarded_tickets", "monitoring_hours", "termination", "relocation", "footage_request",
        ):
            destination = source_list_id
        with job["state_lock"]:
            live = _find_result_item(
                job["results"].get(source_list_id) or [], issue_id, unit, camera_target,
            )
            if live is not None:
                if fields:
                    live.update(fields)
                if destination != source_list_id:
                    job["results"][source_list_id] = [
                        row for row in (job["results"].get(source_list_id) or [])
                        if row is not live
                    ]
                    job["results"][destination].append(live)
                job["version"] += 1
        return jsonify({
            "ok": True,
            "unit": unit,
            "category": destination,
            "output": output or "",
        })

    category, output, error = work_tool.validate_unit_status(unit)
    if error:
        return _error(error, 404)
    to_list_id = "truly_down" if category == "stale_vpn" else (category or "")
    led_status = {
        "false_positives": "green", "nuc_down": "yellow",
        "scrypted_outage": "yellow", "truly_down": "red",
    }.get(to_list_id)
    _sync_shared_validate_result(
        unit, issue_id, source_list_id,
        to_list_id, {"led_status": led_status} if led_status else None,
    )
    _apply_validation_to_recovery_email_status(unit, category)
    return jsonify({
        "ok": True,
        "unit": unit,
        "category": category,
        "output": output,
    })

@app.route("/issues/validate-unit-full/<unit>", methods=["POST"])
def issues_validate_unit_full(unit):
    result, error = work_tool.validate_unit_full(unit)
    if error:
        return _error(error, 404)
    payload = request.get_json(silent=True) or {}
    extra_fields = {"led_status": result["led_status"]} if result.get("led_status") else None
    # validate_unit_full leaves move_to = "" for the false_positives category
    # (there's no dedicated "down" list to name) — mirror the frontend's own
    # fallback here so the shared job actually relocates the ticket instead
    # of just patching led_status in place, which a later /issues/state poll
    # then reverts (the RD3410 "status LED didn't properly update" bug: the
    # calling browser moved the row locally, the server's copy never moved,
    # the next shared-state snapshot silently put it back).
    to_list_id = result.get("move_to") or (
        "false_positives" if result.get("category") == "false_positives" else ""
    )
    if payload.get("stay_in_list"):
        # Camera View / speaker / camera / panel / etc. rows: the ticket's
        # list is about what kind of work it is, not the unit's state, so
        # Full validate only patches the LED in place (Andrew's request,
        # 2026-10-07 — a Camera View ticket stays put even with its NUC down).
        to_list_id = ""
    _sync_shared_validate_result(
        unit, payload.get("issue_id"), payload.get("source_list_id"),
        to_list_id, extra_fields,
    )
    _apply_validation_to_recovery_email_status(unit, result.get("category"))
    return jsonify({"ok": True, **result})

@app.route("/issues/revalidate-list/<list_id>", methods=["POST"])
def issues_revalidate_list(list_id):
    if list_id not in ISSUE_RESULT_KEYS or list_id in NON_REVALIDATABLE_LISTS:
        return _error("This list cannot be revalidated")
    result, status = _revalidate_shared_list(list_id)
    if status == 409:
        return _error(result["error"], 409)
    if not result.get("ok"):
        return jsonify(result), status or 500
    return jsonify(result)

# Lists whose tickets aren't about a unit's connectivity — never re-pinged.
NON_REVALIDATABLE_LISTS = (
    "discarded_tickets",
    "monitoring_hours",
    "termination",
    "relocation",
    "footage_request",
)
UP_STEADY_REVALIDATE_SECONDS = _env_int("UP_STEADY_REVALIDATE_SECONDS", 30 * 60)
DOWN_FULL_REVALIDATE_SECONDS = _env_int("DOWN_FULL_REVALIDATE_SECONDS", 30 * 60)

# Lists whose Revalidate is a router/compute ping, so the result can also
# correct a unit's recovery email status.
EMAIL_STATUS_REVALIDATE_LISTS = ("false_positives", "truly_down", "nuc_down", "scrypted_outage")

def _revalidate_shared_list(list_id, only_units=None, scheduled=False, reason=""):
    """
    Re-run each ticket's list-specific check (revalidate_list_entry) and
    move it to wherever that check says it now belongs. Shared by the
    "Revalidate" list button, the 30-minute Up Steady re-check and the
    recovery-email trigger (see _revalidate_up_steady_from_email_check).

    only_units limits it to tickets for those units. scheduled=True is for
    background callers: it skips (rather than queues) when another refresh
    holds the lock, leaves the net sheet as loaded (generate_net_array
    empties net_array while other threads may be reading it), and writes a
    short summary to the shared console instead of every ping.

    Returns (result_dict, http_status): status None on success, 409 when
    the report isn't ready or another refresh is running.
    """
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        return {"ok": False, "error": "Shared report is not ready"}, 409
    if not job["poll_lock"].acquire(blocking=False):
        return {"ok": False, "error": "Another refresh is already running"}, 409
    wanted = (
        {str(u or "").strip().upper() for u in only_units}
        if only_units is not None else None
    )

    captured_stdout = io.StringIO()
    moves = []
    checked = 0
    moved = 0
    try:
        with issues_validation_lock:
            _push_stdout_capture(captured_stdout)
            try:
                if scheduled:
                    work_tool.ensure_net_array()
                else:
                    work_tool.generate_net_array()
                with job["state_lock"]:
                    snapshot = [
                        {
                            "issue_id": item.get("issue_id") or "",
                            "unit": item.get("unit") or "",
                            "camera_target": item.get("camera_target") or "",
                        }
                        for item in (job["results"].get(list_id) or [])
                        if wanted is None
                        or str(item.get("unit") or "").strip().upper() in wanted
                    ]
                print(
                    f"Revalidating {len(snapshot)} ticket"
                    f"{'' if len(snapshot) == 1 else 's'} in {list_id.replace('_', ' ')}"
                )
                total = len(snapshot)
                print(f"__PROGRESS__ 0 {total} starting")
                for index, key in enumerate(snapshot, 1):
                    with job["state_lock"]:
                        item = _find_result_item(
                            job["results"].get(list_id) or [],
                            key["issue_id"],
                            key["unit"],
                            key["camera_target"],
                        )
                        item_copy = copy.deepcopy(item) if item else None
                    if item_copy is None:
                        continue
                    checked += 1
                    print(f"__PROGRESS__ {index} {total} {item_copy.get('unit') or ''}")
                    category, fields, output, error = work_tool.revalidate_list_entry(
                        list_id, item_copy
                    )
                    if output:
                        print(output)
                    if error:
                        print(f"{item_copy.get('unit')}: {error}")
                        continue
                    destination = category or list_id
                    if destination not in ISSUE_RESULT_KEYS or destination in NON_REVALIDATABLE_LISTS:
                        destination = list_id
                    with job["state_lock"]:
                        live = _find_result_item(
                            job["results"].get(list_id) or [],
                            key["issue_id"],
                            key["unit"],
                            key["camera_target"],
                        )
                        if live is None:
                            continue
                        if fields:
                            live.update(fields)
                        changed = destination != list_id
                        if changed:
                            job["results"][list_id] = [
                                row for row in (job["results"].get(list_id) or [])
                                if row is not live
                            ]
                            job["results"][destination].append(live)
                            moved += 1
                            print(
                                f"{live.get('unit')} moved to "
                                f"{destination.replace('_', ' ')}"
                            )
                        else:
                            print(f"{live.get('unit')} unchanged")
                    # Only the connectivity lists' re-checks are pings the
                    # email status can trust; a camera/speaker list's
                    # category is about that device, not the unit.
                    if list_id in EMAIL_STATUS_REVALIDATE_LISTS:
                        _apply_validation_to_recovery_email_status(
                            key["unit"], destination
                        )
                    moves.append({
                        "issue_id": key["issue_id"],
                        "unit": key["unit"],
                        "camera_target": key["camera_target"],
                        "from": list_id,
                        "to": destination,
                        "fields": fields or {},
                    })
                print(f"__PROGRESS__ {total} {total} complete")
                if checked:
                    with job["state_lock"]:
                        job["version"] += 1
            finally:
                _pop_stdout_capture()
        # Back up from Down Full: now the switch answers, so the cell/power
        # check can actually tell which kind of outage it was.
        if list_id == "truly_down":
            _recheck_power_vs_cell_for_units(
                m["unit"] for m in moves if m["to"] == "false_positives"
            )
        captured_output = captured_stdout.getvalue()
        if scheduled:
            when = _arizona_now().strftime("%H:%M")
            summary = [
                f"[{when}] {reason or 'Scheduled re-check'}: {checked} "
                f"{list_id.replace('_', ' ')} ticket(s) checked, {moved} moved"
            ]
            summary += [
                f"  {m['unit']} moved to {m['to'].replace('_', ' ')}"
                for m in moves if m["to"] != list_id
            ]
            JobStdout(SHARED_ISSUES_JOB_ID, None).write("\n".join(summary) + "\n")
        elif captured_output:
            JobStdout(SHARED_ISSUES_JOB_ID, None).write(
                captured_output + ("" if captured_output.endswith("\n") else "\n")
            )
        return {
            "ok": True,
            "list_id": list_id,
            "checked": checked,
            "moved": moved,
            "moves": moves,
            "logs": captured_output.splitlines(),
        }, None
    except Exception as exc:
        captured_output = captured_stdout.getvalue()
        if captured_output and not scheduled:
            JobStdout(SHARED_ISSUES_JOB_ID, None).write(
                captured_output + ("" if captured_output.endswith("\n") else "\n")
            )
        return {
            "ok": False,
            "error": str(exc),
            "logs": captured_output.splitlines(),
        }, 500
    finally:
        job["poll_lock"].release()


def _revalidate_list_loop(list_id, label, interval_seconds, first_delay_seconds=None):
    """
    Re-check every ticket in one list every interval_seconds, moving each
    to wherever its check now says it belongs (_revalidate_shared_list).
    Read-only pings, same as the fleet polls, so deliberately NOT gated on
    automated_tasks_paused(). The first pass waits (by default one full
    interval): the startup validation has only just checked these tickets.

    Up Steady: so a unit that drops after startup leaves Up Steady (and its
    green LED) on its own — caught live 2026-10-08: RD3073 sat green while
    the hourly recovery-email check already knew it was down.
    Down Full (Andrew's request, 2026-10-13): the mirror — units that came
    back sat red in Down Full until someone hit Revalidate. One that moves
    to Up Steady also gets its cell/power check (see
    _recheck_power_vs_cell_for_units).
    """
    _shared_console_print(f"{label}: every {interval_seconds // 60} minutes")
    time.sleep(interval_seconds if first_delay_seconds is None else first_delay_seconds)
    while True:
        try:
            result, status = _revalidate_shared_list(list_id, scheduled=True, reason=label)
            if status == 409:
                _shared_console_print(f"{label} skipped — {result['error']}")
        except Exception as exc:
            _shared_console_print(f"{label} failed: {exc}")
        time.sleep(interval_seconds)


# Recovery-email statuses that mean the check found the unit NOT back up.
RECOVERY_EMAIL_DOWN_STATUSES = ("needs_initial_email", "pending_recovery")

def _revalidate_up_steady_from_email_check(by_unit):
    """
    The hourly recovery-email check pings every unit on the ART report. When
    it finds one down that is sitting in Up Steady, re-check just those
    tickets right away instead of waiting for the next 30-minute pass. The
    email check is only the trigger: revalidate_list_entry still decides
    where each ticket goes, so there is one rule for list placement.
    """
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if not by_unit or job is None or job.get("results") is None:
        return
    down = {
        unit for unit, info in by_unit.items()
        if info.get("status") in RECOVERY_EMAIL_DOWN_STATUSES
    }
    with job["state_lock"]:
        in_up_steady = {
            str(item.get("unit") or "").strip().upper()
            for item in (job["results"].get("false_positives") or [])
        }
    targets = sorted(down & in_up_steady)
    if not targets:
        return
    result, status = _revalidate_shared_list(
        "false_positives", only_units=targets, scheduled=True,
        reason="Recovery email check found " + ", ".join(targets) + " down — re-checking",
    )
    if status == 409:
        _shared_console_print(
            f"Up Steady re-check for {', '.join(targets)} skipped — {result['error']} "
            "(the 30-minute re-check will catch them)"
        )


# Recovery-email statuses that mean the check found the unit back up.
RECOVERY_EMAIL_UP_STATUSES = ("needs_recovery_email", "potential_false_positive")

def _revalidate_down_full_from_email_check(by_unit):
    """
    The mirror of _revalidate_up_steady_from_email_check. Nothing re-pings
    Down Full after startup, so a unit that came back sat red there while
    the hourly email check already had it as "Recovery email needed"
    (RD3064/RD3184/RD3518, 2026-10-13). Re-check just those tickets; the
    email check is only the trigger, revalidate_list_entry decides placement.
    """
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if not by_unit or job is None or job.get("results") is None:
        return
    up = {
        unit for unit, info in by_unit.items()
        if info.get("status") in RECOVERY_EMAIL_UP_STATUSES
    }
    with job["state_lock"]:
        in_down_full = {
            str(item.get("unit") or "").strip().upper()
            for item in (job["results"].get("truly_down") or [])
        }
    targets = sorted(up & in_down_full)
    if not targets:
        return
    result, status = _revalidate_shared_list(
        "truly_down", only_units=targets, scheduled=True,
        reason="Recovery email check found " + ", ".join(targets) + " up — re-checking",
    )
    if status == 409:
        _shared_console_print(
            f"Down Full re-check for {', '.join(targets)} skipped — {result['error']} "
            "(the next hourly email check will retry)"
        )

@app.route("/issues/validate-stale-vpn/<unit>", methods=["POST"])
def issues_validate_stale_vpn(unit):
    result, error = work_tool.validate_stale_vpn_status(unit)
    if error:
        return _error(error, 404)
    _patch_shared_issue_fields(
        unit,
        {
            "led_status": result.get("status"),
            "compute_label": result.get("compute_label"),
        },
        result_keys=("stale_vpn",),
    )
    result["ok"] = True
    return jsonify(result)

@app.route("/issues/validate-camera-view/<unit>", methods=["POST"])
def issues_validate_camera_view(unit):
    result, error = work_tool.validate_camera_view_status(unit)
    if error:
        return _error(error, 404)
    _patch_shared_issue_fields(
        unit,
        {
            "camera_view_status": result.get("status"),
            "compute_label": result.get("compute_label"),
        },
        result_keys=("camera_view",),
    )
    result["ok"] = True
    return jsonify(result)

@app.route("/issues/unit-context/<unit>", methods=["GET"])
def issues_unit_context(unit):
    payload, error = work_tool.unit_context_for_ui(unit)
    if error:
        return _error(error)
    return jsonify(payload)

def _issues_site_id_from_request(unit):
    subject = str(request.args.get("subject") or "").strip()
    is_project = request.args.get("is_project") in ("1", "true", "True")
    site_id, error = work_tool.resolve_dashboard_site_id(unit, subject, is_project=is_project)
    if error:
        return None, error
    return site_id, None


@app.route("/issues/shield/<unit>", methods=["GET"])
def issues_shield(unit):
    site_id, error = _issues_site_id_from_request(unit)
    if error:
        return error, 404
    url = work_tool.shield_web_url(site_id)
    if not url:
        return "workTLD is not set in .env", 502
    return redirect(url)


@app.route("/issues/shield-component/<unit>", methods=["GET"])
def issues_shield_component(unit):
    url = work_tool.shield_component_web_url(unit)
    if not url:
        return "Unit or workTLD is missing", 404
    return redirect(url)


@app.route("/issues/router/<unit>", methods=["GET"])
def issues_router(unit):
    """Plain redirect to http://<router ip>/ — no login automation, unlike /issues/switch/."""
    ip = work_tool.router_ip_for_unit(unit)
    if not ip:
        return f"No router IP in net sheet for {unit}", 502
    return redirect(f"http://{ip}/")


@app.route("/issues/attached-mu/<unit>", methods=["GET"])
def issues_attached_mu(unit):
    subject = (request.args.get("subject") or "").strip()
    mu = work_tool.resolve_attached_mu_code(unit, subject)
    url = work_tool.shield_component_web_url(mu) if mu else ""
    return jsonify({
        "unit": str(unit or "").strip(),
        "mu": mu or "",
        "url": url,
    })


@app.route("/issues/site-page/<unit>", methods=["GET"])
def issues_site_page(unit):
    site_id, error = _issues_site_id_from_request(unit)
    if error:
        return error, 404
    url = work_tool.erp_site_web_url(site_id)
    if not url:
        return "workTLD is not set in .env", 502
    return redirect(url)


@app.route("/issues/event-records/<unit>", methods=["GET"])
def issues_event_records(unit):
    url = work_tool.erp_event_records_web_url(unit)
    if not url:
        return "Unit or workTLD is missing", 404
    return redirect(url)

@app.route("/issues/art-site-contacts/<unit>", methods=["POST"])
def issues_art_site_contacts(unit):
    """ART report 152 (Site Contacts), filtered to this ticket's own site — see work_tool.get_art_site_contacts."""
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or request.args.get("subject") or "").strip()
    info, error = work_tool.get_art_site_contacts(unit, subject)
    if error:
        return _error(error)
    return jsonify({"ok": True, **info})

@app.route("/issues/switch/<unit>", methods=["GET"])
def issues_switch(unit):
    info, error = work_tool.switch_login_info(unit)
    if error:
        return error, 502
    return render_template("switch_redirect.html", **info)

@app.route("/issues/relay/<unit>", methods=["GET"])
def issues_relay(unit):
    info, error = work_tool.relay_login_info(unit)
    if error:
        return error, 502
    return render_template("relay_redirect.html", **info)

@app.route("/issues/pve/<unit>", methods=["GET"])
def issues_pve(unit):
    url, error = work_tool.start_pve_local_proxy(unit)
    if error:
        return error, 502
    return redirect(url)

@app.route("/recovery_email", methods=["GET"])
def recovery_email_form():
    art_path = work_tool.art_recovery_report_path()
    art_mtime = ""
    if os.path.isfile(art_path):
        try:
            art_mtime = datetime.fromtimestamp(os.path.getmtime(art_path)).strftime(
                "%Y-%m-%d %H:%M"
            )
        except Exception:
            art_mtime = "unknown"
    return render_template(
        "recovery_email.html",
        art_report_ready=os.path.isfile(art_path),
        art_report_mtime=art_mtime,
    )

@app.route("/recovery_email/results", methods=["POST"])
def recovery_email_results():
    source = str(request.form.get("source") or "upload").strip().lower()
    delete_after = True
    job_id = uuid.uuid4().hex
    report_path = None

    if source == "art":
        report_path, error = work_tool.download_art_noc_outage_report()
        if error:
            return f"ART download failed: {error}", 502
        delete_after = False
    elif source == "art_cached":
        report_path = work_tool.art_recovery_report_path()
        if not os.path.isfile(report_path):
            report_path, error = work_tool.download_art_noc_outage_report()
            if error:
                return f"ART download failed: {error}", 502
        delete_after = False
    else:
        report = request.files.get("report_file")
        if not report:
            return "Missing report file", 400
        report_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{secure_filename(report.filename)}")
        report.save(report_path)
        report.close()

    stream_jobs[job_id] = {
        "queue": queue.Queue(),
        "done": False,
        "results": None,
    }
    thread = threading.Thread(
        target=_run_recovery_email_check,
        args=(job_id, report_path, delete_after),
        daemon=True,
    )
    thread.start()
    return redirect(url_for("recovery_email_watch", job_id=job_id))

@app.route("/recovery_email/watch/<job_id>", methods=["GET"])
def recovery_email_watch(job_id):
    if job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template(
        "recovery_email_results.html",
        job_id=job_id,
        work_tld=work_tool.work_tld(),
        mesh_base_url=work_tool.meshcentral_base_url(),
        raindance_base_url=work_tool.raindance_base_url(),
    )

@app.route("/recovery_email/stream/<job_id>", methods=["GET"])
def recovery_email_stream(job_id):
    return _sse_stream(job_id)

@app.route("/linux/stream/<job_id>", methods=["GET"])
def linux_stream(job_id):
    return _page_moved("Linux Diagnostic Tool")

def _arizona_now():
    return datetime.now(ARIZONA_TZ)

def _next_arizona_validation_time(now=None):
    now = now or _arizona_now()
    candidates = []
    for day_offset in range(0, 2):
        day = now.date() + timedelta(days=day_offset)
        for hour in ARIZONA_VALIDATION_HOURS:
            dt = datetime(
                day.year,
                day.month,
                day.day,
                hour,
                ARIZONA_VALIDATION_MINUTE,
                0,
                tzinfo=ARIZONA_TZ,
            )
            if dt > now:
                candidates.append(dt)
    return min(candidates)

def _run_scheduled_issues_validation():
    with shared_issue_job_lock:
        if SHARED_ISSUES_JOB_ID not in stream_jobs:
            _create_issue_job(SHARED_ISSUES_JOB_ID)
            print("Scheduled Arizona validation created the shared ticket queue")
            return
        job = stream_jobs[SHARED_ISSUES_JOB_ID]
        if not job.get("done"):
            print("Scheduled Arizona validation skipped — validation already running")
            return
    _run_issues_validation(SHARED_ISSUES_JOB_ID, scheduled=True)

def _next_arizona_missing_components_time(now=None):
    now = now or _arizona_now()
    for day_offset in range(0, 2):
        day = now.date() + timedelta(days=day_offset)
        dt = datetime(
            day.year,
            day.month,
            day.day,
            ARIZONA_MISSING_COMPONENTS_HOUR,
            ARIZONA_MISSING_COMPONENTS_MINUTE,
            0,
            tzinfo=ARIZONA_TZ,
        )
        if dt > now:
            return dt
    return now + timedelta(days=1)

def _run_scheduled_add_missing_components():
    with shared_issue_job_lock:
        job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        print(
            "Scheduled Add Missing Components/Sites skipped — shared report is not ready"
        )
        return
    deadline = time.time() + 10 * 60
    while True:
        if job["poll_lock"].acquire(blocking=False):
            break
        if time.time() >= deadline:
            print(
                "Scheduled Add Missing Components/Sites skipped — "
                "another ERP update is already running"
            )
            return
        time.sleep(15)
    try:
        _run_add_missing_components(job, scheduled=True)
    finally:
        job["poll_lock"].release()

def _arizona_validation_loop():
    while True:
        nxt = _next_arizona_validation_time()
        delay = (nxt - _arizona_now()).total_seconds()
        while delay > 0:
            time.sleep(min(delay, 60))
            delay = (_next_arizona_validation_time() - _arizona_now()).total_seconds()
        try:
            print(
                "Starting scheduled ticket-queue validation at "
                f"{_arizona_now().isoformat()}"
            )
            _run_scheduled_issues_validation()
        except Exception as exc:
            print(f"Scheduled ticket-queue validation failed: {exc}")
        time.sleep(61)

def _arizona_missing_components_loop():
    while True:
        nxt = _next_arizona_missing_components_time()
        delay = (nxt - _arizona_now()).total_seconds()
        while delay > 0:
            time.sleep(min(delay, 60))
            delay = (
                _next_arizona_missing_components_time() - _arizona_now()
            ).total_seconds()
        try:
            _run_scheduled_add_missing_components()
        except Exception as exc:
            print(f"Scheduled Add Missing Components/Sites failed: {exc}")
        time.sleep(61)

def _next_arizona_netsheet_sync_time(now=None):
    now = now or _arizona_now()
    for day_offset in range(0, 2):
        day = now.date() + timedelta(days=day_offset)
        dt = datetime(
            day.year,
            day.month,
            day.day,
            ARIZONA_NETSHEET_SYNC_HOUR,
            ARIZONA_NETSHEET_SYNC_MINUTE,
            0,
            tzinfo=ARIZONA_TZ,
        )
        if dt > now:
            return dt
    return now + timedelta(days=1)

def _run_scheduled_netsheet_sync():
    with shared_issue_job_lock:
        job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        print("Scheduled Sync netsheet from v19 skipped — shared report is not ready")
        return
    deadline = time.time() + 10 * 60
    while True:
        if job["poll_lock"].acquire(blocking=False):
            break
        if time.time() >= deadline:
            print(
                "Scheduled Sync netsheet from v19 skipped — "
                "another ERP update is already running"
            )
            return
        time.sleep(15)
    try:
        _run_netsheet_sync(job, scheduled=True)
    finally:
        job["poll_lock"].release()

def _arizona_netsheet_sync_loop():
    while True:
        nxt = _next_arizona_netsheet_sync_time()
        delay = (nxt - _arizona_now()).total_seconds()
        while delay > 0:
            time.sleep(min(delay, 60))
            delay = (_next_arizona_netsheet_sync_time() - _arizona_now()).total_seconds()
        try:
            _run_scheduled_netsheet_sync()
        except Exception as exc:
            print(f"Scheduled Sync netsheet from v19 failed: {exc}")
        time.sleep(61)

_arizona_scheduler_started = False
_arizona_scheduler_lock = threading.Lock()

def _start_arizona_validation_scheduler():
    global _arizona_scheduler_started
    with _arizona_scheduler_lock:
        if _arizona_scheduler_started:
            return
        _arizona_scheduler_started = True
        # Bookends the whole startup sequence below so it's obvious in
        # stdout where it begins and ends — each thread started in between
        # prints its own "first pass in Ns" line the moment it launches,
        # then "poll starting..."/"checked N" (or its own equivalent) once
        # that delay elapses, so a tech watching stdout right after a
        # restart can see exactly which background report is scheduled,
        # which one is currently mid-run, and which have already completed
        # their first pass — instead of the dashboard just quietly filling
        # in over the next few minutes with no indication why.
        _shared_console_print("=== Starting background pollers/schedulers ===")
        # Stage 1 of the startup order (see "Startup order" near
        # make_fleet_report): the initial ping sweep. The print above
        # already creates the shared job as a side effect; this says so
        # outright so the sweep never depends on a log line.
        _ensure_shared_issue_job()
        _shared_console_print(
            "Startup order: 1. initial ping sweep (running now) -> "
            "2. weather (Battery Outlook) -> 3. Power vs Cell -> "
            "4. reports: ART report + recovery email check, VRM Disconnected, "
            "Power & Infra Alerts, Units Unplugged, Shaded Units, Dead Panels "
            "-> Camera Outage Report last"
        )
        if automated_tasks_paused():
            print(
                "PAUSE_AUTOMATED_TASKS is enabled — daily 4:00/4:05/4:10 AM "
                "jobs stay paused until cleared (hourly ART report refresh "
                "and automatic ERP ticket/project polling now run "
                "regardless, per 2026-09-15 request — see their own "
                "scheduler comments)"
            )
        thread = threading.Thread(
            target=_arizona_validation_loop,
            daemon=True,
            name="arizona-validation",
        )
        thread.start()
        nxt = _next_arizona_validation_time()
        if not automated_tasks_paused():
            print(
                "Arizona ticket-queue validation scheduled for "
                f"{nxt.strftime('%Y-%m-%d %H:%M %Z')} "
                "(4:00 AM MST daily)"
            )
        missing_thread = threading.Thread(
            target=_arizona_missing_components_loop,
            daemon=True,
            name="arizona-missing-components",
        )
        missing_thread.start()
        missing_nxt = _next_arizona_missing_components_time()
        print(
            "Arizona Add Missing Components/Sites scheduled for "
            f"{missing_nxt.strftime('%Y-%m-%d %H:%M %Z')} "
            "(4:05 AM MST daily)"
        )
        netsheet_thread = threading.Thread(
            target=_arizona_netsheet_sync_loop,
            daemon=True,
            name="arizona-netsheet-sync",
        )
        netsheet_thread.start()
        netsheet_nxt = _next_arizona_netsheet_sync_time()
        print(
            "Arizona Sync netsheet from v19 scheduled for "
            f"{netsheet_nxt.strftime('%Y-%m-%d %H:%M %Z')} "
            "(4:10 AM MST daily)"
        )
        art_thread = threading.Thread(
            target=_art_recovery_report_loop,
            daemon=True,
            name="art-recovery-report",
        )
        art_thread.start()
        # Always-on regardless of PAUSE_AUTOMATED_TASKS too — see
        # _run_scheduled_art_recovery_report's own comment.
        print(
            "ART NOC outage report (reportId=153) refresh scheduled "
            f"every {ART_REPORT_REFRESH_SECONDS // 60} minutes, each followed "
            "by the recovery email status check"
        )
        erp_poll_thread = threading.Thread(
            target=_erp_ticket_project_poll_loop,
            daemon=True,
            name="erp-ticket-project-poll",
        )
        erp_poll_thread.start()
        # Read-only pings, so always on like the fleet polls — see
        # _revalidate_list_loop. Down Full starts half an interval later so
        # the two passes don't collide on the shared poll lock (a collision
        # just skips that pass).
        threading.Thread(
            target=_revalidate_list_loop,
            args=("false_positives", "Up Steady re-check", UP_STEADY_REVALIDATE_SECONDS),
            daemon=True,
            name="up-steady-revalidate",
        ).start()
        threading.Thread(
            target=_revalidate_list_loop,
            args=(
                "truly_down", "Down Full re-check", DOWN_FULL_REVALIDATE_SECONDS,
                DOWN_FULL_REVALIDATE_SECONDS + UP_STEADY_REVALIDATE_SECONDS // 2,
            ),
            daemon=True,
            name="down-full-revalidate",
        ).start()
        # Also always-on regardless of PAUSE_AUTOMATED_TASKS — see
        # _run_scheduled_erp_ticket_project_pull's own comment.
        print(
            "ERP ticket/project pull scheduled every "
            f"{ERP_POLL_INTERVAL_SECONDS // 60} minutes"
        )
        power_infra_thread = threading.Thread(
            target=_power_infra_alerts_loop,
            daemon=True,
            name="power-infra-alerts",
        )
        power_infra_thread.start()
        # Always-on regardless of PAUSE_AUTOMATED_TASKS — see
        # _run_scheduled_power_infra_alerts's docstring.
        print(
            "Power & Infra Alerts (Zabbix + VRM) poll scheduled every "
            f"{POWER_INFRA_ALERTS_REFRESH_SECONDS // 60} minutes"
        )
        # Listed in startup order. All start now, but each holds its first
        # pass on the stage before it (wait_for_stage / ready_fn on each
        # make_fleet_report call) — weather, then Power vs Cell, then the
        # rest, per Andrew's own request, 2026-10-02. The Camera Outage
        # Report thread (started below) waits for all of them.
        for loop_fn, thread_name, refresh_seconds, label in (
            (_fleet_battery_outlook_loop, "fleet-battery-outlook", FLEET_BATTERY_OUTLOOK_REFRESH_SECONDS, "Battery Outlook"),
            (_power_vs_cell_outage_loop, "power-vs-cell-outage", POWER_VS_CELL_OUTAGE_REFRESH_SECONDS, "Up Steady Power vs Cell"),
            (_fleet_vrm_freshness_loop, "fleet-vrm-freshness", FLEET_VRM_FRESHNESS_REFRESH_SECONDS, "VRM Disconnected"),
            (_fleet_power_status_loop, "fleet-power-status", FLEET_POWER_STATUS_REFRESH_SECONDS, "Units Unplugged"),
            (_fleet_shading_status_loop, "fleet-shading-status", FLEET_SHADING_STATUS_REFRESH_SECONDS, "Shaded Units"),
            (_fleet_dead_panel_loop, "fleet-dead-panel", FLEET_DEAD_PANEL_REFRESH_SECONDS, "Dead Panels"),
        ):
            fleet_thread = threading.Thread(target=loop_fn, daemon=True, name=thread_name)
            fleet_thread.start()
            # Always-on too — see _run_fleet_check's docstring.
            print(f"Fleet {label} report poll scheduled every {refresh_seconds // 60} minutes")
        camera_thread = threading.Thread(
            target=_camera_outage_report_loop,
            daemon=True,
            name="camera-outage-report",
        )
        camera_thread.start()
        print(
            "Camera Outage Report + camera find scheduled every "
            f"{CAMERA_OUTAGE_REFRESH_SECONDS // 60} minutes (first run after every other report)"
        )
        _shared_console_print(
            "=== All background pollers/schedulers launched — watch for each "
            "one's own \"first pass in Ns\" / \"poll starting...\" / \"checked "
            "N\" (or equivalent) lines above as they come online over the "
            "next few minutes ==="
        )

def _run_scheduled_art_recovery_report():
    # Deliberately NOT gated on automated_tasks_paused() — Andrew's own
    # request, 2026-09-15: resume the hourly ART pull specifically, while
    # the 4am Add-Missing-Components/netsheet-sync jobs stay paused. Same
    # "named exception, not a blanket flip" pattern as the fleet-report
    # polls and Power & Infra Alerts above.
    when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
    print(f"[{when}] Scheduled ART recovery report starting...")
    path, error = work_tool.download_art_noc_outage_report()
    if error:
        print(f"[{when}] Scheduled ART recovery report failed: {error}")
    else:
        print(f"[{when}] Scheduled ART recovery report refreshed: {path}")
    # The hourly recovery-email check rides on this hourly download, so
    # it always reads the report that was just fetched. A failed download
    # still runs it against the previous copy, which beats no answer.
    _run_recovery_email_status_check(download_if_missing=False)


# ---- Recovery email status --------------------------------------------------
# Which units need an outage email, which need a recovery email — the same
# answer the Recovery Email Check page gives, run hourly (chained onto the
# ART report refresh above) and cached per unit so the Graphs modal's
# indicator is a cheap read. Read-only: pings units and reads the ART
# spreadsheet, never sends an email or writes to ERP, so — like the fleet
# polls — it is not gated on automated_tasks_paused(). Like every
# scheduler here it doesn't run in sandbox; POST .../refresh runs it there.
_recovery_email_status_cache = {
    "by_unit": {},
    "checked_at": None,
    "error": None,
    "running": False,
    # Bumped on every change (each check, each validation correction);
    # /issues/state carries it so open pages re-read the cache when it moves.
    "rev": 0,
}
_recovery_email_status_lock = threading.Lock()


def _run_recovery_email_status_check(download_if_missing=True):
    """Run one check and update the cache. Returns False if one was already running."""
    with _recovery_email_status_lock:
        if _recovery_email_status_cache["running"]:
            return False
        _recovery_email_status_cache["running"] = True
    when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
    print(f"[{when}] Recovery email status check starting...")
    try:
        by_unit, error = work_tool.recovery_email_status_check(download_if_missing=download_if_missing)
    except Exception as exc:
        by_unit, error = None, f"Recovery email status check crashed: {exc}"
    with _recovery_email_status_lock:
        _recovery_email_status_cache["running"] = False
        if error:
            # Keep the last good result; only the error updates, so the UI
            # can say "as of <earlier>, last check failed" instead of
            # showing every unit as needing nothing.
            _recovery_email_status_cache["error"] = error
        else:
            _recovery_email_status_cache["by_unit"] = by_unit
            _recovery_email_status_cache["checked_at"] = time.time()
            _recovery_email_status_cache["error"] = None
            _recovery_email_status_cache["rev"] += 1
    if error:
        print(f"[{when}] Recovery email status check failed: {error}")
    else:
        counts = {}
        for info in by_unit.values():
            counts[info["status"]] = counts.get(info["status"], 0) + 1
        print(
            f"[{when}] Recovery email status: "
            f"{counts.get('needs_initial_email', 0)} need an outage email, "
            f"{counts.get('needs_recovery_email', 0)} need a recovery email "
            f"({len(by_unit)} unit(s) on the report)"
        )
        try:
            _revalidate_up_steady_from_email_check(by_unit)
        except Exception as exc:
            print(f"[{when}] Up Steady re-check after the email check failed: {exc}")
        try:
            _revalidate_down_full_from_email_check(by_unit)
        except Exception as exc:
            print(f"[{when}] Down Full re-check after the email check failed: {exc}")
    return True


def _apply_validation_to_recovery_email_status(unit, category):
    """
    Re-sort one unit's cached email status from a validation that just
    pinged it, so a unit the hourly check caught mid-blip doesn't say
    "Outage email needed" for the rest of the hour (RD1020, 2026-10-09).
    The next hourly check replaces this with its own fresh answer.
    """
    unit_key = str(unit or "").strip().upper()
    if not unit_key or not category:
        return
    with _recovery_email_status_lock:
        info = (_recovery_email_status_cache.get("by_unit") or {}).get(unit_key)
        new_status = work_tool.recovery_email_status_after_validation(info, category)
        if not new_status or new_status == info.get("status"):
            return
        updated = dict(info)
        updated["status"] = new_status
        updated["previous_status"] = info.get("status")
        updated["revalidated_at"] = time.time()
        by_unit = dict(_recovery_email_status_cache["by_unit"])
        by_unit[unit_key] = updated
        _recovery_email_status_cache["by_unit"] = by_unit
        _recovery_email_status_cache["rev"] += 1
    _shared_console_print(
        f"Recovery email status for {unit_key}: {info.get('status')} -> {new_status} "
        f"(validation found {category.replace('_', ' ')})"
    )


@app.route("/issues/recovery-email-status", methods=["GET"])
def issues_recovery_email_status():
    with _recovery_email_status_lock:
        cache = dict(_recovery_email_status_cache)
    return jsonify({"ok": True, **cache})


@app.route("/issues/recovery-email-status/refresh", methods=["POST"])
def issues_recovery_email_status_refresh():
    with _recovery_email_status_lock:
        if _recovery_email_status_cache["running"]:
            return jsonify({"ok": True, "started": False, "running": True})
    thread = threading.Thread(
        target=_with_shared_job_stdout_capture,
        args=(_run_recovery_email_status_check,),
        daemon=True,
        name="recovery-email-status-refresh",
    )
    thread.start()
    return jsonify({"ok": True, "started": True, "running": True})


def _art_recovery_report_loop():
    # Starts the moment Power vs Cell's first pass is done (Andrew's
    # request, 2026-10-02), so the Graphs modal's email status pill is filled
    # soon after a restart. Then every ART_REPORT_REFRESH_SECONDS (hourly):
    # download the ART report, then run the recovery email check on it. See
    # "Startup order" near make_fleet_report.
    _wait_for_startup_stage(STARTUP_STAGE_POWER_VS_CELL, "ART report + recovery email check")
    while True:
        try:
            _with_shared_job_stdout_capture(_run_scheduled_art_recovery_report)
        except Exception as exc:
            _shared_console_print(f"Scheduled ART recovery report failed: {exc}")
        if not _art_first_pass_done.is_set():
            _art_first_pass_done.set()
        time.sleep(ART_REPORT_REFRESH_SECONDS)

def _run_scheduled_erp_ticket_project_pull():
    """
    One background pass pulling BOTH the shared ticket queue (scope=
    "issues") and NOC/Prep projects (scope="projects") — the server-side
    equivalent of clicking "Pull Issues"/"Pull Projects" by hand, so the
    dashboard stays current even with no browser tab open (the client's
    own 30-min auto-poll only ever refreshes whichever ONE panel,
    Issues or Projects, happens to be active in an open tab — see
    pollForNewIssues in issues_results.html). Reuses
    _poll_shared_issue_queue directly, not a re-implementation, so this
    can never drift from what the manual buttons do.

    Deliberately NOT gated on automated_tasks_paused() — Andrew's own
    request, 2026-09-15: resume automatic ticket/project pull
    specifically, while the 4am Add-Missing-Components/netsheet-sync jobs
    stay paused. Same "named exception, not a blanket flip" pattern as
    the fleet-report polls, Power & Infra Alerts, and the ART report — see
    _poll_shared_issue_queue's own docstring, which no longer checks that
    flag at all.
    """
    job_id = _ensure_shared_issue_job()
    job = stream_jobs.get(job_id)
    if not job or not job.get("done"):
        print("Scheduled ERP ticket/project pull skipped — initial validation still running")
        return
    when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
    print(f"[{when}] Scheduled ERP ticket/project pull starting...")
    for scope in ("issues", "projects"):
        response, _status = _poll_shared_issue_queue(job_id, scope=scope, force=True)
        if not response.get("ok"):
            print(f"[{when}] Scheduled ERP {scope} pull failed: {response.get('error')}")
            continue
        if response.get("skipped"):
            continue
        if scope == "issues":
            print(
                f"[{when}] Scheduled ERP issue pull: {response.get('new_count', 0)} new, "
                f"{response.get('removed_count', 0)} removed, {response.get('restored_count', 0)} restored, "
                f"{response.get('updated_count', 0)} updated"
            )
        else:
            print(f"[{when}] Scheduled ERP project pull: {response.get('project_count', 0)} project(s)")


def _erp_ticket_project_poll_loop():
    # Brief startup delay so the service finishes boot (and the shared
    # job's own initial validation has a head start) before the first
    # scheduled pass.
    _shared_console_print("ERP ticket/project pull: first pass in 90s (after the initial validation run)")
    time.sleep(90)
    while True:
        try:
            _with_shared_job_stdout_capture(_run_scheduled_erp_ticket_project_pull)
        except Exception as exc:
            _shared_console_print(f"Scheduled ERP ticket/project pull failed: {exc}")
        time.sleep(ERP_POLL_INTERVAL_SECONDS)

def _run_scheduled_power_infra_alerts():
    """
    Poll Zabbix + VRM, cache the result, and log what changed since the
    last poll — new alarms appearing or clearing, not just a full dump every
    time. This is the "log/notify" half of the request; it never writes to
    Zabbix or VRM, only reads. The cache it fills is what the dashboard's
    warning glyphs and the Power & Infra Alerts panel's cached view read.

    Deliberately NOT gated on automated_tasks_paused() — unlike the
    4:00/4:05/4:10 AM validation jobs and the 30-minute ERP poll that flag
    exists to hold off, this is a read-only Zabbix+VRM poll with no side
    effects, and gating it meant Power & Infra Alerts (and the fleet report
    polls below) never populated on their own — a tech had to open the page
    and hit Refresh just to see anything, every single time the service
    restarted. Same reasoning _shading_snapshot_scheduler_loop already
    applies to its own always-on loop.
    """
    when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
    print(f"[{when}] Power & Infra Alerts poll starting...")
    info, error = work_tool.combined_power_infra_alerts()
    if error:
        print(f"[{when}] Scheduled Power & Infra Alerts poll failed: {error}")
        return
    rows = info.get("rows") or []
    with _power_infra_cache_lock:
        previous_units = {r["unit"] for r in _power_infra_cache.get("rows") or []}
        current_units = {r["unit"] for r in rows}
        _power_infra_cache["rows"] = rows
        _power_infra_cache["fetched_at"] = time.time()
        _power_infra_cache["zabbix_error"] = info.get("zabbix_error")
        _power_infra_cache["vrm_error"] = info.get("vrm_error")

    new_units = current_units - previous_units
    cleared_units = previous_units - current_units
    if new_units:
        print(f"[{when}] Power & Infra Alerts: new — {', '.join(sorted(new_units))}")
    if cleared_units:
        print(f"[{when}] Power & Infra Alerts: cleared — {', '.join(sorted(cleared_units))}")
    if not new_units and not cleared_units:
        print(f"[{when}] Power & Infra Alerts: no change ({len(rows)} unit(s) flagged)")

    # Per-alarm (not just per-unit) episode tracking — see alarm_history.py.
    # This is the persistent version of the new/cleared diff just above;
    # that diff only ever lived in a print statement and reset to nothing
    # on every service restart.
    try:
        alarm_history.record_snapshot(rows)
    except Exception as exc:
        print(f"[{when}] Alarm history record failed: {exc}")


def _power_infra_alerts_loop():
    # Stage 4 of the startup order (see "Startup order" near
    # make_fleet_report): after the ping sweep, weather and Power vs Cell.
    _wait_for_startup_stage(STARTUP_STAGE_POWER_VS_CELL, "Power & Infra Alerts poll")
    while True:
        try:
            _with_shared_job_stdout_capture(_run_scheduled_power_infra_alerts)
        except Exception as exc:
            _shared_console_print(f"Scheduled Power & Infra Alerts poll failed: {exc}")
        if not _power_infra_first_pass_done.is_set():
            _power_infra_first_pass_done.set()
        time.sleep(POWER_INFRA_ALERTS_REFRESH_SECONDS)


def _run_fleet_check(label, check_fn, cache, cache_lock, after_check_fn=None):
    """
    Shared body for the four fleet-wide VRM poll loops below: fetch, cache,
    log one line. Never lets a bad poll wipe out a good cache — on error,
    the previous rows just stay in place for the next read (only
    cache["error"] updates, so the UI can still show "data as of a while
    ago" instead of nothing).

    Deliberately NOT gated on automated_tasks_paused() — see
    _run_scheduled_power_infra_alerts's docstring for why: these are the
    Units Unplugged/Shaded Units/Dead Panels/VRM Disconnected reports, and
    a tech shouldn't have to hit each one's Refresh button by hand just to
    see whether anything is wrong right after the service starts.

    after_check_fn(rows), if given, runs once per successful poll, after
    the cache updates — currently just the Shaded Units report's own
    auto-schedule step (see _auto_schedule_shading_snapshots). A failure
    in it is logged, not raised — a broken hook must never look like the
    fleet check itself failed.
    """
    when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
    # Paired with the "checked N installation(s)"/"failed" line below so
    # stdout shows a clear start/end for each pass — otherwise a poll that
    # takes a minute-plus (real VRM load, not a couple of seconds) is
    # invisible the whole time it's running, right when a tech watching
    # stdout after a service restart most wants to know it's in progress.
    print(f"[{when}] Fleet {label} poll starting...")
    try:
        rows, error = check_fn()
    except Exception as exc:
        print(f"[{when}] Fleet {label} poll failed: {exc}")
        with cache_lock:
            cache["error"] = str(exc)
        return
    if error:
        print(f"[{when}] Fleet {label} poll failed: {error}")
        with cache_lock:
            cache["error"] = error
        return
    with cache_lock:
        cache["rows"] = rows or []
        cache["fetched_at"] = time.time()
        cache["error"] = None
    print(f"[{when}] Fleet {label}: checked {len(rows or [])} installation(s)")
    if after_check_fn is not None:
        try:
            after_check_fn(rows or [])
        except Exception as exc:
            print(f"[{when}] Fleet {label} poll's after-check step failed: {exc}")


def _camera_unit_for_shading_snapshot(unit):
    """
    A snapshot task's own `unit` is the VRM installation (an MU trailer
    for most of the fleet, per fleet_shading_status) — right for the dip
    verification, which is genuinely per-trailer solar data, but usually
    wrong for the camera fetch: an MU trailer doesn't carry its own
    fisheye, its ERP-linked RD/FD head does (see CLAUDE.md's "Unit
    conventions"). Every OTHER caller that needs a camera off a trailer
    (renderFleetReportRow, fleet_shading_status's own row.head_units)
    already resolves this; this was the one path that didn't, and it
    reliably failed every capture for exactly the units that need it
    (checked live, 2026-09-14: several units' tasks stuck at "Dip
    confirmed... but camera fetch failed: No fisheye configured for
    MUxxxx" — read straight off the bare MU code with nothing to resolve
    it, three wasted attempts each).

    Falls back to `unit` unchanged on any failure or when it isn't an MU
    code at all (an RD/FD-only ACRD unit already has its own camera).
    """
    unit = str(unit or "").strip().upper()
    if not unit.startswith("MU"):
        return unit
    try:
        heads_by_mu, error = work_tool._erp_heads_for_mu_trailers([unit])
    except Exception:
        return unit
    if error:
        return unit
    heads = heads_by_mu.get(unit) or []
    return heads[0] if heads else unit


SHADING_DIP_CAPTURE_HOUR_TOLERANCE = 1


def _run_due_shading_snapshot_tasks():
    """
    Process every snapshot task whose scheduled attempt has arrived:
    re-verify the dip is actually happening right now — via
    work_tool.verify_shading_dip_now for a plain "dip"-mode task, or
    work_tool.verify_compressed_window_dip_now for a "compressed_window"
    one (see schedule_task's own docstring for why these two need
    different logic) — and only THEN spend a camera fetch on it. Either
    outcome consumes one attempt — see shading_snapshots' own
    record_attempt_failure/record_captured for the retry-vs-exhausted
    logic.
    """
    for task in shading_snapshots.due_tasks():
        task_id = task["id"]
        unit = task["unit"]
        subject = task.get("subject") or ""
        verify_mode = task.get("verify_mode") or "dip"
        retarget_hour = None
        try:
            # A "cutoff" (recurring daily cliff) is verified the same way:
            # near its edge, is output still down vs the last few hours' peak?
            if verify_mode in ("compressed_window", "cutoff"):
                is_dip, detail, _current_watts, _reference_watts = work_tool.verify_compressed_window_dip_now(
                    unit, subject,
                    task.get("window_start_minutes_utc"), task.get("window_end_minutes_utc"),
                )
            else:
                # Scans every hour today already has a reading for and
                # finds the dip wherever it actually is, not just the hour
                # this task was originally scheduled at — see
                # verify_shading_dip_now's own docstring (caught live
                # 2026-09-16, MU8087: nearly a 4-hour drift). That widens
                # WHERE a dip gets found, but a real dip found several
                # hours away from right now is still the wrong moment for
                # a camera fetch — a photo taken now wouldn't show it (see
                # RD3365/MU7034, same day: scheduled for 7am, real dip
                # around noon). So a confirmed dip whose hour isn't close
                # to the current one doesn't get captured either — instead
                # the task retargets to that hour instead of just retrying
                # the same stale one again next time.
                is_dip, detail, _current_watts, _typical_watts, worst_hour = work_tool.verify_shading_dip_now(
                    unit, subject
                )
                if is_dip and worst_hour is not None:
                    now_hour = datetime.utcnow().hour
                    hour_gap = min((worst_hour - now_hour) % 24, (now_hour - worst_hour) % 24)
                    if hour_gap > SHADING_DIP_CAPTURE_HOUR_TOLERANCE:
                        is_dip = False
                        retarget_hour = worst_hour
                        detail = (
                            f"{detail} — that's not close to the current hour ({now_hour}:00 UTC), "
                            f"so retargeting to {worst_hour}:00 UTC instead of capturing a photo "
                            f"that wouldn't show it"
                        )
        except Exception as exc:
            shading_snapshots.record_attempt_failure(task_id, f"Verification error: {exc}")
            continue
        if not is_dip:
            shading_snapshots.record_attempt_failure(
                task_id, f"Not captured: {detail or 'could not verify a current dip'}",
                new_peak_hour_utc=retarget_hour,
            )
            continue
        camera_unit = _camera_unit_for_shading_snapshot(unit)
        try:
            image, error = work_tool.camera_snapshot(camera_unit, task["camera_target"])
        except Exception as exc:
            image, error = None, str(exc)
        if error or not image:
            shading_snapshots.record_attempt_failure(
                task_id, f"Dip confirmed ({detail}) but camera fetch failed: {error}"
            )
            continue
        shading_snapshots.record_captured(task_id, image, f"Captured — {detail}")


def _shading_snapshot_scheduler_loop():
    # Brief startup delay so the service finishes boot before the first
    # pass. Deliberately does NOT check automated_tasks_paused() — same as
    # the fleet-report/Power & Infra Alerts loops above, now: each task
    # here is a specific, user-scheduled one-off (a button click created
    # it, aimed at a specific future day), not a recurring automatic poll,
    # and it only ever does read-only VRM/camera GETs plus writes to this
    # app's own local snapshot store — none of what PAUSE_AUTOMATED_TASKS
    # exists to hold off (ERP polling/writes, the 4 AM validation jobs).
    # Running it in sandbox too is also how this feature gets exercised
    # there at all — unlike the fleet-report pollers, its own startup isn't
    # gated behind WORK_TOOL_ENV != "sandbox" either (see
    # _start_shading_snapshot_scheduler).
    time.sleep(90)
    while True:
        try:
            _run_due_shading_snapshot_tasks()
        except Exception as exc:
            print(f"Shading snapshot scheduler pass failed: {exc}")
        try:
            shading_snapshots.prune_old(SHADING_SNAPSHOT_RETENTION_DAYS)
        except Exception as exc:
            print(f"Shading snapshot prune failed: {exc}")
        time.sleep(SHADING_SNAPSHOT_POLL_SECONDS)


_shading_snapshot_scheduler_started = False
_shading_snapshot_scheduler_lock = threading.Lock()


def _start_shading_snapshot_scheduler():
    global _shading_snapshot_scheduler_started
    with _shading_snapshot_scheduler_lock:
        if _shading_snapshot_scheduler_started:
            return
        _shading_snapshot_scheduler_started = True
        thread = threading.Thread(
            target=_shading_snapshot_scheduler_loop, daemon=True, name="shading-snapshot-scheduler",
        )
        thread.start()
        print(
            "Shading snapshot scheduler checking for due tasks every "
            f"{SHADING_SNAPSHOT_POLL_SECONDS // 60} minute(s)"
        )


ART_REPORT_REFRESH_SECONDS = _env_int("ART_REPORT_REFRESH_SECONDS", 3600)
# Brought down from 600 (10min) to 1800 (30min) — Andrew's own request,
# 2026-09-22, matching every other VRM-calling fleet poll's cadence (see
# FLEET_POWER_STATUS_REFRESH_SECONDS's own comment). Unlike VRM Disconnected
# below, this one's real VRM alarm reads per unit, not a free check.
POWER_INFRA_ALERTS_REFRESH_SECONDS = _env_int("POWER_INFRA_ALERTS_REFRESH_SECONDS", 1800)
# Longer than POWER_INFRA_ALERTS_REFRESH_SECONDS on purpose — each of these
# costs a real fan-out of VRM calls across the whole fleet (a minute or more
# wall-clock, not a couple of seconds), so polling them as often would mean
# a near-continuous background load against VRM's API for marginal freshness
# gain. VRM freshness itself is the exception — see its loop above.
FLEET_POWER_STATUS_REFRESH_SECONDS = _env_int("FLEET_POWER_STATUS_REFRESH_SECONDS", 1800)
# Brought down from 3600 (60min) to 1800 (30min), matching every other
# fleet report's cadence — Andrew's own request, 2026-09-15: no reason for
# Shaded Units/Dead Panels to be twice as stale as Units Unplugged/Battery
# Outlook/Up Steady when they cost the same shape of VRM fan-out.
FLEET_SHADING_STATUS_REFRESH_SECONDS = _env_int("FLEET_SHADING_STATUS_REFRESH_SECONDS", 1800)
FLEET_DEAD_PANEL_REFRESH_SECONDS = _env_int("FLEET_DEAD_PANEL_REFRESH_SECONDS", 1800)
# Brought up from 600 (10min) to 1800 (30min), matching every other fleet
# report's cadence — Andrew's own request, 2026-09-24. Still the cheapest of
# the six (see fleet_vrm_freshness_status's own docstring: no per-site VRM
# calls at all), so it stays the shortest stagger delay of the group even at
# the same refresh interval — just no longer polling faster than the data
# meaningfully changes for no reason.
FLEET_VRM_FRESHNESS_REFRESH_SECONDS = _env_int("FLEET_VRM_FRESHNESS_REFRESH_SECONDS", 1800)
# One VRM diagnostics call + one GPS resolution + one (metro-shared)
# forecast fetch per site — comparable load to FLEET_POWER_STATUS's single
# VRM call, so the same interval. Also matches how slowly the underlying
# data actually changes: SOC swings meaningfully hour to hour, but the
# 5-day cloud outlook it's being weighed against barely moves in 30
# minutes.
FLEET_BATTERY_OUTLOOK_REFRESH_SECONDS = _env_int("FLEET_BATTERY_OUTLOOK_REFRESH_SECONDS", 1800)
# Same interval as FLEET_POWER_STATUS — one real fan-out across every Up
# Steady unit, most of which short-circuit on a cheap Zabbix-only check
# (see unit_power_vs_cell_outage's docstring) and only SSH the ones with an
# actual loss window to explain.
POWER_VS_CELL_OUTAGE_REFRESH_SECONDS = _env_int("POWER_VS_CELL_OUTAGE_REFRESH_SECONDS", 1800)
# How often the shading-snapshot scheduler checks for due tasks. Short,
# unlike the fleet-report polls above — a task's own next_attempt_at is
# already a full day out, so there's no cost to checking often, and it's
# what keeps a scheduled capture from missing its window by more than a
# few minutes.
SHADING_SNAPSHOT_POLL_SECONDS = _env_int("SHADING_SNAPSHOT_POLL_SECONDS", 300)
# Scheduling a snapshot task used to be a purely manual click (the single
# "Schedule Snapshot" button, or the bulk one) — checked live, 2026-09-21:
# the queue had sat completely empty for days, not because the capture
# mechanism was broken (its own history was a healthy 33/42 captured), but
# because nobody had clicked either button since the last bulk run. Andrew's
# own call: a unit showing up "shaded" in the fleet report should get a
# task on its own, no click required — see _auto_schedule_shading_snapshots,
# hooked into the Shaded Units poll's after_check_fn below. One cooldown
# per unit (its most recent task's updated_at, regardless of that task's
# outcome) keeps a persistently-shaded unit — the common case, not the
# exception — from getting a fresh task queued on every ~30-minute poll
# once its last one finished.
#
# updated_at, not created_at: every task's own next_attempt_at is already
# ~24h after it was created (see schedule_task's docstring on why it
# always waits a day), so gating the cooldown on created_at meant it
# expired within minutes of the attempt actually running — a fresh photo
# of a still-shaded unit got immediately superseded by a brand-new pending
# task on the very next poll, which is also what the Shaded Units report
# shows (latest_tasks_by_unit picks one task per unit). Caught live,
# 2026-09-23: every currently-"shaded" row on the report showed a bare
# "scheduled" line with no photo, even though the day's capture history
# had plenty of hits — each one's evidence had been overwritten by its own
# successor task within the same day. updated_at anchors the cooldown to
# the last actual attempt instead, so a fresh capture stays the visible
# "latest" task, thumbnail and all, for a full day.
SHADING_SNAPSHOT_AUTO_SCHEDULE_COOLDOWN_SECONDS = _env_int(
    "SHADING_SNAPSHOT_AUTO_SCHEDULE_COOLDOWN_SECONDS", 24 * 3600
)


def _auto_schedule_shading_snapshots(rows):
    """
    Schedule a snapshot task for every currently-shaded row the fleet
    Shaded Units check just returned — see SHADING_SNAPSHOT_AUTO_SCHEDULE_
    COOLDOWN_SECONDS above for why this is safe to call on every poll.
    Reuses shading_snapshots.schedule_task directly (the same call
    issues_schedule_shading_snapshot-bulk makes by hand), so a unit that
    already has a pending task is left alone either way (schedule_task's
    own de-dup).
    """
    camera_target = "fisheye"
    candidates = [
        row for row in (rows or [])
        if row.get("shading_status") == "shaded"
        and row.get("unit")
        and row.get("shading_worst_hour_utc") is not None
    ]
    if not candidates:
        return
    latest_by_unit = shading_snapshots.latest_tasks_by_unit(
        units=[row["unit"] for row in candidates]
    )
    now = time.time()
    scheduled = []
    for row in candidates:
        unit = str(row["unit"]).strip().upper()
        latest = latest_by_unit.get(unit)
        if latest and (now - (latest.get("updated_at") or latest.get("created_at") or 0)) < SHADING_SNAPSHOT_AUTO_SCHEDULE_COOLDOWN_SECONDS:
            continue
        task_id, created, _next_attempt_at = shading_snapshots.schedule_task(
            unit, "", camera_target, row["shading_worst_hour_utc"],
            verify_mode=row.get("shading_source") or "dip",
            window_start_minutes_utc=row.get("shading_window_start_minutes_utc"),
            window_end_minutes_utc=row.get("shading_window_end_minutes_utc"),
        )
        if task_id is not None and created:
            scheduled.append(unit)
    if scheduled:
        print(f"Auto-scheduled {len(scheduled)} shading snapshot task(s): {', '.join(scheduled)}")


# ---- Startup order ----------------------------------------------------------
# Andrew's own request, 2026-10-02: after a restart the background work runs
# in a fixed order instead of on staggered fixed delays —
#   1. the initial ping sweep (the shared ticket-queue validation, started
#      the moment the scheduler starts),
#   2. weather (the Battery Outlook report), once 1 has finished,
#   3. Power vs Cell (needs 1's results; see _power_vs_cell_sweep_units),
#   4. the reports: the ART report download + recovery email check, the
#      other fleet reports and Power & Infra Alerts — and, last of all, once
#      every one of those has done its first pass, the Camera Outage Report
#      with its per-unit camera find (_camera_outage_report_loop).
# Each stage's first pass sets its Event whether it succeeded or failed, and
# every wait is capped at STARTUP_STAGE_TIMEOUT_SECONDS, so one hung stage
# delays the reports after it instead of blocking them forever.
STARTUP_STAGE_TIMEOUT_SECONDS = _env_int("STARTUP_STAGE_TIMEOUT_SECONDS", 1800)
_startup_weather_done = threading.Event()
_startup_power_vs_cell_done = threading.Event()
# (Event, name, previous stage or None). Waiting on a stage waits on its
# previous stage first, each with its own timeout, so if weather hangs, the
# stage-4 reports still wait for Power vs Cell to actually run after it,
# instead of all timing out at the same moment and running alongside it.
STARTUP_STAGE_WEATHER = (_startup_weather_done, "weather (Battery Outlook)", None)
STARTUP_STAGE_POWER_VS_CELL = (_startup_power_vs_cell_done, "Power vs Cell", STARTUP_STAGE_WEATHER)
STARTUP_ORDER_TEXT = (
    "ping sweep -> weather -> Power vs Cell -> reports (Camera Outage Report last)"
)

# One Event per stage-4 report, set after its first pass. The Camera Outage
# Report job waits on all of them so it really is the last thing to run.
_startup_report_events = []


def _startup_report_event():
    event = threading.Event()
    _startup_report_events.append(event)
    return event


# The two hand-written stage-4 loops' own "first pass done" events (the
# fleet reports get theirs through make_fleet_report's marks_stage).
_power_infra_first_pass_done = _startup_report_event()
_art_first_pass_done = _startup_report_event()


# ---- Camera Outage Report (server side) -------------------------------------
# The last thing to run at startup (Andrew's request, 2026-10-02), then every
# CAMERA_OUTAGE_REFRESH_SECONDS: the Zabbix list of units with the SNUC-Watch
# camera-buffer alert open, then — one unit at a time, like the page's own
# Find All Cameras — the same per-unit find each row's Find Camera button
# runs (Scrypted RAM-folder check, or the camera ping sweep for a NUC unit).
# Read-only. Cached so opening Reports shows the result instantly instead of
# re-running the sweep in a browser. Like every scheduler here, it doesn't
# start in sandbox; the page falls back to its live load + Find All there.
CAMERA_OUTAGE_REFRESH_SECONDS = _env_int("CAMERA_OUTAGE_REFRESH_SECONDS", 3600)
_camera_outage_cache = {
    "units": [],
    "finds": {},
    "fetched_at": None,
    "error": None,
    "running": False,
}
_camera_outage_cache_lock = threading.Lock()


def _camera_outage_find(row):
    """One unit's camera find, shaped like the matching POST route's JSON."""
    unit = row.get("unit")
    if row.get("has_scrypted"):
        result, error = work_tool.scrypted_ram_folder_status(unit)
    else:
        result, error = work_tool.unit_camera_outage_ping_check(unit)
    if error:
        return {"ok": False, "error": error}
    return {"ok": True, **(result or {})}


def _run_camera_outage_sweep():
    when = _arizona_now().strftime("%Y-%m-%d %H:%M %Z")
    print(f"[{when}] Camera Outage Report starting...")
    rows, error = work_tool.fleet_camera_outage_report()
    if error:
        with _camera_outage_cache_lock:
            _camera_outage_cache["error"] = error
        print(f"[{when}] Camera Outage Report failed: {error}")
        return
    rows = rows or []
    finds = {}
    with _camera_outage_cache_lock:
        _camera_outage_cache["running"] = True
    try:
        for row in rows:
            unit = row.get("unit")
            try:
                finds[unit] = _camera_outage_find(row)
            except Exception as exc:
                finds[unit] = {"ok": False, "error": str(exc)}
    finally:
        with _camera_outage_cache_lock:
            _camera_outage_cache["units"] = rows
            _camera_outage_cache["finds"] = finds
            _camera_outage_cache["fetched_at"] = time.time()
            _camera_outage_cache["error"] = None
            _camera_outage_cache["running"] = False
    found = sum(1 for f in finds.values() if f.get("ok"))
    print(f"[{when}] Camera Outage Report: {len(rows)} unit(s) with the alert open, "
          f"camera find ran on {found}/{len(rows)}")


def _camera_outage_report_loop():
    # Last stage of the startup order: after every other report's first pass.
    _wait_for_startup_reports("Camera Outage Report")
    while True:
        try:
            _with_shared_job_stdout_capture(_run_camera_outage_sweep)
        except Exception as exc:
            _shared_console_print(f"Scheduled Camera Outage Report failed: {exc}")
        time.sleep(CAMERA_OUTAGE_REFRESH_SECONDS)


@app.route("/issues/camera-outage-report/cached", methods=["GET"])
def issues_camera_outage_report_cached():
    """The scheduled Camera Outage Report + per-unit finds — never runs a check itself."""
    with _camera_outage_cache_lock:
        snapshot = dict(_camera_outage_cache)
    return jsonify({"ok": True, **snapshot})


def _wait_for_startup_reports(label):
    """Block until every stage-4 report has done its first pass, with one
    overall STARTUP_STAGE_TIMEOUT_SECONDS cap measured from when Power vs
    Cell finished (or gave up)."""
    _wait_for_startup_stage(STARTUP_STAGE_POWER_VS_CELL, label)
    pending = [e for e in _startup_report_events if not e.is_set()]
    if not pending:
        return
    _shared_console_print(
        f"{label}: waiting for the other {len(pending)} report(s) to finish their first pass "
        f"(startup order: {STARTUP_ORDER_TEXT})"
    )
    deadline = time.time() + STARTUP_STAGE_TIMEOUT_SECONDS
    for event in pending:
        if not event.wait(max(0, deadline - time.time())):
            _shared_console_print(
                f"{label}: other reports still running after "
                f"{STARTUP_STAGE_TIMEOUT_SECONDS // 60} minutes — starting anyway"
            )
            return


def _wait_for_startup_stage(stage, label):
    """Block until `stage` has finished its first pass, or
    STARTUP_STAGE_TIMEOUT_SECONDS passes after its previous stage did.
    No-op once it's set, so this costs nothing after startup."""
    event, stage_name, previous = stage
    if event.is_set():
        return
    if previous is not None:
        _wait_for_startup_stage(previous, label)
        if event.is_set():
            return
    _shared_console_print(
        f"{label}: waiting for {stage_name} to finish its first pass "
        f"(startup order: {STARTUP_ORDER_TEXT})"
    )
    if not event.wait(STARTUP_STAGE_TIMEOUT_SECONDS):
        _shared_console_print(
            f"{label}: {stage_name} still hasn't finished after "
            f"{STARTUP_STAGE_TIMEOUT_SECONDS // 60} minutes — starting anyway"
        )


def make_fleet_report(route, endpoint, label, check_fn, refresh_seconds, startup_delay_seconds,
                       augment_fn=None, ready_fn=None, ready_poll_seconds=30, after_check_fn=None,
                       wait_for_stage=None, marks_stage=None):
    """
    Builds one fleet-wide report end to end: its cache + lock, its
    `route` (live) and `route + "/cached"` routes, and its background poll
    loop — the one shape that Units Unplugged, Shaded Units, Dead Panels,
    VRM Disconnected, Battery Outlook and Up Steady Power vs Cell all
    shared, differing only in the arguments below (never in structure).
    Returns (cache, cache_lock, loop_fn): the caller binds these to plain
    module globals so the handful of other spots that still read a cache
    directly (issues_schedule_shading_snapshot_bulk's shading cache read)
    keep working unchanged, and so _start_arizona_validation_scheduler can
    hand loop_fn to a Thread exactly like before.

    `endpoint` becomes both this route's and its `/cached` sibling's Flask
    endpoint name (with "_cached" appended) — kept identical to each
    report's old function name so nothing that ever inspects the URL map
    sees a change.

    `startup_delay_seconds` staggers the six loops apart so they don't all
    launch in the same instant (each is a genuine minute-plus of
    concurrent VRM calls, bar VRM Disconnected which is cheap — see its
    call below). `ready_fn`, if given, is polled every `ready_poll_seconds`
    after that delay until it returns True before the steady-state loop
    begins — only Power vs Cell needs this, to wait for the shared
    ticket-queue pull's first run (see _power_vs_cell_sweep_units).

    `wait_for_stage` (an (Event, name) pair, see "Startup order" above)
    holds the first pass until that earlier stage has finished; the
    startup delay then counts from there, so it only staggers reports
    within the same stage. `marks_stage` is the Event this report sets once
    its own first pass is over, success or not.

    Deliberately NOT gated on automated_tasks_paused() — see
    _run_fleet_check's docstring for why.
    """
    cache = {"rows": [], "fetched_at": None, "error": None}
    cache_lock = threading.Lock()

    def _live_route():
        return _fleet_cache_route(check_fn, cache, cache_lock, augment_fn=augment_fn)

    def _cached_route():
        return _fleet_cached_route(cache, cache_lock, augment_fn=augment_fn)

    app.add_url_rule(route, endpoint, _live_route, methods=["GET"])
    app.add_url_rule(route + "/cached", endpoint + "_cached", _cached_route, methods=["GET"])

    def _loop():
        if wait_for_stage is not None:
            _wait_for_startup_stage(wait_for_stage, f"Fleet {label} poll")
        if startup_delay_seconds:
            _shared_console_print(
                f"Fleet {label} poll: first pass in {startup_delay_seconds}s "
                "(staggered so the background polls don't all hit VRM at once)"
            )
            time.sleep(startup_delay_seconds)
        if ready_fn is not None:
            printed_waiting = False
            while not ready_fn():
                if not printed_waiting:
                    _shared_console_print(
                        f"Fleet {label} poll: waiting on the shared ticket-queue "
                        "pull's first run before its own first pass..."
                    )
                    printed_waiting = True
                time.sleep(ready_poll_seconds)
        while True:
            try:
                # Tee'd into the shared job's own console stream — see
                # _with_shared_job_stdout_capture — so this thread's prints
                # (including _run_fleet_check's own "starting"/"checked N"
                # lines) land in the dashboard's Stdout pane, not just the
                # real process console nobody watching the browser can see.
                _with_shared_job_stdout_capture(
                    lambda: _run_fleet_check(
                        label, check_fn, cache, cache_lock, after_check_fn=after_check_fn
                    )
                )
            except Exception as exc:
                _shared_console_print(f"Fleet {label} poll failed: {exc}")
            if marks_stage is not None and not marks_stage.is_set():
                marks_stage.set()
                _shared_console_print(f"Startup: Fleet {label} first pass done — next stage can start")
            time.sleep(refresh_seconds)

    return cache, cache_lock, _loop


# Backs the VRM Disconnected report. No per-site VRM calls at all (see
# fleet_vrm_freshness_status), so this one adds no real load regardless of
# cadence — first of the stage-4 reports, with no stagger delay, even
# though its refresh interval now matches the others (see
# FLEET_VRM_FRESHNESS_REFRESH_SECONDS's own comment).
_fleet_vrm_freshness_cache, _fleet_vrm_freshness_cache_lock, _fleet_vrm_freshness_loop = make_fleet_report(
    "/issues/fleet-vrm-freshness", "issues_fleet_vrm_freshness", "VRM freshness",
    work_tool.fleet_vrm_freshness_status, FLEET_VRM_FRESHNESS_REFRESH_SECONDS, 0,
    wait_for_stage=STARTUP_STAGE_POWER_VS_CELL, marks_stage=_startup_report_event(),
)
# Backs the Battery Outlook report: one VRM diagnostics read + one GPS
# resolution + one (metro-shared) forecast fetch per site, run
# concurrently. Checked live (2026-09-13): ~186 installations after
# staleness/site filters, ~104s. Stage 3 of the startup order: right after
# Power vs Cell and before every other report (Andrew's own requests,
# 2026-09-21 and 2026-10-02), so the forecast data is already pulled by the
# time the others (which read the same net-sheet/GPS context) start.
_fleet_battery_outlook_cache, _fleet_battery_outlook_cache_lock, _fleet_battery_outlook_loop = make_fleet_report(
    "/issues/fleet-battery-outlook", "issues_fleet_battery_outlook", "battery outlook",
    work_tool.fleet_battery_outlook_status, FLEET_BATTERY_OUTLOOK_REFRESH_SECONDS, 0,
    # Stage 2: right after the initial ping sweep finishes (same "shared
    # job done" check Power vs Cell uses), before Power vs Cell.
    ready_fn=lambda: _power_vs_cell_sweep_units()[0] is not None,
    ready_poll_seconds=5,
    marks_stage=_startup_weather_done,
)
# Backs the Units Unplugged report's manual Refresh (live, ~a minute,
# concurrent VRM calls); the scheduled poll is what keeps /cached warm day
# to day.
_fleet_power_status_cache, _fleet_power_status_cache_lock, _fleet_power_status_loop = make_fleet_report(
    "/issues/fleet-power-status", "issues_fleet_power_status", "power status",
    work_tool.fleet_power_status, FLEET_POWER_STATUS_REFRESH_SECONDS, 30,
    wait_for_stage=STARTUP_STAGE_POWER_VS_CELL, marks_stage=_startup_report_event(),
)
# Backs the Shaded Units report. augment_fn attaches each row's own most
# recent shading-snapshot task after every cache refresh (see
# _augment_shading_rows_with_snapshot_tasks) — never baked into the stored
# cache, so it always reflects the task's current state. after_check_fn
# auto-schedules a snapshot task for every row this poll finds shaded —
# see _auto_schedule_shading_snapshots.
_fleet_shading_status_cache, _fleet_shading_status_cache_lock, _fleet_shading_status_loop = make_fleet_report(
    "/issues/fleet-shading-status", "issues_fleet_shading_status", "shading status",
    work_tool.fleet_shading_status, FLEET_SHADING_STATUS_REFRESH_SECONDS, 60,
    augment_fn=_augment_shading_rows_with_snapshot_tasks,
    after_check_fn=_auto_schedule_shading_snapshots,
    wait_for_stage=STARTUP_STAGE_POWER_VS_CELL, marks_stage=_startup_report_event(),
)
# Backs the Dead Panels report.
_fleet_dead_panel_cache, _fleet_dead_panel_cache_lock, _fleet_dead_panel_loop = make_fleet_report(
    "/issues/fleet-dead-panel-status", "issues_fleet_dead_panel_status", "dead panel",
    work_tool.fleet_dead_panel_status, FLEET_DEAD_PANEL_REFRESH_SECONDS, 90,
    wait_for_stage=STARTUP_STAGE_POWER_VS_CELL, marks_stage=_startup_report_event(),
)
# Backs the Up Steady / Offline compute / Scrypted outage lists' "Diagnose
# (Cell/Power)" buttons. SSH-heavy (see fleet_power_vs_cell_outage_status),
# so slower than the VRM fleet checks above. ready_fn covers the ordinary
# startup case, where the shared ticket-queue pull (and so the sweep's own
# unit list) hasn't finished its first run yet.
_power_vs_cell_cache, _power_vs_cell_cache_lock, _power_vs_cell_outage_loop = make_fleet_report(
    "/issues/fleet-power-vs-cell-outage", "issues_fleet_power_vs_cell_outage", "power vs cell outage",
    _power_vs_cell_check_fn, POWER_VS_CELL_OUTAGE_REFRESH_SECONDS, 0,
    # Stage 3: after weather (which itself waited for the ping sweep).
    wait_for_stage=STARTUP_STAGE_WEATHER,
    ready_fn=lambda: _power_vs_cell_sweep_units()[0] is not None,
    # A dict lookup, so poll it often: every later report waits on this
    # one, and a 30s poll could leave the whole chain idle for 30s.
    ready_poll_seconds=5,
    marks_stage=_startup_power_vs_cell_done,
)

if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or __name__ != "__main__":
    if WORK_TOOL_ENV != "sandbox":
        _start_arizona_validation_scheduler()
    # Unlike the line above, no sandbox exclusion — see
    # _shading_snapshot_scheduler_loop's own comment for why.
    _start_shading_snapshot_scheduler()

if __name__ == "__main__":
    debug = WORK_TOOL_ENV == "sandbox"
    if not debug and WORK_TOOL_ENV != "sandbox":
        _start_arizona_validation_scheduler()
    # debug=True (sandbox only) means app.run() below uses Werkzeug's
    # reloader, which re-executes this whole script in a child process
    # with WERKZEUG_RUN_MAIN=true — the PARENT ("watcher") process reaches
    # this same line too but never actually serves requests, so it must
    # not start a real background thread here. Without this check, sandbox
    # would run two live copies of the scheduler (one that never serves,
    # one that does), each independently hitting VRM/cameras.
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _start_shading_snapshot_scheduler()
    # Bind every interface by default. The live instance runs as the Windows
    # service "IssuesDashboard", which starts flask_endpoints.py directly and
    # therefore never sees run_live.bat — so the DEFAULT has to be the value
    # the NOC needs, not something a .bat opts into. People reach this box at
    # its LAN IP (http://<host>:5000); defaulting to loopback silently breaks
    # the service and looks exactly like "the app didn't start".
    #
    # To narrow it, set WORK_TOOL_BIND=127.0.0.1 — put it in .env, which the
    # service does read, rather than in a .bat, which it does not.
    bind_host = str(os.getenv("WORK_TOOL_BIND") or "0.0.0.0").strip() or "0.0.0.0"
    print(
        f"Starting work_tool ({WORK_TOOL_ENV}) on "
        f"http://127.0.0.1:{WORK_TOOL_PORT} (data: {DATA_DIR})"
    )
    if bind_host == "127.0.0.1":
        print(
            "  Bound to loopback only — this machine's LAN IP will refuse "
            "connections. Unset WORK_TOOL_BIND (or set 0.0.0.0) to reach it "
            "from the network."
        )
    else:
        # Say the LAN address out loud: people reach this box by IP, and a
        # silent loopback bind looks exactly like "the app didn't start".
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            lan_ip = ""
        if lan_ip and not lan_ip.startswith("127."):
            print(f"  Also reachable on http://{lan_ip}:{WORK_TOOL_PORT}")
        print(
            f"  NOTE: bound to {bind_host} — the dashboard is unauthenticated, "
            "so this assumes a trusted network."
        )
    app.run(host=bind_host, port=WORK_TOOL_PORT, debug=debug, threaded=True)