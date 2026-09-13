"""
Scheduled "photograph the panels while they're actually shaded" tasks,
backed by SQLite — storage layer only, mirroring alarm_history.py's and
unit_history.py's shared-connection-under-a-lock pattern. The scheduler
loop and camera/VRM calls live in flask_endpoints.py and work_tool.weather
(verify_shading_dip_now); this module just tracks task state and holds the
captured images on disk.

Why "the following day," not "right now": detect_solar_shading only tells
us the hour a dip WAS at recently — VRM's hourly data means the exact
minute is fuzzy, and a snapshot fired blindly at that minute could just as
easily catch a clear sky (the shade moved, that day happens to be
overcast, or it's simply not there anymore). So a task never captures on
the same pass it was created: it always aims at the NEXT day's occurrence
of the peak hour, and even then only fires if
work_tool.weather.verify_shading_dip_now reconfirms the dip is actually
happening right then. If it isn't, the attempt is spent without a photo
and the task tries again the following day, for up to `attempts_total`
tries before giving up.

One row per snapshot TASK (not per attempt) — attempts_used/next_attempt_at
just advance in place, matching alarm_history's "diff and update," not
"log every poll" philosophy for the same reason: this fleet is small
enough, and a snapshot task short-lived enough (a few days, a few
attempts), that there is nothing to gain from a separate attempts table.
"""

from __future__ import annotations

import calendar
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta

_DB_LOCK = threading.Lock()
_CONN = None
_DB_PATH = None

# How many attempts (each on a subsequent day) a task gets before giving
# up without ever confirming the dip / getting a usable photo.
DEFAULT_ATTEMPTS_TOTAL = 3

# How long a finished (or abandoned) task's row AND its image file stick
# around before cleanup — this is a storage-constrained work PC (see
# unit_history.py's own MAX_EVENTS comment), and a week is plenty of time
# for someone to have actually looked at the photo.
DEFAULT_RETENTION_DAYS = 7


def _data_dir():
    override = str(os.getenv("WORK_TOOL_DATA_DIR") or "").strip()
    if override:
        if not os.path.isabs(override):
            override = os.path.join(os.path.dirname(os.path.abspath(__file__)), override)
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "live")


def db_path():
    global _DB_PATH
    if _DB_PATH is None:
        directory = _data_dir()
        os.makedirs(directory, exist_ok=True)
        _DB_PATH = os.path.join(directory, "shading_snapshots.db")
    return _DB_PATH


def _images_dir():
    directory = os.path.join(_data_dir(), "shading_snapshot_images")
    os.makedirs(directory, exist_ok=True)
    return directory


def _connect():
    """Open (once) and return the shared connection. Caller holds _DB_LOCK."""
    global _CONN
    if _CONN is not None:
        return _CONN
    conn = sqlite3.connect(db_path(), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS snapshot_tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            unit            TEXT    NOT NULL,
            subject         TEXT    NOT NULL DEFAULT '',
            camera_target   TEXT    NOT NULL DEFAULT 'fisheye',
            peak_hour_utc   INTEGER NOT NULL,
            attempts_total  INTEGER NOT NULL,
            attempts_used   INTEGER NOT NULL DEFAULT 0,
            next_attempt_at REAL,
            status          TEXT    NOT NULL DEFAULT 'pending',
            image_filename  TEXT,
            captured_at     REAL,
            last_note       TEXT,
            created_at      REAL    NOT NULL,
            updated_at      REAL    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_snapshot_tasks_unit
            ON snapshot_tasks (unit, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshot_tasks_due
            ON snapshot_tasks (status, next_attempt_at);
        """
    )
    conn.commit()
    _CONN = conn
    return _CONN


def next_occurrence_following_day(hour_utc, now=None, days_ahead=1):
    """
    Epoch seconds for hour_utc:00 UTC, `days_ahead` calendar days after
    `now` (default 1 — "the following day"). A pure date computation, so
    it's tested without a live clock dependency beyond the `now` param.

    Deliberately calendar.timegm, not datetime.timestamp(): the latter
    treats a naive datetime as LOCAL time, and this box's local clock is
    US Mountain (confirmed elsewhere this session), not UTC — using
    .timestamp() here would silently shift every scheduled time by the
    local UTC offset.
    """
    now = now if now is not None else time.time()
    now_date = datetime.utcfromtimestamp(now).date() + timedelta(days=int(days_ahead))
    candidate = datetime(now_date.year, now_date.month, now_date.day, int(hour_utc) % 24, 0, 0)
    return float(calendar.timegm(candidate.timetuple()))


def schedule_task(unit, subject, camera_target, peak_hour_utc, attempts_total=DEFAULT_ATTEMPTS_TOTAL, now=None):
    """
    Create a snapshot task for `unit`, aimed at the next day's occurrence
    of peak_hour_utc. If a pending task already exists for this exact
    (unit, camera_target), returns that one instead of creating a
    duplicate — chiefly for the bulk "schedule for every shaded unit"
    action, so re-running it doesn't pile up repeats for units still
    waiting on an earlier task.

    Returns (task_id, created, next_attempt_at) or (None, False, None) on
    a storage error — never raises into the caller.
    """
    unit = str(unit or "").strip().upper()
    if not unit:
        return None, False, None
    now = now if now is not None else time.time()
    try:
        with _DB_LOCK:
            conn = _connect()
            existing = conn.execute(
                "SELECT id, next_attempt_at FROM snapshot_tasks"
                " WHERE unit = ? AND camera_target = ? AND status = 'pending'"
                " ORDER BY created_at DESC LIMIT 1",
                (unit, camera_target),
            ).fetchone()
            if existing:
                return existing["id"], False, existing["next_attempt_at"]

            next_attempt_at = next_occurrence_following_day(peak_hour_utc, now=now, days_ahead=1)
            cursor = conn.execute(
                "INSERT INTO snapshot_tasks"
                " (unit, subject, camera_target, peak_hour_utc, attempts_total, attempts_used,"
                "  next_attempt_at, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, 0, ?, 'pending', ?, ?)",
                (unit, str(subject or ""), camera_target, int(peak_hour_utc), int(attempts_total),
                 next_attempt_at, now, now),
            )
            conn.commit()
            return cursor.lastrowid, True, next_attempt_at
    except Exception as exc:
        print(f"[shading_snapshots] could not schedule task for {unit}: {exc}")
        return None, False, None


def due_tasks(now=None, limit=100):
    """Pending tasks whose next_attempt_at has arrived. Never raises."""
    now = now if now is not None else time.time()
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT * FROM snapshot_tasks WHERE status = 'pending' AND next_attempt_at <= ?"
                " ORDER BY next_attempt_at ASC LIMIT ?",
                (now, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        print(f"[shading_snapshots] could not read due tasks: {exc}")
        return []


def record_attempt_failure(task_id, note, now=None):
    """
    One attempt spent without a photo — the dip wasn't confirmed, the
    camera fetch failed, or VRM/ERP couldn't be reached this pass. Either
    reschedules for the following day (attempts remain) or marks the task
    exhausted. Never raises.
    """
    now = now if now is not None else time.time()
    try:
        with _DB_LOCK:
            conn = _connect()
            row = conn.execute(
                "SELECT attempts_total, attempts_used, peak_hour_utc FROM snapshot_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if not row:
                return False
            attempts_used = row["attempts_used"] + 1
            if attempts_used >= row["attempts_total"]:
                conn.execute(
                    "UPDATE snapshot_tasks SET attempts_used = ?, status = 'exhausted',"
                    " last_note = ?, updated_at = ? WHERE id = ?",
                    (attempts_used, note, now, task_id),
                )
            else:
                next_attempt_at = next_occurrence_following_day(
                    row["peak_hour_utc"], now=now, days_ahead=1
                )
                conn.execute(
                    "UPDATE snapshot_tasks SET attempts_used = ?, next_attempt_at = ?,"
                    " last_note = ?, updated_at = ? WHERE id = ?",
                    (attempts_used, next_attempt_at, note, now, task_id),
                )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[shading_snapshots] could not record attempt failure for task {task_id}: {exc}")
        return False


def record_captured(task_id, image_bytes, note, now=None):
    """Save the image to disk and mark the task captured. Never raises."""
    now = now if now is not None else time.time()
    filename = f"{int(task_id)}.jpg"
    try:
        with open(os.path.join(_images_dir(), filename), "wb") as fh:
            fh.write(image_bytes)
    except OSError as exc:
        return record_attempt_failure(task_id, f"Captured but could not save to disk: {exc}", now=now)
    try:
        with _DB_LOCK:
            conn = _connect()
            conn.execute(
                "UPDATE snapshot_tasks SET attempts_used = attempts_used + 1, status = 'captured',"
                " image_filename = ?, captured_at = ?, last_note = ?, updated_at = ? WHERE id = ?",
                (filename, now, note, now, task_id),
            )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[shading_snapshots] could not record capture for task {task_id}: {exc}")
        return False


def get_task(task_id):
    try:
        with _DB_LOCK:
            conn = _connect()
            row = conn.execute("SELECT * FROM snapshot_tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        print(f"[shading_snapshots] could not read task {task_id}: {exc}")
        return None


def image_path_for(task_id):
    """Absolute path to a captured task's image, or None if it has none."""
    task = get_task(task_id)
    if not task or not task.get("image_filename"):
        return None
    path = os.path.join(_images_dir(), task["image_filename"])
    return path if os.path.isfile(path) else None


def latest_tasks_by_unit(units=None):
    """
    The single most recent task per unit — for the diagnostics panel and
    the Shaded Units report to show "pending / captured / exhausted" plus
    a thumbnail link without listing every historical attempt. `units`
    narrows to a specific set of unit keys (already-uppercased); omit for
    every unit that has ever had a task.
    """
    try:
        with _DB_LOCK:
            conn = _connect()
            if units:
                placeholders = ",".join("?" for _ in units)
                rows = conn.execute(
                    f"SELECT * FROM snapshot_tasks WHERE unit IN ({placeholders})"
                    " ORDER BY created_at DESC",
                    tuple(u.strip().upper() for u in units),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM snapshot_tasks ORDER BY created_at DESC"
                ).fetchall()
        latest = {}
        for row in rows:
            latest.setdefault(row["unit"], dict(row))
        return latest
    except Exception as exc:
        print(f"[shading_snapshots] could not read latest tasks: {exc}")
        return {}


def cancel_task(task_id):
    try:
        with _DB_LOCK:
            conn = _connect()
            conn.execute(
                "UPDATE snapshot_tasks SET status = 'cancelled', updated_at = ? WHERE id = ? AND status = 'pending'",
                (time.time(), task_id),
            )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[shading_snapshots] could not cancel task {task_id}: {exc}")
        return False


def _vacuum(conn):
    """Same VACUUM dance as unit_history._vacuum — see its docstring."""
    previous = conn.isolation_level
    try:
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.isolation_level = previous


def prune_old(retention_days=DEFAULT_RETENTION_DAYS, now=None):
    """
    Delete any task (finished or not) older than retention_days, along
    with its image file on disk — a stray pending task that old is
    orphaned anyway (attempts_total * ~1 day always finishes it in under a
    week at the default settings). Returns the number of tasks deleted.
    Never raises.
    """
    now = now if now is not None else time.time()
    cutoff = now - max(0, float(retention_days)) * 86400
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT id, image_filename FROM snapshot_tasks WHERE created_at < ?", (cutoff,)
            ).fetchall()
            if not rows:
                return 0
            images_dir = _images_dir()
            for row in rows:
                if row["image_filename"]:
                    try:
                        os.remove(os.path.join(images_dir, row["image_filename"]))
                    except OSError:
                        pass  # already gone, or never wrote — not fatal to the DB cleanup
            ids = [row["id"] for row in rows]
            conn.execute(
                f"DELETE FROM snapshot_tasks WHERE id IN ({','.join('?' for _ in ids)})", ids
            )
            conn.commit()
            _vacuum(conn)
        print(f"[shading_snapshots] pruned {len(rows)} task(s) older than {retention_days}d")
        return len(rows)
    except Exception as exc:
        print(f"[shading_snapshots] prune failed: {exc}")
        return 0
