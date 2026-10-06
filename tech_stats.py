"""
Per-tech ticket-handling stats, backed by SQLite.

Tracks the three ticket dispositions the dashboard already exposes —
Resolved (the Resolve Selected flow), Worked, and Skipped (the two R/W/S
checkboxes) — against a tech identity. There is no login system, so "tech"
is a free-text name the tech types into the dashboard once (stored in their
browser, sent with each request); this is self-reported, not authenticated.
The request's IP address is stored alongside each event purely as a
debugging breadcrumb (e.g. spotting two techs who both saved themselves as
"Alex"), never as the primary identity — IP addresses churn (DHCP, VPN,
roaming laptops) in a way a typed name doesn't.

One row per (tech, issue_id, kind): marking a ticket worked/skipped/
resolved upserts that row (bumps its timestamp, replaces its unit/ip),
and un-checking worked/skipped deletes it. This keeps counts accurate
under repeated toggling — clicking a checkbox on/off several times counts
as at most one event, not one per click.

Same file-layout/threading/WAL conventions as unit_history.py and
alarm_history.py — see unit_history.py's module docstring for the reasoning
(live service restarts often, so nothing here lives in memory; WAL so a
long read doesn't block a write).
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta

_DB_LOCK = threading.Lock()
_CONN = None
_DB_PATH = None

KINDS = ("resolved", "worked", "skipped")


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
        _DB_PATH = os.path.join(directory, "tech_stats.db")
    return _DB_PATH


def _connect():
    """Open (once) and return the shared connection. Caller holds _DB_LOCK."""
    global _CONN
    if _CONN is not None:
        return _CONN
    conn = sqlite3.connect(db_path(), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA wal_autocheckpoint=256")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tech_ticket_events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            tech      TEXT    NOT NULL,
            issue_id  TEXT    NOT NULL,
            kind      TEXT    NOT NULL,
            unit      TEXT,
            ip        TEXT,
            ts        REAL    NOT NULL,
            UNIQUE(tech, issue_id, kind)
        );
        CREATE INDEX IF NOT EXISTS idx_tech_ticket_events_tech_ts
            ON tech_ticket_events (tech, ts DESC);
        CREATE INDEX IF NOT EXISTS idx_tech_ticket_events_ts
            ON tech_ticket_events (ts DESC);
        """
    )
    conn.commit()
    _CONN = conn
    return _CONN


def record(tech, issue_id, kind, unit=None, ip=None):
    """
    Upsert one (tech, issue_id, kind) event — a tech marking a ticket
    resolved/worked/skipped. Re-recording the same triple just bumps its
    timestamp (and refreshes unit/ip) rather than creating a duplicate, so
    toggling a checkbox off and back on never inflates the count.

    Never raises: stats are a nice-to-have and a locked/corrupt database
    must not break the ticket action itself. Returns True when written.
    """
    tech = str(tech or "").strip()
    issue_id = str(issue_id or "").strip()
    kind = str(kind or "").strip().lower()
    if not tech or not issue_id or kind not in KINDS:
        return False
    try:
        with _DB_LOCK:
            conn = _connect()
            conn.execute(
                "INSERT INTO tech_ticket_events (tech, issue_id, kind, unit, ip, ts)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(tech, issue_id, kind) DO UPDATE SET"
                " ts=excluded.ts, unit=excluded.unit, ip=excluded.ip",
                (
                    tech, issue_id, kind,
                    str(unit).strip() if unit else None,
                    str(ip).strip() if ip else None,
                    time.time(),
                ),
            )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[tech_stats] could not record {tech}/{issue_id}/{kind}: {exc}")
        return False


def clear(tech, issue_id, kind):
    """Remove a (tech, issue_id, kind) event — a tech un-checking worked/skipped."""
    tech = str(tech or "").strip()
    issue_id = str(issue_id or "").strip()
    kind = str(kind or "").strip().lower()
    if not tech or not issue_id or kind not in KINDS:
        return False
    try:
        with _DB_LOCK:
            conn = _connect()
            conn.execute(
                "DELETE FROM tech_ticket_events WHERE tech = ? AND issue_id = ? AND kind = ?",
                (tech, issue_id, kind),
            )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[tech_stats] could not clear {tech}/{issue_id}/{kind}: {exc}")
        return False


# Rolling windows, not calendar-aligned — same "days back from now" shape as
# unit_history's own `days` parameter, simpler to reason about than a
# Mon-Sun/calendar-month boundary and consistent with the rest of the app.
_WINDOWS = (("week", 7), ("month", 30), ("year", 365))


def _empty_counts():
    return {"resolved": 0, "worked": 0, "skipped": 0, "total": 0}


def summary(tech):
    """
    Ticket counts for `tech`, broken down by kind, over week/month/year
    rolling windows plus all-time. Returns a dict even for an unknown or
    blank tech (all zeros) rather than None, so the frontend never needs a
    null-check before rendering it.
    """
    tech = str(tech or "").strip()
    result = {
        "tech": tech,
        "week": _empty_counts(),
        "month": _empty_counts(),
        "year": _empty_counts(),
        "all_time": _empty_counts(),
        "last_event": None,
    }
    if not tech:
        return result
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT kind, ts FROM tech_ticket_events WHERE tech = ?", (tech,)
            ).fetchall()
    except Exception as exc:
        print(f"[tech_stats] could not summarise {tech}: {exc}")
        return result

    now = time.time()
    cutoffs = {name: now - days * 86400 for name, days in _WINDOWS}
    last_ts = None
    for row in rows:
        kind = row["kind"]
        ts = row["ts"]
        if kind not in KINDS:
            continue
        if last_ts is None or ts > last_ts:
            last_ts = ts
        result["all_time"][kind] += 1
        result["all_time"]["total"] += 1
        for name, cutoff in cutoffs.items():
            if ts >= cutoff:
                result[name][kind] += 1
                result[name]["total"] += 1
    result["last_event"] = (
        datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S") if last_ts else None
    )
    return result


def known_techs():
    """Every tech name seen, most active first — for a "whose stats?" picker."""
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT tech, COUNT(*) AS n, MAX(ts) AS last_ts"
                " FROM tech_ticket_events GROUP BY tech ORDER BY n DESC"
            ).fetchall()
    except Exception as exc:
        print(f"[tech_stats] could not list techs: {exc}")
        return []
    return [
        {
            "tech": row["tech"],
            "count": row["n"],
            "last_event": datetime.fromtimestamp(row["last_ts"]).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for row in rows
    ]


# Generous ceiling/window — a tech triaging dozens of tickets a day is still
# only a few thousand rows a year, nowhere near unit_history's per-poll
# volume, so there is room to keep years of history without the file
# becoming a storage concern on this storage-tight workstation.
MAX_EVENTS = 500_000
VACUUM_AFTER_DELETED = 1000


def _vacuum(conn):
    """See unit_history._vacuum's identical comment — VACUUM cannot run inside
    a transaction, and sqlite3 opens one implicitly, so drop to autocommit first."""
    previous = conn.isolation_level
    try:
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.isolation_level = previous


def prune(keep_days=730, max_events=MAX_EVENTS):
    """Drop events older than keep_days, enforce the row ceiling, reclaim space."""
    try:
        with _DB_LOCK:
            conn = _connect()
            cutoff = (datetime.now() - timedelta(days=max(0, float(keep_days)))).timestamp()
            deleted = conn.execute(
                "DELETE FROM tech_ticket_events WHERE ts < ?", (cutoff,)
            ).rowcount or 0

            if max_events:
                remaining = conn.execute("SELECT COUNT(*) FROM tech_ticket_events").fetchone()[0]
                excess = remaining - int(max_events)
                if excess > 0:
                    deleted += conn.execute(
                        "DELETE FROM tech_ticket_events WHERE id IN ("
                        " SELECT id FROM tech_ticket_events ORDER BY ts ASC LIMIT ?)",
                        (excess,),
                    ).rowcount or 0
            conn.commit()

            if deleted >= VACUUM_AFTER_DELETED:
                _vacuum(conn)
        if deleted:
            print(f"[tech_stats] pruned {deleted} event(s); database now {file_size_mb():.1f} MB")
        return deleted
    except Exception as exc:
        print(f"[tech_stats] prune failed: {exc}")
        return 0


def compact():
    """Reclaim disk unconditionally. For the maintenance route / manual use."""
    try:
        before = file_size_bytes()
        with _DB_LOCK:
            _vacuum(_connect())
        after = file_size_bytes()
        return {"ok": True, "before_bytes": before, "after_bytes": after,
                "freed_bytes": max(0, before - after)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def file_size_bytes():
    total = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            total += os.path.getsize(db_path() + suffix)
        except OSError:
            pass
    return total


def file_size_mb():
    return file_size_bytes() / (1024 * 1024)


def stats():
    """Row count, tech count, and date range — for a health/debug readout."""
    try:
        with _DB_LOCK:
            conn = _connect()
            row = conn.execute(
                "SELECT COUNT(*) AS n, MIN(ts) AS first_ts, MAX(ts) AS last_ts,"
                " COUNT(DISTINCT tech) AS techs FROM tech_ticket_events"
            ).fetchone()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else None
    size = file_size_bytes()
    events = row["n"] or 0
    return {
        "ok": True,
        "path": db_path(),
        "events": events,
        "techs": row["techs"],
        "first": fmt(row["first_ts"]),
        "last": fmt(row["last_ts"]),
        "bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "max_events": MAX_EVENTS,
    }
