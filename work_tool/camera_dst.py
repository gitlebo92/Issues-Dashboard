"""
Camera DST Fix: unstick cameras whose Scrypted RAM folder stopped populating.

Andrew's procedure (scratch_test.dst_fix, 2026-10-14), made safe to run from
the dashboard: turn DST off on each not-populating camera, reboot the
Scrypted VM (qm reboot 101), wait for Scrypted to come back, then put each
camera's DST setting back to what it was.

Works on any camera on the unit's RAM-folder list (Fisheye, C1-180/C1-PTZ,
C2-180/C2-PTZ, Camera 3/4), not just the fisheye — the cameras come from
scrypted_ram_folder_status, the same check as Get Ram Folder. PVE units
(>= 3300) only: a NUC unit has no VM 101 and no RAM folders.

Every camera this turns DST off on is restored in a `finally`, so a failed
reboot or wait never leaves a camera with DST changed. The streaming entry
points run the work on a background thread, so a closed browser tab can't
interrupt it half way either.
"""

import json
import os
import queue
import socket
import threading
import time

import paramiko
import requests
from dotenv import load_dotenv
from requests.auth import HTTPDigestAuth

from ._core import (
    _camera_vendor,
    _normalize_netsheet_unit,
    _scrypted_ssh_target,
    env_path,
    list_unit_cameras,
    uses_pve,
)
from .diagnostics import (
    _camera_target_for_ram_camera_name,
    _pve_ssh_target,
    fleet_camera_outage_report,
    scrypted_ram_folder_status,
)
from .locks import unit_busy_end, unit_busy_start, unit_busy_touch

CAMERA_DST_FIX_ACTION = "Camera DST Fix"
# qm reboot waits for a clean guest shutdown before starting it again.
_DST_FIX_REBOOT_TIMEOUT_SEC = 600
# After qm reboot returns: how long Scrypted's SSH port gets to answer, and
# how long Scrypted then gets to load its cameras before DST goes back on
# (the 30 s Andrew's procedure waited).
_DST_FIX_SCRYPTED_UP_TIMEOUT_SEC = 300
_DST_FIX_SETTLE_SEC = 30
_DST_FIX_HTTP_TIMEOUT_SEC = 15
_DST_FIX_RESULT_PREFIX = "__DST_FIX_RESULT__ "
_fleet_dst_fix_lock = threading.Lock()


def _fish_credentials():
    load_dotenv(env_path)
    user = (os.getenv("fishuser") or "").strip().strip('"').strip("'")
    password = (os.getenv("fishpass") or "").strip().strip('"').strip("'")
    return user, password


def _parse_locales(text):
    """{'DSTEnable': 'true', 'DSTStart.Month': '3', ...} from a getConfig body."""
    values = {}
    for line in str(text or "").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key.startswith("table.Locales."):
            values[key[len("table.Locales."):]] = value.strip()
    return values


def _camera_cgi(host, port, auth, query):
    return requests.get(
        f"http://{host}:{port}/cgi-bin/configManager.cgi?{query}",
        auth=auth, timeout=_DST_FIX_HTTP_TIMEOUT_SEC,
    )


def _read_camera_dst(camera, auth):
    """
    (port, dst_enable 'true'/'false', error). Tries the camera's own port,
    then 80 and 10080 — but only moves on when a port doesn't answer or
    404s; a 401 stops at once, since every retry is another failed login
    against the camera's lockout counter.
    """
    host = camera["host"]
    ports = []
    for port in (camera.get("port"), 80, 10080):
        if port and port not in ports:
            ports.append(port)
    last_error = "no port answered"
    for port in ports:
        try:
            response = _camera_cgi(host, port, auth, "action=getConfig&name=Locales")
        except requests.exceptions.RequestException as exc:
            last_error = f"{host}:{port} did not answer ({exc.__class__.__name__})"
            continue
        if response.status_code == 401:
            return None, None, f"{host}:{port} rejected fishuser/fishpass (HTTP 401) — check them in .env"
        if response.status_code == 404:
            last_error = f"{host}:{port} has no configManager.cgi (HTTP 404)"
            continue
        if response.status_code != 200:
            return None, None, f"{host}:{port} returned HTTP {response.status_code}"
        value = _parse_locales(response.text).get("DSTEnable", "").lower()
        if value not in ("true", "false"):
            return None, None, f"{host}:{port} has no Locales.DSTEnable setting (got: {response.text.strip()[:120]!r})"
        return port, value, None
    return None, None, last_error


def _write_camera_dst(host, port, auth, value):
    """None on success, else an error sentence. Dahua answers a good write with a bare OK."""
    try:
        response = _camera_cgi(host, port, auth, f"action=setConfig&Locales.DSTEnable={value}")
    except requests.exceptions.RequestException as exc:
        return f"{host}:{port} did not answer ({exc.__class__.__name__})"
    body = response.text.strip()
    if response.status_code != 200 or body.upper() != "OK":
        return f"{host}:{port} refused DSTEnable={value} (HTTP {response.status_code}: {body[:120]!r})"
    return None


def _reboot_scrypted_vm(unit):
    """(ok, message). Runs qm reboot 101 and waits for it to finish."""
    ip, ssh_username, ssh_password, error = _pve_ssh_target(unit)
    if error:
        return False, error
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=ip, port=22, username=ssh_username, password=ssh_password,
            timeout=30, allow_agent=False, look_for_keys=False,
        )
        _stdin, stdout, stderr = client.exec_command("qm reboot 101", timeout=_DST_FIX_REBOOT_TIMEOUT_SEC)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        errors = stderr.read().decode("utf-8", errors="replace").strip()
        status = stdout.channel.recv_exit_status()
        if status != 0:
            return False, f"qm reboot 101 failed on {ip} (exit {status}): {errors or output or 'no output'}"
        return True, f"qm reboot 101 finished on {ip}"
    except paramiko.AuthenticationException:
        return False, (
            f"PVE SSH authentication failed for {ssh_username}@{ip}. "
            "Set pvesshuser=root and pvepass in .env."
        )
    except Exception as exc:
        return False, f"qm reboot 101 on {ip} failed: {exc}"
    finally:
        client.close()


def _wait_for_port(host, port, timeout_sec):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=5):
                return True
        except OSError:
            time.sleep(5)
    return False


def _cameras_to_fix(unit, emit):
    """
    (cameras, any_failing, error): the unit's not-populating cameras this
    fix can act on, one entry per physical camera.
    """
    info, error = scrypted_ram_folder_status(unit)
    if error:
        return None, False, f"RAM folder check failed: {error}"
    failing = [c for c in (info or {}).get("cameras") or [] if not c.get("ok")]
    if not failing:
        return [], False, None
    emit(f"Not populating: {', '.join(c['name'] for c in failing)}")

    cameras, error = list_unit_cameras(unit)
    if error:
        return None, True, error
    by_target = {c.get("target"): c for c in cameras or []}
    picked = []
    seen = set()
    for folder in failing:
        target = _camera_target_for_ram_camera_name(folder["name"])
        if not target:
            emit(f"  {folder['name']}: skipped - can't tell which camera this folder belongs to "
                 "(Scrypted room lookup failed); run Get Camera Rooms")
            continue
        if target in seen:
            continue  # C1-180 and C1-PTZ are one camera on one IP
        seen.add(target)
        camera = by_target.get(target)
        if not camera:
            emit(f"  {folder['name']}: skipped - no IP for {target} on {unit}")
            continue
        vendor = _camera_vendor(unit, camera, cameras)
        if vendor != "dahua":
            emit(f"  {camera['label']}: skipped - {vendor.title()} camera; the DST fix is Dahua only")
            continue
        picked.append(camera)
    return picked, True, None


def _dst_fix_unit(unit, emit):
    """
    The fix for one unit. emit(line) receives progress. Returns (status,
    message); status is "fixed", "nothing" (every folder populating),
    "skipped" (nothing safe to do) or "failed".
    """
    unit = _normalize_netsheet_unit(unit) or str(unit or "").strip().upper()
    if not unit:
        return "failed", "Missing unit"
    if not uses_pve(unit):
        return "skipped", f"{unit} is a NUC unit - this fix restarts Scrypted's VM 101, which only PVE units (>= 3300) have"
    user, password = _fish_credentials()
    if not user or not password:
        return "failed", "fishuser/fishpass not set in .env"
    _pve_ip, _u, _p, error = _pve_ssh_target(unit)
    if error:
        return "failed", error
    _row, scrypted_host, error = _scrypted_ssh_target(unit)
    if error:
        return "failed", error

    started, token, existing = unit_busy_start(unit, CAMERA_DST_FIX_ACTION)
    if not started:
        return "skipped", f"{unit} is busy: {(existing or {}).get('action') or 'another action'}"

    def step(line, phase=None):
        emit(line)
        unit_busy_touch(unit, token, phase=phase, log_line=line)

    changed = []  # (camera, port, original value) for every camera DST was turned off on
    auth = HTTPDigestAuth(user, password)
    try:
        step(f"Checking RAM folders on {unit}...", phase="check")
        cameras, any_failing, error = _cameras_to_fix(unit, step)
        if error:
            return "failed", f"{unit}: {error}"
        if not any_failing:
            return "nothing", f"{unit}: every camera RAM folder is populating - nothing to do"
        if not cameras:
            return "skipped", f"{unit}: no not-populating camera this fix can act on - Scrypted was not restarted"

        for camera in cameras:
            port, original, error = _read_camera_dst(camera, auth)
            if error:
                step(f"  {camera['label']}: skipped - {error}")
                continue
            if original == "true":
                error = _write_camera_dst(camera["host"], port, auth, "false")
                if error:
                    step(f"  {camera['label']}: skipped - {error}")
                    continue
                step(f"  {camera['label']} ({camera['host']}): DST turned off (was on)")
            else:
                step(f"  {camera['label']} ({camera['host']}): DST already off - leaving it off")
            changed.append((camera, port, original))
        if not changed:
            return "failed", f"{unit}: no camera could be read or changed - Scrypted was not restarted"

        step(f"Rebooting Scrypted (qm reboot 101) on {unit}...", phase="reboot")
        ok, message = _reboot_scrypted_vm(unit)
        step(message)
        if not ok:
            return "failed", f"{unit}: {message}"
        step(f"Waiting up to {_DST_FIX_SCRYPTED_UP_TIMEOUT_SEC // 60} min for Scrypted ({scrypted_host}) to answer...", phase="wait")
        if not _wait_for_port(scrypted_host, 22, _DST_FIX_SCRYPTED_UP_TIMEOUT_SEC):
            return "failed", f"{unit}: Scrypted did not come back within {_DST_FIX_SCRYPTED_UP_TIMEOUT_SEC // 60} min - check it in PVE"
        step(f"Scrypted is up; giving it {_DST_FIX_SETTLE_SEC} s to load its cameras...")
        time.sleep(_DST_FIX_SETTLE_SEC)
        return "fixed", (
            f"{unit}: DST fix done on {', '.join(c['label'] for c, _p, _o in changed)} - "
            "run Get Ram Folder in a few minutes to confirm the folders fill"
        )
    finally:
        restore_failed = []
        for camera, port, original in changed:
            if original != "true":
                continue
            error = _write_camera_dst(camera["host"], port, auth, "true")
            if error:
                restore_failed.append(camera["label"])
                step(f"  {camera['label']}: RESTORE FAILED - {error}. Turn DST back on in the camera's own page.")
            else:
                step(f"  {camera['label']}: DST turned back on")
        if restore_failed:
            step(f"WARNING: DST is still OFF on {', '.join(restore_failed)} ({unit})")
        unit_busy_end(unit, token)


def camera_dst_fix(unit, emit=print):
    """
    Camera DST Fix for one unit. Returns (ok, message) — ok is True when
    it ran, or when every camera folder was already populating.

        ok, message = work_tool.camera_dst_fix("RD3417")
    """
    status, message = _dst_fix_unit(unit, emit)
    return status in ("fixed", "nothing"), message


def camera_dst_fix_all(emit=print):
    """
    Camera DST Fix on every unit on the Camera Outage Report, one at a
    time. Returns (summary, error); summary maps status -> [messages].
    """
    if not _fleet_dst_fix_lock.acquire(blocking=False):
        return None, "A DST Fix All run is already in progress"
    try:
        rows, error = fleet_camera_outage_report()
        if error:
            return None, f"Camera Outage Report failed: {error}"
        rows = rows or []
        summary = {"fixed": [], "nothing": [], "skipped": [], "failed": []}
        emit(f"DST Fix All: {len(rows)} unit(s) on the Camera Outage Report")
        for index, row in enumerate(rows, 1):
            unit = row.get("unit")
            emit(f"[{index}/{len(rows)}] {unit}")
            try:
                status, message = _dst_fix_unit(unit, lambda line: emit("  " + line))
            except Exception as exc:
                status, message = "failed", f"{unit}: {exc}"
            summary[status].append(message)
            emit(f"  -> {message}")
        emit(
            f"DST Fix All done: {len(summary['fixed'])} fixed, {len(summary['nothing'])} already populating, "
            f"{len(summary['skipped'])} skipped, {len(summary['failed'])} failed"
        )
        return summary, None
    finally:
        _fleet_dst_fix_lock.release()


def _stream_in_background(work):
    """
    Run work(emit) on a daemon thread and yield its lines as they arrive.
    The work keeps going if the reader goes away, so a closed browser tab
    can't stop a fix between turning DST off and putting it back.
    """
    lines = queue.Queue()
    done = object()

    def run():
        try:
            work(lambda line: lines.put(str(line)))
        except Exception as exc:
            lines.put(f"DST fix crashed: {exc}")
        finally:
            lines.put(done)

    threading.Thread(target=run, name="camera-dst-fix", daemon=True).start()
    while True:
        line = lines.get()
        if line is done:
            return
        print(line)
        yield line + "\n"


def stream_camera_dst_fix(unit):
    """Live output for the per-unit button; last line is a __DST_FIX_RESULT__ JSON sentinel."""

    def work(emit):
        status, message = _dst_fix_unit(unit, emit)
        emit(message)
        emit(_DST_FIX_RESULT_PREFIX + json.dumps({"unit": unit, "status": status, "message": message}))
    return _stream_in_background(work)


def stream_camera_dst_fix_all():
    """Live output for DST Fix All; last line is a __DST_FIX_RESULT__ JSON sentinel."""

    def work(emit):
        summary, error = camera_dst_fix_all(emit)
        if error:
            emit(error)
            emit(_DST_FIX_RESULT_PREFIX + json.dumps({"status": "failed", "message": error}))
            return
        counts = {key: len(value) for key, value in summary.items()}
        status = "failed" if counts["failed"] else "fixed"
        emit(_DST_FIX_RESULT_PREFIX + json.dumps({"status": status, "counts": counts}))
    return _stream_in_background(work)
