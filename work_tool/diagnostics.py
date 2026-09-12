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
import urllib3

from ._core import (  # noqa: F401  (re-exported dependencies)
    _host_only,
    _net_row_for_unit,
    _ping_host,
    _ping_reachable,
    _pve_ssh_credentials,
    _scrypted_ssh_credentials,
    _scrypted_ssh_target,
    ensure_unit_net_info,
    env_path,
    list_unit_cameras,
    username,
    uses_pve,
    validate_unit_full,
)


# Platform services managed on the Scrypted box, in start order. Kept in sync
# with refresh_platform_services() — if you add a service to one, add it here.
PLATFORM_SERVICES = (
    "database", "watchdog", "web", "metadata", "images", "capture",
    "smtp", "alarms", "events", "onvif", "monitor", "snmp", "cache",
)
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

    names = [f"{company}-{svc}.service" for svc in PLATFORM_SERVICES]
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
