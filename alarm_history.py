"""
Per-alarm history for combined_power_infra_alerts(), backed by SQLite.

Zabbix and VRM only ever show what's active RIGHT NOW — once a Zabbix
problem resolves it drops out of problem.get entirely, and VRM's alarm=true
flag carries no "since when" at all. Neither system can answer "has this
happened before," "how long did it run last time," or "is this unit a
repeat offender" — this module exists to make those answerable from data
the dashboard is already polling anyway (see _run_scheduled_power_infra_alerts
in flask_endpoints.py), at effectively zero extra API cost.

Storage model: one row per EPISODE (a (unit, source, name) alarm condition
being continuously active), not one row per poll. A poll only ever UPDATEs
an already-open episode's last_seen, or opens/closes one — it never inserts
a fresh row for something already open. This is the only viable shape at
this fleet's scale: a naive "log every active alarm every poll" table would
add ~1,700 rows per 10-minute poll (~245,000/day) for a fleet that, checked
live (2026-09-13), had 1,433 active Zabbix problems + a couple hundred VRM
alarms at once. Episode rows only grow when something genuinely NEW starts,
which live data suggests is a few dozen to a couple hundred a day, not
hundreds of thousands — the same gap in growth rate that makes unit_history's
flat per-check-event table workable for its own (much lower-volume) domain
but wrong for this one.

The database is a single file in the data dir (`alarm_history.db`), separate
per environment (live/sandbox have different data dirs) like unit_history.db.

Threading: same shared-connection-under-a-lock pattern as unit_history.py,
since Flask serves this app with threaded=True.
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
        _DB_PATH = os.path.join(directory, "alarm_history.db")
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
        CREATE TABLE IF NOT EXISTS alarm_episodes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            unit         TEXT    NOT NULL,
            source       TEXT    NOT NULL,
            name         TEXT    NOT NULL,
            severity     INTEGER,
            corroborated INTEGER NOT NULL DEFAULT 0,
            first_seen   REAL    NOT NULL,
            last_seen    REAL    NOT NULL,
            closed_at    REAL
        );
        CREATE INDEX IF NOT EXISTS idx_alarm_episodes_unit  ON alarm_episodes (unit, first_seen DESC);
        CREATE INDEX IF NOT EXISTS idx_alarm_episodes_open  ON alarm_episodes (unit, source, name) WHERE closed_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_alarm_episodes_close ON alarm_episodes (closed_at);
        """
    )
    conn.commit()
    _CONN = conn
    return _CONN


def _active_keys_from_rows(rows):
    """
    (unit, source, name) -> severity, corroborated for every currently-active
    alarm across every row combined_power_infra_alerts() returned. One key
    per Zabbix problem AND per VRM alarm — a unit with three open Zabbix
    problems and a VRM alarm contributes four keys, since each is its own
    episode with its own start/stop.

    Deliberately reads own_zabbix_problems, NOT zabbix_problems: the latter
    is corroboration-enriched — an MU trailer's row folds in its RD/FD
    head's own Zabbix problems too (see combined_power_infra_alerts), which
    is correct for deciding "is this unit's row corroborated" but would be
    wrong here — it would record the head's NUC problem as if the trailer
    itself had it, inflating the trailer's own episode/frequency counts
    with a problem that was never really on that hardware.
    """
    active = {}
    for row in rows or []:
        unit = str(row.get("unit") or "").strip().upper()
        if not unit:
            continue
        corroborated = bool(row.get("corroborated"))
        for problem in row.get("own_zabbix_problems") or []:
            name = str(problem.get("name") or "").strip()
            if not name:
                continue
            key = (unit, "zabbix", name)
            active[key] = {"severity": problem.get("severity"), "corroborated": corroborated}
        vrm_alarm = row.get("vrm_alarm")
        if vrm_alarm:
            name = str(vrm_alarm.get("alarm_detail") or "VRM alarm").strip()
            key = (unit, "vrm", name)
            active[key] = {"severity": None, "corroborated": corroborated}
    return active


def record_snapshot(rows):
    """
    Diff the current combined_power_infra_alerts() rows against whatever
    episodes are still open in the database, and update accordingly:
      - still active  -> bump last_seen (and severity/corroborated) in place
      - newly active  -> open a new episode
      - no longer active -> close it (closed_at = its own last_seen, the
        last moment it was actually confirmed active — we don't know the
        exact second it cleared between this poll and the last one, so the
        last confirmed sighting is the honest number, not "now")

    Never raises — this is a nice-to-have layered on top of a poll that
    already has its own job to do (filling _power_infra_cache); a locked or
    corrupt database here must not affect that. Returns
    (opened, closed, updated) counts, or None if it couldn't run at all.
    """
    active = _active_keys_from_rows(rows)
    now = time.time()
    try:
        with _DB_LOCK:
            conn = _connect()
            open_rows = conn.execute(
                "SELECT id, unit, source, name, last_seen FROM alarm_episodes WHERE closed_at IS NULL"
            ).fetchall()
            open_by_key = {(r["unit"], r["source"], r["name"]): r for r in open_rows}

            opened = closed = updated = 0
            for key, info in active.items():
                existing = open_by_key.get(key)
                if existing:
                    conn.execute(
                        "UPDATE alarm_episodes SET last_seen = ?, severity = ?, corroborated = ? WHERE id = ?",
                        (now, info["severity"], 1 if info["corroborated"] else 0, existing["id"]),
                    )
                    updated += 1
                else:
                    unit, source, name = key
                    conn.execute(
                        "INSERT INTO alarm_episodes"
                        " (unit, source, name, severity, corroborated, first_seen, last_seen, closed_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                        (unit, source, name, info["severity"], 1 if info["corroborated"] else 0, now, now),
                    )
                    opened += 1

            for key, row in open_by_key.items():
                if key not in active:
                    conn.execute(
                        "UPDATE alarm_episodes SET closed_at = last_seen WHERE id = ?",
                        (row["id"],),
                    )
                    closed += 1
            conn.commit()
        return (opened, closed, updated)
    except Exception as exc:
        print(f"[alarm_history] could not record snapshot: {exc}")
        return None


def _since_ts(days):
    return (datetime.now() - timedelta(days=max(0, float(days)))).timestamp()


def unit_alarm_history(unit, days=30, limit=200):
    """
    Every episode (open or closed) for a unit in the window, newest first.
    duration_seconds is (closed_at or now) - first_seen, so an open episode
    shows how long it's been running so far, not None.
    """
    unit = str(unit or "").strip().upper()
    if not unit:
        return []
    now = time.time()
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT source, name, severity, corroborated, first_seen, last_seen, closed_at"
                " FROM alarm_episodes WHERE unit = ? AND first_seen >= ? ORDER BY first_seen DESC LIMIT ?",
                (unit, _since_ts(days), int(limit)),
            ).fetchall()
    except Exception as exc:
        print(f"[alarm_history] could not read {unit}: {exc}")
        return []
    out = []
    for row in rows:
        end = row["closed_at"] if row["closed_at"] is not None else now
        out.append({
            "source": row["source"],
            "name": row["name"],
            "severity": row["severity"],
            "corroborated": bool(row["corroborated"]),
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "closed_at": row["closed_at"],
            "is_open": row["closed_at"] is None,
            "duration_seconds": max(0, end - row["first_seen"]),
        })
    return out


def unit_alarm_recurrence(unit, days=30):
    """
    How often this unit's alarms have come back, not just whether one is
    active right now. episode_count over 1 for the same (source, name) means
    it cleared and returned within the window — "recurring," not "ongoing."
    """
    episodes = unit_alarm_history(unit, days=days, limit=1000)
    by_name = {}
    for ep in episodes:
        key = (ep["source"], ep["name"])
        by_name.setdefault(key, []).append(ep)
    recurring = [
        {
            "source": source, "name": name, "episode_count": len(eps),
            "total_open_seconds": sum(e["duration_seconds"] for e in eps),
            "currently_open": any(e["is_open"] for e in eps),
            "most_recent_first_seen": max(e["first_seen"] for e in eps),
        }
        for (source, name), eps in by_name.items()
        if len(eps) > 1
    ]
    recurring.sort(key=lambda r: -r["episode_count"])
    return {
        "unit": unit,
        "days": days,
        "total_episodes": len(episodes),
        "distinct_alarms": len(by_name),
        "recurring": recurring,
    }


def fleet_alarm_frequency(days=7, min_episodes=2, limit=50):
    """Units with the most alarm episodes in the window, worst first — the
    "repeat offenders" list unit_history's fleet_flappers() does for
    validation checks, but for Zabbix/VRM alarms."""
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT unit, COUNT(*) AS episodes, COUNT(DISTINCT source || '|' || name) AS distinct_alarms,"
                " SUM(CASE WHEN closed_at IS NULL THEN 1 ELSE 0 END) AS currently_open,"
                " MAX(last_seen) AS last_seen"
                " FROM alarm_episodes WHERE first_seen >= ?"
                " GROUP BY unit HAVING COUNT(*) >= ?"
                " ORDER BY episodes DESC LIMIT ?",
                (_since_ts(days), int(min_episodes), int(limit)),
            ).fetchall()
    except Exception as exc:
        print(f"[alarm_history] could not compute fleet frequency: {exc}")
        return []
    return [
        {
            "unit": row["unit"],
            "episodes": row["episodes"],
            "distinct_alarms": row["distinct_alarms"],
            "currently_open": row["currently_open"],
            "last_seen": datetime.fromtimestamp(row["last_seen"]).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for row in rows
    ]


# Far lower than unit_history's 200k — episode rows only grow when an alarm
# condition genuinely starts, not once per poll (see module docstring), so
# this fleet needs nowhere near that ceiling; kept as a hard backstop only.
MAX_EPISODES = 50_000
VACUUM_AFTER_DELETED = 500


def _vacuum(conn):
    """See unit_history._vacuum — same reasoning: DELETE alone never shrinks
    the file, VACUUM does, and it can't run inside sqlite3's implicit
    transaction."""
    previous = conn.isolation_level
    try:
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.isolation_level = previous


def prune(keep_days=90, max_episodes=MAX_EPISODES):
    """
    Drop CLOSED episodes older than keep_days, then enforce the row
    ceiling, then reclaim freed space. Open episodes are never pruned by
    age alone — an alarm that's been open longer than keep_days is exactly
    the kind of thing this module exists to still be able to answer "how
    long has this run" about, so pruning it because of its own age would
    defeat the point. Returns rows deleted.
    """
    try:
        with _DB_LOCK:
            conn = _connect()
            deleted = conn.execute(
                "DELETE FROM alarm_episodes WHERE closed_at IS NOT NULL AND closed_at < ?",
                (_since_ts(keep_days),),
            ).rowcount or 0

            if max_episodes:
                remaining = conn.execute("SELECT COUNT(*) FROM alarm_episodes").fetchone()[0]
                excess = remaining - int(max_episodes)
                if excess > 0:
                    # Only ever drop closed rows for the ceiling too — same
                    # reasoning as the age-based prune above.
                    deleted += conn.execute(
                        "DELETE FROM alarm_episodes WHERE id IN ("
                        " SELECT id FROM alarm_episodes WHERE closed_at IS NOT NULL"
                        " ORDER BY closed_at ASC LIMIT ?)",
                        (excess,),
                    ).rowcount or 0
            conn.commit()

            if deleted >= VACUUM_AFTER_DELETED:
                _vacuum(conn)
        if deleted:
            print(f"[alarm_history] pruned {deleted} episode(s); database now {file_size_mb():.1f} MB")
        return deleted
    except Exception as exc:
        print(f"[alarm_history] prune failed: {exc}")
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
    """Row count, open/closed split, and date range — for a health/debug readout."""
    try:
        with _DB_LOCK:
            conn = _connect()
            row = conn.execute(
                "SELECT COUNT(*) AS n, MIN(first_seen) AS first_ts, MAX(last_seen) AS last_ts,"
                " COUNT(DISTINCT unit) AS units,"
                " SUM(CASE WHEN closed_at IS NULL THEN 1 ELSE 0 END) AS open_episodes"
                " FROM alarm_episodes"
            ).fetchone()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else None
    size = file_size_bytes()
    episodes = row["n"] or 0
    return {
        "ok": True,
        "path": db_path(),
        "episodes": episodes,
        "open_episodes": row["open_episodes"] or 0,
        "units": row["units"],
        "first": fmt(row["first_ts"]),
        "last": fmt(row["last_ts"]),
        "bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "max_episodes": MAX_EPISODES,
    }
