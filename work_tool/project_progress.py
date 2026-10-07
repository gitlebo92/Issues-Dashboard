"""
Project Progress check: is a NOC project finished on NOC's side, moving,
or forgotten?

Pure functions only — no ERP calls. validate_project_records (in _core)
attaches the result to every Projects list entry it already builds, so this
costs nothing beyond the 30-minute ERP pull the dashboard already does.

Re-exported by work_tool/__init__.py like every other submodule.
"""

from datetime import datetime, timedelta, timezone


# Thresholds are the same for every NOC project for now (Andrew,
# 2026-10-07): they come from Camera Adjustment projects, where 83.3%
# (5 of 6 tasks) means NOC's own tasks are done. Kept as named constants so
# per-project-type percentages can be added later without touching the
# logic below.
NOC_DONE_PERCENT = 83.3
STALLED_MIN_PERCENT = 10.0   # above this, work has started
STALLED_MAX_PERCENT = 82.0   # below this, NOC still has tasks open
NEEDS_ATTENTION_AFTER = timedelta(days=2)

PROGRESS_DONE = "noc_done"
PROGRESS_STALLED = "stalled"
PROGRESS_NOT_STARTED = "not_started"
PROGRESS_IN_PROGRESS = "in_progress"
NEEDS_ATTENTION_STATUSES = (PROGRESS_STALLED, PROGRESS_NOT_STARTED)


def _us_dst_bounds_utc(year, standard_offset_hours):
    """
    US daylight saving for one year, as UTC instants: 2 AM local on the
    second Sunday of March (standard time) to 2 AM local on the first Sunday
    of November (daylight time).
    """
    march_first = datetime(year, 3, 1)
    second_sunday = march_first + timedelta(days=(6 - march_first.weekday()) % 7 + 7)
    nov_first = datetime(year, 11, 1)
    first_sunday = nov_first + timedelta(days=(6 - nov_first.weekday()) % 7)
    start = second_sunday.replace(hour=2) - timedelta(hours=standard_offset_hours)
    end = first_sunday.replace(hour=2) - timedelta(hours=standard_offset_hours + 1)
    return start, end


def erp_time_to_utc(value):
    """
    ERP (Frappe) stores datetimes as naive strings in its System Settings
    time zone, which is America/Boise — checked live, 2026-10-07. Boise is
    US Mountain time: UTC-7, UTC-6 under daylight saving.

    Done by hand rather than with zoneinfo: zoneinfo needs the tzdata
    package on Windows, and the live service runs as SYSTEM, so adding it
    means an admin system-wide install (see the run-work-tool skill). The
    US rule has been fixed since 2007.

    Returns an aware UTC datetime, or None for a blank/unparseable value.
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        local = datetime.fromisoformat(text[:26])
    except ValueError:
        return None
    if local.tzinfo is not None:
        return local.astimezone(timezone.utc)
    standard_offset = -7
    naive_utc = local - timedelta(hours=standard_offset)
    dst_start, dst_end = _us_dst_bounds_utc(local.year, standard_offset)
    if dst_start <= naive_utc < dst_end:
        naive_utc -= timedelta(hours=1)
    return naive_utc.replace(tzinfo=timezone.utc)


def project_progress_status(percent_complete, modified, now=None):
    """
    Classify one NOC project. `modified` is ERP's raw modified string;
    `now` (aware, defaults to the current time) is injectable for tests.

    Returns {"status", "idle_days", "needs_attention"}:
      - noc_done:    >= 83.3% — NOC's tasks are finished.
      - stalled:     > 10% and < 82%, unchanged in ERP for over 2 days.
      - not_started: <= 10%, unchanged in ERP for over 2 days.
      - in_progress: anything else (still moving, or under 2 days, or the
        82-83.3% gap no real task count lands in).
    idle_days is whole days since the last ERP change, or None if ERP gave
    no usable modified time — in which case nothing is flagged, rather than
    guessing that a project is forgotten.
    """
    try:
        percent = float(percent_complete) if percent_complete not in (None, "") else 0.0
    except (TypeError, ValueError):
        percent = 0.0
    now = now or datetime.now(timezone.utc)
    modified_utc = erp_time_to_utc(modified)
    idle = (now - modified_utc) if modified_utc else None
    idle_days = max(0, int(idle.total_seconds() // 86400)) if idle is not None else None
    stale = idle is not None and idle > NEEDS_ATTENTION_AFTER

    if percent >= NOC_DONE_PERCENT:
        status = PROGRESS_DONE
    elif stale and STALLED_MIN_PERCENT < percent < STALLED_MAX_PERCENT:
        status = PROGRESS_STALLED
    elif stale and percent <= STALLED_MIN_PERCENT:
        status = PROGRESS_NOT_STARTED
    else:
        status = PROGRESS_IN_PROGRESS
    return {
        "status": status,
        "idle_days": idle_days,
        "needs_attention": status in NEEDS_ATTENTION_STATUSES,
    }
