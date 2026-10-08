"""
FD camera discovery from the unit's MikroTik router.

Most FD rows in net_sheet.csv carry only a router IP, and FD sites don't fit
the net sheet's five camera slots anyway (FD1034 has seven cameras across two
buildings; one site has 26). The router's DHCP leases do know every camera,
labelled in the lease comment:

    SC-FD1034-CBRE-EW-N-Bldg-C01-Ent-E-(Connected-NBldg-NetonixSwitch-P7)
    SC-FD2001-Camera1                      (host-name SC-FD2001-C1)

so this reads them over SSH (read-only `/ip dhcp-server lease print`) and
caches the list per unit. Surveyed 2026-10-08: 34 of 69 FD routers answer on
the router SSH port; 16 of those label cameras this way. Units whose router
is unreachable, or whose cameras use fixed IPs (no leases, e.g. FD1020),
return a readable error and callers keep using the net sheet.

Re-exported by work_tool/__init__.py like every other submodule.
"""

import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import paramiko

from ._core import _host_only, _ping_host, _ping_reachable, is_fd_unit, router_ip_for_unit


# MikroTik routers take SSH on 10000 in this fleet, not 22 (Andrew, 2026-10-07).
ROUTER_SSH_PORT = int(str(os.getenv("ROUTER_SSH_PORT") or "10000").strip() or "10000")
FD_CAMERA_CACHE_SECONDS = 60 * 60       # a found list is good for an hour
FD_CAMERA_FAILURE_CACHE_SECONDS = 5 * 60  # don't wait on a dead router every click
_LEASE_COMMAND = "/ip dhcp-server lease print terse without-paging"

_fd_camera_cache = {}
_fd_camera_cache_lock = threading.Lock()

# Keys in `print terse` output are lowercase words joined by hyphens.
_TERSE_KEY_SPLIT = re.compile(r"\s+(?=[a-z][a-z0-9-]*=)")
# "...-C01-Ent-E", "...-C3", "...-C12-..." — a camera number after a hyphen.
_CAMERA_C_NUMBER = re.compile(r"-C0?(\d{1,2})(?=-|\(|$)", re.IGNORECASE)
_CAMERA_WORD_NUMBER = re.compile(r"Camera\s*0?(\d{1,2})\b", re.IGNORECASE)


def parse_dhcp_leases(text):
    """Parse `/ip dhcp-server lease print terse` output into a list of dicts."""
    leases = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if "address=" not in line:
            continue
        lease = {}
        for token in _TERSE_KEY_SPLIT.split(line):
            key, sep, value = token.partition("=")
            if sep and re.fullmatch(r"[a-z][a-z0-9-]*", key):
                lease[key] = value.strip()
        leases.append(lease)
    return leases


def _camera_number(text):
    text = str(text or "")
    match = _CAMERA_C_NUMBER.search(text) or _CAMERA_WORD_NUMBER.search(text)
    return int(match.group(1)) if match else None


def _camera_name(comment, host_name, unit):
    """
    "SC-FD1034-CBRE-EW-N-Bldg-C01-Ent-E-(Connected-...)" -> "CBRE-EW-N-Bldg-C01-Ent-E".
    Falls back to the host name when the lease has no comment.
    """
    name = str(comment or host_name or "").strip()
    name = re.sub(r"\(.*$", "", name).strip(" -")
    prefix = re.compile(r"^(?:SC-)?" + re.escape(str(unit or "")) + r"-?", re.IGNORECASE)
    return prefix.sub("", name, count=1).strip(" -") or name


def cameras_from_leases(leases, unit):
    """
    Pick the camera leases out of a router's lease list. A lease is a camera
    when its comment (or, failing that, its host name) carries a camera
    number: "-C01-", "-C3", or "Camera1". Speakers, switches, the iLO and
    the MicroServer don't, so they drop out. Sorted by IP.
    """
    cameras = []
    for lease in leases or []:
        comment = lease.get("comment", "")
        host_name = lease.get("host-name", "")
        number = _camera_number(comment)
        if number is None and not comment:
            number = _camera_number(host_name)
        if number is None:
            continue
        ip = _host_only(lease.get("active-address") or lease.get("address") or "")
        if not ip:
            continue
        cameras.append({
            "name": _camera_name(comment, host_name, unit),
            "number": number,
            "ip": ip,
            "mac": lease.get("active-mac-address") or lease.get("mac-address") or "",
            "status": lease.get("status", ""),
        })

    def ip_key(camera):
        try:
            return tuple(int(part) for part in camera["ip"].split("."))
        except ValueError:
            return (999,)
    return sorted(cameras, key=ip_key)


def _read_router_leases(router_ip):
    """SSH the router and return (lease_text, error). Read-only."""
    username = (os.getenv("routeruser") or "").strip().strip('"').strip("'")
    password = (os.getenv("routerpass") or "").strip().strip('"').strip("'")
    if not username or not password:
        return "", "Set routeruser and routerpass in .env to read FD cameras from the router."
    client = paramiko.SSHClient()
    try:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=router_ip,
            port=ROUTER_SSH_PORT,
            username=username,
            password=password,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        _stdin, stdout, stderr = client.exec_command(_LEASE_COMMAND, timeout=30)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace").strip()
    except paramiko.AuthenticationException:
        return "", f"Router {router_ip} rejected routeruser/routerpass from .env."
    except Exception as exc:
        return "", (
            f"Couldn't reach router {router_ip} on SSH port {ROUTER_SSH_PORT} ({exc}). "
            "It may be down, or not take SSH on that port."
        )
    finally:
        client.close()
    if err and not out:
        return "", f"Router {router_ip} refused the lease listing: {err}"
    return out, None


def fd_router_cameras(unit, refresh=False):
    """
    Cameras for an FD unit, read from its router's DHCP leases.

    Returns (cameras, error): cameras is a list of
    {"name", "number", "ip", "mac", "status"} sorted by IP. A found list is
    cached for an hour; a failure for five minutes, so an unreachable router
    doesn't add a 10-second wait to every click. refresh=True skips the cache.
    """
    unit = str(unit or "").strip().upper()
    if not unit:
        return None, "Missing unit"
    if not is_fd_unit(unit):
        return None, f"{unit} is not an FD unit; its cameras come from the net sheet."
    now = time.time()
    if not refresh:
        with _fd_camera_cache_lock:
            cached = _fd_camera_cache.get(unit)
        if cached and cached["expires"] > now:
            return cached["cameras"], cached["error"]

    router_ip = router_ip_for_unit(unit)
    if not router_ip:
        cameras, error = None, f"No router IP for {unit} in the net sheet or ERP."
    else:
        text, error = _read_router_leases(router_ip)
        cameras = None
        if not error:
            cameras = cameras_from_leases(parse_dhcp_leases(text), unit)
            if not cameras:
                cameras, error = None, (
                    f"Router {router_ip} has no camera leases for {unit} "
                    "(its cameras may use fixed IPs). Using the net sheet instead."
                )
    ttl = FD_CAMERA_FAILURE_CACHE_SECONDS if error else FD_CAMERA_CACHE_SECONDS
    with _fd_camera_cache_lock:
        _fd_camera_cache[unit] = {"cameras": cameras, "error": error, "expires": now + ttl}
    return cameras, error


# ---- Camera-outage tickets --------------------------------------------------
# Camera targets are normally CAMERA_ENDPOINTS keys (net sheet slots). A
# router-sourced camera is "fd:<camera name>" instead; ping_camera in _core
# resolves it through the cached list above. The front end treats targets as
# opaque ids, so the row's Ping buttons, Ping All and Revalidate need nothing
# extra.
FD_TARGET_PREFIX = "fd:"
# A word in a ticket subject that names a site camera: "MzdUsedBldg-C02-Rear-W".
_SUBJECT_CAMERA_WORD = re.compile(r"-C0?\d{1,2}(?:-|\(|$)", re.IGNORECASE)


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def is_fd_camera_target(target):
    return str(target or "").startswith(FD_TARGET_PREFIX)


def fd_camera_target(camera):
    return FD_TARGET_PREFIX + camera["name"]


def fd_camera_label(camera, site_cameras=None):
    """
    Short label for a row: building + camera number, "MzdUsedBldg-C02".
    With site_cameras, widens leftwards until no other camera on the site
    has the same label (FD1034: "N-Bldg-C01" vs "S-Bldg-C01", not "Bldg-C01").
    """
    def label(cam, width):
        parts = cam["name"].split("-")
        for index, part in enumerate(parts):
            if re.fullmatch(r"C0?\d{1,2}", part, re.IGNORECASE):
                return "-".join(parts[max(0, index - width):index + 1])
        return cam["name"]

    others = [c for c in site_cameras or [] if c["name"] != camera["name"]]
    for width in range(1, 6):
        mine = label(camera, width)
        if not any(label(other, width) == mine for other in others):
            return mine
    return camera["name"]


def fd_camera_for_target(unit, target):
    """The router camera a "fd:<name>" target refers to, or None."""
    if not is_fd_camera_target(target):
        return None
    cameras, _error = fd_router_cameras(unit)
    name = target[len(FD_TARGET_PREFIX):]
    return next((c for c in cameras or [] if c["name"] == name), None)


def fd_cameras_for_ticket(unit, subject, slot_targets=(), generic=False):
    """
    Which router cameras an FD camera-outage ticket is about, or None to keep
    the net-sheet behaviour (not FD, router unreachable, or nothing matched).

    - The subject names a site camera ("Camera Outage MzdUsedBldg-C02-Rear-W
      down", FD1040): that camera, matched by name.
    - A generic "Camera Outage": every camera the router knows.
    - "Camera 2" / "C2" (slot_targets): the router camera numbered 2, only
      when that number is unique on the site — FD1040 has five C01s, one
      per building, so a bare number there can't pick one.
    """
    if not is_fd_unit(unit):
        return None
    words = [
        word.strip(".,;:")
        for word in re.split(r"\s+", str(subject or ""))
        if _SUBJECT_CAMERA_WORD.search(word)
    ]
    slot_numbers = {
        int(t[len("camera"):]) for t in slot_targets or ()
        if re.fullmatch(r"camera\d", str(t))
    }
    if not words and not generic and not slot_numbers:
        return None
    cameras, error = fd_router_cameras(unit)
    if error or not cameras:
        return None
    if words:
        wanted = [_norm(w) for w in words]
        matched = [
            c for c in cameras
            if any(w and (w in _norm(c["name"]) or _norm(c["name"]) in w) for w in wanted)
        ]
        return matched or None
    if generic:
        return list(cameras)
    matched = []
    for number in sorted(slot_numbers):
        same_number = [c for c in cameras if c["number"] == number]
        if len(same_number) != 1:
            return None
        matched.append(same_number[0])
    return matched or None


def fd_router_cameras_with_ping(unit, refresh=False):
    """fd_router_cameras plus a quick ping of each camera ("up": True/False)."""
    cameras, error = fd_router_cameras(unit, refresh=refresh)
    if error:
        return None, error

    def ping(camera):
        _code, output = _ping_host(camera["ip"], max_echoes=2)
        return dict(camera, up=_ping_reachable(output))

    with ThreadPoolExecutor(max_workers=min(8, len(cameras))) as pool:
        return list(pool.map(ping, cameras)), None
