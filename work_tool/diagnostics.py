"""
Read-only unit diagnostics. Nothing here changes state on a device.

Split out of the original single-file work_tool.py. Everything here is
re-exported by work_tool/__init__.py, so each name is still reachable as
`work_tool.<name>` exactly as before.
"""

import time
import base64
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
from xml.etree import ElementTree
import urllib3

from ._core import (  # noqa: F401  (re-exported dependencies)
    _erp_heads_for_mu_trailers,
    _fetch_erp_component_site_map,
    _fetch_erp_issue_doc,
    _format_switch_uptime_seconds,
    _host_only,
    _iter_remote_pty_command,
    _net_row_for_unit,
    _ping_host,
    _ping_reachable,
    _pve_ssh_credentials,
    _sc_component_name,
    _scrypted_ssh_credentials,
    _scrypted_ssh_target,
    _scrypted_web_credentials,
    ensure_unit_net_info,
    env_path,
    get_robofiber_uptime,
    is_hikvision_unit,
    list_unit_cameras,
    open_camera_targets_for_unit,
    ping_camera,
    username,
    uses_pve,
    validate_unit_full,
    work_tld,
)
from .weather import vrm_active_alarms_by_unit  # noqa: F401  (re-exported dependency)


# Platform services managed on the Scrypted box, in start order. Kept in sync
# with refresh_platform_services() — if you add a service to one, add it here.
# Verified live against 6 real boxes across two subnets/regions (2026-09-12):
# every one runs exactly these 15, no more, no less — indexer and rtsp were
# missing from this list despite being real, active services on every box.
PLATFORM_SERVICES = (
    "database", "watchdog", "web", "metadata", "images", "indexer", "capture",
    "rtsp", "smtp", "alarms", "events", "onvif", "monitor", "snmp", "cache",
)
# docker.service hosts the core engine the 15 sentracam-* daemons depend on,
# but it doesn't follow the {company}-<name>.service naming convention, so
# it can't just be added to PLATFORM_SERVICES above — it's tracked here and
# joined in below instead.
PLATFORM_SERVICES_UNPREFIXED = ("docker",)
def _ssh_read(host, username, password, command, timeout=60, connect_timeout=30):
    """
    Run one read-only command over SSH and return (stdout_text, error).

    stderr is folded into the output only when stdout is empty, so a command
    that warns but succeeds still reports its result.
    """
    if not host:
        return "", "Missing host"
    if not username or not password:
        return "", "Missing SSH credentials in .env"
    client = paramiko.SSHClient()
    try:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            port=22,
            username=username,
            password=password,
            timeout=connect_timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
    except paramiko.AuthenticationException:
        return "", f"SSH authentication failed for {username}@{host}"
    except Exception as exc:
        return "", f"SSH to {host} failed: {exc}"
    finally:
        client.close()
    if not out and err:
        return err, None
    return out, None
def scrypted_service_status(unit):
    """
    Which platform services are actually running on the unit's Scrypted box.

    The read that should come before "Restart All Services" — it names the
    one service that died instead of restarting all thirteen blind.
    Returns (info, error).
    """
    load_dotenv(env_path)
    _row, host, error = _scrypted_ssh_target(unit)
    if error:
        return None, error
    username, password = _scrypted_ssh_credentials()
    company = (os.getenv("company") or "").strip().strip('"').strip("'")
    if not company:
        return None, "Set `company` in .env — it prefixes the platform service names"

    names = (
        [f"{svc}.service" for svc in PLATFORM_SERVICES_UNPREFIXED]
        + [f"{company}-{svc}.service" for svc in PLATFORM_SERVICES]
    )
    # One call, one line per service: "<name> <active-state> <sub-state>".
    command = (
        "for s in " + " ".join(shlex.quote(n) for n in names) + "; do "
        "printf '%s %s %s\\n' \"$s\" \"$(systemctl is-active \"$s\" 2>/dev/null)\" "
        "\"$(systemctl show -p SubState --value \"$s\" 2>/dev/null)\"; done"
    )
    raw, error = _ssh_read(host, username, password, command, timeout=60)
    if error:
        return None, error
    if not raw:
        return None, f"No service status returned from {host}"

    services = []
    for line in raw.splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        sub = parts[2] if len(parts) > 2 else ""
        services.append({
            "name": name,
            "short": name.replace(f"{company}-", "").replace(".service", ""),
            "state": state,
            "sub_state": sub,
            "ok": state == "active",
        })

    down = [s["short"] for s in services if not s["ok"]]
    if not services:
        summary = f"No platform services found on {unit}"
        status = "warn"
    elif not down:
        summary = f"All {len(services)} platform services active on {unit}"
        status = "ok"
    else:
        summary = (
            f"{len(down)} of {len(services)} services not active on {unit}: "
            + ", ".join(down)
        )
        status = "fail"

    return {
        "unit": unit,
        "host": host,
        "status": status,
        "summary": summary,
        "services": services,
        "down": down,
        "output": raw,
    }, None
# The RAM-drive snapshot folders on a Scrypted box are named after each
# camera device — but NOT consistently by the same identifier. Checked
# live, 2026-09-21, across several units: some name the folder after the
# device's "room" field (e.g. "SC000852" — RD3500/RD3556/RD3431), others
# after Scrypted's own internal numeric device id instead (e.g.
# "scrypted-101" — RD3419, where device id 101 is that unit's Fisheye,
# room SC000312; the folder is /mnt/ram/cameras/scrypted-101/, not
# .../SC000312/). A version of this that only tried camera_rooms()'s
# SMTP-derived room code (matching Scrypted's own "room" field, so no
# improvement there either) left every RD3419-shaped unit's folders
# unlabeled by their raw "scrypted-10x" name and wrongly read as "not
# populating" — the count itself was accurate, only the label was wrong,
# but a label a tech can't recognize is as good as none. Registering BOTH
# candidate keys per camera below means whichever naming scheme an
# installation actually uses resolves to the same friendly label.
_SCRYPTED_RAM_ROOM_CAMERA_LABELS = (
    ("C1-180", "C1-180"),
    ("C1-PTZ", "C1-PTZ"),
    ("C2-180", "C2-180"),
    ("C2-PTZ", "C2-PTZ"),
    ("FISHEYE", "Fisheye"),
)
_SCRYPTED_RAM_FULLSIZE_HEALTHY_MIN = 5
def _camera_target_for_ram_camera_name(name):
    """
    Netsheet camera target (fisheye/camera1-4) for a RAM-folder row's
    friendly name (see _SCRYPTED_RAM_ROOM_CAMERA_LABELS) — "C1-180"/
    "C1-PTZ" are the same physical camera1 IP's two channels (confirmed
    with Andrew, 2026-09-24: on a >=3300 unit, camera1 hosts a fixed 180
    on channel 1 and PTZ on channel 2, sharing one IP), so both map to
    "camera1"; likewise "C2-*" -> camera2. Only used to pick which host
    to ping for the not-populating secondary check below, not to
    distinguish the two channels — ICMP can't tell them apart anyway,
    both live on the same IP.
    """
    text = str(name or "").strip().upper()
    if text == "FISHEYE":
        return "fisheye"
    match = re.match(r"^C(\d)-", text)
    if match:
        return "camera" + match.group(1)
    return None
async def _scrypted_camera_rooms_by_folder(unit):
    """
    Map each 180/PTZ/Fisheye camera's Scrypted room AND its Scrypted
    device id (the two folder-naming schemes seen live — see the comment
    above) back to a friendly camera label. Returns ({room_or_id: label}, error).
    """
    from scrypted_sdk import connect_scrypted_client

    web_username, web_password = _scrypted_web_credentials()
    if not web_username or not web_password:
        return None, "scryptuserweb/scryptpass are not set in .env"
    tld = work_tld()
    if not tld:
        return None, "workTLD is not set in .env"
    base_url = f"https://{unit.lower()}.{tld}"
    loop = asyncio.get_running_loop()
    try:
        transport, sdk = await connect_scrypted_client(loop, base_url, web_username, web_password)
    except Exception as exc:
        return None, f"Scrypted login failed for {unit}: {exc}"
    try:
        rooms_by_label = {}
        for device_id, state in sdk.systemManager.getSystemState().items():
            name = str((state.get("name") or {}).get("value") or "")
            if "SC" not in name or "AA" in name or "TT" in name:
                continue
            room = (state.get("room") or {}).get("value")
            name_upper = name.upper()
            for needle, label in _SCRYPTED_RAM_ROOM_CAMERA_LABELS:
                if needle in name_upper:
                    if room:
                        rooms_by_label[room] = label
                    if device_id:
                        rooms_by_label[f"scrypted-{device_id}"] = label
                    break
        return rooms_by_label, None
    finally:
        try:
            await transport.close()
        except Exception:
            pass
def _camera_rooms_by_label(unit):
    """
    {folder_key: friendly_label} for labeling RAM-folder rows — see
    _scrypted_camera_rooms_by_folder. Best-effort: a failure here (no
    scryptuserweb/scryptpass, Scrypted unreachable) just means folder rows
    show up unlabeled by their raw folder name instead of a camera name —
    it doesn't fail the RAM-folder populating check itself, which reads
    the RAM drive directly over SSH and doesn't depend on this at all.
    Returns ({key: label}, error) — error is informational only, callers
    are not required to abort on it.
    """
    rooms_by_label, error = asyncio.run(_scrypted_camera_rooms_by_folder(unit))
    return rooms_by_label or {}, error
def _merge_ram_folder_rows(raw_rows, rooms_by_label):
    """
    (room, count) pairs from the raw `/mnt/ram/cameras/*/` listing, merged
    down to one row per camera LABEL rather than one per raw folder name.
    A camera can have more than one folder on disk at once — verified
    live, RD3419, 2026-09-21: its snapshot mixin restarted mid-session and
    switched from naming folders after Scrypted's device id
    ("scrypted-101") to naming them after the room field ("SC000312"),
    leaving the old id-named folders behind, empty, with no `fullsize`
    subdirectory at all. _scrypted_camera_rooms_by_folder registers both
    naming schemes under the same label for exactly this reason, so both
    folders land here mapped to "Fisheye" — keeping whichever one
    actually has files (the real, currently-written one) means the dead
    leftover can't read as a second camera that's "not populating."
    Folders that don't match any known label still show up individually,
    unlabeled, same as before this existed.
    """
    by_name = {}
    for room, count in raw_rows:
        name = rooms_by_label.get(room, room)
        existing = by_name.get(name)
        if existing is None or count > existing["file_count"]:
            by_name[name] = {
                "room": room,
                "name": name,
                "file_count": count,
                "ok": count >= _SCRYPTED_RAM_FULLSIZE_HEALTHY_MIN,
            }
    return list(by_name.values())
def _expected_camera_ram_labels(unit):
    """
    The camera RAM-folder labels this unit SHOULD have — derived purely
    from the netsheet camera config (open_camera_targets_for_unit, the
    same ACRD/Tippy/>=3300 camera-count rules used everywhere else) plus
    uses_pve's own PTZ-channel inference (camera1/camera2 each split into
    a fixed-180 and a PTZ channel on a >=3300 unit — see
    _ptz_channel_for_camera's own comment), never by asking Scrypted.

    Corrected with Andrew, 2026-10-01: this used to come from
    _scrypted_camera_rooms_by_folder's live Scrypted systemManager query
    instead — but that's a folder-NAME-to-label mapping aid (matching the
    actual room code/device id a RAM folder happens to be named after),
    not a trustworthy source for how many cameras a unit has. A Scrypted
    login failure, an incomplete/misconfigured device list, or any other
    live hiccup silently undercounted "Found N camera(s)" — exactly when
    this check runs (chasing a camera/Scrypted problem) is also when that
    live query is least reliable. The config-derived set here is the same
    deterministic answer the rest of the app already agrees on, and holds
    regardless of whether Scrypted itself is reachable right now.
    """
    targets = open_camera_targets_for_unit(unit)
    pve = uses_pve(unit)
    labels = []
    for n in (1, 2, 3, 4):
        target = f"camera{n}"
        if target not in targets:
            continue
        if pve and n in (1, 2):
            labels.append(f"C{n}-180")
            labels.append(f"C{n}-PTZ")
        else:
            labels.append(f"Camera {n}")
    if "fisheye" in targets:
        labels.append("Fisheye")
    return labels
def _add_missing_camera_rows(cameras, expected_labels):
    """
    Add a row for any expected camera with NO RAM folder on disk at all —
    not just an existing-but-empty one. Without this, a camera whose
    snapshot folder was never created (its capture mixin never started, or
    the box just rebooted) silently disappears from the report instead of
    showing up as a finding. Caught live, RD3421, 2026-09-30: this unit
    has 5 expected cameras, but only 3 had any folder on disk — C1-180 and
    C1-PTZ had none at all and were missing from the list entirely instead
    of reporting as failing.
    Mutates `cameras` in place (appends only).
    """
    present = {c["name"] for c in cameras}
    for label in expected_labels:
        if label in present:
            continue
        cameras.append({
            "room": None,
            "name": label,
            "file_count": 0,
            "ok": False,
            "no_folder": True,
        })
def _add_camera_reachability(unit, cameras):
    """
    For each not-populating camera, ping its actual device — the
    secondary check that tells "camera itself is dead" (folder empty
    because nothing's feeding it) apart from "camera answers fine, only
    Scrypted's own capture stopped" (folder empty despite the camera
    being reachable) — two different problems with two different fixes.
    Andrew's own request, 2026-09-28. Mutates `cameras` in place, adding
    "camera_reachable": True/False/None to each failing entry — None
    means either the folder's name couldn't be mapped back to a netsheet
    target (see _camera_target_for_ram_camera_name) or the ping itself
    couldn't run (e.g. unit not in the net sheet), not a real verdict.
    Healthy (already-populating) cameras are left untouched — nothing to
    disambiguate there.
    """
    for camera in cameras:
        if camera.get("ok"):
            continue
        target = _camera_target_for_ram_camera_name(camera.get("name"))
        if not target:
            camera["camera_reachable"] = None
            continue
        result = ping_camera(unit, target)
        if not result:
            camera["camera_reachable"] = None
            continue
        _code, output = result
        camera["camera_reachable"] = _ping_reachable(output)
def scrypted_ram_folder_status(unit):
    """
    Which cameras are actually populating /mnt/ram/cameras/<room>/fullsize
    on the unit's Scrypted box. The expected camera set comes from the
    netsheet config (see _expected_camera_ram_labels); Scrypted's own room
    assignment is only used to map a raw folder name back to that camera's
    friendly label. Returns (info, error).
    """
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"

    rooms_by_label, _room_error = _camera_rooms_by_label(unit)

    _row, host, error = _scrypted_ssh_target(unit)
    if error:
        return None, error
    ssh_username, ssh_password = _scrypted_ssh_credentials()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cameras = []
    try:
        client.connect(hostname=host, username=ssh_username, password=ssh_password, timeout=30)
        list_cmd = (
            f"echo {shlex.quote(ssh_password)} | sudo -S bash -c "
            # nullglob: without it, a unit with NOTHING under
            # /mnt/ram/cameras/ yet (mount just created, box freshly
            # rebooted) leaves the glob unexpanded, and the loop runs
            # once on the literal string "/mnt/ram/cameras/*/" — basename
            # of that is "*", reported as one camera named "*" that's
            # "not populating" (looks like every camera is down; it just
            # means the listing found nothing at all). Caught live, RD3340,
            # 2026-09-22.
            "'shopt -s nullglob; for d in /mnt/ram/cameras/*/; do "
            'room=$(basename "$d"); '
            'count=$(ls -1 "$d/fullsize" 2>/dev/null | wc -l); '
            'printf "%s %s\\n" "$room" "$count"; done\''
        )
        _stdin, stdout, stderr = client.exec_command(list_cmd, timeout=30)
        raw = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")
        # sudo -S always echoes its password prompt to stderr, success or
        # not — treating any non-empty stderr as a failure misread a unit
        # with genuinely empty output (nullglob correctly finding zero
        # camera folders) as this SSH call itself having failed, surfacing
        # "[sudo] password for sentracam:" as if it were the real error
        # instead of falling through to the accurate "No camera RAM
        # folders found" below. Strip just that routine prompt line first.
        err_for_check = re.sub(r"^\[sudo\]\s*password for [^:]+:\s*", "", err, flags=re.IGNORECASE).strip()
        if not raw and err_for_check:
            return None, err_for_check

        raw_rows = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            room, count_text = parts
            try:
                count = int(count_text)
            except ValueError:
                continue
            raw_rows.append((room, count))
        cameras = _merge_ram_folder_rows(raw_rows, rooms_by_label)
        # Only synthesize "missing" rows when the room/device-id mapping
        # actually resolved something — with no mapping at all we can't
        # tell an expected camera's folder apart from an unrecognized raw
        # name, so claiming 5 specific cameras are "missing" on top of
        # already showing their folders unlabeled would double-count the
        # same cameras twice. Caught live, RD3375, 2026-10-01 (Scrypted
        # login failed outright): without this guard it reported "7 of 11"
        # instead of the real 5.
        if rooms_by_label:
            _add_missing_camera_rows(cameras, _expected_camera_ram_labels(unit))
    except Exception as exc:
        return None, f"SSH to Scrypted box on {unit} failed: {exc}"
    finally:
        client.close()

    if not cameras:
        return None, f"No camera RAM folders found on {unit}"

    _add_camera_reachability(unit, cameras)
    failing = [c["name"] for c in cameras if not c["ok"]]
    if not failing:
        summary = f"All {len(cameras)} camera RAM folders populating on {unit}"
        status = "ok"
    else:
        summary = (
            f"{len(failing)} of {len(cameras)} camera RAM folders not "
            f"populating on {unit}: " + ", ".join(failing)
        )
        status = "fail"

    return {
        "unit": unit,
        "host": host,
        "status": status,
        "summary": summary,
        "cameras": cameras,
    }, None
def stream_scrypted_ram_folder_status(unit):
    """
    Same check as scrypted_ram_folder_status, but yields output live as it
    runs instead of collecting it all before returning — same reasoning as
    stream_update_unit_patch_version: the Scrypted room lookup and the
    remote listing can each take a few seconds, and a tech watching this
    run wants to see progress, not a blank pane until it either finishes
    or errors out.

    Yields plain text chunks. Never raises into the caller — any
    lookup/connection/SSH error is yielded as a line instead.
    """
    unit = str(unit or "").strip()
    if not unit:
        yield "Missing unit\n"
        return

    # The expected camera set comes from the netsheet config (+ uses_pve's
    # PTZ-channel inference) — see _expected_camera_ram_labels — never
    # from Scrypted's own live state, so this line is accurate even when
    # Scrypted itself is the thing having a bad day. Corrected with
    # Andrew, 2026-10-01, after this used to ask Scrypted's systemManager
    # directly and could silently undercount when that query was
    # incomplete or failed outright.
    expected_labels = _expected_camera_ram_labels(unit)
    yield (
        f"Expecting {len(expected_labels)} camera(s) on {unit}: "
        + ", ".join(expected_labels) + "\n"
    )
    yield f"Looking up Scrypted room/device-id mapping for {unit}...\n"
    rooms_by_label, room_error = _camera_rooms_by_label(unit)
    if room_error:
        yield (
            f"Scrypted room lookup incomplete ({room_error}) — folders "
            "below will show unlabeled by their raw folder name instead "
            "of a camera name.\n"
        )

    _row, host, error = _scrypted_ssh_target(unit)
    if error:
        yield f"{error}\n"
        return
    ssh_username, ssh_password = _scrypted_ssh_credentials()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    yield f"Connecting to {unit} ({host})...\n"
    try:
        client.connect(hostname=host, username=ssh_username, password=ssh_password, timeout=30)
    except Exception as exc:
        yield f"SSH connect to {host} failed: {exc}\n"
        return
    yield "Connected — listing /mnt/ram/cameras...\n"

    list_cmd = "sudo -S bash -c " + shlex.quote(
        # nullglob — see scrypted_ram_folder_status's identical comment.
        "shopt -s nullglob; for d in /mnt/ram/cameras/*/; do "
        'room=$(basename "$d"); '
        'count=$(ls -1 "$d/fullsize" 2>/dev/null | wc -l); '
        'printf "%s %s\\n" "$room" "$count"; done'
    )
    raw_lines = []
    exit_status = None
    try:
        for item in _iter_remote_pty_command(client, list_cmd, ssh_password, timeout=60):
            if isinstance(item, tuple):
                exit_status = item[1]
            elif item:
                raw_lines.append(item)
                yield item
    except Exception as exc:
        yield f"\nRAM folder check error: {exc}\n"
        return
    finally:
        try:
            client.close()
        except Exception:
            pass

    raw_rows = []
    for line in "".join(raw_lines).splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        room, count_text = parts
        try:
            count = int(count_text)
        except ValueError:
            continue
        raw_rows.append((room, count))
    cameras = _merge_ram_folder_rows(raw_rows, rooms_by_label)
    # See scrypted_ram_folder_status's identical guard: with no working
    # room/device-id mapping, "missing" rows would double-count cameras
    # whose folders are already showing up unlabeled by raw name.
    if rooms_by_label:
        _add_missing_camera_rows(cameras, expected_labels)

    if not cameras:
        yield f"\nNo camera RAM folders found on {unit} (exit {exit_status})\n"
        return

    failing = [c["name"] for c in cameras if not c["ok"]]
    if not failing:
        yield f"\nAll {len(cameras)} camera RAM folders populating on {unit}\n"
    else:
        yield (
            f"\n{len(failing)} of {len(cameras)} camera RAM folders not "
            f"populating on {unit}: " + ", ".join(failing) + "\n"
        )
        yield "Checking whether each is actually reachable...\n"
        _add_camera_reachability(unit, cameras)
        any_unreachable = False
        for camera in cameras:
            if camera.get("ok"):
                continue
            reachable = camera.get("camera_reachable")
            if reachable is False:
                any_unreachable = True
            verdict = (
                "camera unreachable too — likely dead/offline" if reachable is False
                else "camera IS reachable — Scrypted-side capture issue, not the camera itself" if reachable is True
                else "could not determine camera reachability"
            )
            yield f"  {camera['name']}: {verdict}\n"
        # A trailing, machine-readable line the frontend pulls out of the
        # stream (and never displays) to decide whether to flip this
        # unit's LED to yellow — a camera that's not just "not populating"
        # but confirmed UNREACHABLE is a real degraded-hardware finding,
        # not just a Scrypted-side capture hiccup, and is worth surfacing
        # on the ticket's own status light. Deliberately does NOT move the
        # ticket to a different list — Up Steady tickets stay in Up Steady,
        # this only changes which LED color they show. Andrew's own
        # request, 2026-10-01.
        yield "__RAM_FOLDER_RESULT__ " + json.dumps({"any_camera_unreachable": any_unreachable}) + "\n"
def _parse_size_table(text, wanted_mounts=("/",)):
    """Pull the rows we care about out of `df -h` output."""
    rows = []
    for line in str(text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        mount = parts[-1]
        if wanted_mounts and mount not in wanted_mounts:
            continue
        use = parts[-2].rstrip("%")
        try:
            use_pct = int(use)
        except ValueError:
            use_pct = None
        rows.append({
            "filesystem": parts[0],
            "size": parts[-5],
            "used": parts[-4],
            "available": parts[-3],
            "use_percent": use_pct,
            "mount": mount,
        })
    return rows
def pve_host_resources(unit):
    """
    Memory, disk, load and VM state on the unit's PVE host (read-only).

    Answers "is the host wedged, or is only the guest down?" in one call.
    Returns (info, error).
    """
    load_dotenv(env_path)
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    row = ensure_unit_net_info(unit, needed_indexes=(11,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    host = _host_only(row[11] if len(row) > 11 else "")
    if not host:
        return None, f"No PVE IP for {unit}"
    username, password, cred_error = _pve_ssh_credentials()
    if cred_error:
        return None, cred_error

    command = (
        "echo '__UPTIME__'; uptime; "
        "echo '__MEM__'; free -m; "
        "echo '__DISK__'; df -h; "
        "echo '__VMS__'; qm list 2>/dev/null || echo 'qm unavailable'; "
        "echo '__VM101__'; qm status 101 2>/dev/null || echo 'no VM 101'"
    )
    raw, error = _ssh_read(host, username, password, command, timeout=90)
    if error:
        return None, error
    if not raw:
        return None, f"No output from PVE host {host}"

    sections = {}
    current = None
    for line in raw.splitlines():
        marker = re.fullmatch(r"__([A-Z0-9]+)__", line.strip())
        if marker:
            current = marker.group(1).lower()
            sections[current] = []
        elif current:
            sections[current].append(line)
    sections = {key: "\n".join(value).strip() for key, value in sections.items()}

    info = {"unit": unit, "host": host, "output": raw, "sections": sections}
    reasons = []
    status = "ok"

    # Memory: the "Mem:" row of free -m, in MiB.
    mem_match = re.search(r"^Mem:\s+(\d+)\s+(\d+)\s+(\d+)", sections.get("mem", ""), re.M)
    if mem_match:
        total, used, free_mb = (int(mem_match.group(i)) for i in (1, 2, 3))
        info.update({
            "mem_total_mb": total, "mem_used_mb": used, "mem_free_mb": free_mb,
            "mem_used_percent": round(used * 100 / total) if total else None,
        })
        if total and used * 100 / total >= 90:
            status = "fail"
            reasons.append(f"memory {round(used * 100 / total)}% used")

    swap_match = re.search(r"^Swap:\s+(\d+)\s+(\d+)", sections.get("mem", ""), re.M)
    if swap_match:
        swap_total, swap_used = int(swap_match.group(1)), int(swap_match.group(2))
        info.update({"swap_total_mb": swap_total, "swap_used_mb": swap_used})
        if swap_total and swap_used * 100 / swap_total >= 50:
            if status == "ok":
                status = "warn"
            reasons.append(f"swap {round(swap_used * 100 / swap_total)}% used")

    disks = _parse_size_table(sections.get("disk", ""), wanted_mounts=("/",))
    if disks:
        info["root_disk"] = disks[0]
        use_pct = disks[0].get("use_percent")
        if isinstance(use_pct, int):
            if use_pct >= 90:
                status = "fail"
                reasons.append(f"root filesystem {use_pct}% full")
            elif use_pct >= 80:
                if status == "ok":
                    status = "warn"
                reasons.append(f"root filesystem {use_pct}% full")

    load_match = re.search(r"load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", sections.get("uptime", ""))
    if load_match:
        info["load_1m"] = float(load_match.group(1))
        info["load_5m"] = float(load_match.group(2))
        info["load_15m"] = float(load_match.group(3))

    vm_state = ""
    vm_match = re.search(r"status:\s*(\S+)", sections.get("vm101", ""))
    if vm_match:
        vm_state = vm_match.group(1)
        info["vm101_status"] = vm_state
        if vm_state != "running":
            status = "fail"
            reasons.append(f"VM 101 is {vm_state}")
    elif "no VM 101" in sections.get("vm101", ""):
        info["vm101_status"] = "missing"
        status = "fail"
        reasons.append("VM 101 not present")

    info["status"] = status
    info["reasons"] = reasons
    parts = []
    if info.get("mem_used_percent") is not None:
        parts.append(f"mem {info['mem_used_percent']}%")
    if info.get("root_disk", {}).get("use_percent") is not None:
        parts.append(f"disk {info['root_disk']['use_percent']}%")
    if info.get("load_1m") is not None:
        parts.append(f"load {info['load_1m']}")
    if vm_state:
        parts.append(f"VM 101 {vm_state}")
    detail = ", ".join(parts) if parts else "see output"
    info["summary"] = (
        f"PVE host for {unit} looks healthy — {detail}"
        if status == "ok"
        else f"PVE host for {unit} needs attention ({'; '.join(reasons)}) — {detail}"
    )
    return info, None
def nuc_host_resources(unit):
    """
    Memory, disk and CPU load on a unit's Windows NUC, read over SSH.

    Mirrors what pve_host_resources() answers for PVE units ("is the host
    actually under pressure") — this half of the fleet had no resource
    visibility at all before this, only reboot/uptime/chkdsk. One PowerShell
    one-liner emits JSON directly rather than text this function has to
    parse, so there's no regex layer to keep in sync with Windows' output
    formatting the way the PVE/Linux checks have to be.
    Returns (info, error).
    """
    load_dotenv(env_path)
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    if uses_pve(unit):
        return None, f"{unit} uses PVE — use PVE Host Resources instead"
    row = ensure_unit_net_info(unit, needed_indexes=(3,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    host = _host_only(row[3] if len(row) > 3 else "")
    if not host:
        return None, f"No NUC IP for {unit}"
    nucuser = (os.getenv("nucuser") or "").strip().strip('"').strip("'")
    nucpass = (os.getenv("nucpass") or "").strip().strip('"').strip("'")
    if not nucuser or not nucpass:
        return None, "Set nucuser/nucpass in .env"

    ps_script = (
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "$cpu = (Get-CimInstance Win32_Processor | "
        "Measure-Object -Property LoadPercentage -Average).Average; "
        # Single-quoted throughout (PowerShell escapes an embedded single
        # quote by doubling it: ''). The whole script is itself wrapped in
        # double quotes for -Command "..." below, so any double quote here
        # would need Windows command-line-level escaping too — avoiding
        # that nesting entirely is what actually survives SSH intact.
        "$disk = Get-CimInstance Win32_LogicalDisk -Filter 'DeviceID=''C:'''; "
        "[PSCustomObject]@{"
        "TotalMemMB=[math]::Round($os.TotalVisibleMemorySize/1024);"
        "FreeMemMB=[math]::Round($os.FreePhysicalMemory/1024);"
        "CpuLoadPct=$cpu;"
        "DiskSizeGB=[math]::Round($disk.Size/1GB,1);"
        "DiskFreeGB=[math]::Round($disk.FreeSpace/1GB,1)"
        "} | ConvertTo-Json -Compress"
    )
    command = f'powershell -NoProfile -NonInteractive -Command "{ps_script}"'
    raw, error = _ssh_read(host, nucuser, nucpass, command, timeout=45)
    if error:
        return None, error
    if not raw:
        return None, f"No output from NUC {host}"

    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None, f"Could not parse NUC resource output from {host}: {raw[:200]}"

    total_mb = parsed.get("TotalMemMB")
    free_mb = parsed.get("FreeMemMB")
    used_mb = (total_mb - free_mb) if isinstance(total_mb, (int, float)) and isinstance(free_mb, (int, float)) else None
    mem_used_percent = round(used_mb * 100 / total_mb) if used_mb is not None and total_mb else None
    disk_size_gb = parsed.get("DiskSizeGB")
    disk_free_gb = parsed.get("DiskFreeGB")
    disk_used_percent = (
        round((disk_size_gb - disk_free_gb) * 100 / disk_size_gb)
        if disk_size_gb and disk_free_gb is not None
        else None
    )
    cpu_load_pct = parsed.get("CpuLoadPct")

    info = {
        "unit": unit,
        "host": host,
        "mem_total_mb": total_mb,
        "mem_used_mb": used_mb,
        "mem_free_mb": free_mb,
        "mem_used_percent": mem_used_percent,
        "disk_size_gb": disk_size_gb,
        "disk_free_gb": disk_free_gb,
        "disk_used_percent": disk_used_percent,
        "cpu_load_percent": cpu_load_pct,
        "output": raw,
    }

    reasons = []
    status = "ok"
    if mem_used_percent is not None and mem_used_percent >= 90:
        status = "fail"
        reasons.append(f"memory {mem_used_percent}% used")
    if disk_used_percent is not None:
        if disk_used_percent >= 90:
            status = "fail"
            reasons.append(f"C: {disk_used_percent}% full")
        elif disk_used_percent >= 80 and status == "ok":
            status = "warn"
            reasons.append(f"C: {disk_used_percent}% full")
    if isinstance(cpu_load_pct, (int, float)) and cpu_load_pct >= 90 and status == "ok":
        status = "warn"
        reasons.append(f"CPU {round(cpu_load_pct)}% load")

    info["status"] = status
    info["reasons"] = reasons
    parts = []
    if mem_used_percent is not None:
        parts.append(f"mem {mem_used_percent}%")
    if disk_used_percent is not None:
        parts.append(f"C: {disk_used_percent}%")
    if cpu_load_pct is not None:
        parts.append(f"CPU {round(cpu_load_pct)}%")
    detail = ", ".join(parts) if parts else "see output"
    info["summary"] = (
        f"NUC for {unit} looks healthy — {detail}"
        if status == "ok"
        else f"NUC for {unit} needs attention ({'; '.join(reasons)}) — {detail}"
    )
    return info, None


# ---- NUC Disk Health ---------------------------------------------------------
# Windows NUCs had chkdsk and nothing else for disk health (the Linux/Scrypted
# units have their own checks). Three read-only sources, all over the same SSH
# login chkdsk uses, verified live on RD1009 and RD3059 (2026-10-05):
#   - Get-PhysicalDisk: each drive's own HealthStatus/OperationalStatus.
#   - Get-StorageReliabilityCounter: SMART-style temperature, wear, read/write
#     error counts, power-on hours. NVMe drives often leave the error counts
#     blank — that's "not reported", not zero.
#   - MSStorageDriver_FailurePredictStatus: the SMART predict-failure flag —
#     SATA drives only; NVMe never shows up here.
#   - The System event log: warnings/errors from the disk, NTFS and storage
#     driver providers over the last 90 days.
# Each event provider is queried on its own inside try/catch: one
# FilterHashtable listing a provider the machine doesn't have (Intel's iaStorA
# wasn't on RD3059) throws and returns NOTHING for the providers that do exist.
# Sent with -EncodedCommand because nested quotes don't survive cmd.exe.
_NUC_DISK_HEALTH_PS = r"""
$ProgressPreference='SilentlyContinue'
$disks = @(Get-PhysicalDisk | ForEach-Object { [PSCustomObject]@{
  DeviceId=[string]$_.DeviceId; Name=$_.FriendlyName; Media=[string]$_.MediaType; Bus=[string]$_.BusType;
  Health=[string]$_.HealthStatus; Operational=[string]$_.OperationalStatus; SizeGB=[math]::Round($_.Size/1GB) } })
$rel = @(Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | ForEach-Object { [PSCustomObject]@{
  DeviceId=[string]$_.DeviceId; Temperature=$_.Temperature; TemperatureMax=$_.TemperatureMax; Wear=$_.Wear;
  ReadErrorsTotal=$_.ReadErrorsTotal; ReadErrorsUncorrected=$_.ReadErrorsUncorrected;
  WriteErrorsTotal=$_.WriteErrorsTotal; WriteErrorsUncorrected=$_.WriteErrorsUncorrected; PowerOnHours=$_.PowerOnHours } })
$pred = @(Get-CimInstance -Namespace root\wmi -ClassName MSStorageDriver_FailurePredictStatus -ErrorAction SilentlyContinue | ForEach-Object { [PSCustomObject]@{
  Instance=$_.InstanceName; PredictFailure=[bool]$_.PredictFailure; Reason=$_.Reason } })
$events = @()
foreach ($p in 'disk','Ntfs','Microsoft-Windows-Ntfs','stornvme','storahci','iaStorA','iaStorAC','iaStorAVC','volmgr','Microsoft-Windows-StorPort') {
  try {
    $events += @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName=$p;Level=1,2,3;StartTime=(Get-Date).AddDays(-90)} -MaxEvents 200 -ErrorAction Stop | ForEach-Object {
      [PSCustomObject]@{ Provider=$_.ProviderName; Id=$_.Id; Level=$_.Level; Time=$_.TimeCreated.ToUniversalTime().ToString('o');
        Message=$(if ($_.Message) { ($_.Message -split "`n")[0].Trim() } else { '' }) } })
  } catch {}
}
[PSCustomObject]@{ Disks=$disks; Reliability=$rel; Predict=$pred; Events=$events } | ConvertTo-Json -Depth 4 -Compress
"""

# (provider family, event id) -> (tier, plain-English meaning). "critical"
# means the disk or file system is actually failing; "warning" is an early
# sign worth watching. Anything else from these providers is listed but
# doesn't change the verdict (e.g. disk 34, "driver disabled the write
# cache", which RD1009's Miray RAM drive logs routinely).
_NUC_DISK_EVENT_MEANINGS = {
    ("disk", 7): ("critical", "bad block"),
    ("disk", 11): ("critical", "controller error"),
    ("disk", 51): ("critical", "I/O error during paging"),
    ("disk", 52): ("critical", "SMART predicts the drive will fail"),
    ("disk", 154): ("critical", "hardware error"),
    ("ntfs", 55): ("critical", "file system corruption"),
    ("ntfs", 98): ("critical", "volume needs chkdsk to repair it"),
    ("ntfs", 137): ("critical", "file system transaction error"),
    ("disk", 153): ("warning", "I/O had to be retried"),
    ("storage", 129): ("warning", "drive stopped responding and was reset"),
}


def _nuc_disk_event_family(provider):
    name = str(provider or "").lower()
    if name == "disk":
        return "disk"
    if "ntfs" in name:
        return "ntfs"
    if name in ("stornvme", "storahci", "volmgr") or name.startswith("iastor") or "storport" in name:
        return "storage"
    return name


def _as_list(value):
    """ConvertTo-Json turns a one-item array into a bare object."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _summarize_nuc_disk_health(unit, parsed, now=None):
    """
    Turn the PowerShell JSON (_NUC_DISK_HEALTH_PS) into a verdict. Pure — no
    SSH — so tests/test_diagnostics.py can feed it captured output.
    Returns the info dict (status ok/warn/fail, reasons, summary, disks,
    events).
    """
    now = now or datetime.now(timezone.utc)
    reliability = {str(r.get("DeviceId")): r for r in _as_list(parsed.get("Reliability")) if isinstance(r, dict)}
    predicts = [p for p in _as_list(parsed.get("Predict")) if isinstance(p, dict)]

    disks = []
    for d in _as_list(parsed.get("Disks")):
        if not isinstance(d, dict):
            continue
        rel = reliability.get(str(d.get("DeviceId")), {})
        name = str(d.get("Name") or "").strip()
        # MSStorageDriver_FailurePredictStatus has no device id — match on
        # the model, which its InstanceName embeds (truncated, no spaces).
        model_key = name.replace(" ", "").upper()[:12]
        predict = next(
            (p for p in predicts if model_key and model_key in str(p.get("Instance") or "").replace(" ", "").upper()),
            None,
        )
        disks.append({
            "device_id": str(d.get("DeviceId")),
            "name": name,
            "media": d.get("Media") or "",
            "bus": d.get("Bus") or "",
            "health": d.get("Health") or "",
            "operational": d.get("Operational") or "",
            "size_gb": d.get("SizeGB"),
            "temperature": rel.get("Temperature"),
            "temperature_max": rel.get("TemperatureMax"),
            "wear": rel.get("Wear"),
            "read_errors_total": rel.get("ReadErrorsTotal"),
            "read_errors_uncorrected": rel.get("ReadErrorsUncorrected"),
            "write_errors_total": rel.get("WriteErrorsTotal"),
            "write_errors_uncorrected": rel.get("WriteErrorsUncorrected"),
            "power_on_hours": rel.get("PowerOnHours"),
            "predict_failure": predict.get("PredictFailure") if predict else None,
        })
    disk_by_number = {d["device_id"]: d["name"] for d in disks}

    grouped = {}
    for e in _as_list(parsed.get("Events")):
        if not isinstance(e, dict):
            continue
        provider = str(e.get("Provider") or "")
        event_id = e.get("Id")
        key = (provider, event_id)
        try:
            when = datetime.fromisoformat(str(e.get("Time")).replace("Z", "+00:00"))
        except ValueError:
            when = None
        group = grouped.setdefault(key, {"provider": provider, "id": event_id, "count": 0,
                                         "last": None, "message": "", "disk": ""})
        group["count"] += 1
        if when and (group["last"] is None or when > group["last"]):
            group["last"] = when
            group["message"] = str(e.get("Message") or "")
    events = []
    for group in grouped.values():
        tier, meaning = _NUC_DISK_EVENT_MEANINGS.get(
            (_nuc_disk_event_family(group["provider"]), group["id"]), ("other", "")
        )
        match = re.search(r"\\Device\\Harddisk(\d+)\\", group["message"])
        days_ago = (now - group["last"]).total_seconds() / 86400 if group["last"] else None
        events.append({
            "provider": group["provider"],
            "id": group["id"],
            "count": group["count"],
            "tier": tier,
            "meaning": meaning,
            "message": group["message"],
            "disk": disk_by_number.get(match.group(1), "") if match else "",
            "last": group["last"].isoformat() if group["last"] else None,
            "days_ago": round(days_ago, 1) if days_ago is not None else None,
        })
    tier_rank = {"critical": 0, "warning": 1, "other": 2}
    events.sort(key=lambda ev: (tier_rank[ev["tier"]], ev["days_ago"] if ev["days_ago"] is not None else 999))

    fail, warn = [], []
    for d in disks:
        label = d["name"] or f"disk {d['device_id']}"
        if d["health"] and d["health"] != "Healthy":
            fail.append(f"{label} reports {d['health']}")
        if d["predict_failure"] is True:
            fail.append(f"{label}: SMART predicts failure")
        for field, what in (("read_errors_uncorrected", "uncorrected read"), ("write_errors_uncorrected", "uncorrected write")):
            if isinstance(d[field], (int, float)) and d[field] > 0:
                fail.append(f"{label}: {d[field]} {what} error(s)")
        if isinstance(d["wear"], (int, float)) and d["wear"] >= 80:
            warn.append(f"{label} {d['wear']}% worn")
        if isinstance(d["temperature"], (int, float)) and d["temperature"] >= 70:
            warn.append(f"{label} at {d['temperature']}°C")
    for ev in events:
        if ev["tier"] == "other":
            continue
        recent = ev["days_ago"] is not None and ev["days_ago"] <= 30
        text = f"{ev['count']}x {ev['meaning']} (event {ev['provider']} {ev['id']})"
        if ev["tier"] == "critical" and recent:
            fail.append(text)
        else:
            warn.append(text)

    status = "fail" if fail else ("warn" if warn else "ok")
    reasons = fail + warn
    flagged = [ev for ev in events if ev["tier"] != "other"]
    detail = f"{len(disks)} drive(s), " + (
        f"{sum(ev['count'] for ev in flagged)} failure-related event(s) in 90 days" if flagged
        else "no failure-related events in 90 days"
    )
    summary = (
        f"Disks on {unit}'s NUC look healthy — {detail}" if status == "ok"
        else f"Disks on {unit}'s NUC need attention ({'; '.join(reasons)}) — {detail}"
    )
    return {"unit": unit, "status": status, "reasons": reasons, "summary": summary,
            "disks": disks, "events": events}


def nuc_disk_health(unit):
    """
    Read-only disk health for a unit's Windows NUC: drive health, SMART
    counters, SMART predict-failure, and 90 days of disk/NTFS/storage-driver
    events, with the ones that mean a failing disk called out. See the
    block comment above _NUC_DISK_HEALTH_PS. Returns (info, error).
    """
    load_dotenv(env_path)
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    if uses_pve(unit):
        return None, f"{unit} uses PVE — use NVMe Health for its disks instead"
    row = ensure_unit_net_info(unit, needed_indexes=(3,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    host = _host_only(row[3] if len(row) > 3 else "")
    if not host:
        return None, f"No NUC IP for {unit}"
    nucuser = (os.getenv("nucuser") or "").strip().strip('"').strip("'")
    nucpass = (os.getenv("nucpass") or "").strip().strip('"').strip("'")
    if not nucuser or not nucpass:
        return None, "Set nucuser/nucpass in .env"

    encoded = base64.b64encode(_NUC_DISK_HEALTH_PS.encode("utf-16-le")).decode("ascii")
    command = f"powershell -NoProfile -NonInteractive -EncodedCommand {encoded}"
    raw, error = _ssh_read(host, nucuser, nucpass, command, timeout=120)
    if error:
        return None, error
    if not raw:
        return None, f"No output from NUC {host}"
    try:
        parsed = json.loads(raw[raw.find("{"):]) if "{" in raw else None
    except (ValueError, TypeError):
        parsed = None
    if not isinstance(parsed, dict):
        return None, f"Could not read disk health from NUC {host}: {raw[:200]}"
    info = _summarize_nuc_disk_health(unit, parsed)
    info["host"] = host
    return info, None



def camera_reachability_matrix(unit):
    """
    Reach every camera, the fisheye and the speaker for a unit in one pass.

    Pings run concurrently, so the whole matrix costs about as long as the
    slowest single endpoint rather than the sum of them.
    Returns (info, error).
    """
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    cameras, error = list_unit_cameras(unit)
    if error:
        return None, error

    targets = [
        {"target": cam["target"], "label": cam["label"], "host": cam["host"]}
        for cam in (cameras or [])
    ]
    row = _net_row_for_unit(unit)
    speaker_ip = _host_only(row[4] if row and len(row) > 4 else "")
    if speaker_ip:
        targets.append({"target": "speaker", "label": "Speaker", "host": speaker_ip})

    if not targets:
        return None, f"No camera or speaker IPs in the net sheet for {unit}"

    def check(item):
        code, output = _ping_host(item["host"], max_echoes=2, stop_on_success=True)
        return {
            **item,
            "reachable": _ping_reachable(output),
            "returncode": code,
        }

    results = []
    with ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
        futures = {pool.submit(check, item): item for item in targets}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                item = futures[future]
                results.append({**item, "reachable": False, "error": str(exc)})

    order = {"fisheye": 0, "camera1": 1, "camera2": 2, "camera3": 3, "camera4": 4, "speaker": 5}
    results.sort(key=lambda item: order.get(item.get("target"), 99))

    down = [item["label"] for item in results if not item.get("reachable")]
    up_count = len(results) - len(down)
    if not down:
        status, summary = "ok", f"All {len(results)} endpoints reachable on {unit}"
    elif up_count == 0:
        status, summary = "fail", f"No endpoints reachable on {unit} — check the switch or router"
    else:
        status, summary = "warn", f"{len(down)} of {len(results)} unreachable on {unit}: " + ", ".join(down)

    return {
        "unit": unit,
        "status": status,
        "summary": summary,
        "endpoints": results,
        "down": down,
        "reachable_count": up_count,
        "total": len(results),
    }, None
def hikvision_analytics_status(unit):
    """
    Field/Line Detection rule state on a Hikvision unit's cameras, read over
    plain HTTP (ISAPI) with the same fishuser/fishpass creds as the fisheye
    snapshot. Reports what's configured — enabled or not — rather than
    judging whether it should be; that's an operational call, not this
    function's.

    Hikvision only (MU sites). Dahua's cgi-bin analytics endpoint was checked
    directly against two fisheye units and wasn't reachable on either — every
    /cgi-bin/ path 404'd, not just the analytics one — so there is no Dahua
    equivalent here yet. Returns (info, error).
    """
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    cameras, error = list_unit_cameras(unit)
    if error:
        return None, error
    if not is_hikvision_unit(unit, cameras=cameras):
        return None, f"{unit} is not a Hikvision unit — analytics status is only available for Hikvision cameras"

    load_dotenv(env_path)
    fishuser = os.getenv("fishuser")
    fishpass = os.getenv("fishpass")
    if not fishuser or not fishpass:
        return None, "Set fishuser/fishpass in .env — camera analytics status uses the same creds as fisheye snapshots"

    camera_targets = [cam for cam in (cameras or []) if cam.get("target") != "fisheye" and cam.get("host")]
    if not camera_targets:
        return None, f"No camera IPs in the net sheet for {unit}"

    rule_paths = (
        ("field_detection", "Field Detection", "/ISAPI/Smart/FieldDetection/1"),
        ("line_detection", "Line Detection", "/ISAPI/Smart/LineDetection/1"),
    )

    def _rule_enabled(xml_bytes):
        try:
            root = ElementTree.fromstring(xml_bytes)
        except ElementTree.ParseError:
            return None
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] == "enabled":
                return (el.text or "").strip().lower() == "true"
        return None

    def check_camera(cam):
        host = cam["host"]
        result = {"target": cam.get("target"), "label": cam.get("label"), "host": host, "rules": {}}
        for key, label, path in rule_paths:
            url = f"http://{host}{path}"
            rule = {"label": label}
            try:
                resp = requests.get(url, auth=HTTPDigestAuth(fishuser, fishpass), timeout=10)
                if resp.status_code == 401:
                    resp = requests.get(url, auth=HTTPBasicAuth(fishuser, fishpass), timeout=10)
                if resp.status_code == 200:
                    rule["reachable"] = True
                    rule["enabled"] = _rule_enabled(resp.content)
                else:
                    rule["reachable"] = False
                    rule["http_status"] = resp.status_code
            except requests.RequestException as exc:
                rule["reachable"] = False
                rule["error"] = str(exc)
            result["rules"][key] = rule
        return result

    with ThreadPoolExecutor(max_workers=min(8, len(camera_targets))) as pool:
        results = list(pool.map(check_camera, camera_targets))

    reachable_count = sum(
        1 for r in results if any(rule.get("reachable") for rule in r["rules"].values())
    )
    if reachable_count == len(results):
        status = "ok"
    elif reachable_count == 0:
        status = "fail"
    else:
        status = "warn"

    enabled_summary = [
        f"{r['label']} {rule['label']}"
        for r in results
        for rule in r["rules"].values()
        if rule.get("reachable") and rule.get("enabled")
    ]
    summary = f"Analytics reachable on {reachable_count}/{len(results)} camera(s) on {unit}"
    summary += f" — enabled: {', '.join(enabled_summary)}" if enabled_summary else " — no rules enabled"

    return {
        "unit": unit,
        "status": status,
        "summary": summary,
        "cameras": results,
    }, None
def run_unit_diagnostics(unit):
    """
    Every read-only check that applies to a unit, in one call — the 3 AM button.

    Each check is independent: one failing (no PVE, smartctl missing, SSH
    refused) records its error and the rest still run. Returns (info, error);
    error is only set when the unit itself cannot be resolved.
    """
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    row = ensure_unit_net_info(unit)
    if not row:
        return None, f"Unit {unit} not found in net sheet"

    has_pve = uses_pve(unit)
    checks = [
        ("connectivity", "Connectivity", lambda: validate_unit_full(unit)),
        ("cameras", "Camera reachability", lambda: camera_reachability_matrix(unit)),
    ]
    if has_pve:
        checks.extend([
            ("services", "Platform services", lambda: scrypted_service_status(unit)),
            ("pve_host", "PVE host resources", lambda: pve_host_resources(unit)),
            ("nvme", "NVMe health", lambda: pve_nvme_health(unit)),
        ])
    else:
        checks.append(("nuc_host", "NUC resources", lambda: nuc_host_resources(unit)))

    results = {}
    problems = []
    # Sequential on purpose: these SSH into the same two hosts, and a NOC
    # box hammering one unit with five concurrent sessions is how you get
    # sshd rate-limiting in the middle of an outage.
    for key, label, fn in checks:
        try:
            info, error = fn()
        except Exception as exc:
            info, error = None, str(exc)
        if error or info is None:
            results[key] = {"label": label, "ok": False, "error": error or "no result"}
            problems.append(f"{label}: {error or 'no result'}")
            continue
        status = info.get("status") if isinstance(info, dict) else None
        entry = {"label": label, "ok": True, "result": info}
        if status:
            entry["status"] = status
            if status != "ok":
                problems.append(f"{label}: {info.get('summary') or status}")
        results[key] = entry

    if not problems:
        summary = f"All checks passed for {unit}"
        status = "ok"
    else:
        summary = f"{len(problems)} issue(s) found on {unit}"
        status = "fail"

    return {
        "unit": unit,
        "status": status,
        "summary": summary,
        "problems": problems,
        "checks": results,
        "has_pve": has_pve,
    }, None
NVME_SMART_DEFAULT_DEVICE = "/dev/nvme0n1"
# Percentage Used at or above this is worth flagging — NVMe rates endurance
# as a percentage of rated writes, so 100% means the drive has burned through
# its warranty life (it usually keeps working, but plan a swap).
NVME_WEAR_WARN_PERCENT = 80
def _parse_nvme_smart(text):
    """
    Pull the fields worth reading out of `smartctl -a` NVMe output.

    Returns a dict with whatever was found; missing keys simply stay absent
    so a different smartctl version or a SATA disk degrades to raw output
    instead of raising.
    """
    info = {}
    patterns = {
        "overall_health": r"SMART overall-health self-assessment test result:\s*(\S+)",
        "model": r"Model Number:\s*(.+)",
        "serial": r"Serial Number:\s*(.+)",
        "firmware": r"Firmware Version:\s*(.+)",
        "critical_warning": r"Critical Warning:\s*(\S+)",
        "temperature_c": r"Temperature:\s*(\d+) Celsius",
        "available_spare": r"Available Spare:\s*(\d+)%",
        "available_spare_threshold": r"Available Spare Threshold:\s*(\d+)%",
        "percentage_used": r"Percentage Used:\s*(\d+)%",
        "power_on_hours": r"Power On Hours:\s*([\d,\s]+)",
        "power_cycles": r"Power Cycles:\s*([\d,\s]+)",
        "unsafe_shutdowns": r"Unsafe Shutdowns:\s*([\d,\s]+)",
        "media_errors": r"Media and Data Integrity Errors:\s*([\d,\s]+)",
        "error_log_entries": r"Error Information Log Entries:\s*([\d,\s]+)",
        "data_units_written": r"Data Units Written:\s*([\d,\s]+)",
        # NVMe spec's own composite-temperature counters — cumulative
        # MINUTES the drive's temperature has spent at/above the
        # warning/critical threshold, not just its instantaneous reading
        # above. A drive can read a perfectly normal temperature right now
        # and still have a nonzero count here from an earlier thermal
        # event (e.g. a cooling problem that's since cleared) — this is
        # the field that catches that history.
        "warning_temp_time": r"Warning\s+Comp\.?\s*Temperature Time:\s*([\d,\s]+)",
        "critical_temp_time": r"Critical\s+Comp\.?\s*Temperature Time:\s*([\d,\s]+)",
    }
    numeric_keys = (
        "temperature_c", "available_spare", "available_spare_threshold",
        "percentage_used", "power_on_hours", "power_cycles",
        "unsafe_shutdowns", "media_errors", "error_log_entries",
        "warning_temp_time", "critical_temp_time",
    )
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if not match:
            continue
        value = match.group(1).strip()
        if key in numeric_keys:
            # smartctl thousand-separates counters ("15,203" / "24 551 238").
            # Text fields like Model Number keep their internal spaces.
            try:
                info[key] = int(re.sub(r"[,\s]", "", value))
            except (TypeError, ValueError):
                info[key] = value
        else:
            info[key] = value
    return info
def _nvme_health_verdict(info):
    """
    Reduce parsed SMART fields to (status, [reasons]) for the dashboard LED.

    status is "ok", "warn" or "fail". Deliberately conservative: anything we
    could not read leaves the status alone rather than inventing a problem.
    """
    reasons = []
    status = "ok"

    health = str(info.get("overall_health") or "").upper()
    if health and health != "PASSED":
        status = "fail"
        reasons.append(f"overall-health {health}")

    warning = str(info.get("critical_warning") or "").strip()
    if warning and warning not in ("0x00", "0x0000", "0"):
        status = "fail"
        reasons.append(f"critical warning {warning}")

    media_errors = info.get("media_errors")
    if isinstance(media_errors, int) and media_errors > 0:
        status = "fail"
        reasons.append(f"{media_errors} media/data integrity errors")

    spare = info.get("available_spare")
    threshold = info.get("available_spare_threshold")
    if isinstance(spare, int) and isinstance(threshold, int) and spare <= threshold:
        status = "fail"
        reasons.append(f"available spare {spare}% at/below threshold {threshold}%")

    used = info.get("percentage_used")
    if isinstance(used, int) and used >= NVME_WEAR_WARN_PERCENT:
        if status == "ok":
            status = "warn"
        reasons.append(f"{used}% of rated endurance used")

    temp = info.get("temperature_c")
    if isinstance(temp, int) and temp >= 70:
        if status == "ok":
            status = "warn"
        reasons.append(f"{temp}C drive temperature")

    # These catch a thermal event the CURRENT reading above can miss
    # entirely — the drive may read perfectly normal right now and still
    # have spent real time over threshold earlier (a cooling problem
    # that's since cleared, a hot rack during a heat wave).
    critical_temp_time = info.get("critical_temp_time")
    if isinstance(critical_temp_time, int) and critical_temp_time > 0:
        status = "fail"
        reasons.append(f"critical temperature threshold hit ({critical_temp_time} min total)")

    warning_temp_time = info.get("warning_temp_time")
    if isinstance(warning_temp_time, int) and warning_temp_time > 0:
        if status == "ok":
            status = "warn"
        reasons.append(f"warning temperature threshold hit ({warning_temp_time} min total)")

    return status, reasons
def pve_nvme_health(unit, device=None):
    """
    SSH to the unit's PVE host and read NVMe SMART health with smartctl.

    Read-only — smartctl -a only reports, it does not start a self-test.
    Returns (info, error). info carries the parsed fields, a status of
    "ok"/"warn"/"fail", a one-line summary, and the raw smartctl output.
    """
    load_dotenv(env_path)
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    device = str(device or NVME_SMART_DEFAULT_DEVICE).strip() or NVME_SMART_DEFAULT_DEVICE
    # Path only — this is interpolated into a remote shell command.
    if not re.fullmatch(r"/dev/[A-Za-z0-9/_-]+", device):
        return None, f"Refusing unexpected device path: {device}"

    row = ensure_unit_net_info(unit, needed_indexes=(11,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[11] if len(row) > 11 else "")
    if not ip:
        return None, f"No PVE IP for {unit}"
    username, password, cred_error = _pve_ssh_credentials()
    if cred_error:
        return None, cred_error

    command = f"smartctl -a {shlex.quote(device)} 2>&1; echo __RC__=$?"
    client = paramiko.SSHClient()
    try:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=ip,
            port=22,
            username=username,
            password=password,
            timeout=30,
            allow_agent=False,
            look_for_keys=False,
        )
        _stdin, stdout, stderr = client.exec_command(command, timeout=90)
        raw = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace").strip()
    except paramiko.AuthenticationException:
        return None, (
            f"PVE SSH authentication failed for {username}@{ip}. "
            "SSH uses the Linux user only (usually root), not root@pam. "
            "Set pvesshuser=root and pvepass in .env."
        )
    except Exception as exc:
        return None, f"PVE SSH to {ip} failed: {exc}"
    finally:
        client.close()

    returncode = None
    match = re.search(r"__RC__=(\d+)\s*$", raw)
    if match:
        returncode = int(match.group(1))
        raw = raw[:match.start()]
    raw = raw.strip()

    if "command not found" in raw.lower() or returncode == 127:
        return None, (
            f"smartctl is not installed on the PVE host for {unit} "
            f"({ip}). Install it there with: apt-get install -y smartmontools"
        )
    if not raw:
        return None, f"No smartctl output from {ip}{(' — ' + err) if err else ''}"
    if re.search(r"Unable to detect device type|No such device|failed: INQUIRY", raw, re.I):
        return None, (
            f"smartctl could not read {device} on {unit} ({ip}). "
            f"Run `lsblk -d -o NAME,SIZE,MODEL` there to find the right device."
        )

    info = _parse_nvme_smart(raw)
    status, reasons = _nvme_health_verdict(info)

    parts = []
    if info.get("percentage_used") is not None:
        parts.append(f"{info['percentage_used']}% used")
    if info.get("available_spare") is not None:
        parts.append(f"{info['available_spare']}% spare")
    if info.get("temperature_c") is not None:
        parts.append(f"{info['temperature_c']}C")
    if info.get("power_on_hours") is not None:
        parts.append(f"{info['power_on_hours']}h powered on")
    detail = ", ".join(parts) if parts else (info.get("overall_health") or "see output")

    if status == "ok":
        summary = f"NVMe on {unit} looks healthy — {detail}"
    else:
        summary = f"NVMe on {unit} needs attention ({'; '.join(reasons)}) — {detail}"

    info.update({
        "unit": unit,
        "host": ip,
        "device": device,
        "status": status,
        "reasons": reasons,
        "summary": summary,
        "returncode": returncode,
        "output": raw,
    })
    return info, None
# Storage-related I/O/filesystem/ATA/NVMe error terms — shared by both the
# dmesg and journalctl -k greps in pve_kernel_io_errors below. Deliberately
# narrower than a bare "reset|timeout|abort" (which also matches routine,
# unrelated USB/network resets in these logs) — ata/nvme prefixed so only
# a storage controller's own reset/timeout/abort counts.
_PVE_IO_ERROR_PATTERN = (
    r"I/O error"
    r"|blk_update_request"
    r"|critical medium error"
    r"|ata[0-9]+.*(exception|error|reset)"
    r"|nvme[0-9]*n?[0-9]*.*(error|timeout|reset|abort)"
    r"|EXT4-fs error"
    r"|EXT4-fs.*remount.*read-only"
    r"|XFS.*(error|corrupt)"
    r"|btrfs.*(error|corrupt)"
    r"|remounting filesystem read-only"
    r"|Unrecoverable error"
)
def _pve_ssh_target(unit):
    """(ip, username, password, error) for the unit's PVE host — shared setup for the three checks below."""
    unit = str(unit or "").strip()
    if not unit:
        return None, None, None, "Missing unit"
    row = ensure_unit_net_info(unit, needed_indexes=(11,))
    if not row:
        return None, None, None, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[11] if len(row) > 11 else "")
    if not ip:
        return None, None, None, f"No PVE IP for {unit}"
    ssh_username, ssh_password, cred_error = _pve_ssh_credentials()
    if cred_error:
        return None, None, None, cred_error
    return ip, ssh_username, ssh_password, None
def _pve_ssh_read(ip, ssh_username, ssh_password, command, timeout=60):
    """_ssh_read, but with the same actionable auth-failure hint pve_nvme_health gives."""
    raw, error = _ssh_read(ip, ssh_username, ssh_password, command, timeout=timeout)
    if error and "authentication failed" in error.lower():
        return raw, (
            f"{error}. SSH uses the Linux user only (usually root), not root@pam. "
            "Set pvesshuser=root and pvepass in .env."
        )
    return raw, error
def pve_kernel_io_errors(unit, journal_days=30):
    """
    SSH to the unit's PVE host and grep for storage I/O/NVMe/ATA/filesystem
    error signatures — read-only, grep only reports. Two sources in one SSH
    round trip:
      - `dmesg -T`: the kernel ring buffer, only covers since the host's
        last boot (it doesn't persist across reboots).
      - `journalctl -k --since <journal_days> days ago`: the persisted
        journal, so it also catches an error from an earlier boot that
        dmesg's buffer has since dropped.
    Returns (info, error).
    """
    load_dotenv(env_path)
    try:
        journal_days = int(journal_days)
    except (TypeError, ValueError):
        journal_days = 30
    journal_days = max(1, min(journal_days, 365))

    ip, ssh_username, ssh_password, error = _pve_ssh_target(unit)
    if error:
        return None, error
    unit = str(unit or "").strip()

    pattern = shlex.quote(_PVE_IO_ERROR_PATTERN)
    since = shlex.quote(f"{journal_days} days ago")
    command = (
        "echo __DMESG__; "
        f"dmesg -T 2>&1 | grep -iE {pattern} | tail -n 40; "
        "echo __JOURNAL__; "
        f"journalctl -k --since {since} --no-pager 2>&1 | grep -iE {pattern} | tail -n 100"
    )
    raw, error = _pve_ssh_read(ip, ssh_username, ssh_password, command)
    if error:
        return None, error

    dmesg_section, _, journal_section = (raw or "").partition("__JOURNAL__")
    dmesg_lines = [
        line for line in dmesg_section.replace("__DMESG__", "").splitlines() if line.strip()
    ]
    journal_lines = [line for line in journal_section.splitlines() if line.strip()]

    if dmesg_lines or journal_lines:
        status = "fail" if (len(dmesg_lines) + len(journal_lines)) >= 10 else "warn"
        summary = (
            f"{unit} ({ip}): {len(dmesg_lines)} I/O error line(s) in dmesg (since last boot), "
            f"{len(journal_lines)} in the last {journal_days}d of journal"
        )
    else:
        status = "ok"
        summary = f"{unit} ({ip}): no I/O errors in dmesg or the last {journal_days}d of journal"

    return {
        "unit": unit,
        "host": ip,
        "status": status,
        "summary": summary,
        "journal_days": journal_days,
        "dmesg_error_count": len(dmesg_lines),
        "dmesg_lines": dmesg_lines,
        "journal_error_count": len(journal_lines),
        "journal_lines": journal_lines,
    }, None
def pve_boot_errors(unit):
    """
    SSH to the unit's PVE host and read every error-or-worse (err/crit/
    alert/emerg) journal entry since the host's last boot — read-only.

    Broader net than pve_kernel_io_errors: not limited to the kernel
    facility or to I/O-shaped wording, so it also catches a service
    (mdadm, zed/ZFS, a filesystem repair tool) reporting real trouble
    through its own log lines that never go through dmesg at all.
    Returns (info, error).
    """
    load_dotenv(env_path)
    ip, ssh_username, ssh_password, error = _pve_ssh_target(unit)
    if error:
        return None, error
    unit = str(unit or "").strip()

    command = "journalctl -b -p err --no-pager 2>&1 | tail -n 100"
    raw, error = _pve_ssh_read(ip, ssh_username, ssh_password, command)
    if error:
        return None, error

    lines = [
        line for line in (raw or "").splitlines()
        if line.strip() and "-- No entries --" not in line and "-- Boot " not in line
    ]

    if lines:
        status = "fail" if len(lines) >= 10 else "warn"
        summary = f"{unit} ({ip}): {len(lines)} error-or-worse journal entr{'y' if len(lines) == 1 else 'ies'} since last boot"
    else:
        status = "ok"
        summary = f"{unit} ({ip}): no error-or-worse journal entries since last boot"

    return {
        "unit": unit,
        "host": ip,
        "status": status,
        "summary": summary,
        "error_count": len(lines),
        "lines": lines,
    }, None
def pve_filesystem_health(unit):
    """
    SSH to the unit's PVE host and check whether a filesystem is already
    mounted read-only — read-only itself (findmnt/lsblk only report).

    ext4's default errors=remount-ro mount option means a box that hit
    persistent I/O errors often SILENTLY remounts root read-only rather
    than crashing — services keep running (until they try to write) and
    nothing pages anyone, so this is the single clearest "this already
    happened" signal on the box: cheaper and more certain than inferring
    it from log grepping. lsblk's own RO column backstops findmnt for any
    OTHER mounted block device besides root.
    Returns (info, error).
    """
    load_dotenv(env_path)
    ip, ssh_username, ssh_password, error = _pve_ssh_target(unit)
    if error:
        return None, error
    unit = str(unit or "").strip()

    command = (
        "echo __FINDMNT__; "
        "findmnt -P -no SOURCE,FSTYPE,OPTIONS / 2>&1; "
        "echo __LSBLK__; "
        "lsblk -P -o NAME,RO,RM,SIZE,FSTYPE,MOUNTPOINT 2>&1"
    )
    raw, error = _pve_ssh_read(ip, ssh_username, ssh_password, command)
    if error:
        return None, error

    findmnt_section, _, lsblk_section = (raw or "").partition("__LSBLK__")
    findmnt_section = findmnt_section.replace("__FINDMNT__", "").strip()

    def _parse_pairs(line):
        return dict(re.findall(r'(\w+)="([^"]*)"', line))

    findmnt_line = next((l for l in findmnt_section.splitlines() if l.strip()), "")
    findmnt_info = _parse_pairs(findmnt_line) if findmnt_line else {}
    root_options = findmnt_info.get("OPTIONS", "")
    root_fs_read_only = bool(root_options) and "ro" in root_options.split(",")

    read_only_devices = []
    for line in lsblk_section.splitlines():
        if not line.strip():
            continue
        info = _parse_pairs(line)
        mount = info.get("MOUNTPOINT", "")
        # RM=1 (removable, e.g. a CD-ROM entry Proxmox sometimes lists) is
        # legitimately read-only and not a finding. Also require an actual
        # MOUNTPOINT — caught live on RD3320: Proxmox's own LVM-thin data
        # volume (`pve-data`, the thin pool's own plumbing LV, no FSTYPE,
        # never mounted) always reports RO=1 on every stock Proxmox host,
        # which would otherwise flag every single one of them as "failed".
        if info.get("RO") == "1" and info.get("RM") != "1" and mount:
            name = info.get("NAME", "?")
            read_only_devices.append(f"{name} ({mount})")

    if root_fs_read_only or read_only_devices:
        status = "fail"
        parts = []
        if root_fs_read_only:
            parts.append(f"root ({findmnt_info.get('SOURCE', '/')}) is mounted read-only")
        if read_only_devices:
            parts.append("read-only device(s): " + ", ".join(read_only_devices))
        summary = f"{unit} ({ip}): " + "; ".join(parts)
    else:
        status = "ok"
        summary = f"{unit} ({ip}): root filesystem and all block devices are read-write"

    return {
        "unit": unit,
        "host": ip,
        "status": status,
        "summary": summary,
        "root_fs_read_only": root_fs_read_only,
        "root_fs_source": findmnt_info.get("SOURCE", ""),
        "root_fs_fstype": findmnt_info.get("FSTYPE", ""),
        "root_fs_options": root_options,
        "read_only_devices": read_only_devices,
    }, None
def pve_link_stats(unit):
    """
    SSH to the unit's PVE host and read `ip -s link` — read-only, a pure
    stats dump. Uses `-j` (JSON) rather than scraping the columnar text
    output, which iproute2 has changed the spacing/column-set of before;
    confirmed live (2026-09-30, iproute2 6.1.0) that JSON stats live under
    stats64.rx/tx with errors/dropped/over_errors (RX) and
    errors/dropped/carrier_errors/collisions (TX) — any interface with a
    nonzero value in any of those is flagged, so a tech scanning a box with
    a dozen interfaces (physical NICs, the bond, the bridge, per-VM taps)
    doesn't have to eyeball every row by hand. Flagged interfaces are
    listed first in the result, ahead of the full interface list.
    Returns (info, error).
    """
    load_dotenv(env_path)
    ip, ssh_username, ssh_password, error = _pve_ssh_target(unit)
    if error:
        return None, error
    unit = str(unit or "").strip()

    raw, error = _pve_ssh_read(ip, ssh_username, ssh_password, "ip -j -s link 2>&1")
    if error:
        return None, error
    raw = (raw or "").strip()
    if not raw:
        return None, f"No `ip -s link` output from {ip}"
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None, f"Could not parse `ip -s link` JSON output from {ip} (unexpected iproute2 version?): {raw[:200]}"
    if not isinstance(parsed, list):
        return None, f"Unexpected `ip -s link` JSON shape from {ip}"

    def _n(d, key):
        try:
            return int((d or {}).get(key) or 0)
        except (TypeError, ValueError):
            return 0

    interfaces = []
    for item in parsed:
        stats = item.get("stats64") or item.get("stats") or {}
        rx = stats.get("rx") or {}
        tx = stats.get("tx") or {}
        rx_errors = _n(rx, "errors")
        rx_dropped = _n(rx, "dropped")
        rx_over_errors = _n(rx, "over_errors")
        tx_errors = _n(tx, "errors")
        tx_dropped = _n(tx, "dropped")
        tx_carrier_errors = _n(tx, "carrier_errors")
        tx_collisions = _n(tx, "collisions")
        flagged = bool(
            rx_errors or rx_dropped or rx_over_errors
            or tx_errors or tx_dropped or tx_carrier_errors or tx_collisions
        )
        interfaces.append({
            "name": item.get("ifname") or "?",
            "state": item.get("operstate") or "",
            "flags": item.get("flags") or [],
            "rx_bytes": _n(rx, "bytes"),
            "rx_packets": _n(rx, "packets"),
            "rx_errors": rx_errors,
            "rx_dropped": rx_dropped,
            "rx_over_errors": rx_over_errors,
            "tx_bytes": _n(tx, "bytes"),
            "tx_packets": _n(tx, "packets"),
            "tx_errors": tx_errors,
            "tx_dropped": tx_dropped,
            "tx_carrier_errors": tx_carrier_errors,
            "tx_collisions": tx_collisions,
            "flagged": flagged,
        })

    if not interfaces:
        return None, f"No interfaces parsed from `ip -s link` on {ip}"

    flagged_interfaces = [iface for iface in interfaces if iface["flagged"]]
    if flagged_interfaces:
        status = "warn"
        summary = (
            f"{unit} ({ip}): {len(flagged_interfaces)} of {len(interfaces)} interface(s) "
            "have dropped packets or errors: "
            + ", ".join(iface["name"] for iface in flagged_interfaces)
        )
    else:
        status = "ok"
        summary = f"{unit} ({ip}): all {len(interfaces)} interfaces clean — no drops or errors"

    return {
        "unit": unit,
        "host": ip,
        "status": status,
        "summary": summary,
        "interfaces": interfaces,
        "flagged_interfaces": flagged_interfaces,
    }, None
def _zabbix_call(method, params):
    """One JSON-RPC call to the Zabbix API. Raises on transport/API error."""
    url = (os.getenv("zab_url") or "").strip()
    token = (os.getenv("zab_token") or "").strip()
    if not url or not token:
        raise RuntimeError("Set zab_url/zab_token in .env — Zabbix lookups need API access")
    response = requests.post(
        url,
        json={"jsonrpc": "2.0", "method": method, "params": params, "auth": token, "id": 1},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message") or str(data["error"]))
    return data.get("result")

# Zabbix hosts are named "<unit>-<devicetype>" (RD3422-Switch, MU1041-Switch,
# RD3524-SNUC-PVE, ...). Device type itself sometimes contains a hyphen
# (SNUC-PVE/SNUC-Watch/SNUC-Win), so this anchors on the unit prefix
# (RD/FD/MU + digits) rather than trying to enumerate every device type.
_ZABBIX_HOST_UNIT_RE = re.compile(r"^((?:RD|FD|MU)\d+)-(.+)$", re.IGNORECASE)


# Rough, FIXED (no DST) UTC offset per region code — good enough to place a
# Zabbix event in "early morning" vs "midday," not precise to the hour.
# Zabbix hosts carry no per-unit timezone the way VRM installations do (see
# _resolve_vrm_site's timezone_name), so this is the best available without
# one. PHX is exact year-round (Arizona doesn't observe DST); the others
# drift up to an hour off during DST (roughly March-November) — stated
# here rather than silently assumed away.
_REGION_UTC_OFFSET_HOURS = {
    "PHX": -7,
    "LAX": -8, "OAK": -8,
    "SLC": -7, "DEN": -7,
    "HOU": -6,
}
# A down-event has to START in this LOCAL hour range to count as
# "early morning" — before a reasonable sunrise, fleet-wide.
_EARLY_MORNING_DOWN_HOURS = (3, 6)
# ...and recover (resolve) within this LOCAL hour range — mid-morning,
# consistent with solar output ramping back up enough to run the unit
# again. Wide on purpose: exact recovery time depends on season and how
# depleted the battery got, not just sunrise.
_EARLY_MORNING_RECOVERY_HOURS = (7, 12)
# A single occurrence could be anything (a real network blip, a manual
# reboot). Require it on at least this many DISTINCT days in the lookback
# window before calling it a pattern.
_EARLY_MORNING_MIN_DAYS = 3
# Reachability-flavored trigger names worth checking — deliberately a
# substring allowlist, not every Zabbix trigger on the host (a CPU or swap
# alarm firing at 4am says nothing about power).
_REACHABILITY_TRIGGER_SUBSTRINGS = ("unavailable", "not available", "no response")


def detect_early_morning_outage_pattern(unit, region_code=None, days=21):
    """
    For a unit with NO VRM trailer to check directly — the telemetry-free
    equivalent of detect_solar_shading / detect_dead_panel, using what
    Zabbix can see instead: if overnight battery reserve isn't enough to
    last until the sun is back up, the unit browns out and its NUC/router
    goes unreachable, then it comes back once solar starts producing
    again. Looks for that specific pattern — unreachable starting in the
    early-morning hours, recovering mid-morning — recurring on multiple
    distinct days, using each Zabbix event's own r_eventid to pair a
    problem with its actual resolution (not just sequential guessing).

    This does NOT distinguish shading from a dead panel from an
    undersized battery for that site's load — all three would produce the
    same reachability signature. It also cannot fire for a unit with no
    resolvable region (no PHX/LAX/OAK/HOU/SLC/DEN in its subject) since
    there's nothing to place "early morning" against.

    Returns (found, detail, confidence, matching_days) where found is
    True/False/None (a lookup problem — see detail), matching_days lists
    the dates (as strings) the pattern was seen on.
    """
    region = str(region_code or "").strip().upper()
    utc_offset = _REGION_UTC_OFFSET_HOURS.get(region)
    if utc_offset is None:
        return None, f"No resolvable region for this unit's local time (checked: {region or 'none'})", None, []

    unit_key = str(unit or "").strip().upper()
    if not unit_key:
        return None, "Invalid unit", None, []
    try:
        hosts = _zabbix_call("host.get", {
            "output": ["hostid", "host"],
            "search": {"host": unit_key},
        })
    except Exception as exc:
        return None, f"Zabbix host lookup failed: {exc}", None, []
    # Router is present on every unit regardless of NUC vs PVE; NUC/SNUC-*
    # cover the compute side on units that have one.
    reachability_hosts = [
        h for h in (hosts or [])
        if h.get("host", "").upper().startswith(unit_key + "-")
        and any(tag in h["host"].upper() for tag in ("ROUTER", "NUC", "SNUC"))
    ]
    if not reachability_hosts:
        return None, f"No Zabbix Router/NUC host found for {unit_key}", None, []
    hostids = [h["hostid"] for h in reachability_hosts]

    try:
        events = _zabbix_call("event.get", {
            "output": ["eventid", "clock", "value", "name", "r_eventid"],
            "hostids": hostids,
            "source": 0, "object": 0,
            "time_from": int(time.time()) - days * 86400,
            "sortfield": ["clock"], "sortorder": "ASC",
        })
    except Exception as exc:
        return None, f"Zabbix event lookup failed: {exc}", None, []

    problems_by_id = {
        e["eventid"]: e for e in (events or [])
        if e.get("value") == "1"
        and any(tag in str(e.get("name") or "").lower() for tag in _REACHABILITY_TRIGGER_SUBSTRINGS)
    }
    resolutions_by_id = {e["eventid"]: e for e in (events or []) if e.get("value") == "0"}
    if not problems_by_id:
        return False, (
            f"No reachability problem events (ICMP/agent unavailable) on {unit_key}'s "
            f"Router/NUC host(s) in the last {days}d"
        ), None, []

    matching_dates = set()
    total_reachability_events = len(problems_by_id)
    for problem in problems_by_id.values():
        r_id = problem.get("r_eventid")
        resolution = resolutions_by_id.get(r_id) if r_id and r_id != "0" else None
        if not resolution:
            continue  # still open, or resolved by a resolution event outside this window
        down_local_hour = (datetime.utcfromtimestamp(int(problem["clock"])) + timedelta(hours=utc_offset)).hour
        up_time = datetime.utcfromtimestamp(int(resolution["clock"])) + timedelta(hours=utc_offset)
        up_local_hour = up_time.hour
        if (_EARLY_MORNING_DOWN_HOURS[0] <= down_local_hour <= _EARLY_MORNING_DOWN_HOURS[1]
                and _EARLY_MORNING_RECOVERY_HOURS[0] <= up_local_hour <= _EARLY_MORNING_RECOVERY_HOURS[1]):
            matching_dates.add(up_time.date().isoformat())

    if len(matching_dates) < _EARLY_MORNING_MIN_DAYS:
        return False, (
            f"{len(matching_dates)} early-morning-down/mid-morning-recovery day(s) in the last {days}d "
            f"({total_reachability_events} reachability event(s) total) — below the "
            f"{_EARLY_MORNING_MIN_DAYS}-day pattern threshold"
        ), None, sorted(matching_dates)

    # Confidence scales with how many distinct days showed the pattern —
    # capped well short of certain, same principle as the VRM-based
    # checks: this is a recurring-symptom match, not a direct measurement,
    # and a genuine network/ISP issue at the same time of day (not power)
    # would look identical here.
    confidence = max(35, min(80, round(35 + len(matching_dates) * 6)))
    detail = (
        f"{len(matching_dates)} day(s) in the last {days}d where {unit_key} went unreachable "
        f"between {_EARLY_MORNING_DOWN_HOURS[0]}-{_EARLY_MORNING_DOWN_HOURS[1]} (approx. local, region {region}) "
        f"and recovered between {_EARLY_MORNING_RECOVERY_HOURS[0]}-{_EARLY_MORNING_RECOVERY_HOURS[1]} — "
        f"consistent with insufficient overnight battery reserve (shading, a dead panel, or an "
        f"undersized array for this site's load all look the same here)"
    )
    return True, detail, confidence, sorted(matching_dates)


ZABBIX_PROBLEM_MAX_AGE_DAYS = 7


def zabbix_active_problems_by_unit(max_age_days=ZABBIX_PROBLEM_MAX_AGE_DAYS):
    """
    Every currently-active Zabbix problem within the last max_age_days,
    fleet-wide in two calls, grouped by unit. Read-only (problem.get /
    trigger.get — neither acknowledges or closes anything). Returns
    ({unit: [problem, ...]}, error).

    Andrew's own request, 2026-09-16: a problem that's been open for
    weeks isn't useful NOC-alert noise the way a fresh one is — by the
    time something has sat open that long, either nobody's chasing it as
    an active problem or it belongs on a different, slower-moving list
    entirely, not mixed in with what a tech should look at right now.
    Filtered by "clock" (problem.get's own open-since timestamp) before
    the trigger/host lookup, so an old problem also doesn't cost a
    trigger.get round trip for a host that would just get filtered out
    anyway. max_age_days=None keeps every open problem, same as before
    this filter existed, for a caller that genuinely wants the full list.

    This used to be event.get(value=1, sort by eventid DESC, limit 500) —
    which is NOT "the 500 currently active problems," it's "the 500 most
    RECENTLY FIRED problem-state events," including ones that have long
    since recovered (event.get returns historical log entries, not current
    state). Checked live (2026-09-13): that query was hitting its 500 cap
    with events all within the last ~5 hours, while problem.get — the API
    Zabbix actually provides for "what's open right now" — reported 1,432
    genuinely still-open problems fleet-wide at the same moment. Any
    problem that had been open longer than whatever it took to fire 500
    newer ones elsewhere in the fleet was invisible to this function and
    everything built on it (the alarm glyph, Power & Infra Alerts) with no
    indication anything was missing — a real, live false-negative, not a
    theoretical one.

    problem.get doesn't support selectHosts directly, so host attribution
    is a second call: trigger.get on the distinct objectids (trigger ids)
    problem.get returned, with selectHosts — one batch call for the whole
    fleet, not one per problem (checked live: ~1,400 problems, ~1.2s total
    for both calls combined).
    """
    params = {
        "output": ["eventid", "objectid", "name", "severity", "clock"],
        "recent": False,
    }
    if max_age_days is not None:
        params["time_from"] = int(time.time() - max_age_days * 86400)
    try:
        problems = _zabbix_call("problem.get", params)
    except Exception as exc:
        return None, f"Zabbix problem lookup failed: {exc}"
    problems = problems or []
    if not problems:
        return {}, None

    trigger_ids = sorted({p.get("objectid") for p in problems if p.get("objectid")})
    host_by_trigger = {}
    if trigger_ids:
        try:
            triggers = _zabbix_call("trigger.get", {
                "output": ["triggerid"],
                "triggerids": trigger_ids,
                "selectHosts": ["host"],
            })
        except Exception as exc:
            return None, f"Zabbix trigger/host lookup failed: {exc}"
        for trigger in triggers or []:
            hosts = trigger.get("hosts") or []
            if hosts:
                host_by_trigger[trigger.get("triggerid")] = str(hosts[0].get("host") or "")

    by_unit = {}
    for problem in problems:
        host_name = host_by_trigger.get(problem.get("objectid"), "")
        if not host_name:
            continue
        match = _ZABBIX_HOST_UNIT_RE.match(host_name)
        unit = match.group(1).upper() if match else host_name
        device = match.group(2) if match else ""
        by_unit.setdefault(unit, []).append({
            "device": device,
            "host": host_name,
            "name": problem.get("name"),
            "severity": int(problem.get("severity") or 0),
            "clock": int(problem.get("clock") or 0),
        })
    return by_unit, None
# Same alert SNUC-Watch fires that the camera-outage glyph looks for
# client-side (see CAMERA_OUTAGE_ALERT_PATTERN in issues_results.js) —
# kept as one regex here too rather than shipping the pattern only in JS,
# so the fleet-wide report and the per-unit glyph can't drift apart.
CAMERA_OUTAGE_ALERT_PATTERN = re.compile(
    r"camera image buffer.*remained below.*for \d+ minutes", re.IGNORECASE
)
def fleet_camera_outage_report():
    """
    Fleet-wide list of units with the SNUC-Watch "Camera image buffer on
    /mnt/ram has remained below X% for N minutes" alert currently open —
    the server-side, whole-fleet counterpart to the camera-outage glyph's
    lazy per-unit check, for a tech who wants the full list up front
    instead of finding these one command-menu open at a time. Read-only.
    Returns (rows, error).
    """
    by_unit, error = zabbix_active_problems_by_unit()
    if error:
        return None, error
    by_unit = by_unit or {}

    rows = []
    for unit, problems in by_unit.items():
        matches = [
            p for p in problems
            if CAMERA_OUTAGE_ALERT_PATTERN.search(str(p.get("name") or ""))
        ]
        if not matches:
            continue
        problem = max(matches, key=lambda p: p.get("clock") or 0)
        rows.append({
            "unit": unit,
            "name": problem.get("name"),
            "clock": problem.get("clock"),
            "has_scrypted": uses_pve(unit),
        })
    rows.sort(key=lambda r: r.get("clock") or 0)
    return rows, None
def combined_power_infra_alerts():
    """
    Zabbix's active problems and VRM's active battery alarms, merged by
    unit — two independent systems that have never been cross-referenced
    here. A unit flagged by both is the highest-confidence signal (e.g. a
    NUC Zabbix can't reach *and* a low-battery alarm on the same trailer
    points at a power problem, not a software one); a unit flagged by only
    one still surfaces, since either system alone already beats nothing.

    Correlation is mostly a plain string match on unit identifier, since
    Zabbix monitors an MU trailer's own switch under the same MU number VRM
    uses for that trailer's battery. The one crosswalk that plain matching
    can't do — an RD/FD head's own NUC/Router/Speaker problems don't share
    a name with its attached MU trailer's battery alarm — is closed with a
    single bulk ERP reverse lookup (_erp_heads_for_mu_trailers) over just
    the MU units that showed up here, not the whole fleet: each such row
    gets a "head_units" list of the RD/FD unit(s) whose ERP parent_component
    points at that trailer, and their Zabbix problems (if any) are folded
    into the row so it corroborates and sorts correctly. The ERP call is
    non-fatal — if it fails, rows still return, just without that fold-in.
    Returns ({unit: {zabbix, vrm, both}}, error) plus the two raw error
    strings if either source failed (the other source's data still comes
    back rather than failing the whole call).
    """
    zabbix_by_unit, zabbix_error = zabbix_active_problems_by_unit()
    vrm_by_unit, vrm_error = vrm_active_alarms_by_unit()
    zabbix_by_unit = zabbix_by_unit or {}
    vrm_by_unit = vrm_by_unit or {}

    units = set(zabbix_by_unit) | set(vrm_by_unit)
    mu_units = [u for u in units if u.upper().startswith("MU")]
    mu_to_heads = {}
    if mu_units:
        mu_to_heads, crosswalk_error = _erp_heads_for_mu_trailers(mu_units)
        mu_to_heads = mu_to_heads or {}
        # Non-fatal by design (rows still return without the fold-in), but
        # non-fatal must not mean silent — this exact call came back HTTP
        # 400 once the fleet passed ~200 alarmed MU units in one poll
        # (fixed with chunking in _erp_heads_for_mu_trailers) and nothing
        # printed a trace of it at the time.
        if crosswalk_error:
            print(f"combined_power_infra_alerts: ERP head crosswalk failed: {crosswalk_error}")

    # Drop MU trailers with no ERP Site linked to their Component — same
    # "not a real, currently-deployed trailer" case fleet_power_status/
    # fleet_shading_status/etc. exclude for the same reason (see
    # _fleet_vrm_installations_with_heads). Reuses the identical bulk
    # Component-site lookup, not a new call — one more chunked ERP GET
    # alongside the head crosswalk already made above.
    no_site_mus = set()
    if mu_units:
        site_cache = {}
        try:
            _fetch_erp_component_site_map(
                [_sc_component_name(u) for u in mu_units], site_cache, quiet=True,
            )
        except Exception as exc:
            # Fail open — never let a broken site lookup wipe out an
            # otherwise-working alert poll.
            print(f"combined_power_infra_alerts: ERP Site lookup failed: {exc}")
            site_cache = None
        if site_cache is not None:
            no_site_mus = {
                u for u in mu_units
                if not (site_cache.get(_sc_component_name(u)) or {}).get("site")
            }
            if no_site_mus:
                print(
                    f"combined_power_infra_alerts: {len(no_site_mus)} MU(s) have no ERP Site "
                    f"linked, excluded as inactive: {', '.join(sorted(no_site_mus))}"
                )

    rows = []
    for unit in units:
        if unit in no_site_mus:
            continue
        # own_zabbix_problems is what THIS unit's own Zabbix hosts actually
        # reported — kept separate from the fold-in below so callers that
        # care about true attribution (alarm_history, recording who is
        # really having a problem) don't double-count a head's own problem
        # under its trailer's row too.
        own_zabbix_problems = list(zabbix_by_unit.get(unit) or [])
        zabbix_problems = list(own_zabbix_problems)
        vrm_alarm = vrm_by_unit.get(unit)
        head_units = mu_to_heads.get(unit, []) if unit.upper().startswith("MU") else []
        for head in head_units:
            zabbix_problems.extend(zabbix_by_unit.get(head) or [])
        both = bool(zabbix_problems) and bool(vrm_alarm)
        max_severity = max((p["severity"] for p in zabbix_problems), default=0)
        rows.append({
            "unit": unit,
            "head_units": head_units,
            "zabbix_problems": sorted(zabbix_problems, key=lambda p: -p["severity"]),
            "own_zabbix_problems": own_zabbix_problems,
            "vrm_alarm": vrm_alarm,
            "corroborated": both,
            "max_zabbix_severity": max_severity,
        })
    # Corroborated first (both systems agree), then by worst Zabbix severity,
    # then VRM-only alarms.
    rows.sort(key=lambda r: (not r["corroborated"], -r["max_zabbix_severity"], r["vrm_alarm"] is None))
    return {
        "rows": rows,
        "zabbix_error": zabbix_error,
        "vrm_error": vrm_error,
    }, None
# One graph per (device, metric) the UI offers. Router/Switch are the only
# device types every unit has in Zabbix with an identical key namespace
# (plain ICMP checks) — NUC/SNUC-Watch/SNUC-PVE each use a different key
# namespace (system.cpu.util vs pve.cpu.utilization vs nothing at all for
# older units), so this stays scoped to what's actually universal rather
# than branching three ways for a first version.
NETWORK_LATENCY_METRICS = (
    ("router_response", "Router", "icmppingsec", "Router Ping Response Time", "s"),
    ("router_loss", "Router", "icmppingloss", "Router Ping Loss", "%"),
    ("switch_response", "Switch", "icmppingsec", "Switch Ping Response Time", "s"),
    ("switch_loss", "Switch", "icmppingloss", "Switch Ping Loss", "%"),
)
def unit_network_latency_history(unit, hours=24, loss_aggregate="avg"):
    """
    Router/Switch ICMP ping response time and loss over time, from Zabbix's
    own history — the same checks behind "ICMP Ping: High ping loss/response
    time", the single most common active-problem type on this fleet (see
    combined_power_infra_alerts's real numbers). A live SSH/ping snapshot
    only answers "is it up right now"; this answers "has it been flaky."

    loss_aggregate only affects the two *_loss charts once hours pushes
    past 7 days into Zabbix's hourly-trend data (see use_trends below) —
    "avg" (default, what the Network Latency Graphs display uses) shows a
    genuine flat plateau for an outage that spans most of an hour, but
    dilutes a real, sustained SHORTER outage (say, 20-40 minutes) down
    below any meaningful threshold once averaged across the other quiet
    minutes in that same hour — found live (2026-09-14): a real ~29-minute
    100%-loss window on RD3020 averaged to ~25-32% per hour bucket, well
    under unit_power_vs_cell_outage's 90% cutoff, so that check silently
    missed a real outage older than 7 days. "max" (what that check now
    asks for) uses the hour's own peak loss instead, which a real
    high-loss stretch of any length within the hour still hits — response-
    time metrics are unaffected either way; averaging is still the right
    read for those.
    Returns (info, error).
    """
    unit = str(unit or "").strip().upper()
    if not unit:
        return None, "Missing unit"
    try:
        hours = max(1, min(int(hours), 24 * 90))
    except (TypeError, ValueError):
        hours = 24
    # Zabbix's raw per-poll history isn't kept indefinitely — checked live:
    # still present 25 days back, gone by 30. trend.get (hourly avg/min/max,
    # kept far longer) is what 30d/90d actually use; history.get keeps the
    # native ~3min resolution for anything a week or less.
    use_trends = hours > 24 * 7

    device_names = sorted({m[1] for m in NETWORK_LATENCY_METRICS})
    host_names = [f"{unit}-{device}" for device in device_names]
    try:
        hosts = _zabbix_call("host.get", {
            "output": ["hostid", "host"],
            "filter": {"host": host_names},
        })
    except Exception as exc:
        return None, f"Zabbix host lookup failed: {exc}"
    host_by_device = {}
    for host in hosts or []:
        for device in device_names:
            if host.get("host") == f"{unit}-{device}":
                host_by_device[device] = host.get("hostid")
    if not host_by_device:
        return None, f"No Zabbix Router/Switch host found for {unit}"

    try:
        items = _zabbix_call("item.get", {
            "hostids": list(host_by_device.values()),
            "output": ["itemid", "key_", "value_type", "hostid"],
        })
    except Exception as exc:
        return None, f"Zabbix item lookup failed: {exc}"
    hostid_to_device = {v: k for k, v in host_by_device.items()}
    item_by_device_key = {}
    for item in items or []:
        device = hostid_to_device.get(item.get("hostid"))
        if device:
            item_by_device_key[(device, item.get("key_"))] = item

    end = int(time.time())
    start = end - hours * 3600
    charts = {}
    for key, device, zab_key, label, chart_unit in NETWORK_LATENCY_METRICS:
        item = item_by_device_key.get((device, zab_key))
        if not item:
            charts[key] = {"label": label, "unit": chart_unit, "points": [], "min": None, "max": None, "latest": None}
            continue
        try:
            if use_trends:
                raw = _zabbix_call("trend.get", {
                    "itemids": item["itemid"],
                    "time_from": start,
                    "time_till": end,
                    "sortfield": "clock",
                    "sortorder": "ASC",
                })
                is_loss_metric = key.endswith("_loss")
                value_key = "value_max" if (is_loss_metric and loss_aggregate == "max") else "value_avg"
            else:
                raw = _zabbix_call("history.get", {
                    "itemids": item["itemid"],
                    "history": int(item.get("value_type") or 0),
                    "time_from": start,
                    "time_till": end,
                    "sortfield": "clock",
                    "sortorder": "ASC",
                })
                value_key = "value"
        except Exception as exc:
            charts[key] = {"label": label, "unit": chart_unit, "points": [], "min": None, "max": None, "latest": None, "error": str(exc)}
            continue
        points = []
        for entry in raw or []:
            try:
                value = float(entry[value_key])
            except (KeyError, TypeError, ValueError):
                continue
            # Loss is already 0-100 from Zabbix; response time comes in
            # seconds, which is what it's labeled and charted as here.
            points.append({"t": int(entry["clock"]) * 1000, "v": value})
        values = [p["v"] for p in points]
        charts[key] = {
            "label": label,
            "unit": chart_unit,
            "points": points,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "latest": values[-1] if values else None,
        }

    return {
        "unit": unit,
        "hours": hours,
        "resolution": "hourly average" if use_trends else "native (~3min)",
        "charts": charts,
    }, None
# Same trigger every unit's Router/Switch host in Zabbix carries — checked
# live, 2026-09-17: "ICMP Ping: Unavailable by ICMP ping" on RD3336-Router
# fired/resolved 6 times (12 events) in the trailing 7 days.
_ZABBIX_FLAP_TRIGGER_DESCRIPTION = "ICMP Ping: Unavailable by ICMP ping"
_ZABBIX_FLAP_DEVICE_SUFFIXES = ("-Router", "-Switch")
# Zabbix API calls are POSTs (no URL-length limit the way ERP's chunked GET
# lookups have — see _erp_heads_for_mu_trailers), but a few thousand
# objectids in one event.get is still worth chunking defensively rather
# than assuming the server has no size limit of its own.
_ZABBIX_FLAP_EVENT_CHUNK = 500
def fleet_zabbix_flap_report(days=7, min_transitions=3, limit=50):
    """
    Fleet-wide "who's flapping," read directly from Zabbix's own Router/
    Switch ICMP-availability trigger history — a genuinely different,
    complementary signal from unit_history's own Flap Report (see
    fleet_flap_report). That one only ever sees a unit a tech has
    actually clicked Validate on (or the handful of always-on scheduled
    exceptions), so with PAUSE_AUTOMATED_TASKS holding the periodic
    revalidation jobs off, most of the fleet has no recorded history at
    all. Caught live, 2026-09-17 (RD3336): visibly flapping the whole
    time on its own Network Latency graph, with zero unit_history
    entries because nobody had happened to re-validate it recently.
    Zabbix, in contrast, has been watching every unit's Router/Switch
    continuously and independently this whole time regardless of ticket
    status or the pause, so this reads straight from ITS OWN trigger
    state history instead of trying to re-derive "flapping" from raw
    ping-loss numbers here — Zabbix already does that threshold
    evaluation per poll, at native (~3min) resolution, not diluted by
    the hourly averaging unit_network_latency_history's own docstring
    already warns can hide a real, shorter outage.

    Scoped to Router+Switch only (not NUC/SNUC-*/PVE), same reasoning
    NETWORK_LATENCY_METRICS's own comment gives: those are the two
    device types every unit in the fleet has, with an identical trigger
    namespace, so this stays universal instead of branching per device
    type for a first version.

    "transitions" counts PROBLEM<->RESOLVED flips within the window —
    the same definition unit_history.flap_summary uses, so the same
    min_transitions threshold means the same thing in both reports.
    down_seconds is real downtime duration (summed PROBLEM-to-RESOLVED
    gaps, open-ended if still down) — something the poll-based Flap
    Report can't give at all, since it only ever samples point-in-time.

    Returns (units, error). units: [{"unit", "days", "transitions",
    "down_seconds", "last_seen", "currently_healthy", "timeline",
    "device"}], worst (most transitions) first. device is "Router",
    "Switch", or "Router+Switch" depending on which host(s) actually
    flapped — a tech cares that this unit's connectivity flapped, not
    which specific device technically carried the trigger.
    """
    try:
        triggers = _zabbix_call("trigger.get", {
            "output": ["triggerid"],
            "selectHosts": ["host"],
            "filter": {"description": _ZABBIX_FLAP_TRIGGER_DESCRIPTION},
        })
    except Exception as exc:
        return None, f"Zabbix trigger lookup failed: {exc}"

    trigger_unit = {}
    for trigger in triggers or []:
        hosts = trigger.get("hosts") or []
        if not hosts:
            continue
        host_name = str(hosts[0].get("host") or "")
        if not host_name.endswith(_ZABBIX_FLAP_DEVICE_SUFFIXES):
            continue
        match = _ZABBIX_HOST_UNIT_RE.match(host_name)
        if not match:
            continue
        trigger_unit[trigger["triggerid"]] = (match.group(1).upper(), match.group(2))
    if not trigger_unit:
        return [], None

    time_from = int(time.time() - days * 86400)
    trigger_ids = list(trigger_unit.keys())
    events_by_unit = {}
    for start in range(0, len(trigger_ids), _ZABBIX_FLAP_EVENT_CHUNK):
        chunk = trigger_ids[start:start + _ZABBIX_FLAP_EVENT_CHUNK]
        try:
            events = _zabbix_call("event.get", {
                "output": ["clock", "value", "objectid"],
                "objectids": chunk,
                "time_from": time_from,
                "sortfield": "clock",
                "sortorder": "ASC",
            })
        except Exception as exc:
            return None, f"Zabbix event lookup failed: {exc}"
        for event in events or []:
            unit, device = trigger_unit.get(event.get("objectid"), (None, None))
            if not unit:
                continue
            events_by_unit.setdefault(unit, []).append({
                "ts": int(event["clock"]),
                "healthy": event.get("value") == "0",
                "device": device,
            })

    now = time.time()
    results = []
    for unit, events in events_by_unit.items():
        events.sort(key=lambda e: e["ts"])
        transitions = 0
        previous = None
        devices = set()
        down_seconds = 0
        pending_down_ts = None
        for event in events:
            devices.add(event["device"])
            if previous is not None and event["healthy"] != previous:
                transitions += 1
            if not event["healthy"]:
                pending_down_ts = event["ts"]
            elif pending_down_ts is not None:
                down_seconds += event["ts"] - pending_down_ts
                pending_down_ts = None
            previous = event["healthy"]
        if pending_down_ts is not None:
            down_seconds += now - pending_down_ts
        if transitions < int(min_transitions):
            continue
        last = events[-1]
        results.append({
            "unit": unit,
            "days": days,
            "transitions": transitions,
            "down_seconds": round(down_seconds),
            "last_seen": datetime.fromtimestamp(last["ts"]).strftime("%Y-%m-%d %H:%M:%S"),
            "currently_healthy": last["healthy"],
            "timeline": [{"ts": e["ts"], "healthy": e["healthy"]} for e in events],
            "device": "+".join(sorted(devices)),
        })
    results.sort(key=lambda r: (-r["transitions"], -r["down_seconds"], r["unit"]))
    return results[:int(limit)], None
_SWITCH_UPTIME_UNIT_SECONDS = {"day": 86400, "hour": 3600, "min": 60, "sec": 1}
def _parse_switch_uptime_seconds(text):
    """
    Parse a switch's own uptime text into whole seconds. One parser
    covers both switch types get_robofiber_uptime returns text for —
    Robofiber HGW's raw "N Day(s) N Hour(s) N Min(s) N Sec(s)" (checked
    live: "151 Days 1 Hour 31 Mins 3 Secs" — singular when the count is 1)
    and Netonix's, which is pre-formatted through the identical
    Days/Hours/Mins/Secs shape before this ever sees it (see
    _format_switch_uptime_seconds). Returns None if nothing parseable.
    """
    if not text:
        return None
    total = 0
    found = False
    for match in re.finditer(r"(\d+)\s*(day|hour|hr|min|sec)s?\b", text, re.IGNORECASE):
        value = int(match.group(1))
        unit_word = match.group(2).lower()
        if unit_word == "hr":
            unit_word = "hour"
        seconds_per = _SWITCH_UPTIME_UNIT_SECONDS.get(unit_word)
        if seconds_per is None:
            continue
        total += value * seconds_per
        found = True
    return total if found else None
# Arizona (Phoenix) never observes DST, so this fixed -7 offset is correct
# year-round — see work_tool.weather's identical _ARIZONA_TZ. Used for
# every timestamp unit_power_vs_cell_outage shows a tech, not UTC — found
# live (2026-09-14): a real 8:04 AM MST outage read as "8:00 AM" in a UTC
# label was mistaken for the same local hour, when it was actually 1:00 AM
# MST, a routine source of exactly this kind of confusion.
_ARIZONA_TZ = timezone(timedelta(hours=-7), "MST")
# How close "the switch came back up" has to land to the loss window's
# start/end to count as a match rather than coincidence — wide enough to
# cover the switch's own boot time after power returns plus Zabbix's own
# ~3-minute native poll granularity, narrow enough that two genuinely
# distinct events don't get conflated.
_POWER_VS_CELL_TOLERANCE_SECONDS = 15 * 60
# Same idea, widened for a loss window found in Zabbix trend data (see
# unit_network_latency_history's use_trends) rather than native history —
# past 7 days the window's own start/end only land on hourly buckets, not
# individual ~3-minute polls, so the edge a real event lands on can be off
# by close to an hour even before Zabbix's own poll jitter. Matching the
# tight native tolerance against a coarse window would call a real
# power/cell match "inconclusive" just because the edges don't line up to
# the minute — this is the same comparison, just with room for the
# resolution it's actually working with.
_POWER_VS_CELL_TOLERANCE_SECONDS_COARSE = 90 * 60
# How much loss counts as "fully down" for a window, not just flaky —
# matches the "100%" a tech reads straight off the graph as a flat
# plateau, with a little headroom so one missed/late poll doesn't split a
# real full outage into two separate windows.
_POWER_VS_CELL_LOSS_THRESHOLD = 90.0
def _all_high_loss_windows(points, threshold=_POWER_VS_CELL_LOSS_THRESHOLD):
    """
    Every contiguous run of points at/above `threshold`% loss, by
    timestamp, oldest first — same run-detection _latest_high_loss_window
    always used, just returning every qualifying run instead of only the
    newest one (see unit_power_vs_cell_outage's older-window reasoning,
    which needs to see all of them, not just the latest). Returns a list
    of (start_ms, end_ms, point_count) tuples, empty if no point in the
    whole series ever reached the threshold.
    """
    ordered = sorted(
        (p for p in (points or []) if p.get("t") is not None), key=lambda p: p["t"]
    )
    windows = []
    run_start = None
    run_end = None
    run_count = 0
    for point in ordered:
        value = point.get("v")
        if value is not None and value >= threshold:
            if run_start is None:
                run_start = point["t"]
                run_count = 0
            run_count += 1
            run_end = point["t"]
        else:
            if run_start is not None:
                windows.append((run_start, run_end, run_count))
            run_start = None
            run_count = 0
    if run_start is not None:
        windows.append((run_start, run_end, run_count))
    return windows
def _latest_high_loss_window(points, threshold=_POWER_VS_CELL_LOSS_THRESHOLD):
    """
    The most recent contiguous run of points at/above `threshold`% loss,
    by timestamp — the flat plateau a tech reads a router-loss graph for
    (see the "cell outage" example this was built from: a solid 100%
    stretch from 9/9 3:31 PM to 9/10 6:50 PM). Returns
    (start_ms, end_ms, point_count), or None if no point in the whole
    series ever reached the threshold.
    """
    windows = _all_high_loss_windows(points, threshold)
    return windows[-1] if windows else None
# How much loss counts as worth noting near a reboot boundary even when it
# never reached the full outage threshold above — see _reboot_bounce_note.
# Lower than _POWER_VS_CELL_LOSS_THRESHOLD on purpose: the question here
# isn't "was this a full outage" (that's the threshold above), it's "was
# there ANY real network trouble at all right when the switch came up," so
# a modest, genuine blip should still count as "not a clean bounce."
_POWER_VS_CELL_BOUNCE_LOSS_FLOOR = 30.0
def _reboot_bounce_note(switch_up_since, loss_points, tolerance_seconds):
    """
    Andrew's second half of this: a switch reboot with NO corresponding
    Zabbix loss reading anywhere near it — not even a modest one, let
    alone a real outage — is best explained by a manual/relay power-cycle
    (a "bounce") brief enough that Zabbix's own ~3-minute poll cadence
    never caught it, rather than an actual network outage that happened
    to leave no trace. Returns a short supporting note, or None when
    there WAS some elevated reading nearby (so this stays silent rather
    than asserting a bounce over real, if inconclusive, evidence).
    """
    if switch_up_since is None:
        return None
    nearby = [
        p for p in (loss_points or [])
        if p.get("t") is not None and p.get("v") is not None
        and abs(p["t"] / 1000 - switch_up_since) <= tolerance_seconds
    ]
    if not nearby:
        return None
    if any(p["v"] >= _POWER_VS_CELL_BOUNCE_LOSS_FLOOR for p in nearby):
        return None
    return (
        "no elevated router loss anywhere near when the switch came up either — "
        "consistent with a manual/relay bounce, not a network outage that went unlogged"
    )
def _verdict_for_window(window_start, window_end, switch_up_since, tolerance_seconds):
    """
    Classify ONE loss window against the switch's current uptime, same
    four-way read unit_power_vs_cell_outage's docstring describes. Returns
    (verdict, reason, case) — `case` is "power_edge" / "cell_before" /
    "cell_after_reboot" / "inconclusive", so the caller can still attach
    the reboot-bounce note only to the case it applies to.
    """
    if abs(switch_up_since - window_end) <= tolerance_seconds:
        return "power_outage", "switch came back up right when pings resumed", "power_edge"
    if switch_up_since <= window_start - tolerance_seconds:
        return (
            "cell_outage",
            "switch has been up continuously since before the outage began",
            "cell_before",
        )
    if switch_up_since > window_end + tolerance_seconds:
        # The switch's CURRENT uptime doesn't reach back to this window at
        # all — it's since rebooted again for some other reason. See the
        # docstring's third case: this window's own cause didn't coincide
        # with a switch restart we can see, which points to cellular,
        # hedged because we can't rule out an unlogged reboot in between.
        return (
            "cell_outage",
            (
                "switch's current uptime starts well after this loss window ended (it's "
                "since rebooted again for an unrelated reason) — likely cellular, since "
                "whatever caused this window didn't coincide with a switch restart, though "
                "this can't rule out an earlier reboot this check has no record of"
            ),
            "cell_after_reboot",
        )
    # Switch rebooted somewhere INSIDE the window itself — genuinely
    # ambiguous (could be power loss mid-outage, could be an unrelated
    # coincidental reboot); not enough to lean either way.
    return (
        "inconclusive",
        "switch's own uptime doesn't line up with either edge of the loss window",
        "inconclusive",
    )
def _ticket_created_at_epoch(issue_id):
    """
    (epoch_seconds, label, error) for when the ERP Issue was opened — used
    to pick which loss window a ticket is actually about when more than
    one qualifies. Frappe's own "creation" field has no timezone suffix;
    this fleet's ERP site (like every other ERP timestamp this codebase
    already displays — see _ARIZONA_TZ) is configured in Arizona local
    time, not UTC, so it's parsed as such rather than assumed UTC.

    Fails soft: any lookup/parse problem here should degrade the caller to
    its duration fallback, not break the whole diagnostic, so this never
    raises — errors come back as the third tuple element instead.
    """
    issue_id = str(issue_id or "").strip()
    if not issue_id:
        return None, "", "Missing issue_id"
    doc, error = _fetch_erp_issue_doc(issue_id)
    if error:
        return None, "", error
    raw = str((doc or {}).get("creation") or "").strip()
    if not raw:
        return None, "", f"Issue {issue_id} has no creation timestamp"
    raw = raw.split(".", 1)[0]  # drop the microseconds Frappe includes
    try:
        naive = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None, "", f"Could not parse Issue {issue_id} creation timestamp: {raw}"
    localized = naive.replace(tzinfo=_ARIZONA_TZ)
    return localized.timestamp(), localized.strftime("%Y-%m-%d %H:%M %Z"), None
def _closest_window_to_ticket(scored_windows, ticket_created_at):
    """
    Of `scored_windows`, the one whose interval is closest to when the
    ticket was opened — a window that CONTAINS ticket_created_at wins
    outright (gap 0); otherwise the smallest gap to either edge wins.
    Returns None (not a guess) when it can't decide: no windows, or two+
    windows tie for closest — the caller falls back to duration then.
    """
    if ticket_created_at is None or not scored_windows:
        return None
    def gap(window):
        if window["start"] <= ticket_created_at <= window["end"]:
            return 0.0
        return min(
            abs(ticket_created_at - window["start"]),
            abs(ticket_created_at - window["end"]),
        )
    ranked = sorted(scored_windows, key=gap)
    if len(ranked) >= 2 and gap(ranked[0]) == gap(ranked[1]):
        return None
    return ranked[0]
_SWITCH_UPTIME_CACHE = {}
_SWITCH_UPTIME_CACHE_LOCK = threading.Lock()
# Safety ceiling: re-confirm over SSH at least this often even when no new
# loss window shows up, since a reboot that never dipped router ICMP loss
# above _POWER_VS_CELL_LOSS_THRESHOLD would otherwise go undetected forever
# (see unit_power_vs_cell_outage's "cell_after_reboot" case, which already
# treats that as possible rather than provably absent).
_SWITCH_UPTIME_CACHE_MAX_AGE_SEC = 6 * 3600
def _cached_switch_up_since(unit, newest_window_end):
    """
    Reuse a prior SSH'd switch uptime instead of asking the switch again,
    when nothing has happened since that would make the answer stale:
    every loss window the caller is about to score was already scored as
    of the last real check, and that check isn't older than the safety
    ceiling above. `switch_up_since` (a fixed point in time, assuming no
    reboot) is what carries forward — `switch_uptime_seconds` is just
    "now minus that", so it grows correctly between checks with no SSH at
    all. Returns (switch_up_since, uptime_text) or (None, None) on a miss.
    """
    now = time.time()
    with _SWITCH_UPTIME_CACHE_LOCK:
        cached = _SWITCH_UPTIME_CACHE.get(unit)
    if not cached:
        return None, None
    if cached["checked_at"] < newest_window_end:
        return None, None
    if now - cached["checked_at"] > _SWITCH_UPTIME_CACHE_MAX_AGE_SEC:
        return None, None
    return cached["switch_up_since"], cached["uptime_text"]
def _store_switch_up_since(unit, switch_up_since, uptime_text):
    with _SWITCH_UPTIME_CACHE_LOCK:
        _SWITCH_UPTIME_CACHE[unit] = {
            "switch_up_since": switch_up_since,
            "uptime_text": uptime_text,
            "checked_at": time.time(),
        }
def unit_power_vs_cell_outage(unit, subject="", hours=24 * 14, issue_id=None):
    """
    Power outage vs. cell/carrier outage for a down unit — automates the
    comparison a tech makes by hand: pull the switch's own uptime (when
    it last came back up) and the router's most recent stretch of ~100%
    ICMP ping loss from Zabbix history, then compare the two.

    - Switch came up right around when the loss window ENDED (pings
      resumed) -> the switch itself lost and regained power -> POWER
      OUTAGE.
    - Switch has been running continuously since before the loss window
      even STARTED -> it never lost power at all, so whatever broke
      connectivity has to be upstream of it -> CELL (carrier/backhaul)
      OUTAGE.
    - Switch's CURRENT uptime starts well AFTER the (most recent) loss
      window already ended — it's since rebooted again for some other,
      unrelated reason. Reported live (RD3020, 2026-09-14): the switch's
      current uptime traced back only ~5.5h, entirely unrelated to a real
      ~29-minute outage the day before — but per Andrew's own read
      ("prior to rebooting, switch uptime was 83 days... a Zabbix outage
      [then] means it was cellular"), a window that predates the current
      reboot AND has no reboot of its own between it and now still points
      to cellular, since whatever caused it didn't coincide with a switch
      restart. This can't be as certain as the two cases above — the
      switch's own log doesn't retain reboot history far enough back to
      independently confirm no OTHER reboot happened in between (checked
      live: this fleet's Netonix syslogs are a few hours of DHCP-renewal
      noise, not a real history) — so it's still reported as CELL OUTAGE
      (same verdict, not a new one) but with a hedged reason spelling out
      that dependency, plus (see _reboot_bounce_note) whether the
      switch's OWN reboot shows any Zabbix signal at all, which is
      supporting-not-decisive evidence either way.
    - Anything else (switch rebooted mid-window for some unrelated
      reason, no clear full-loss window in range, uptime text didn't
      parse) comes back inconclusive rather than guessed at — a lead,
      same "confidence, not certainty" spirit as the shading/dead-panel
      checks, not a verdict to act on blind.

    When multiple qualifying loss windows fall in range, picking which one
    the TICKET is actually about — not just which one looks most severe —
    matters. Andrew's rule, in priority order:
      1. If an `issue_id` is given, the window whose interval contains (or
         sits closest to) the ERP ticket's own creation time is the
         relevant one — that's the direct signal for "which outage is
         this ticket about," more reliable than a guess based on shape.
      2. Only when that's inconclusive (no issue_id, the ERP lookup
         failed, or two windows tie for closest to the ticket's creation
         time) does it fall back to the window with the LONGER duration —
         a brief power blip doesn't outrank a longer carrier outage just
         because it happened more recently.
    Windows that all agree still point at one verdict regardless of which
    one gets picked to display.

    Returns (info, error).
    """
    unit = str(unit or "").strip().upper()
    if not unit:
        return None, "Missing unit"
    try:
        # Default/cap at 2 weeks, not unit_network_latency_history's own
        # 90d max — a unit whose switch has been quietly up for many days
        # can easily have its last real outage older than a 72h window
        # (reported live: RD3122, switch up 5d+, "no recent outage window"
        # against the old 72h default). Past 7 days the underlying Zabbix
        # query switches to hourly-trend data (see use_trends below) —
        # coarser, but _POWER_VS_CELL_TOLERANCE_SECONDS_COARSE accounts
        # for that rather than silently losing precision.
        hours = max(1, min(int(hours), 24 * 14))
    except (TypeError, ValueError):
        hours = 24 * 14

    # Zabbix history first, deliberately — it's the cheap half of this
    # check (no SSH), and most units asked about here (especially a fleet
    # sweep over every Up Steady unit) will have no qualifying loss window
    # at all. SSH'ing into every switch just to throw the answer away for
    # units with nothing to explain would turn a fleet-wide sweep into a
    # genuinely slow, needless SSH hammering of the whole switch fleet.
    #
    # Two-phase, native precision preferred: query native ~3-minute
    # history for whatever portion of the request falls in the last 7
    # days (Zabbix's own raw-history retention ceiling), and ONLY fall
    # back to coarser hourly-trend data (loss_aggregate="max" — see
    # unit_network_latency_history's own comment on why max, not avg) for
    # the older remainder past that, and only if the native phase found
    # nothing. Reported live, 2026-09-14 (RD3124): a real, continuous
    # 101-minute 100%-loss outage from 3 days earlier — well within native
    # range — collapsed to a meaningless "8:00-8:00 UTC" single-hour
    # window, because the 2-week DEFAULT lookback alone pushed the whole
    # query into hourly-trend mode regardless of how recent the actual
    # event turned out to be. Always preferring native data when it's
    # available avoids coarsening a precise, recent event just because the
    # requested window also happens to reach further back.
    native_hours = min(hours, 24 * 7)
    latency_info, latency_error = unit_network_latency_history(unit, native_hours)
    if latency_error:
        return None, latency_error
    loss_points = (
        ((latency_info or {}).get("charts") or {}).get("router_loss", {}).get("points") or []
    )
    tolerance_seconds = _POWER_VS_CELL_TOLERANCE_SECONDS
    windows = _all_high_loss_windows(loss_points)
    if not windows and hours > 24 * 7:
        older_info, older_error = unit_network_latency_history(unit, hours, loss_aggregate="max")
        if older_error:
            return None, older_error
        older_points = (
            ((older_info or {}).get("charts") or {}).get("router_loss", {}).get("points") or []
        )
        # Only the portion older than what the native phase above already
        # covered — the native call is authoritative for its own range;
        # re-finding the same stretch at coarser precision here would
        # only make an already-checked window worse, never better.
        native_cutoff_ms = (time.time() - native_hours * 3600) * 1000
        loss_points = [p for p in older_points if (p.get("t") or 0) < native_cutoff_ms]
        windows = _all_high_loss_windows(loss_points)
        if windows:
            tolerance_seconds = _POWER_VS_CELL_TOLERANCE_SECONDS_COARSE
    if not windows:
        return {
            "unit": unit,
            "verdict": "no_recent_outage",
            "status": "ok",
            "reason": f"no {_POWER_VS_CELL_LOSS_THRESHOLD:g}%+ router loss window in the last {hours}h",
            "checked_at": time.time(),
            "switch_uptime_text": "",
            "switch_uptime_seconds": None,
            "switch_up_since": None,
            "loss_window_start": None,
            "loss_window_end": None,
            "loss_window_points": 0,
            "loss_threshold": _POWER_VS_CELL_LOSS_THRESHOLD,
            "summary": (
                f"{unit} — no recent outage window: no {_POWER_VS_CELL_LOSS_THRESHOLD:g}%+ "
                f"router loss in the last {hours}h to compare switch uptime against "
                "(switch not checked — nothing to explain)."
            ),
        }, None

    # A real loss window exists — worth an SSH round trip to find out when
    # the switch itself last came up, unless a previous check already
    # covered every window in range and isn't stale (see
    # _cached_switch_up_since): a switch's uptime only moves forward
    # between reboots, so "now minus a previously-confirmed up-since" is
    # exactly what a fresh SSH would report, at zero extra cost.
    newest_window_end = windows[-1][1] / 1000
    switch_up_since, uptime_text = _cached_switch_up_since(unit, newest_window_end)
    now = time.time()
    if switch_up_since is None:
        uptime_info, uptime_error = get_robofiber_uptime(unit)
        if uptime_error:
            return None, uptime_error
        uptime_text = (uptime_info or {}).get("uptime") or ""
        switch_uptime_seconds = _parse_switch_uptime_seconds(uptime_text)
        if switch_uptime_seconds is None:
            return None, f"Could not parse switch uptime from: {uptime_text or '(empty)'}"
        now = time.time()
        switch_up_since = now - switch_uptime_seconds
        _store_switch_up_since(unit, switch_up_since, uptime_text)
    else:
        switch_uptime_seconds = now - switch_up_since

    switch_uptime_label = _format_switch_uptime_seconds(switch_uptime_seconds)
    switch_up_since_label = datetime.fromtimestamp(switch_up_since, tz=_ARIZONA_TZ).strftime("%Y-%m-%d %H:%M %Z")

    # Classify every qualifying window against the switch's (single, known)
    # current uptime, oldest first — not just the most recent one — so a
    # mix of verdicts among them can be resolved by duration rather than
    # blindly trusting whichever happened last.
    scored_windows = []
    for w_start_ms, w_end_ms, w_points in windows:
        w_start = w_start_ms / 1000
        w_end = w_end_ms / 1000
        w_verdict, w_reason, w_case = _verdict_for_window(
            w_start, w_end, switch_up_since, tolerance_seconds
        )
        scored_windows.append({
            "start": w_start,
            "end": w_end,
            "points": w_points,
            "verdict": w_verdict,
            "reason": w_reason,
            "case": w_case,
            "duration": w_end - w_start,
        })

    # Prefer a definite verdict over "inconclusive" as the pool to pick
    # from. WHICH window gets picked, when more than one qualifies, is
    # decided in priority order:
    #   1. The one closest to (or containing) the ticket's own creation
    #      time, when issue_id resolves to one and it clearly points at a
    #      single window — the direct signal for "which outage is this
    #      ticket about."
    #   2. Otherwise, the one that lasted LONGER — a brief power blip
    #      doesn't outrank a longer carrier outage just because it
    #      happened more recently or because the ticket lookup failed.
    definite_windows = [w for w in scored_windows if w["verdict"] != "inconclusive"]
    candidates = definite_windows or scored_windows

    ticket_created_at = None
    ticket_created_label = ""
    ticket_lookup_error = None
    if issue_id:
        ticket_created_at, ticket_created_label, ticket_lookup_error = _ticket_created_at_epoch(issue_id)

    chosen = _closest_window_to_ticket(candidates, ticket_created_at) if ticket_created_at is not None else None
    picked_by = "ticket_creation"
    if chosen is None:
        chosen = max(candidates, key=lambda w: (w["duration"], w["end"]))
        picked_by = "duration"

    verdict = chosen["verdict"]
    reason = chosen["reason"]
    window_start = chosen["start"]
    window_end = chosen["end"]
    window_points = chosen["points"]
    older_window_count = len(windows) - 1
    window_start_label = datetime.fromtimestamp(window_start, tz=_ARIZONA_TZ).strftime("%Y-%m-%d %H:%M %Z")
    window_end_label = datetime.fromtimestamp(window_end, tz=_ARIZONA_TZ).strftime("%H:%M %Z")

    other_candidates = [w for w in candidates if w is not chosen]
    if other_candidates:
        if picked_by == "ticket_creation":
            reason += (
                f"; picked over {len(other_candidates)} other qualifying window(s) in the last "
                f"{hours}h as the one matching the ticket's own creation time ({ticket_created_label})"
            )
        elif ticket_created_at is not None:
            reason += (
                f"; the ticket's creation time ({ticket_created_label}) didn't clearly point at one "
                f"of the {len(other_candidates)} qualifying window(s) over the others, so the "
                "longest-lasting one was used instead"
            )
        elif ticket_lookup_error:
            reason += (
                f"; could not check the ticket's creation time ({ticket_lookup_error}), so the "
                f"longest-lasting of {len(other_candidates)} other qualifying window(s) was used instead"
            )
        else:
            disagreeing = [w for w in other_candidates if w["verdict"] != verdict]
            if disagreeing:
                kinds = ", ".join(sorted({w["verdict"].replace("_", " ") for w in disagreeing}))
                reason += (
                    f"; {len(disagreeing)} other {_POWER_VS_CELL_LOSS_THRESHOLD:g}%+ window(s) in the "
                    f"last {hours}h read as {kinds} but lasted less time — the longer outage is "
                    "treated as the relevant one"
                )
            elif chosen["case"] == "cell_after_reboot" and older_window_count:
                reason += (
                    f"; {older_window_count} earlier {_POWER_VS_CELL_LOSS_THRESHOLD:g}%+ window(s) "
                    f"also found in the last {hours}h, same read likely applies to those too"
                )

    if chosen["case"] == "cell_after_reboot":
        bounce_note = _reboot_bounce_note(switch_up_since, loss_points, tolerance_seconds)
        if bounce_note:
            reason += f"; the switch's own reboot {bounce_note}"

    summary = (
        f"{unit} — {verdict.replace('_', ' ')}: {reason}. "
        f"Switch up {switch_uptime_label} (since {switch_up_since_label}); "
        f"router loss {_POWER_VS_CELL_LOSS_THRESHOLD:g}%+ from {window_start_label} to {window_end_label}."
    )
    # A definite verdict is worth a toast (warn — a finding, not a
    # failure); inconclusive stays quiet, same as an outage report
    # skipping units it can't reach a verdict on.
    status = "warn" if verdict in ("power_outage", "cell_outage") else "ok"

    return {
        "unit": unit,
        "verdict": verdict,
        "status": status,
        "reason": reason,
        "checked_at": now,
        "switch_uptime_text": uptime_text,
        "switch_uptime_seconds": switch_uptime_seconds,
        "switch_up_since": switch_up_since,
        "loss_window_start": window_start,
        "loss_window_end": window_end,
        "loss_window_points": window_points,
        "loss_threshold": _POWER_VS_CELL_LOSS_THRESHOLD,
        "window_picked_by": picked_by,
        "ticket_created_at": ticket_created_at,
        "summary": summary,
    }, None
def fleet_power_vs_cell_outage_status(units, max_workers=8, unit_issue_ids=None):
    """
    Power-vs-cell-outage for a whole list of units at once, concurrently —
    backs the Up Steady list's "Diagnose Power vs Cell" sweep (both the
    scheduled one that runs on startup and the manual on-demand button).
    Unlike the VRM-based fleet_* checks in weather.py, this has no
    fleet-wide "every installation" source of its own — the caller
    supplies the unit list (in practice, whatever's currently in the
    shared job's Up Steady/false_positives results), since this check has
    nothing to do with VRM installations at all.

    unit_issue_ids is an optional {unit: issue_id} map — Up Steady rows
    are real ERP tickets too, so when the caller has that mapping handy
    each unit's check gets it passed straight through to
    unit_power_vs_cell_outage, which uses it to prefer the loss window
    matching when the ticket was actually opened over its longest-duration
    fallback (see that function's docstring). Omit it (or leave a unit out
    of it) and that unit falls back the same as ever — this is additive,
    not required.

    Lower default concurrency than the VRM fleet checks (8, not 10) —
    each unit that actually has a loss window costs a real SSH connection
    to its switch, which is heavier than an HTTP call to VRM, and a
    fleet's worth of switches all getting SSH'd into at once is more
    load, not less, than the same fleet's VRM installations getting
    polled at once. Units with no qualifying loss window never touch SSH
    at all (see unit_power_vs_cell_outage's own reordering), so in
    practice most of a sweep is fast Zabbix-only checks with just a
    handful of real SSH connections mixed in.

    Returns (rows, error). Each row is whatever unit_power_vs_cell_outage
    returns for that unit, plus "unit" always present (or "error" if that
    one unit's check itself failed — the rest of the sweep still comes
    back).
    """
    unique_units = sorted({str(u or "").strip().upper() for u in (units or []) if str(u or "").strip()})
    if not unique_units:
        return [], None
    unit_issue_ids = unit_issue_ids or {}

    def check_one(unit):
        info, error = unit_power_vs_cell_outage(unit, issue_id=unit_issue_ids.get(unit))
        if error:
            return {"unit": unit, "error": error}
        return info

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        rows = list(pool.map(check_one, unique_units))
    return rows, None
