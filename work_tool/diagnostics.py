"""
Read-only unit diagnostics. Nothing here changes state on a device.

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
    _format_switch_uptime_seconds,
    _host_only,
    _net_row_for_unit,
    _ping_host,
    _ping_reachable,
    _pve_ssh_credentials,
    _sc_component_name,
    _scrypted_ssh_credentials,
    _scrypted_ssh_target,
    ensure_unit_net_info,
    env_path,
    get_robofiber_uptime,
    is_hikvision_unit,
    list_unit_cameras,
    username,
    uses_pve,
    validate_unit_full,
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
    }
    numeric_keys = (
        "temperature_c", "available_spare", "available_spare_threshold",
        "percentage_used", "power_on_hours", "power_cycles",
        "unsafe_shutdowns", "media_errors", "error_log_entries",
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


def zabbix_active_problems_by_unit():
    """
    Every currently-active Zabbix problem, fleet-wide in two calls, grouped
    by unit. Read-only (problem.get / trigger.get — neither acknowledges or
    closes anything). Returns ({unit: [problem, ...]}, error).

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
    try:
        problems = _zabbix_call("problem.get", {
            "output": ["eventid", "objectid", "name", "severity", "clock"],
            "recent": False,
        })
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
def unit_network_latency_history(unit, hours=24):
    """
    Router/Switch ICMP ping response time and loss over time, from Zabbix's
    own history — the same checks behind "ICMP Ping: High ping loss/response
    time", the single most common active-problem type on this fleet (see
    combined_power_infra_alerts's real numbers). A live SSH/ping snapshot
    only answers "is it up right now"; this answers "has it been flaky."
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
                value_key = "value_avg"
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
def _latest_high_loss_window(points, threshold=_POWER_VS_CELL_LOSS_THRESHOLD):
    """
    The most recent contiguous run of points at/above `threshold`% loss,
    by timestamp — the flat plateau a tech reads a router-loss graph for
    (see the "cell outage" example this was built from: a solid 100%
    stretch from 9/9 3:31 PM to 9/10 6:50 PM). Returns
    (start_ms, end_ms, point_count), or None if no point in the whole
    series ever reached the threshold.
    """
    ordered = sorted(
        (p for p in (points or []) if p.get("t") is not None), key=lambda p: p["t"]
    )
    best = None
    run_start = None
    run_count = 0
    for point in ordered:
        value = point.get("v")
        if value is not None and value >= threshold:
            if run_start is None:
                run_start = point["t"]
                run_count = 0
            run_count += 1
            best = (run_start, point["t"], run_count)
        else:
            run_start = None
            run_count = 0
    return best
def unit_power_vs_cell_outage(unit, subject="", hours=24 * 14):
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
    - Anything else (switch rebooted mid-window for some unrelated
      reason, no clear full-loss window in range, uptime text didn't
      parse) comes back inconclusive rather than guessed at — a lead,
      same "confidence, not certainty" spirit as the shading/dead-panel
      checks, not a verdict to act on blind.

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
    latency_info, latency_error = unit_network_latency_history(unit, hours)
    if latency_error:
        return None, latency_error
    loss_points = (
        ((latency_info or {}).get("charts") or {}).get("router_loss", {}).get("points") or []
    )
    # Which tolerance applies depends on what resolution the loss window
    # itself was actually found in — see _POWER_VS_CELL_TOLERANCE_SECONDS_
    # COARSE's own comment.
    tolerance_seconds = (
        _POWER_VS_CELL_TOLERANCE_SECONDS_COARSE
        if (latency_info or {}).get("resolution") == "hourly average"
        else _POWER_VS_CELL_TOLERANCE_SECONDS
    )
    window = _latest_high_loss_window(loss_points)
    if window is None:
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

    # A real loss window exists — now it's worth the SSH round trip to
    # find out when the switch itself last came up.
    uptime_info, uptime_error = get_robofiber_uptime(unit)
    if uptime_error:
        return None, uptime_error
    uptime_text = (uptime_info or {}).get("uptime") or ""
    switch_uptime_seconds = _parse_switch_uptime_seconds(uptime_text)
    if switch_uptime_seconds is None:
        return None, f"Could not parse switch uptime from: {uptime_text or '(empty)'}"

    now = time.time()
    switch_up_since = now - switch_uptime_seconds
    switch_uptime_label = _format_switch_uptime_seconds(switch_uptime_seconds)
    switch_up_since_label = datetime.fromtimestamp(switch_up_since, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    window_start_ms, window_end_ms, window_points = window
    window_start = window_start_ms / 1000
    window_end = window_end_ms / 1000
    window_start_label = datetime.fromtimestamp(window_start, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    window_end_label = datetime.fromtimestamp(window_end, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if abs(switch_up_since - window_end) <= tolerance_seconds:
        verdict = "power_outage"
        reason = "switch came back up right when pings resumed"
    elif switch_up_since <= window_start - tolerance_seconds:
        verdict = "cell_outage"
        reason = "switch has been up continuously since before the outage began"
    else:
        verdict = "inconclusive"
        reason = "switch's own uptime doesn't line up with either edge of the loss window"

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
        "summary": summary,
    }, None
def fleet_power_vs_cell_outage_status(units, max_workers=8):
    """
    Power-vs-cell-outage for a whole list of units at once, concurrently —
    backs the Up Steady list's "Diagnose Power vs Cell" sweep (both the
    scheduled one that runs on startup and the manual on-demand button).
    Unlike the VRM-based fleet_* checks in weather.py, this has no
    fleet-wide "every installation" source of its own — the caller
    supplies the unit list (in practice, whatever's currently in the
    shared job's Up Steady/false_positives results), since this check has
    nothing to do with VRM installations at all.

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

    def check_one(unit):
        info, error = unit_power_vs_cell_outage(unit)
        if error:
            return {"unit": unit, "error": error}
        return info

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        rows = list(pool.map(check_one, unique_units))
    return rows, None
