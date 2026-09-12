"""
Per-unit validation history, backed by SQLite.

Every validation the dashboard already runs gets recorded here, so questions
like "has RD3076 flapped this week?" and "which units are worst right now?"
are answerable without sending a single extra packet. The live service
restarts often, so nothing here lives in memory.

The database is a single file in the data dir (`unit_history.db`), separate
per environment because live and sandbox have different data dirs. It is
append-only apart from `prune()`.

Threading: Flask serves this app with threaded=True, so one module-level
connection is shared under a lock with check_same_thread=False. WAL mode
keeps a long read from blocking a write.
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

# Categories the dashboard assigns. "false_positives" is the healthy one;
# everything else is some flavour of down.
HEALTHY_CATEGORIES = {"false_positives"}


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
        _DB_PATH = os.path.join(directory, "unit_history.db")
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
    # Checkpoint sooner than the 1000-page default so the -wal file stays small.
    conn.execute("PRAGMA wal_autocheckpoint=256")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS unit_events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            unit      TEXT    NOT NULL,
            ts        REAL    NOT NULL,
            kind      TEXT    NOT NULL,
            category  TEXT,
            led       TEXT,
            healthy   INTEGER,
            detail    TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_unit_events_unit_ts ON unit_events (unit, ts DESC);
        CREATE INDEX IF NOT EXISTS idx_unit_events_ts      ON unit_events (ts DESC);
        """
    )
    conn.commit()
    _CONN = conn
    return _CONN


def _is_healthy(category, led=None):
    if led:
        return str(led).strip().lower() == "green"
    return str(category or "").strip() in HEALTHY_CATEGORIES


def record(unit, kind, category=None, led=None, detail=None):
    """
    Append one observation for a unit.

    kind: "validate_quick" / "validate_full" / "revalidate" / "poll" — free
    text, so new callers do not need a schema change.

    Never raises: history is a nice-to-have, and a locked or corrupt database
    must not break a validation run. Returns True when the row was written.
    """
    unit = str(unit or "").strip().upper()
    if not unit:
        return False
    try:
        with _DB_LOCK:
            conn = _connect()
            conn.execute(
                "INSERT INTO unit_events (unit, ts, kind, category, led, healthy, detail)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    unit,
                    time.time(),
                    str(kind or "validate"),
                    str(category) if category else None,
                    str(led) if led else None,
                    1 if _is_healthy(category, led) else 0,
                    str(detail)[:2000] if detail else None,
                ),
            )
            conn.commit()
        return True
    except Exception as exc:
        print(f"[history] could not record {unit}: {exc}")
        return False


def _since_ts(days):
    return (datetime.now() - timedelta(days=max(0, float(days)))).timestamp()


def history(unit, days=30, limit=200):
    """Most recent observations for a unit, newest first."""
    unit = str(unit or "").strip().upper()
    if not unit:
        return []
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT ts, kind, category, led, healthy, detail FROM unit_events"
                " WHERE unit = ? AND ts >= ? ORDER BY ts DESC LIMIT ?",
                (unit, _since_ts(days), int(limit)),
            ).fetchall()
        return [
            {
                "ts": row["ts"],
                "when": datetime.fromtimestamp(row["ts"]).strftime("%Y-%m-%d %H:%M:%S"),
                "kind": row["kind"],
                "category": row["category"],
                "led": row["led"],
                "healthy": bool(row["healthy"]),
                "detail": row["detail"],
            }
            for row in rows
        ]
    except Exception as exc:
        print(f"[history] could not read {unit}: {exc}")
        return []


def flap_summary(unit, days=7):
    """
    How unstable a unit has been recently.

    "transitions" counts healthy <-> unhealthy flips in chronological order,
    which is what distinguishes a unit that is simply down (one transition,
    still down) from one that keeps bouncing (many).
    """
    unit = str(unit or "").strip().upper()
    empty = {
        "unit": unit, "days": days, "checks": 0, "down_checks": 0,
        "transitions": 0, "last_seen": None, "currently_healthy": None,
    }
    if not unit:
        return empty
    try:
        with _DB_LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT ts, healthy FROM unit_events WHERE unit = ? AND ts >= ? ORDER BY ts ASC",
                (unit, _since_ts(days)),
            ).fetchall()
    except Exception as exc:
        print(f"[history] could not summarise {unit}: {exc}")
        return empty
    if not rows:
        return empty

    transitions = 0
    previous = None
    down = 0
    for row in rows:
        healthy = bool(row["healthy"])
        if not healthy:
            down += 1
        if previous is not None and healthy != previous:
            transitions += 1
        previous = healthy
    last = rows[-1]
    return {
        "unit": unit,
        "days": days,
        "checks": len(rows),
        "down_checks": down,
        "transitions": transitions,
        "last_seen": datetime.fromtimestamp(last["ts"]).strftime("%Y-%m-%d %H:%M:%S"),
        "currently_healthy": bool(last["healthy"]),
    }


def fleet_flappers(days=7, min_transitions=3, limit=50):
    """Units with the most healthy/unhealthy flips in the window, worst first."""
    try:
        with _DB_LOCK:
            conn = _connect()
            units = [
                row["unit"]
                for row in conn.execute(
                    "SELECT DISTINCT unit FROM unit_events WHERE ts >= ?",
                    (_since_ts(days),),
                ).fetchall()
            ]
    except Exception as exc:
        print(f"[history] could not list units: {exc}")
        return []
    summaries = [flap_summary(unit, days=days) for unit in units]
    flapping = [s for s in summaries if s["transitions"] >= int(min_transitions)]
    flapping.sort(key=lambda s: (-s["transitions"], -s["down_checks"], s["unit"]))
    return flapping[:int(limit)]


# Hard ceiling on stored rows, independent of age. At roughly 104 bytes per
# row (payload plus both indexes) 200,000 rows is about 20 MB, so this bounds
# the file even if something starts recording far more often than expected.
MAX_EVENTS = 200_000

# Only reclaim disk when a prune actually freed a worthwhile amount — VACUUM
# rewrites the whole file, so doing it after every trivial delete is wasteful.
VACUUM_AFTER_DELETED = 1000


def _vacuum(conn):
    """
    Return freed pages to the filesystem.

    DELETE alone only marks pages reusable inside the file; the file itself
    never shrinks. VACUUM rebuilds it — but it cannot run inside a
    transaction, and sqlite3 opens one implicitly for us, so commit and drop
    to autocommit first. Getting this wrong is silent: the prune "succeeds"
    and the file stays exactly the same size.
    """
    previous = conn.isolation_level
    try:
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.isolation_level = previous


def prune(keep_days=90, max_events=MAX_EVENTS):
    """
    Drop observations older than keep_days, then enforce the row ceiling, then
    reclaim the freed space. Returns rows deleted.
    """
    try:
        with _DB_LOCK:
            conn = _connect()
            deleted = conn.execute(
                "DELETE FROM unit_events WHERE ts < ?", (_since_ts(keep_days),)
            ).rowcount or 0

            # Age-based pruning alone cannot bound the file, so also cap the
            # row count, dropping the oldest rows beyond the ceiling.
            if max_events:
                remaining = conn.execute("SELECT COUNT(*) FROM unit_events").fetchone()[0]
                excess = remaining - int(max_events)
                if excess > 0:
                    deleted += conn.execute(
                        "DELETE FROM unit_events WHERE id IN ("
                        " SELECT id FROM unit_events ORDER BY ts ASC LIMIT ?)",
                        (excess,),
                    ).rowcount or 0
            conn.commit()

            if deleted >= VACUUM_AFTER_DELETED:
                _vacuum(conn)
        if deleted:
            print(f"[history] pruned {deleted} event(s); database now {file_size_mb():.1f} MB")
        return deleted
    except Exception as exc:
        print(f"[history] prune failed: {exc}")
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
    """Size on disk including the write-ahead log and shared-memory files."""
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
    """Row count and date range — for a health/debug readout."""
    try:
        with _DB_LOCK:
            conn = _connect()
            row = conn.execute(
                "SELECT COUNT(*) AS n, MIN(ts) AS first_ts, MAX(ts) AS last_ts,"
                " COUNT(DISTINCT unit) AS units FROM unit_events"
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
        "units": row["units"],
        "first": fmt(row["first_ts"]),
        "last": fmt(row["last_ts"]),
        "bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "bytes_per_event": round(size / events) if events else None,
        "max_events": MAX_EVENTS,
    }
