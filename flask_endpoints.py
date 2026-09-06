from flask import Flask, request, jsonify, render_template, Response, redirect, url_for
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


def automated_tasks_paused():
    """True when sandbox, or PAUSE_AUTOMATED_TASKS is set in .env (reloads each check)."""
    if WORK_TOOL_ENV == "sandbox":
        return True
    load_dotenv(ENV_PATH, override=True)
    value = str(os.getenv("PAUSE_AUTOMATED_TASKS") or "").strip().lower()
    return value in ("1", "true", "yes", "on")

UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    return (
        str((issue or {}).get("issue_type") or "").strip().lower(),
        str((issue or {}).get("issue_subtype") or "").strip().lower(),
    )

def _item_class_differs(item, issue):
    """True if the listed row's Issue Type or Subtype does not match ERP."""
    item = item or {}
    issue = issue or {}
    erp_type, erp_subtype = _issue_class_key(issue)
    item_type = str(item.get("issue_type") or "").strip().lower()
    item_subtype = str(item.get("issue_subtype") or "").strip().lower()
    if item.get("reason") and "issue_subtype" not in item and "undiagnosed" not in item:
        return False
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
    """Move one shared-job issue row from from_key to to_key."""
    issue_id = str(issue_id or "").strip()
    unit = str(unit or "").strip()
    if not issue_id or not unit or from_key == to_key:
        return False
    if from_key not in results or to_key not in results:
        return False
    moved = None
    remaining = []
    for item in results.get(from_key) or []:
        if (
            _item_issue_id(item) == issue_id
            and str((item or {}).get("unit") or "").strip() == unit
        ):
            moved = item
        else:
            remaining.append(item)
    if not moved:
        return False
    results[from_key] = remaining
    if extra_fields:
        moved.update(extra_fields)
    results.setdefault(to_key, []).append(moved)
    return True

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
    original_stdout = sys.stdout
    try:
        with issues_validation_lock:
            sys.stdout = JobStdout(job_id, original_stdout)
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
                sys.stdout = original_stdout
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

def _run_recovery_email_check(job_id, report_path):
    import sys
    job = stream_jobs[job_id]
    original_stdout = sys.stdout
    sys.stdout = JobStdout(job_id, original_stdout)
    try:
        work_tool.generate_false_mu()
        work_tool.generate_net_array()
        needs_recovery_email, needs_initial_email, potential_false_positive, pending_recovery, email_status_up_to_date = work_tool.check_missing_recovery_emails(report_path)
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
        sys.stdout = original_stdout
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

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")
@app.route("/victron", methods=["GET"])
def victron_form():
    return render_template("vrm.html")
@app.route("/outage_filter", methods=["GET"])
def outage_form():
    return render_template("outage.html")
@app.route("/issues", methods=["GET"])
def issues_form():
    return render_template("issues.html")
@app.route("/issues/results", methods=["POST"])
def issues_results():
    _ensure_shared_issue_job()
    return redirect(url_for("issues_watch_shared"))

@app.route("/issues/watch", methods=["GET"])
def issues_watch_shared():
    job_id = _ensure_shared_issue_job()
    return render_template(
        "issues_results.html",
        job_id=job_id,
        work_tld=work_tool.work_tld(),
        mesh_base_url=work_tool.meshcentral_base_url(),
        raindance_base_url=work_tool.raindance_base_url(),
        automation_paused=automated_tasks_paused(),
    )

@app.route("/issues/watch/<job_id>", methods=["GET"])
def issues_watch(job_id):
    if job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template(
        "issues_results.html",
        job_id=job_id,
        work_tld=work_tool.work_tld(),
        mesh_base_url=work_tool.meshcentral_base_url(),
        raindance_base_url=work_tool.raindance_base_url(),
        automation_paused=automated_tasks_paused(),
    )

@app.route("/issues/stream/<job_id>", methods=["GET"])
def issues_stream(job_id):
    return _sse_stream(job_id)

@app.route("/issues/state/<job_id>", methods=["GET"])
def issues_state(job_id):
    job = stream_jobs.get(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "Unknown job"}), 404
    try:
        cursor = max(0, int(request.args.get("cursor", 0)))
        client_version = max(0, int(request.args.get("version", 0)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid state cursor"}), 400

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
    return jsonify({
        "ok": True,
        "events": events,
        "cursor": next_cursor,
        "done": job["done"],
        "version": version,
        "validation_run_id": validation_run_id,
        "results": results,
        "resolved_today": resolved,
    })

@app.route("/issues/poll/<job_id>", methods=["POST"])
def issues_poll(job_id):
    job = stream_jobs.get(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "Unknown job"}), 404
    if not job["done"]:
        return jsonify({"ok": False, "error": "Initial validation is still running"}), 409
    payload = request.get_json(silent=True) or {}
    force = bool(payload.get("force"))
    manual = bool(payload.get("manual"))
    scope = str(payload.get("scope") or "issues").strip().lower()
    if scope not in ("issues", "projects"):
        scope = "issues"
    if automated_tasks_paused() and not (force and manual):
        return jsonify({
            "ok": True,
            "skipped": True,
            "paused": True,
            "scope": scope,
            "new_count": 0,
            "removed_count": 0,
            "restored_count": 0,
            "updated_count": 0,
            "project_count": 0,
            "results": _empty_issue_results(),
            "logs": ["Automated ERP refresh paused (PAUSE_AUTOMATED_TASKS)."],
            "resolved_today": _resolved_stats(),
        })
    poll_at_key = "last_poll_at" if scope == "issues" else "last_projects_poll_at"
    if not force:
        with job["state_lock"]:
            if time.time() - float(job.get(poll_at_key) or 0.0) < ERP_POLL_THROTTLE_SECONDS:
                return jsonify({
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
                })
    if not job["poll_lock"].acquire(blocking=False):
        return jsonify({
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
        })

    original_stdout = sys.stdout
    captured_stdout = io.StringIO()
    new_records = []
    missing_ids = set()
    restored_ids = set()
    updated_records = []
    project_count = 0
    fetched_count = None
    try:
        with issues_validation_lock:
            sys.stdout = captured_stdout
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
                                old_type, old_subtype = classifications.get(
                                    issue_id, ("", "")
                                )
                                new_type, new_subtype = _issue_class_key(issue)
                                print(
                                    f"{issue_id} type/subtype "
                                    f"{old_type or '(none)'}/"
                                    f"{old_subtype or '(undiagnosed)'} -> "
                                    f"{new_type or '(none)'}/"
                                    f"{new_subtype or '(undiagnosed)'}"
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
                sys.stdout = original_stdout
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
        return jsonify(response)
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
        return jsonify({
            "ok": False,
            "scope": scope,
            "error": str(exc),
            "logs": captured_output.splitlines(),
        }), 502
    finally:
        job["poll_lock"].release()

@app.route("/issues/resolved", methods=["GET", "POST"])
def issues_resolved():
    if request.method == "GET":
        stats = _resolved_stats()
        stats["ok"] = True
        return jsonify(stats)

    payload = request.get_json(silent=True) or {}
    issue_id = str(payload.get("issue_id") or "").strip()
    if not issue_id:
        return jsonify({"ok": False, "error": "Missing issue_id"}), 400
    stats, added = _mark_issue_resolved(issue_id)
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
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 400
    return jsonify(result)

@app.route("/issues/camera-snapshot/<unit>/<target>", methods=["GET"])
def issues_camera_snapshot(unit, target):
    image, error = work_tool.camera_snapshot(unit, target)
    if error:
        return error, 502
    response = Response(image, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

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
            response.headers.add(key, value)
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
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 500
    return _bounce_output_response(result, "Bounce Switch", "relay")

@app.route("/issues/robofiber-uptime/<unit>", methods=["POST"])
def issues_robofiber_uptime(unit):
    result, error = work_tool.get_robofiber_uptime(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/robofiber-logs-link/<unit>", methods=["POST"])
def issues_robofiber_logs_link(unit):
    result, error = work_tool.get_robofiber_logs_link_events(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/robofiber-logs-month/<unit>", methods=["POST"])
def issues_robofiber_logs_month(unit):
    result, error = work_tool.get_robofiber_logs_last_month(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/bounce-speaker/<unit>", methods=["POST"])
def issues_bounce_speaker(unit):
    result, error = work_tool.bounce_speaker(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 500
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
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **info})

@app.route("/issues/ping-router-long/<unit>", methods=["POST"])
def issues_ping_router_long_start(unit):
    info, error = work_tool.start_router_long_ping(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **info})

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
        return jsonify({"ok": False, "error": message}), 404
    payload = {"ok": True, "message": message}
    if info:
        payload.update(info)
    return jsonify(payload)

@app.route("/issues/ping-camera/<unit>/<target>", methods=["POST"])
def issues_ping_camera(unit, target):
    camera_up, output, error = work_tool.ping_camera_status(unit, target)
    if error:
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 400
    result["ok"] = True
    return jsonify(result)

@app.route("/issues/ping-pve/<unit>", methods=["POST"])
def issues_ping_pve(unit):
    pve_up, output, error = work_tool.ping_pve_status(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 404
    return jsonify({
        "ok": True,
        "unit": unit,
        "pve_up": pve_up,
        "output": output,
    })

@app.route("/issues/set-fields/<preset_id>/<issue_id>", methods=["POST"])
def issues_set_fields(preset_id, issue_id):
    payload = request.get_json(silent=True) or {}
    unit = str(payload.get("unit") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    source_list_id = str(payload.get("source_list_id") or "").strip()
    result, error = work_tool.set_issue_preset_fields(
        preset_id, issue_id, unit, subject=subject
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
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
    if scheduled and automated_tasks_paused():
        print(
            "Scheduled Add Missing Components/Sites skipped — "
            "PAUSE_AUTOMATED_TASKS is enabled"
        )
        return {"checked": 0, "updated": [], "skipped": [], "errors": []}
    with job["state_lock"]:
        tickets = _listed_tickets_with_units(job["results"])
    original_stdout = sys.stdout
    sys.stdout = JobStdout(SHARED_ISSUES_JOB_ID, original_stdout)
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
        sys.stdout = original_stdout


@app.route("/issues/add-missing-components", methods=["POST"])
def issues_add_missing_components():
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        return jsonify({"ok": False, "error": "Shared report is not ready"}), 409
    if not job["poll_lock"].acquire(blocking=False):
        return jsonify({"ok": False, "error": "Another ERP update is already running"}), 409
    try:
        result = _run_add_missing_components(job, scheduled=False)
        result["ok"] = True
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
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
    original_stdout = sys.stdout
    try:
        sys.stdout = io.StringIO()
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
        sys.stdout = original_stdout

@app.route("/issues/sync-netsheet", methods=["POST"])
def issues_sync_netsheet():
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        return jsonify({"ok": False, "error": "Shared report is not ready"}), 409
    if not job["poll_lock"].acquire(blocking=False):
        return jsonify({"ok": False, "error": "Another ERP update is already running"}), 409
    try:
        result = _run_netsheet_sync(job, scheduled=False)
        result["ok"] = True
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    finally:
        job["poll_lock"].release()

@app.route("/issues/check-patch/<unit>", methods=["POST"])
def issues_check_patch(unit):
    info, error = work_tool.get_unit_patch_version(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **info})

@app.route("/issues/carrier/<unit>", methods=["POST"])
def issues_carrier(unit):
    info, error = work_tool.get_unit_carriers(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **info})

@app.route("/issues/reboot-scrypted/<unit>", methods=["POST"])
@app.route("/issues/reboot-snuc/<unit>", methods=["POST"])
def issues_reboot_scrypted(unit):
    ok, message = work_tool.reboot_scrypted(unit)
    if not ok:
        return jsonify({"ok": False, "error": message or "Reboot Scrypted failed"}), 400
    return jsonify({"ok": True, "unit": unit, "message": message or "Restarting"})

@app.route("/issues/reboot-pve/<unit>", methods=["POST"])
def issues_reboot_pve(unit):
    ok, message = work_tool.reboot_pve(unit)
    if not ok:
        return jsonify({"ok": False, "error": message or "Reboot PVE failed"}), 400
    return jsonify({"ok": True, "unit": unit, "message": message or "Restarting"})

@app.route("/issues/reboot-nuc/<unit>", methods=["POST"])
def issues_reboot_nuc(unit):
    ok, message = work_tool.reboot_nuc(unit)
    if not ok:
        return jsonify({"ok": False, "error": message or "Reboot NUC failed"}), 400
    return jsonify({"ok": True, "unit": unit, "message": message or "Restarting"})

@app.route("/issues/nuc-uptime/<unit>", methods=["POST"])
def issues_nuc_uptime(unit):
    ok, message, output = work_tool.nuc_uptime(unit)
    if not ok:
        return jsonify({"ok": False, "error": message or "NUC uptime failed"}), 400
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
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("project_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    created, error = work_tool.create_noc_deployment_project(
        project_id,
        prep_subject=subject or None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **created})

@app.route("/issues/create-termination-project", methods=["POST"])
def issues_create_termination_project():
    payload = request.get_json(silent=True) or {}
    issue_id = str(payload.get("issue_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    created, error = work_tool.create_noc_termination_project(
        issue_id,
        issue_subject=subject or None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **created})

@app.route("/issues/create-relocation-project", methods=["POST"])
def issues_create_relocation_project():
    payload = request.get_json(silent=True) or {}
    issue_id = str(payload.get("issue_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    created, error = work_tool.create_noc_relocation_project(
        issue_id,
        issue_subject=subject or None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **created})

@app.route("/issues/lookup-site", methods=["POST"])
def issues_lookup_site():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    if action not in ("terminate", "activate"):
        return jsonify({"ok": False, "error": "action must be terminate or activate"}), 400
    site, error = work_tool.lookup_erp_site_for_project_action(subject, action)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **site})

@app.route("/issues/terminate-site", methods=["POST"])
def issues_terminate_site():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    site_id = str(payload.get("site_id") or "").strip()
    result, error = work_tool.terminate_erp_site_from_project(
        subject,
        site_id=site_id or None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/activate-site", methods=["POST"])
def issues_activate_site():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    site_id = str(payload.get("site_id") or "").strip()
    result, error = work_tool.activate_erp_site_from_project(
        subject,
        site_id=site_id or None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/clear-mu-coordinates", methods=["POST"])
def issues_clear_mu_coordinates():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    mu = str(payload.get("mu") or "").strip()
    if mu:
        result, error = work_tool.clear_mu_coordinates(mu)
    else:
        result, error = work_tool.clear_mu_coordinates_from_subject(subject, unit=unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/clear-mu-site", methods=["POST"])
def issues_clear_mu_site():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    mu = str(payload.get("mu") or "").strip()
    if mu:
        result, error = work_tool.clear_mu_site(mu)
    else:
        result, error = work_tool.clear_mu_site_from_subject(subject, unit=unit)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/refurbish-projects/preview", methods=["POST"])
def issues_refurbish_projects_preview():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    preview, error = work_tool.preview_refurbish_projects_from_termination(
        subject,
        unit=unit or None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **preview})

@app.route("/issues/refurbish-projects", methods=["POST"])
def issues_refurbish_projects():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    created, error = work_tool.create_refurbish_projects_from_termination(
        subject,
        unit=unit or None,
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **created})

@app.route("/issues/tech-checks/preview", methods=["POST"])
def issues_tech_checks_preview():
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("project_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    if not project_id:
        return jsonify({"ok": False, "error": "Missing project id"}), 400
    if not work_tool._is_noc_deployment_project_subject(subject):
        return jsonify({
            "ok": False,
            "error": "Tech Checks is only available for NOC Deployment projects",
        }), 400
    preview, error = work_tool.preview_project_tech_checks(project_id, subject)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **preview})

@app.route("/issues/tech-checks", methods=["POST"])
def issues_tech_checks():
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("project_id") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    if not project_id:
        return jsonify({"ok": False, "error": "Missing project id"}), 400
    if not work_tool._is_noc_deployment_project_subject(subject):
        return jsonify({
            "ok": False,
            "error": "Tech Checks is only available for NOC Deployment projects",
        }), 400
    result, error = work_tool.complete_project_tech_checks(project_id, subject)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, **result})

@app.route("/issues/validate-unit/<unit>", methods=["POST"])
def issues_validate_unit(unit):
    category, output, error = work_tool.validate_unit_status(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 404
    return jsonify({"ok": True, **result})

@app.route("/issues/revalidate-list/<list_id>", methods=["POST"])
def issues_revalidate_list(list_id):
    if list_id not in ISSUE_RESULT_KEYS or list_id in (
        "discarded_tickets",
        "monitoring_hours",
        "termination",
        "relocation",
    ):
        return jsonify({"ok": False, "error": "This list cannot be revalidated"}), 400
    job = stream_jobs.get(SHARED_ISSUES_JOB_ID)
    if job is None or not job.get("done") or job.get("results") is None:
        return jsonify({"ok": False, "error": "Shared report is not ready"}), 409
    if not job["poll_lock"].acquire(blocking=False):
        return jsonify({"ok": False, "error": "Another refresh is already running"}), 409

    original_stdout = sys.stdout
    captured_stdout = io.StringIO()
    moves = []
    checked = 0
    moved = 0
    try:
        with issues_validation_lock:
            sys.stdout = captured_stdout
            try:
                work_tool.generate_net_array()
                with job["state_lock"]:
                    snapshot = [
                        {
                            "issue_id": item.get("issue_id") or "",
                            "unit": item.get("unit") or "",
                            "camera_target": item.get("camera_target") or "",
                        }
                        for item in (job["results"].get(list_id) or [])
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
                    if destination not in ISSUE_RESULT_KEYS or destination in (
                        "discarded_tickets",
                        "monitoring_hours",
                        "termination",
                        "relocation",
                    ):
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
                sys.stdout = original_stdout
        captured_output = captured_stdout.getvalue()
        if captured_output:
            JobStdout(SHARED_ISSUES_JOB_ID, None).write(
                captured_output + ("" if captured_output.endswith("\n") else "\n")
            )
        return jsonify({
            "ok": True,
            "list_id": list_id,
            "checked": checked,
            "moved": moved,
            "moves": moves,
            "logs": captured_output.splitlines(),
        })
    except Exception as exc:
        captured_output = captured_stdout.getvalue()
        if captured_output:
            JobStdout(SHARED_ISSUES_JOB_ID, None).write(
                captured_output + ("" if captured_output.endswith("\n") else "\n")
            )
        return jsonify({
            "ok": False,
            "error": str(exc),
            "logs": captured_output.splitlines(),
        }), 500
    finally:
        job["poll_lock"].release()

@app.route("/issues/validate-stale-vpn/<unit>", methods=["POST"])
def issues_validate_stale_vpn(unit):
    result, error = work_tool.validate_stale_vpn_status(unit)
    if error:
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 404
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
        return jsonify({"ok": False, "error": error}), 400
    return jsonify(payload)

def _issues_site_id_from_request(unit):
    subject = str(request.args.get("subject") or "").strip()
    site_id, error = work_tool.resolve_dashboard_site_id(unit, subject)
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
    return render_template("recovery_email.html")

@app.route("/recovery_email/results", methods=["POST"])
def recovery_email_results():
    report = request.files.get("report_file")
    if not report:
        return "Missing report file", 400
    job_id = uuid.uuid4().hex
    report_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{report.filename}")
    report.save(report_path)
    report.close()
    stream_jobs[job_id] = {
        "queue": queue.Queue(),
        "done": False,
        "results": None,
    }
    thread = threading.Thread(target=_run_recovery_email_check, args=(job_id, report_path), daemon=True)
    thread.start()
    return redirect(url_for("recovery_email_watch", job_id=job_id))

@app.route("/recovery_email/watch/<job_id>", methods=["GET"])
def recovery_email_watch(job_id):
    if job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template("recovery_email_results.html", job_id=job_id)

@app.route("/recovery_email/stream/<job_id>", methods=["GET"])
def recovery_email_stream(job_id):
    return _sse_stream(job_id)

def _run_linux_diagnostic(job_id, unit):
    import sys
    job = stream_jobs[job_id]
    original_stdout = sys.stdout
    sys.stdout = JobStdout(job_id, original_stdout)
    try:
        work_tool.generate_false_mu()
        work_tool.generate_net_array()
        result = work_tool.run_linux_diagnostic(unit)
        job["results"] = result
        job["queue"].put({"type": "done", "results": result})
    except Exception as e:
        job["queue"].put({"type": "log", "line": f"ERROR: {e}"})
        job["queue"].put({"type": "done", "results": {
            "unit": unit or "",
            "hostname": "",
            "connected": False,
            "output": "",
            "error": str(e),
        }})
    finally:
        sys.stdout = original_stdout
        job["done"] = True

@app.route("/zabbix", methods=["GET"])
def zabbix_form():
    return render_template("zabbix.html")
@app.route("/linux", methods=["GET"])
def linux_form():
    return render_template("linux.html")
@app.route("/linux/results", methods=["POST"])
def linux_results():
    unit = (request.form.get("unit") or "").strip()
    if not unit:
        return "No unit provided", 400
    for row in work_tool.net_array:
        if row[0] == unit:
            hostname = row[12]
            port = 22
            user = os.getenv("scryptuserssh")
            password = os.getenv("scryptpass")
            sshclient = paramiko.SSHClient
            sshclient.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            sshclient.connect(hostname, port, user, password)
            stdin, stdout, stderr = sshclient.exec_command("")

@app.route("/linux/watch/<job_id>", methods=["GET"])
def linux_watch(job_id):
    if job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template("linux_results.html", job_id=job_id)

@app.route("/linux/stream/<job_id>", methods=["GET"])
def linux_stream(job_id):
    return _sse_stream(job_id)
@app.route("/victron/results", methods=["POST"])
def install_checker():
    idUser = (os.getenv("idUser") or "").strip()
    api_token = (os.getenv("victron_token") or "").strip()
    if not idUser or not api_token:
        return (
            "VRM credentials missing: set idUser and victron_token in work_tool/.env",
            500,
        )
    url = f"https://vrmapi.victronenergy.com/v2/users/{idUser}/installations"
    headers = {
        "idUser": f"{idUser}",
        "X-Authorization": f"Token {api_token}"
    }
    unit = request.form.get("unit")
    if not unit:
        return "No unit provided"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return f"VRM request failed: {response.status_code}" 
    data = response.json()
    battery_instance = None
    solar_instance = None
    voltage = None
    current = None
    amps = None
    temp = None
    ftemp = None
    high_volt_alarm = None
    low_volt_alarm = None
    today_yield = None
    yesterday_yield = None
    soc=None

    for record in data.get("records", []):
        if (record.get("name") or "")[-4:] == unit[-4:]:
            print('Unit is added to VRM')
            print(f"Site ID for {unit} is {record.get('idSite')}")
            siteId = record.get('idSite')
            url2 = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/system-overview"
            response2 = requests.get(url2, headers=headers)
            data2 = response2.json()
            for device in data2.get("records", {}).get("devices", []):
                if device["name"] == "Gateway":
                    lastseen = device.get("lastConnection")
                    if isinstance(lastseen, (int, float)):
                        lastseen = datetime.fromtimestamp(lastseen).strftime("%H:%M:%S on %m/%d/%Y") 

                elif "battery" in device.get("name").lower():
                    battery_instance = device.get("instance")
                    print("battery instance: " + str(battery_instance))
                elif "solar charger" in device.get("name").lower():
                    solar_instance = device.get("instance")
                    print("solar instance: " + str(solar_instance))

            if battery_instance is not None:
                url_battery = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/widgets/BatterySummary?instance={battery_instance}"
                battery_response = requests.get(url_battery, headers=headers)
                battery_data = battery_response.json()
                print("--- BATTERY DATA (SOC, Voltage, etc.) ---")
                # print(json.dumps(battery_data, indent=2))
                for instance in battery_data.get("records", {}).get("data", {}).values():
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Voltage":
                        voltage = instance["valueFormattedWithUnit"]
                            
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Current":
                        print('hit')
                        current = instance["valueFormattedWithUnit"]
                        print(f'amps: {current}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Temperature":
                        print('hit')
                        temp = float(instance["valueFormattedValueOnly"])
                        ftemp = temp * 1.8 + 32
                        ftemp = round(ftemp, 2)
                        ftemp = str(ftemp) + " \u00b0F"
                        print(f'temp: {ftemp}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Alarms/LowVoltage":
                        print('hit')
                        low_volt_alarm = instance["valueFormattedWithUnit"]
                        print(f'Low voltage alarm status: {low_volt_alarm}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Alarms/HighVoltage":
                        print('hit')
                        high_volt_alarm = instance["valueFormattedWithUnit"]
                        print(f'High voltage alarm status: {high_volt_alarm}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Soc":
                        print('hit')
                        soc = instance["valueFormattedWithUnit"]
                        print(f'State of Charge: {soc}')

            if solar_instance is not None:
                url_solar = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/widgets/SolarChargerSummary?instance={solar_instance}"
                solar_response = requests.get(url_solar, headers=headers)
                solar_data = solar_response.json()
                #print(json.dumps(solar_data, indent=2))
                for instance in solar_data.get("records", {}).get("data", {}).values():
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/History/Daily/0/Yield":
                        today_yield = instance.get("valueFormattedWithUnit")
                        print(today_yield)

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/History/Daily/1/Yield":
                        yesterday_yield = instance.get("valueFormattedWithUnit")
                        print('hit yesterday')
                        print(yesterday_yield)

                    if isinstance(instance, dict) and instance.get("dataAttributeName") == "Battery watts":
                        print('hit watts')
                        watts = instance.get("valueFormattedWithUnit")
                        print(watts)

                return render_template("result.html",
                unit=unit,
                siteId=siteId,
                lastseen=lastseen,
                soc=soc,
                watts=watts,
                voltage=voltage,
                current=current,
                ftemp=ftemp,
                high_volt_alarm=high_volt_alarm,
                low_volt_alarm=low_volt_alarm,
                today_yield=today_yield,
                yesterday_yield=yesterday_yield
                )

            else:
                print("No Solar Charger instance found in system overview.")

            return "Gateway not found"                
    return "Unit not found in VRM"
@app.route("/outage_filter/results", methods=["POST"])
def outage_filter():
    work_tool.generate_false_mu()
    work_tool.generate_net_array()
    print("Generated")
    mesh_outage = request.files.get("mesh_file")
    issues = request.files.get("issue_file")

    if not mesh_outage or not issues:
        return "Missing Files", 400
    mesh_path = os.path.join(UPLOAD_FOLDER, mesh_outage.filename)
    issue_path = os.path.join(UPLOAD_FOLDER, issues.filename)
    downloads = os.path.join(work_tool.pc_user_home(), "Downloads")
    local_mesh = os.path.join(downloads, "filtered_mesh_vpn.csv")
    local_issue = os.path.join(downloads, "Issue.csv")
    mesh_outage.save(mesh_path)
    issues.save(issue_path)
    mesh_outage.close()
    issues.close()
    work_tool.compare_reports(issue_path, mesh_path)
    work_tool.clear_old_reports(mesh_path, issue_path)

    missing2, nuc_down, stale_vpn, scrypted_outage = work_tool.validate_reports_mesh()
    try:
        os.remove(local_issue)
        os.remove(local_mesh)
        print("removed local files")
    except Exception as e:
        print(f"{e}: Failed, continuing with validation")
    return jsonify({
    "message": "Filtered outage report",
    "missing": missing2,
    "nuc_down": nuc_down,
    "stale_vpn": stale_vpn,
    "scrypted_outage": scrypted_outage,
}), 200

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
        if automated_tasks_paused():
            print(
                "PAUSE_AUTOMATED_TASKS is enabled — daily 4:00/4:05/4:10 AM "
                "jobs and automatic ERP polling are paused until cleared"
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

if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or __name__ != "__main__":
    if WORK_TOOL_ENV != "sandbox":
        _start_arizona_validation_scheduler()

if __name__ == "__main__":
    debug = WORK_TOOL_ENV == "sandbox"
    if not debug and WORK_TOOL_ENV != "sandbox":
        _start_arizona_validation_scheduler()
    print(
        f"Starting work_tool ({WORK_TOOL_ENV}) on "
        f"http://127.0.0.1:{WORK_TOOL_PORT} (data: {DATA_DIR})"
    )
    app.run(host="0.0.0.0", port=WORK_TOOL_PORT, debug=debug, threaded=True)