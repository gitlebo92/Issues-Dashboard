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
import multiprocessing
import paramiko
import threading
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from urllib.parse import quote
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

multiprocessing.freeze_support()
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

def resolve_env_path():
    override = str(os.getenv("WORK_TOOL_ENV_FILE") or "").strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(BASE_DIR, override)
    return resource_path(".env")

env_path = resolve_env_path()

load_dotenv(env_path)

def pc_user():
    return (os.getenv("pcuser") or "").strip().strip('"').strip("'")

def pc_user_home():
    user = pc_user()
    if not user:
        return os.path.expanduser("~")
    return os.path.join("C:\\Users", user)

SENTRA_NETWORK_TOOL_DIR = os.path.join(pc_user_home(), "Documents", "Sentra_Network_Toolv16")

def sentra_network_tool_v19_dir():
    """Directory containing Sentra_Network_toolv19.exe (ERP unit inventory)."""
    override = (os.getenv("SENTRA_NETWORK_TOOL_V19_DIR") or "").strip().strip('"').strip("'")
    if override:
        return override
    return os.path.join(pc_user_home(), "Documents", "Sentra_Network_toolv19")

def work_tld():
    """Return the configured work domain (workTLD), without scheme or leading dot."""
    tld = (os.getenv("workTLD") or "").strip().strip('"').strip("'")
    tld = tld.replace("https://", "").replace("http://", "").strip()
    return tld.split("/")[0].lstrip(".")

def erp_base_url():
    """ERP host at https://erp.{workTLD}."""
    tld = work_tld()
    if not tld:
        return ""
    return f"https://erp.{tld}"

def scrypted_web_url(unit):
    """Open Scrypted at https://{unit}.{workTLD}/endpoint/@scrypted/core/public/#/."""
    tld = work_tld()
    unit_name = str(unit or "").strip()
    if not tld or not unit_name:
        return ""
    return f"https://{unit_name}.{tld}/endpoint/@scrypted/core/public/#/"

def scrypted_open_url(unit):
    """Return a Scrypted web UI URL when the unit has a Scrypted IP in the net sheet."""
    if not net_array:
        generate_net_array()
    row = ensure_unit_net_info(unit, needed_indexes=(12,))
    if not row:
        return ""
    scrypted_ip = _host_only(row[12] if len(row) > 12 else "")
    if not scrypted_ip:
        return ""
    url = scrypted_web_url(unit)
    if url:
        return url
    return f"https://{scrypted_ip}:10443/endpoint/@scrypted/core/public/#/"

SCRYPTED_NO_AUDIO_SUFFIXES = ("FISHEYE", "C1-180", "C2-180")
SCRYPTED_NO_AUDIO_SETTING_KEY = "prebuffer:noAudio"

def _scrypted_web_credentials():
    """Scrypted UI login from scryptuserweb / scryptpass."""
    username = (os.getenv("scryptuserweb") or "").strip().strip('"').strip("'")
    password = (os.getenv("scryptpass") or "").strip().strip('"').strip("'")
    return username, password

def _scrypted_ssh_credentials():
    """Scrypted host SSH login from scryptuserssh / scryptpass."""
    username = (os.getenv("scryptuserssh") or "").strip().strip('"').strip("'")
    password = (os.getenv("scryptpass") or "").strip().strip('"').strip("'")
    return username, password

def _scrypted_setting_truthy(value):
    if value is True:
        return True
    if isinstance(value, (int, float)) and value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "yes"):
        return True
    return False

def _scrypted_no_audio_wanted_names(unit):
    unit_name = str(unit or "").strip().upper()
    if not unit_name:
        return set()
    return {f"SC-{unit_name}-{suffix}" for suffix in SCRYPTED_NO_AUDIO_SUFFIXES}

def set_scrypted_no_audio(unit):
    """Enable No Audio on Fisheye/C1-180/C2-180 cameras. Skip if already set."""
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    tld = work_tld()
    if not tld:
        return None, "workTLD is not set in .env"
    username, password = _scrypted_web_credentials()
    if not username or not password:
        return None, "scryptuserweb/scryptpass are not set in .env"
    base_url = f"https://{unit.lower()}.{tld}"
    wanted = _scrypted_no_audio_wanted_names(unit)
    if not wanted:
        return None, "Missing unit"

    async def _run():
        try:
            from scrypted_sdk import connect_scrypted_client
        except ImportError:
            return None, (
                "scrypted-sdk is not installed "
                "(pip install scrypted-sdk)"
            )
        loop = asyncio.get_running_loop()
        try:
            transport, sdk = await connect_scrypted_client(
                loop, base_url, username, password
            )
        except Exception as exc:
            return None, f"Scrypted login failed for {unit}: {exc}"
        devices = {}
        try:
            for device_id in sdk.systemManager.getSystemState():
                device = sdk.systemManager.getDeviceById(device_id)
                name = str(getattr(device, "name", "") or "").strip()
                if name.upper() not in wanted:
                    continue
                if str(getattr(device, "type", "") or "") != "Camera":
                    continue
                devices[name.upper()] = device

            results = []
            for target in sorted(wanted):
                device = devices.get(target)
                if device is None:
                    results.append({
                        "name": target,
                        "status": "missing",
                        "message": "camera not found",
                    })
                    continue
                try:
                    settings = await device.getSettings()
                    current = None
                    for setting in settings or []:
                        if (setting or {}).get("key") == SCRYPTED_NO_AUDIO_SETTING_KEY:
                            current = (setting or {}).get("value")
                            break
                    if _scrypted_setting_truthy(current):
                        results.append({
                            "name": getattr(device, "name", target),
                            "status": "already_set",
                            "message": "No Audio already enabled",
                        })
                        continue
                    await device.putSetting(SCRYPTED_NO_AUDIO_SETTING_KEY, True)
                    results.append({
                        "name": getattr(device, "name", target),
                        "status": "set",
                        "message": "No Audio enabled",
                    })
                except Exception as exc:
                    results.append({
                        "name": getattr(device, "name", target),
                        "status": "error",
                        "message": str(exc),
                    })
            return {
                "unit": unit,
                "base_url": base_url,
                "devices": results,
            }, None
        finally:
            try:
                await transport.close()
            except Exception:
                pass

    try:
        return asyncio.run(_run())
    except Exception as exc:
        return None, f"Scrypted No Audio failed for {unit}: {exc}"

def shield_web_url(site_id):
    """Open Shield at https://shield.{workTLD}/site/{siteID}."""
    tld = work_tld()
    site = str(site_id or "").strip()
    if not tld or not site:
        return ""
    return f"https://shield.{tld}/site/{site}"


def erp_site_web_url(site_id):
    """Open ERP Site at https://erp.{workTLD}/app/site/{siteID}."""
    base = erp_base_url()
    site = str(site_id or "").strip()
    if not base or not site:
        return ""
    return f"{base}/app/site/{site}"


def erp_event_records_web_url(unit):
    """Open ERP Event Records filtered by SC-{unit}% for the last 7 days."""
    from urllib.parse import urlencode

    base = erp_base_url()
    unit_name = str(unit or "").strip()
    if unit_name.upper().startswith("SC-"):
        unit_name = unit_name[3:].strip()
    if not base or not unit_name:
        return ""
    query = urlencode(
        {
            "component": f'["like","SC-{unit_name}%"]',
            "creation": '["Timespan","last 7 days"]',
        }
    )
    return f"{base}/app/event-record?{query}"


def resolve_dashboard_site_id(unit, subject=""):
    """Resolve Site ID the same way Open Shield does, including project subjects."""
    subject_text = str(subject or "").strip()
    if _is_noc_deployment_project_subject(subject_text):
        site, error = find_erp_site_by_project_subject(subject_text)
        if error:
            return "", error
        site_id = str((site or {}).get("site_id") or "").strip()
        if not site_id:
            return "", "Matched Site has no id"
        return site_id, None
    return resolve_shield_site_id(unit, subject_text)

toolkit = zabbix_tool.Zabbix_Tool_Kit()
username = os.getenv("username")
idUser = os.getenv("idUser")
counter = 0
api_token = os.getenv("victron_token")
url = f"https://vrmapi.victronenergy.com/v2/users/{idUser}/installations"
all_battery_units = []
all_battery_units_mapped = []
low_battery_units = []
depleted_battery_units = []
net_array = []
false_mu_array = []
rd_down = []
fisheyes = []
missing = []
missing_zab = []
false_positive = []
netsheet = resource_path("net_sheet.csv")
mapsheet = resource_path("map_sheet.csv")
false_mu = resource_path("false_mu.csv")

headers = {
    "idUser": f"{idUser}",
    "X-Authorization": f"Token {api_token}"
}

response = requests.get(url, headers=headers)

def main():
    while True:
        global counter
        if counter < 1:
            print('')
            print("USERNAME:", username)
            generate_net_array()
            counter += 1
            if os.path.isfile(mapsheet):
                try:
                    with open(mapsheet, "r", newline='') as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            all_battery_units_mapped.append(row)
                except OSError:
                    pass

        print("Command menu: ")
        print("1. Check if unit is installed in VRM")
        print("2. Check individual trailer battery health using its MU#")
        print("3. Print low battery list")
        print("4. Print depleted battery list")
        print("5. Print all battery list")
        print("6. Check individual trailer battery health using its RD#")
        print("7. Compare mesh and issue reports")
        print("8. Update unit battery array and create or update map sheet (needed for 3, 4, and 5)")
        print("9. Print unit map sheet")
        print("10. Search C:\\Temp directory for fisheye snapshots of a specific unit for solar panel analysis")
        print("11. Update unit battery health list (needed for 3, 4, and 5)")
        print("12. Screenshot fisheye on low battery units")
        print("13. Compare Zabbix and mesh outages for unique units, then check for false positives")
        print("14. Query Zabbix for outage events for a specific unit")
        print("15. Check battery health for all units")
        print("16. Check patch version for specific unit")
        print("17. Check patch version for all units")
        print("18. Unit Outage Verification Tool")
        print("19. Check outages for missing initial/recovery emails")
        cmd = input("Enter a number 1-27: ")
        if cmd == "1":
            install_checker()
        elif cmd == "2":
            unit = str(input('Input MUXXXX: '))
            unit_battery_health(unit)
        elif cmd == "3":
            low_battery_list()
        elif cmd == "4":
            depleted_battery_list()
        elif cmd == "5":
            all_battery_list()
        elif cmd == "6":
            while True:
                unit = str(input('Input RDXXXX to fetch battery. Unit must be 3300 or greater: '))
                if unit.lower() == "quit":
                    break
                else:
                    get_rd_battery(unit)
        elif cmd == "7":
            compare_reports()
            validate_reports_mesh()
        elif cmd == "8":
                all_unit_battery_health()
                with open(mapsheet, 'w', newline='') as csvfile:
                    fieldnames = ["name", "trailer"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_battery_units_mapped)
        elif cmd == "9":
            for row in all_battery_units_mapped:
                print(row["name"] + " - " + row["trailer"])
        elif cmd == "10":
            unit = input('Enter unit to search for in C:\\Temp: ')
            file_search(unit)
        elif cmd == "11":
            print("Scanning unit battery health and updating lists...")
            all_unit_battery_health()
        elif cmd == "12":
            print('Screenshotting fisheye on low battery units and saving to C:\Temp...')
            low_battery_rd_fisheye_tool()
            low_battery_fisheye_screenshotter()
        elif cmd == "13":
            compare_zabbix()
            validate_reports_zab()
        elif cmd == "14":
            try:
                toolkit.query_zabbix_events()
            except:
                print('No zabbix events found')
        elif cmd == "15":
            all_unit_battery_health()
        elif cmd == "16":
            unit = input('Enter unit to check patch version: ')
            check_patch_version(unit)
        elif cmd == "17":
            check_all_patches()
        elif cmd == "18":
            validate_issues_report()
        elif cmd == "19":
            check_missing_recovery_emails()
        elif cmd == "20":
            unit = input('Enter unit to check switch uptime: ')
            get_robofiber_uptime(unit)
        elif cmd == "21":
            unit = input('Enter unit to check switch logs from last month: ')
            get_robofiber_logs_last_month(unit)
        elif cmd == "22":
            unit = input('Enter unit to check switch logs link events for last month: ')
            get_robofiber_logs_link_events(unit)
        elif cmd == "23":
            trailer = input('Enter MU to clear coordinates (e.g. MU7027): ').strip()
            result, error = clear_mu_coordinates(trailer)
            if error:
                print(error)
            else:
                print(
                    f"Cleared coordinates on {result['component']}: "
                    f"was ({result['old_latitude']}, {result['old_longitude']}) "
                    f"-> ({result['latitude']}, {result['longitude']})"
                )
        elif cmd == "24":
            trailer = input('Enter MU to clear site link (e.g. MU7027): ').strip()
            result, error = clear_mu_site(trailer)
            if error:
                print(error)
            else:
                if result.get("unchanged"):
                    print(f"{result['component']} site link already empty")
                else:
                    print(
                        f"Cleared site on {result['component']}: "
                        f"{result['old_site']} -> (empty)"
                    )
        elif cmd == "25":
            unit = input('Enter nuc to reboot ')
            ok, message = reboot_nuc(unit)
            if not ok:
                print(message)
        elif cmd == "26":
            unit = input('Enter scrypted to reboot ')
            ok, message = reboot_scrypted(unit)
            if not ok:
                print(message)
        elif cmd == "27":
            unit = input('Enter nuc to chkdsk: ')
            drive = input('Enter drive: ')
            ok, message, output = chkdsk(unit, drive, read_only=True)
            if output:
                print(output)
            print(message if ok else f"Error: {message}")
        elif cmd == "cls" or cmd == "clr" or cmd == "clear":
            clear_terminal()
        elif cmd == "quit" or cmd == "exit":
            sys.exit()

        else:
            print('Invalid command. Please enter a number one through fourteen.')

def clear_terminal():
    os.sys('cls')

def clear_old_reports(mesh_path, issue_path):
    print('Attempting clear here~~~~~~~~~~~')
    try:
        os.remove(mesh_path)
        os.remove(issue_path)
        print("Cleared old reports")
    except Exception as e:
        print(f'Failed to remove: {e}')
    print('Beginning outage validation')
    
def file_search(unit, root=r'C:\Temp'):
    results = []

    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if unit.lower() in filename.lower():
                print(f'Found snapshot: {filename}')
                results.append(os.path.join(dirpath, filename))
    
    if results:
        for file in results:
            print(f'{file}')
    return results

def _ping_reachable(output):
    return bool(output) and "Reply from" in output and "TTL=" in output and "expired" not in output

def _ping_host(host, max_echoes=4, timeout_ms=1000, stop_on_success=True):
    """Send up to max_echoes pings; optionally stop after the first successful Reply/TTL."""
    host = str(host or "").strip()
    if not host:
        return None, ""
    chunks = []
    last_code = 1
    for _ in range(max(1, int(max_echoes))):
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), host],
            text=True,
            capture_output=True,
        )
        last_code = result.returncode
        text = result.stdout or ""
        if text:
            chunks.append(text.rstrip())
        combined = "\n".join(chunks)
        if stop_on_success and _ping_reachable(combined):
            return 0, combined
    combined = "\n".join(chunks)
    if _ping_reachable(combined):
        return 0, combined
    return last_code, combined

def ping_router(unit, max_echoes=4, stop_on_success=True):
    row = ensure_unit_net_info(unit, needed_indexes=(1,))
    if not row or len(row) <= 1 or not str(row[1]).strip():
        return None
    return _ping_host(
        row[1],
        max_echoes=max_echoes,
        stop_on_success=stop_on_success,
    )

def router_ip_for_unit(unit):
    """Return the netsheet router IP/host for a unit, or empty string."""
    row = ensure_unit_net_info(unit, needed_indexes=(1,))
    if not row or len(row) <= 1:
        return ""
    return _host_only(row[1]) or str(row[1]).strip()

def ping_router_status(unit, mode="quick"):
    """
    Ping the unit router.
    mode: quick (stop on first reply), fixed (always 4 echoes).
    Returns (payload_dict, error).
    """
    unit_key = _normalize_netsheet_unit(unit) or str(unit or "").strip()
    if not unit_key:
        return None, "Missing unit"
    mode_key = str(mode or "quick").strip().lower()
    stop_on_success = mode_key != "fixed"
    label = "Quick Validate" if stop_on_success else "Ping Router"
    result = ping_router(unit_key, max_echoes=4, stop_on_success=stop_on_success)
    if result is None:
        return None, f"No router IP for {unit_key}"
    code, output = result
    reachable = _ping_reachable(output)
    return {
        "unit": unit_key,
        "ip": router_ip_for_unit(unit_key),
        "mode": "quick" if stop_on_success else "fixed",
        "label": label,
        "reachable": reachable,
        "returncode": code,
        "output": output or "",
    }, None

_LONG_PING_MAX_SEC = 30 * 60
_long_ping_lock = threading.Lock()
_long_ping_jobs = {}


def _kill_process_tree(process):
    if process is None or process.poll() is not None:
        return
    pid = process.pid
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def stop_router_long_ping(job_id, reason="stopped"):
    """Stop a long ping job. Returns (ok, message, job_info)."""
    job_key = str(job_id or "").strip()
    with _long_ping_lock:
        job = _long_ping_jobs.get(job_key)
        if not job:
            return False, "Long ping job not found", None
        timer = job.get("timer")
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass
            job["timer"] = None
        process = job.get("process")
        already_done = process is None or process.poll() is not None
        if not already_done:
            _kill_process_tree(process)
        job["stop_reason"] = reason or "stopped"
        job["stopped"] = True
        info = {
            "job_id": job_key,
            "unit": job.get("unit"),
            "ip": job.get("ip"),
            "reason": job["stop_reason"],
        }
    return True, f"Long ping {job['stop_reason']}", info


def start_router_long_ping(unit):
    """
    Start `ping {router_ip} -t` for a unit.
    Auto-cancels after 30 minutes. Returns (payload, error).
    """
    import uuid

    unit_key = _normalize_netsheet_unit(unit) or str(unit or "").strip()
    if not unit_key:
        return None, "Missing unit"
    ip = router_ip_for_unit(unit_key)
    if not ip:
        return None, f"No router IP for {unit_key}"

    replace_ids = []
    with _long_ping_lock:
        for existing_id, existing in list(_long_ping_jobs.items()):
            if existing.get("unit") == unit_key and not existing.get("stopped"):
                replace_ids.append(existing_id)
    for existing_id in replace_ids:
        stop_router_long_ping(existing_id, reason="replaced")

    try:
        process = subprocess.Popen(
            ["ping", ip, "-t"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        return None, f"Unable to start ping: {exc}"

    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "unit": unit_key,
        "ip": ip,
        "process": process,
        "started": time.time(),
        "stopped": False,
        "stop_reason": "",
        "timer": None,
    }

    def _auto_stop(job_key=job_id):
        stop_router_long_ping(job_key, reason="auto-cancelled after 30 minutes")

    timer = threading.Timer(_LONG_PING_MAX_SEC, _auto_stop)
    timer.daemon = True
    job["timer"] = timer
    with _long_ping_lock:
        _long_ping_jobs[job_id] = job
    timer.start()

    return {
        "job_id": job_id,
        "unit": unit_key,
        "ip": ip,
        "max_seconds": _LONG_PING_MAX_SEC,
    }, None


def iter_router_long_ping_output(job_id):
    """Yield stdout lines from a long ping job until it exits or is stopped."""
    job_key = str(job_id or "").strip()
    with _long_ping_lock:
        job = _long_ping_jobs.get(job_key)
        process = job.get("process") if job else None
        unit = job.get("unit") if job else ""
        ip = job.get("ip") if job else ""
    if not job or process is None:
        yield f"Long ping job {job_key} not found\n"
        return
    yield f"Long ping started for {unit} ({ip}) — toggle off to cancel (auto-stop 30 min)\n"
    try:
        for line in process.stdout:
            yield line
            with _long_ping_lock:
                current = _long_ping_jobs.get(job_key) or {}
                if current.get("stopped"):
                    break
    except Exception as exc:
        yield f"Long ping read error: {exc}\n"
    finally:
        with _long_ping_lock:
            current = _long_ping_jobs.get(job_key) or {}
            reason = current.get("stop_reason") or "finished"
            if process.poll() is None:
                _kill_process_tree(process)
            current["stopped"] = True
            timer = current.get("timer")
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass
                current["timer"] = None
        yield f"Long ping {reason} for {unit} ({ip})\n"

def ping_speaker(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(4,))
    if not row or len(row) <= 4 or not str(row[4]).strip():
        return None
    return _ping_host(row[4])


def _detect_switch_type(banner):
    text = str(banner or "")
    if "HGW-802SM-BT" in text or "Welcome to the CLI for HGW" in text:
        return "robofiber"
    if "BusyBox" in text:
        return "netonix"
    return ""

def _format_switch_uptime_seconds(total_seconds):
    try:
        total = int(float(total_seconds))
    except (TypeError, ValueError):
        return str(total_seconds)
    if total < 0:
        total = 0
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return (
        f"{days} Days {hours} Hours {minutes} Mins {seconds} Secs"
    )

ROBOFIBER_SYSLOG_SKIP = ("DHCP", "admin", "Vtysh", "Set Time")
NETONIX_SYSLOG_SKIP = (
    "lease time 600",
    "Sending renew...",
    "starting ntpclient",
    "sysinit",
    "i2c",
    "loaded",
    "using base",
    "using storage",
    "Please be",
    "Emulator",
    "taints kernel",
    "Luton",
    "version",
    "BusyBox",
    "Freeing",
    "cubic registered",
    "(C)",
    "Redundant FIS",
    "RedBoot config",
    "FIS Directory",
    "protocol family 10",
    "Privacy Extensions",
    "Registered protocol",
    "Mounted root",
    "Setting MAC",
)

SWITCH_LOG_MAX_PAGES = 50
SWITCH_LOG_MAX_AGE_DAYS = 30

def _switch_log_cutoff():
    return _arizona_now() - timedelta(days=SWITCH_LOG_MAX_AGE_DAYS)

def _parse_switch_log_timestamp(text):
    """Parse leading timestamps from Robofiber/Netonix switch log lines."""
    text = str(text or "").strip()
    for pattern, fmt in (
        (r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", "%Y-%m-%d %H:%M:%S"),
        (r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})", "%Y/%m/%d %H:%M:%S"),
        (r"^(\d{1,2}/\d{1,2}/\d{4} \d{2}:\d{2}:\d{2})", "%m/%d/%Y %H:%M:%S"),
    ):
        match = re.match(pattern, text)
        if not match:
            continue
        try:
            dt = datetime.strptime(match.group(1), fmt)
            return dt.replace(tzinfo=ARIZONA_TZ)
        except ValueError:
            continue
    match = re.match(
        r"^([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})",
        text,
    )
    if match:
        now = _arizona_now()
        try:
            dt = datetime.strptime(
                f"{match.group(1)} {match.group(2)} {match.group(3)} {now.year}",
                "%b %d %H:%M:%S %Y",
            ).replace(tzinfo=ARIZONA_TZ)
            if dt > now + timedelta(days=1):
                dt = dt.replace(year=now.year - 1)
            return dt
        except ValueError:
            pass
    return None

def _clean_switch_log_line(text):
    """Strip pager redraw backspaces from Robofiber/Netonix log lines."""
    text = str(text or "").strip()
    if "\x08" in text:
        text = re.sub(r"\x08.", "", text)
        text = re.sub(r"\s+", " ", text).strip()
    return text

def _iter_switch_log_lines(
    session,
    command,
    max_pages=SWITCH_LOG_MAX_PAGES,
    cutoff=None,
    newest_first=True,
):
    """Yield switch log lines; stop once logs are older than cutoff on newest-first switches."""
    if cutoff is None:
        cutoff = _switch_log_cutoff()
    channel = session["channel"]
    channel.send(f"{command}\n")
    time.sleep(2)
    output = ""
    page = 0
    idle_rounds = 0
    while page < max_pages:
        time.sleep(0.75)
        if channel.recv_ready():
            idle_rounds = 0
            chunk = channel.recv(65535).decode("utf-8", errors="replace")
            output += chunk
            for line in chunk.splitlines():
                text = _clean_switch_log_line(line)
                if not _is_switch_log_line(text):
                    continue
                ts = _parse_switch_log_timestamp(text)
                if ts is not None and ts < cutoff:
                    if newest_first:
                        return
                    continue
                yield text
            if "more" in chunk.lower():
                page += 1
                channel.send(" ")
                continue
            tail = output[-120:]
            if _at_switch_prompt(output) and "--More--" not in tail:
                break
        else:
            idle_rounds += 1
            tail = output[-120:]
            if "--More--" in tail:
                page += 1
                channel.send(" ")
                idle_rounds = 0
                continue
            if idle_rounds >= 3 and _at_switch_prompt(output):
                break
            if idle_rounds >= 5:
                break

def _open_switch_session(unit):
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    if not net_array:
        generate_net_array()
    load_dotenv(env_path)
    row = ensure_unit_net_info(unit, needed_indexes=(2,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[2] if len(row) > 2 else "")
    if not ip:
        return None, f"No switch IP for {unit}"
    switchuser = os.getenv("switchuser")
    switchpass = os.getenv("switchpass")
    if not switchuser or not switchpass:
        return None, "switchuser/switchpass not set in .env"

    switch_ssh = paramiko.SSHClient()
    try:
        switch_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        switch_ssh.connect(
            hostname=ip,
            port=22,
            username=switchuser,
            password=switchpass,
            timeout=20,
            allow_agent=False,
            look_for_keys=False,
        )
        channel = switch_ssh.invoke_shell()
        time.sleep(1.5)
        banner = ""
        if channel.recv_ready():
            banner = channel.recv(65535).decode("utf-8", errors="replace")
        switch_type = _detect_switch_type(banner)
        if not switch_type:
            return None, (
                f"Unknown switch type for {unit} ({ip}); "
                "expected Robofiber or Netonix banner"
            )
        return {
            "client": switch_ssh,
            "channel": channel,
            "ip": ip,
            "unit": unit,
            "banner": banner,
            "switch_type": switch_type,
        }, None
    except Exception as exc:
        try:
            switch_ssh.close()
        except Exception:
            pass
        return None, f"Switch SSH failed for {unit} ({ip}): {exc}"

def _close_switch_session(session):
    if not session:
        return
    try:
        session["client"].close()
    except Exception:
        pass

def _run_switch_shell_command(session, command, max_pages=10):
    channel = session["channel"]
    channel.send(f"{command}\n")
    time.sleep(2)
    output = ""
    page = 0
    idle_rounds = 0
    while page < max_pages:
        time.sleep(0.75)
        if channel.recv_ready():
            idle_rounds = 0
            chunk = channel.recv(65535).decode("utf-8", errors="replace")
            output += chunk
            if "more" in chunk.lower():
                page += 1
                channel.send(" ")
                continue
            tail = output[-120:]
            if _at_switch_prompt(output) and "--More--" not in tail:
                break
        else:
            idle_rounds += 1
            tail = output[-120:]
            if "--More--" in tail:
                page += 1
                channel.send(" ")
                idle_rounds = 0
                continue
            if idle_rounds >= 3 and _at_switch_prompt(output):
                break
            if idle_rounds >= 5:
                break
    return output

def _is_switch_log_line(text):
    if not text:
        return False
    if "--More--" in text:
        return False
    if text.endswith("#"):
        return False
    lowered = text.lower()
    return lowered not in (
        "show log",
        "show syslog messages",
        "show system",
        "show status",
    )

def _at_switch_prompt(output):
    """True when the shell prompt (not log text) is at the end of captured output."""
    for line in reversed(output.splitlines()):
        text = line.strip()
        if not text or "--More--" in text:
            continue
        return text.endswith("#") and " " not in text
    return False

def _is_link_event_line(text, switch_type):
    lower = text.lower()
    if switch_type == "netonix":
        return (
            "link state" in lower
            or "link up" in lower
            or "link down" in lower
        )
    return (
        "link up" in lower
        or "link down" in lower
        or "status changed to link" in lower
    )

def _fetch_switch_log(unit, max_pages=SWITCH_LOG_MAX_PAGES):
    session, error = _open_switch_session(unit)
    if error:
        return None, None, None, error
    command = (
        "show log"
        if session["switch_type"] == "netonix"
        else "show syslog messages"
    )
    try:
        output = _run_switch_shell_command(session, command, max_pages=max_pages)
    except Exception as exc:
        return None, session["ip"], session["switch_type"], (
            f"Switch log command failed for {unit}: {exc}"
        )
    finally:
        _close_switch_session(session)
    if not output.strip():
        return None, session["ip"], session["switch_type"], (
            f"No log output from switch for {unit}"
        )
    return output, session["ip"], session["switch_type"], None

def get_robofiber_uptime(unit):
    """SSH to the unit switch and return uptime (Robofiber or Netonix)."""
    session, error = _open_switch_session(unit)
    if error:
        print(error)
        return None, error
    try:
        if session["switch_type"] == "netonix":
            output = _run_switch_shell_command(session, "show status", max_pages=1)
            uptime_text = ""
            uptime_seconds = ""
            for line in output.splitlines():
                match = re.search(
                    r"Uptime:\s*([\d.]+)\s*seconds",
                    line,
                    flags=re.IGNORECASE,
                )
                if match:
                    uptime_seconds = match.group(1)
                    formatted = _format_switch_uptime_seconds(uptime_seconds)
                    uptime_text = f"Uptime: {formatted}"
                    print(uptime_text)
                    break
            if not uptime_text:
                msg = f"No uptime in show status output for {unit}"
                print(msg)
                return None, msg
            return {
                "unit": session["unit"],
                "ip": session["ip"],
                "switch_type": session["switch_type"],
                "lines": [uptime_text],
                "system_name": "",
                "uptime": uptime_text,
                "output": uptime_text,
            }, None

        output = _run_switch_shell_command(session, "show system", max_pages=1)
        keywords = ("System Name", "Running Time")
        lines = []
        for line in output.splitlines():
            text = line.strip()
            if text and any(keyword in text for keyword in keywords):
                lines.append(text)
                print(text)
        if not lines:
            msg = f"No System Name/Running Time in switch output for {unit}"
            print(msg)
            return None, msg
        return {
            "unit": session["unit"],
            "ip": session["ip"],
            "switch_type": session["switch_type"],
            "lines": lines,
            "system_name": next(
                (line for line in lines if "System Name" in line),
                "",
            ),
            "uptime": next(
                (line for line in lines if "Running Time" in line),
                "",
            ),
            "output": "\n".join(lines),
        }, None
    except Exception as exc:
        msg = f"Switch uptime failed for {unit}: {exc}"
        print(msg)
        return None, msg
    finally:
        _close_switch_session(session)

def get_robofiber_logs_last_month(unit):
    """Return filtered switch syslog/log lines from the first 10 pager pages."""
    output, ip, switch_type, error = _fetch_switch_log(unit)
    if error:
        print(error)
        return None, error
    skip_terms = (
        NETONIX_SYSLOG_SKIP
        if switch_type == "netonix"
        else ROBOFIBER_SYSLOG_SKIP
    )
    lines = []
    for line in output.splitlines():
        text = line.strip()
        if not _is_switch_log_line(text):
            continue
        lower = text.lower()
        if any(skip.lower() in lower for skip in skip_terms):
            continue
        lines.append(text)
        print(text)
    if not lines:
        msg = (
            f"No syslog lines for {unit} "
            f"(checked {SWITCH_LOG_MAX_PAGES} pager pages; logs may be deeper or filtered)"
        )
        print(msg)
        return None, msg
    return {
        "unit": unit,
        "ip": ip,
        "switch_type": switch_type,
        "lines": lines,
        "output": "\n".join(lines),
        "count": len(lines),
    }, None

def get_robofiber_logs_link_events(unit):
    """Return switch link up/down lines from the last 30 days."""
    session, error = _open_switch_session(unit)
    if error:
        print(error)
        return None, error
    command = (
        "show log"
        if session["switch_type"] == "netonix"
        else "show syslog messages"
    )
    cutoff = _switch_log_cutoff()
    ip = session["ip"]
    switch_type = session["switch_type"]
    lines = []
    try:
        for text in _iter_switch_log_lines(
            session,
            command,
            cutoff=cutoff,
            # Both Netonix and Robofiber buffers are oldest-first; keep paging
            # through sub-cutoff lines instead of stopping at the first old entry.
            newest_first=False,
        ):
            if not _is_link_event_line(text, switch_type):
                continue
            lines.append(text)
            print(text)
    except Exception as exc:
        return None, (
            f"Switch link log command failed for {unit}: {exc}"
        )
    finally:
        _close_switch_session(session)
    if not lines:
        msg = (
            f"No link up/down log lines for {unit} "
            f"in the last {SWITCH_LOG_MAX_AGE_DAYS} days"
        )
        print(msg)
        return None, msg
    return {
        "unit": unit,
        "ip": ip,
        "switch_type": switch_type,
        "lines": lines,
        "output": "\n".join(lines),
        "count": len(lines),
    }, None

CAMERA_ENDPOINTS = {
    "fisheye": (5, "Fisheye"),
    "camera1": (6, "Camera 1"),
    "camera2": (7, "Camera 2"),
    "camera3": (8, "Camera 3"),
    "camera4": (9, "Camera 4"),
}
HIGH_UNIT_OPEN_CAMERA_TARGETS = frozenset({"fisheye", "camera1", "camera2"})

def ping_camera(unit, target):
    endpoint = CAMERA_ENDPOINTS.get(target)
    if not endpoint:
        return None
    column, _ = endpoint
    row = ensure_unit_net_info(unit, needed_indexes=(column,))
    if not row or len(row) <= column or not str(row[column]).strip():
        return None
    host = str(row[column]).strip()
    if target == "fisheye":
        host = _host_only(host)
    return _ping_host(host)
    
def ping_switch(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(2,))
    if not row or len(row) <= 2 or not str(row[2]).strip():
        return None
    return _ping_host(row[2])
    
def ping_nuc(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(3,))
    if not row or len(row) <= 3 or not str(row[3]).strip():
        return None
    return _ping_host(row[3])

def uses_pve(unit):
    try:
        return int(unit[-4:]) >= 3300
    except ValueError:
        return False

def is_fd_unit(unit):
    return str(unit or "").strip().upper().startswith("FD")

def unit_number(unit):
    try:
        return int(str(unit).strip()[-4:])
    except (TypeError, ValueError):
        return None

def open_camera_targets_for_unit(unit):
    """Open Cameras targets; units above 3300 only have fisheye + C1/C2 (C3/C4 duplicate C1/C2 in netsheet)."""
    n = unit_number(unit)
    if n is not None and n > 3300:
        return HIGH_UNIT_OPEN_CAMERA_TARGETS
    return frozenset(CAMERA_ENDPOINTS.keys())

def in_potential_stale_vpn_range(unit):
    """Units 3000-3199 inclusive may be potentially stale VPN when both router and NUC are down."""
    n = unit_number(unit)
    return n is not None and 3000 <= n <= 3199

def ping_compute(unit):
    return ping_pve(unit) if uses_pve(unit) else ping_nuc(unit)

def compute_host_label(unit):
    return "PVE" if uses_pve(unit) else "NUC"

def _nuc_ip(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(3,))
    if not row or len(row) <= 3:
        return ""
    return _host_only(row[3])

def _scrypted_ip(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(12,))
    if not row or len(row) <= 12:
        return ""
    return _host_only(row[12])

def nuc_scrypted_same_ip(unit):
    """True when net-sheet NUC and Scrypted columns share the same host IP."""
    nuc = _nuc_ip(unit)
    scrypted = _scrypted_ip(unit)
    return bool(nuc and scrypted and nuc == scrypted)

def ping_pve(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(11,))
    if not row or len(row) <= 11 or not str(row[11]).strip():
        return None
    return _ping_host(row[11])

def ping_scrypted(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(12,))
    if not row or len(row) <= 12 or not str(row[12]).strip():
        return None
    return _ping_host(row[12]) 

EXPECTED_PATCH_DATE = "20260728"
PATCH_VERSION_COMMAND = (
    "sudo -S sed -nE 's/.*Version:[[:space:]]*(sentracam-watch-[0-9]{8}-[0-9]{6}\\.tar\\.gz).*/\\1/p' "
    "$(ls -t /var/log/sentracam/install-*.log | head -1) | head -1"
)

def _scrypted_ssh_target(unit):
    if not net_array:
        generate_net_array()
    unit = str(unit or "").strip()
    if not unit:
        return None, "", "Missing unit"
    row = ensure_unit_net_info(unit, needed_indexes=(12,))
    if not row:
        return None, "", f"Unit {unit} not found in net sheet"
    host = _host_only(row[12] if len(row) > 12 else "")
    if not host:
        return None, "", f"No Scrypted IP configured for {unit}"
    return row, host, None

def _looks_like_sudo_password_prompt(text):
    """True when the remote PTY is waiting for a sudo password."""
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in lines[-3:]:
        lower = line.lower()
        if "[sudo] password" in lower and lower.endswith(":"):
            return True
    return False

def _run_remote_pty_command(client, command, password, timeout=300, max_sudo_prompts=25):
    """
    Run a remote command on a PTY and feed sudo passwords whenever prompted.
    Deploy scripts often invoke nested sudo calls that each need a password.
    """
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport not available")
    channel = transport.open_session()
    channel.settimeout(1.0)
    channel.get_pty(width=200, height=50)
    channel.exec_command(command)

    chunks = []
    pending = ""
    password_sent = 0
    deadline = time.monotonic() + timeout

    def maybe_send_password(force=False):
        nonlocal password_sent, pending
        if password_sent >= max_sudo_prompts:
            return
        if force or _looks_like_sudo_password_prompt(pending):
            channel.send(f"{password}\n")
            password_sent += 1
            pending = ""

    # First sudo -S prompt may appear before any output is readable.
    time.sleep(0.3)
    maybe_send_password(force=True)

    while time.monotonic() < deadline:
        got_data = False
        if channel.recv_ready():
            got_data = True
            data = channel.recv(65535).decode("utf-8", errors="replace")
            chunks.append(data)
            pending = (pending + data)[-800:]
            maybe_send_password()
        if channel.exit_status_ready():
            while channel.recv_ready():
                chunks.append(
                    channel.recv(65535).decode("utf-8", errors="replace")
                )
            break
        if not got_data:
            time.sleep(0.15)

    if not channel.exit_status_ready():
        channel.close()
        raise TimeoutError(f"Remote command timed out after {timeout}s")

    exit_status = channel.recv_exit_status()
    return "".join(chunks), exit_status

def _parse_patch_version(raw):
    text = str(raw or "").strip()
    match = re.search(
        r"sentracam-watch-(\d{8})-(\d{6})\.tar\.gz",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return {
            "package": match.group(0),
            "date": match.group(1),
            "time": match.group(2),
            "raw": text,
        }
    if len(text) >= 24 and text[16:24].isdigit():
        return {
            "package": text,
            "date": text[16:24],
            "time": text[25:31] if len(text) >= 31 else "",
            "raw": text,
        }
    return {
        "package": text,
        "date": "",
        "time": "",
        "raw": text,
    }

def get_unit_patch_version(unit):
    """SSH to Scrypted and read the latest sentracam-watch install package version."""
    row, host, error = _scrypted_ssh_target(unit)
    if error:
        return None, error
    username, password = _scrypted_ssh_credentials()
    if not username or not password:
        return None, "scryptuserssh/scryptpass are not set in .env"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Checking patch version for {unit} ({host})")
        client.connect(hostname=host, port=22, username=username, password=password, timeout=20)
        result, exit_status = _run_remote_pty_command(
            client,
            PATCH_VERSION_COMMAND,
            password,
            timeout=60,
            max_sudo_prompts=3,
        )
        err = ""
        parsed = _parse_patch_version(result)
        if not parsed.get("date"):
            detail = (result or err or "no version found").strip()
            return None, f"Could not parse patch version for {unit}: {detail[:300]}"
        if exit_status != 0:
            detail = (result or err or f"exit code {exit_status}").strip()
            return None, f"Patch version check failed for {unit}: {detail[:300]}"
        up_to_date = parsed["date"] == EXPECTED_PATCH_DATE
        if up_to_date:
            print(f"Patch version is {parsed['date']}, up to date")
        else:
            print(
                f"Patch version is not {EXPECTED_PATCH_DATE}, it is {parsed['date']}"
            )
        return {
            "unit": unit,
            "host": host,
            "package": parsed["package"],
            "date": parsed["date"],
            "expected_date": EXPECTED_PATCH_DATE,
            "up_to_date": up_to_date,
            "raw": parsed["raw"],
        }, None
    except Exception as exc:
        return None, f"Error checking patch version for {unit}: {exc}"
    finally:
        try:
            client.close()
        except Exception:
            pass

def update_unit_patch_version(unit):
    """SSH to Scrypted and run the install command from .env to update the patch."""
    row, host, error = _scrypted_ssh_target(unit)
    if error:
        return None, error
    username, password = _scrypted_ssh_credentials()
    install_cmd = (os.getenv("install") or "").strip().strip('"').strip("'")
    if not username or not password:
        return None, "scryptuserssh/scryptpass are not set in .env"
    if not install_cmd:
        return None, "install is not set in .env"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Updating patch version for {unit} ({host})")
        client.connect(hostname=host, port=22, username=username, password=password, timeout=20)
        update_command = f"sudo -S bash -c {shlex.quote(install_cmd)}"
        combined, exit_status = _run_remote_pty_command(
            client,
            update_command,
            password,
            timeout=300,
        )
        output = combined.strip()
        stderr_text = ""
        print(f"Update result: {combined}")
        payload = {
            "unit": unit,
            "host": host,
            "output": output,
            "stderr": stderr_text,
            "exit_code": exit_status,
        }
        if exit_status != 0:
            detail = stderr_text or output or f"exit code {exit_status}"
            return payload, (
                f"Patch update failed for {unit} (exit {exit_status}): "
                f"{detail[:500]}"
            )
        return payload, None
    except Exception as exc:
        return {
            "unit": unit,
            "host": host,
            "output": "",
            "stderr": str(exc),
            "exit_code": None,
        }, f"Error updating patch version for {unit}: {exc}"
    finally:
        try:
            client.close()
        except Exception:
            pass

def check_patch_version(unit):
    info, error = get_unit_patch_version(unit)
    if error:
        print(error)
        return
    if info.get("up_to_date"):
        print(f"Patch version is {info['date']}, up to date")
        return
    print(f"Patch version is not {EXPECTED_PATCH_DATE}, it is {info.get('date')}")
    run_update = input("Run update? (Y/N)")
    if run_update.lower()[:1] != "y":
        print("Skipping update")
        return
    print("Updating...")
    result, update_error = update_unit_patch_version(unit)
    if update_error:
        print(update_error)
        return
    print(f"Update result: {result.get('output') or ''}")

def check_all_patches():
    patch_array = []
    if not net_array:
        generate_net_array()
    for row in net_array:
        try:
            rdnum = int(str(row[0]).strip()[-4:])
        except (TypeError, ValueError):
            continue
        if rdnum < 3300:
            continue
        info, error = get_unit_patch_version(row[0])
        if error:
            print(error)
            continue
        if not info.get("up_to_date"):
            print(
                f"Patch version is not {EXPECTED_PATCH_DATE}, "
                f"it is {info.get('date')}. Appended to array"
            )
            patch_array.append(row[0])
    for line in patch_array:
        print(f"{line} is not up to date")
    return patch_array

def validate_reports_zab():
        false_positives = []
    # zabbix_array = []
    # zabbix_path = os.path.join(os.path.expanduser('~'), "Downloads", "zbx_problems_export.csv")
    # with open(zabbix_path, 'r', newline='') as csvfile:
    #     csvreader = csv.reader(csvfile)
    #     for line in csvreader:
    #         zabbix_array.append(line)
        for line in missing_zab:
            print(line)
            if line[-6:].lower() == "router":
                host = line
                unit = line[:6]
                code, output = ping_router(unit)
                
                #output = output.splitlines()
                for line in output.splitlines():
                    print(line)
                #for line in output:
                if "Reply from" in output and "TTL=" in output and "expired" not in output:
                    print(f'False positive unit: {code}: {host}')
                    false_positives.append(host)

            elif line[-6:].lower() == "switch":
                host = line
                unit = line[:6]
                code, output = ping_switch(unit)
                #output = output.splitlines()
                for line in output.splitlines():
                    print(line)
                #for line in output:
                if "Reply from" in output and "TTL=" in output and "expired" not in output:
                    print(f'False positive unit: {code}: {host}')
                    false_positives.append(host)

            elif line[-7:].lower() == "speaker":
                host = line
                unit = line[:6]
                code, output = ping_speaker(unit)
                #output = output.splitlines()
                for line in output.splitlines():
                    print(line)
                #for line in output:
                if "Reply from" in output and "TTL=" in output and "expired" not in output:
                    print(f'False positive unit: {code}: {host}')
                    false_positives.append(host)
       
            elif line[-3:].lower() == "pve":
                host = line
                unit = line[:6]
                code, output = ping_pve(unit)
                #output = output.splitlines()
                for line in output.splitlines():
                    print(line)
                #for line in output:
                if "Reply from" in output and "TTL=" in output and "expired" not in output:
                    print(f'False positive unit: {code}: {host}')
                    false_positives.append(host)

            elif line[-3:].lower() == "nuc":
                host = line
                unit = line[:6]
                code, output = ping_nuc(unit)
                for line in output.splitlines():
                    print(line)
                if "Reply from" in output and "TTL=" in output and "expired" not in output:
                    print(f'False positive unit: {code}: {host}')
                    false_positives.append(host)

            elif line[-2:].lower() == "vm":
                host = line
                unit = line[:6]
                code, output = ping_scrypted(unit)
                #output = output.splitlines()
                for line in output.splitlines():
                    print(line)
                if "Reply from" in output and "TTL=" in output and "expired" not in output:
                    print(f'False positive unit: {code}: {host}')
                    false_positives.append(host)


        if len(false_positives) > 0:
            print('False positives: ')
            for line in false_positives:
                print(line)

def _safe_ping_result(result, missing_message=""):
    if result is None:
        return None, str(missing_message or "")
    return result

def _validate_unit_connectivity(
    unit,
    false_positives,
    nuc_down,
    stale_vpn,
    truly_down,
    scrypted_outage=None,
    result_value=None,
    log=print,
):
    if scrypted_outage is None:
        scrypted_outage = []
    if result_value is None:
        result_value = unit

    log(f"Checking {unit}'s router...")
    code, output = _safe_ping_result(ping_router(unit))
    log(output)
    router_up = _ping_reachable(output)

    # Units >= 3300: router -> PVE only (never NUC). Scrypted only if both are up.
    if uses_pve(unit):
        log(f"Checking {unit}'s PVE...")
        code, pve_output = _safe_ping_result(ping_pve(unit))
        log(pve_output)
        pve_up = _ping_reachable(pve_output)

        if router_up and not pve_up:
            log(f"Router up, PVE down — offline compute: {unit}")
            nuc_down.append(result_value)
            return

        if router_up and pve_up:
            log(f"Checking {unit}'s Scrypted...")
            code, scrypt_output = _safe_ping_result(ping_scrypted(unit))
            log(scrypt_output)
            if _ping_reachable(scrypt_output):
                log(f"Router, PVE, and Scrypted are online — unit fully up: {unit}")
                false_positives.append(result_value)
            elif nuc_scrypted_same_ip(unit):
                log(
                    f"Router and PVE up, shared NUC/Scrypted IP down — "
                    f"offline compute: {unit}"
                )
                nuc_down.append(result_value)
            else:
                log(f"Router and PVE up, Scrypted down — Scrypted outage: {unit}")
                scrypted_outage.append(result_value)
            return

        if not router_up and not pve_up:
            log(f"Router and PVE down — unit fully down (skipping Scrypted): {unit}")
            truly_down.append(result_value)
            return

        # Router down, PVE up
        log(f"Router down, PVE up on {unit}")
        truly_down.append(result_value)
        return

    # Pre-3300 units
    host = compute_host_label(unit)
    if router_up:
        log(f"Checking {unit}'s {host}...")
        missing_compute = _missing_netsheet_ip_message(
            unit, (11,) if uses_pve(unit) else (3,)
        )
        code, output = _safe_ping_result(
            ping_compute(unit),
            missing_message=missing_compute,
        )
        log(output)
        if _ping_reachable(output):
            log(f"Both {host} and Router are online {code}, false positive: {unit}")
            false_positives.append(result_value)
        else:
            log(f"{host} is down, router is up. Bounce {host}.")
            nuc_down.append(result_value)
        return

    # Router down (pre-3300)
    if in_potential_stale_vpn_range(unit):
        compute_result = ping_nuc
        host_checked = "NUC"
    else:
        compute_result = ping_compute
        host_checked = host
    log(f"Checking {unit}'s {host_checked}...")
    missing_compute = _missing_netsheet_ip_message(
        unit,
        (11,) if host_checked == "PVE" else (3,),
    )
    code, output = _safe_ping_result(
        compute_result(unit),
        missing_message=missing_compute,
    )
    log(output)
    if _ping_reachable(output):
        # Classic stale VPN (router down, compute up) — only for the 3000-3199 band
        if in_potential_stale_vpn_range(unit):
            log(f"{host_checked} is up {code}, router is down, potentially stale VPN on {unit}")
            stale_vpn.append(result_value)
        else:
            log(f"{host_checked} is up {code}, router is down on {unit} (outside potential-stale range)")
            truly_down.append(result_value)
    else:
        # Both unreachable: band 3000-3199 => potentially stale VPN; else truly down
        if in_potential_stale_vpn_range(unit):
            log(f"Router and NUC unreachable on {unit} (3000-3199) — potentially stale VPN")
            stale_vpn.append(result_value)
        else:
            log(f"{host_checked} and router are offline. {code}")
            truly_down.append(result_value)

def _issue_ticket_url(issue_id):
    if not issue_id:
        return ""
    return f"{erp_base_url()}/app/issue/{issue_id}"

def _net_row_for_unit(unit):
    if not unit:
        return None
    unit_up = str(unit).strip().upper()
    for row in net_array:
        if row and str(row[0]).strip().upper() == unit_up:
            return row
    return None

def _host_only(value):
    text = (value or "").strip()
    if not text:
        return ""
    text = text.replace("http://", "").replace("https://", "").split("/")[0]
    if ":" in text:
        return text.rsplit(":", 1)[0]
    return text

# Netsheet column layout + ERP/v19 backfill.
# Swap fetch_unit_inventory() later for a native ERP client; keep the exe path for now.
NETSHEET_HEADER = [
    "Unit/Site",
    "Router IP",
    "Switch IP",
    "NUC IP",
    "Speaker IP",
    "Fisheye",
    "Camera 1",
    "Camera 2",
    "Camera 3",
    "Camera 4",
    "Relay",
    "PVE",
    "Scripted",
]
NETSHEET_COL_COUNT = len(NETSHEET_HEADER)
NETSHEET_IP_INDEXES = tuple(range(1, NETSHEET_COL_COUNT))
V19_INVENTORY_TIMEOUT_SEC = 45
_netsheet_file_lock = threading.Lock()
_v19_inventory_cache = {}
_v19_inventory_cache_lock = threading.Lock()

def _normalize_netsheet_unit(unit):
    text = str(unit or "").strip().upper()
    if text.startswith("SC-"):
        text = text[3:]
    match = re.fullmatch(r"([A-Z]{2,4})(\d{3,6})", text)
    if not match:
        return ""
    return f"{match.group(1)}{match.group(2)}"

def _blank_netsheet_row(unit):
    row = [""] * NETSHEET_COL_COUNT
    row[0] = _normalize_netsheet_unit(unit)
    return row

def _pad_netsheet_row(row):
    cells = [str(cell) if cell is not None else "" for cell in (row or [])]
    if len(cells) < NETSHEET_COL_COUNT:
        cells.extend([""] * (NETSHEET_COL_COUNT - len(cells)))
    return cells[:NETSHEET_COL_COUNT]

def _netsheet_row_is_sparse(row, needed_indexes=None):
    if not row:
        return True
    indexes = needed_indexes if needed_indexes is not None else NETSHEET_IP_INDEXES
    padded = _pad_netsheet_row(row)
    for index in indexes:
        if index <= 0 or index >= NETSHEET_COL_COUNT:
            continue
        if not str(padded[index] or "").strip():
            return True
    return False

def _map_v19_role_to_netsheet_index(role):
    text = re.sub(r"\s+", " ", str(role or "").strip())
    if not text:
        return None
    lower = text.lower()
    camera_match = re.fullmatch(r"camera\s*(\d+)", lower)
    if camera_match:
        number = int(camera_match.group(1))
        if 1 <= number <= 4:
            return 5 + number
        return None
    role_map = {
        "router": 1,
        "switch": 2,
        "nuc": 3,
        "speaker": 4,
        "fisheye": 5,
        "relay": 10,
        "pve": 11,
        "scrypted": 12,
        "scripted": 12,
    }
    return role_map.get(lower)

def parse_v19_inventory_output(text):
    """Parse Sentra_Network_toolv19 show/inventory text into netsheet column -> host."""
    inventory = {}
    lines = str(text or "").splitlines()
    in_table = False
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Components:"):
            in_table = True
            continue
        if not in_table:
            continue
        if set(stripped) <= {"-"}:
            continue
        if re.match(r"^Role\b", stripped, flags=re.IGNORECASE):
            continue
        if stripped.startswith("Enter command") or stripped.startswith("[ERP]"):
            continue
        # Prefer fixed-width Role (12) + Component ID (52) from v19 print_inventory.
        role = ""
        address = ""
        if len(line) >= 64:
            role = line[:12].strip()
            address = line[64:].strip()
        if not role or not address:
            parts = re.split(r"\s{2,}", stripped)
            if len(parts) >= 3:
                role = parts[0]
                address = parts[-1]
            elif len(parts) == 2 and re.search(r"\d+\.\d+\.\d+\.\d+", parts[1]):
                role = parts[0]
                address = parts[1]
        host = _host_only(address)
        if not host or not re.search(r"\d+\.\d+\.\d+\.\d+", host):
            continue
        index = _map_v19_role_to_netsheet_index(role)
        if index is None:
            continue
        # Keep first non-empty mapping per column.
        if index not in inventory:
            inventory[index] = host
    return inventory

def run_v19_commands(unit, commands, timeout=None):
    """
    Run one or more stdin commands against Sentra_Network_toolv19.exe.
    Returns (stdout_text, error_message).
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return "", f"Invalid unit: {unit}"

    tool_dir = sentra_network_tool_v19_dir()
    exe_path = os.path.join(tool_dir, "Sentra_Network_toolv19.exe")
    if not os.path.isfile(exe_path):
        return "", f"Network utility not found: {exe_path}"

    command_list = [str(item).strip() for item in (commands or []) if str(item).strip()]
    if not command_list:
        return "", "No v19 commands provided"

    stdin_input = "\n".join(command_list + ["close"]) + "\n"
    timeout_sec = timeout or V19_INVENTORY_TIMEOUT_SEC

    try:
        process = subprocess.Popen(
            [exe_path, unit_key],
            cwd=tool_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            shell=False,
        )
    except OSError as exc:
        return "", f"Unable to start Sentra_Network_toolv19.exe: {exc}"

    try:
        stdout, _ = process.communicate(input=stdin_input, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            stdout, _ = process.communicate(timeout=5)
        except Exception:
            stdout = ""
        return stdout or "", f"v19 command timed out for {unit_key}"

    output = stdout or ""
    if process.returncode not in (0, None) and not output.strip():
        return output, f"v19 exited with code {process.returncode} for {unit_key}"
    return output, None

def fetch_unit_inventory_via_v19_exe(unit):
    """
    Query unit IPs through Sentra_Network_toolv19.exe (stdin protocol).
    Returns (inventory_dict, error). inventory keys are netsheet column indexes.
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return {}, f"Invalid unit: {unit}"

    with _v19_inventory_cache_lock:
        cached = _v19_inventory_cache.get(unit_key)
    if cached is not None:
        inventory, error, _ts = cached
        return dict(inventory), error

    output, error = run_v19_commands(unit, ["show"], timeout=V19_INVENTORY_TIMEOUT_SEC)
    if error and not output.strip():
        with _v19_inventory_cache_lock:
            _v19_inventory_cache[unit_key] = ({}, error, time.time())
        return {}, error

    if "No ERP component was found" in output:
        error = f"No ERP component was found for {unit_key}"
        with _v19_inventory_cache_lock:
            _v19_inventory_cache[unit_key] = ({}, error, time.time())
        return {}, error

    inventory = parse_v19_inventory_output(output)
    if not inventory:
        error = f"No IP addresses parsed from v19 for {unit_key}"
        with _v19_inventory_cache_lock:
            _v19_inventory_cache[unit_key] = ({}, error, time.time())
        return {}, error

    with _v19_inventory_cache_lock:
        _v19_inventory_cache[unit_key] = (dict(inventory), None, time.time())
    return inventory, None


# ICCID issuer prefixes observed on Sentra SIMs (first 6 digits).
ICCID_CARRIER_PREFIXES = (
    ("891480", "Verizon Wireless"),
    ("890124", "TMOBILE"),
    ("890103", "AT&T"),
)


def carrier_from_iccid(iccid):
    """Map an ICCID to AT&T / TMOBILE / Verizon Wireless via Cell carrier prefix."""
    digits = re.sub(r"\D", "", str(iccid or ""))
    if len(digits) < 6:
        return None
    for prefix, name in ICCID_CARRIER_PREFIXES:
        if digits.startswith(prefix):
            return name
    return None


def parse_v19_sim_rows(text):
    """Parse unique SIM rows from Sentra_Network_toolv19 inventory output."""
    sims = []
    seen = set()
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped.upper().startswith("SIM"):
            continue
        iccid = ""
        address = ""
        if len(line) >= 64 and line[:12].strip().upper() == "SIM":
            iccid = line[12:64].strip()
            address = line[64:].strip()
        else:
            parts = re.split(r"\s{2,}", stripped)
            if len(parts) >= 2 and parts[0].upper() == "SIM":
                iccid = parts[1].strip()
                if len(parts) > 2:
                    address = parts[-1].strip()
        digits = re.sub(r"\D", "", iccid)
        # Real ICCIDs are typically 19–22 digits; skip junk like role noise ("2").
        if len(digits) < 15:
            continue
        if digits in seen:
            continue
        seen.add(digits)
        host = _host_only(address) if address else ""
        if host and not re.search(r"\d+\.\d+\.\d+\.\d+", host):
            host = ""
        sims.append(
            {
                "iccid": digits,
                "address": host,
                "carrier": carrier_from_iccid(digits),
                "prefix": digits[:6],
            }
        )
    return sims


def get_unit_carriers(unit):
    """
    Query v19 inventory SIMs and return mapped cell carriers.
    Returns (payload_dict, error_message).
    """
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None, f"Invalid unit: {unit}"

    output, error = run_v19_commands(unit_key, ["show"], timeout=V19_INVENTORY_TIMEOUT_SEC)
    if error and not str(output or "").strip():
        return None, error
    if "No ERP component was found" in (output or ""):
        return None, f"No ERP component was found for {unit_key}"

    sims = parse_v19_sim_rows(output)
    if not sims:
        return None, f"No SIM components found for {unit_key}"

    carriers = []
    for sim in sims:
        name = sim.get("carrier")
        if name and name not in carriers:
            carriers.append(name)
    unknown = [sim["iccid"] for sim in sims if not sim.get("carrier")]
    if not carriers:
        detail = ", ".join(unknown) if unknown else "unknown"
        return None, f"Unknown carrier prefix for ICCID(s): {detail}"

    return {
        "unit": unit_key,
        "carriers": carriers,
        "carrier": " / ".join(carriers),
        "sims": sims,
        "unknown_iccids": unknown,
    }, None


def fetch_unit_inventory(unit):
    """Unit inventory provider. Currently v19.exe; swap to native ERP later."""
    return fetch_unit_inventory_via_v19_exe(unit)

def merge_sparse_net_row(existing_row, unit, inventory):
    """Fill blank netsheet cells from inventory; never overwrite non-empty values."""
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return existing_row, False
    row = _pad_netsheet_row(existing_row) if existing_row else _blank_netsheet_row(unit_key)
    if not row[0]:
        row[0] = unit_key
    changed = False
    for index, host in (inventory or {}).items():
        try:
            index = int(index)
        except (TypeError, ValueError):
            continue
        if index <= 0 or index >= NETSHEET_COL_COUNT:
            continue
        value = _host_only(host)
        if not value:
            continue
        if str(row[index] or "").strip():
            continue
        row[index] = value
        changed = True
    return row, changed

def _read_netsheet_rows_from_disk():
    path = netsheet
    if not os.path.isfile(path):
        return list(NETSHEET_HEADER), []
    with open(path, "r", newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)
    if not rows:
        return list(NETSHEET_HEADER), []
    header = rows[0]
    body = rows[1:]
    # Treat first row as header when it looks like the known header.
    if str(header[0] or "").strip().lower() in ("unit/site", "unit"):
        return header, body
    return list(NETSHEET_HEADER), rows

def persist_net_sheet_updates(updated_by_unit):
    """
    Apply sparse row updates to net_sheet.csv under a lock.
    updated_by_unit: {UNIT: row_list}
    """
    if not updated_by_unit:
        return 0
    with _netsheet_file_lock:
        header, body = _read_netsheet_rows_from_disk()
        by_unit = {}
        order = []
        for row in body:
            if not row:
                continue
            key = str(row[0] or "").strip().upper()
            if not key:
                continue
            if key not in by_unit:
                order.append(key)
            by_unit[key] = _pad_netsheet_row(row)
        for unit_key, row in updated_by_unit.items():
            key = _normalize_netsheet_unit(unit_key)
            if not key:
                continue
            padded = _pad_netsheet_row(row)
            padded[0] = key
            if key not in by_unit:
                order.append(key)
            by_unit[key] = padded
        out_rows = [header if header else list(NETSHEET_HEADER)]
        for key in order:
            out_rows.append(by_unit[key])
        directory = os.path.dirname(os.path.abspath(netsheet)) or "."
        fd, temp_path = tempfile.mkstemp(
            prefix="net_sheet_",
            suffix=".csv",
            dir=directory,
        )
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(out_rows)
            os.replace(temp_path, netsheet)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise
        generate_net_array()
    return len(updated_by_unit)

def _missing_netsheet_ip_message(unit, needed_indexes):
    """Explain when a netsheet IP column is still empty after v19 backfill."""
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return f"No netsheet row for {unit}"
    row = _net_row_for_unit(unit_key) or []
    padded = _pad_netsheet_row(row)
    missing_labels = []
    for index in needed_indexes or ():
        if index <= 0 or index >= NETSHEET_COL_COUNT:
            continue
        if not str(padded[index] or "").strip():
            missing_labels.append(NETSHEET_HEADER[index])
    if not missing_labels:
        return ""
    return (
        f"No {'/'.join(missing_labels)} in net sheet or ERP/v19 inventory for {unit_key}"
    )

def ensure_unit_net_info(unit, needed_indexes=None):
    """
    Ensure netsheet has a row for unit; backfill blank cells via v19/ERP when sparse.
    Returns the in-memory netsheet row (may still be incomplete on provider failure).
    """
    if not net_array:
        generate_net_array()
    unit_key = _normalize_netsheet_unit(unit)
    if not unit_key:
        return None
    row = _net_row_for_unit(unit_key)
    if not _netsheet_row_is_sparse(row, needed_indexes=needed_indexes):
        return row

    inventory, error = fetch_unit_inventory(unit_key)
    if error:
        print(f"[netsheet] ERP/v19 lookup for {unit_key}: {error}")
        return row
    merged, changed = merge_sparse_net_row(row, unit_key, inventory)
    if changed:
        try:
            persist_net_sheet_updates({unit_key: merged})
            print(f"[netsheet] Backfilled {unit_key} from v19 ERP inventory")
        except OSError as exc:
            print(f"[netsheet] Failed to persist {unit_key}: {exc}")
            return merged
        row = _net_row_for_unit(unit_key) or merged
    else:
        row = row or merged

    if needed_indexes:
        missing_msg = _missing_netsheet_ip_message(unit_key, needed_indexes)
        if missing_msg:
            print(f"[netsheet] {missing_msg}")
    return row

def sync_netsheet_from_erp(units=None, include_sparse_sheet_rows=True, max_units=200):
    """
    Bulk backfill missing/sparse netsheet rows via v19.
    units: optional iterable of unit codes (from tickets/projects).
    """
    if not net_array:
        generate_net_array()

    candidates = []
    seen = set()

    def _add(unit_code):
        key = _normalize_netsheet_unit(unit_code)
        if not key or key in seen:
            return
        seen.add(key)
        candidates.append(key)

    for unit_code in units or []:
        _add(unit_code)

    if include_sparse_sheet_rows:
        # Prefer FD and high RD when capping.
        sparse = []
        for row in net_array:
            if not row:
                continue
            key = _normalize_netsheet_unit(row[0])
            if not key or key in seen:
                continue
            if _netsheet_row_is_sparse(row):
                sparse.append(key)
        def _sparse_sort_key(code):
            prefix = code[:2]
            number = unit_number(code) or 0
            fd_first = 0 if prefix == "FD" else 1
            high = 0 if number >= 3300 else 1
            return (fd_first, high, -number, code)
        for key in sorted(sparse, key=_sparse_sort_key):
            if key not in seen:
                seen.add(key)
                candidates.append(key)

    if max_units and len(candidates) > max_units:
        candidates = candidates[:max_units]

    stats = {
        "checked": 0,
        "added": 0,
        "backfilled": 0,
        "unchanged": 0,
        "failed": 0,
        "errors": [],
        "updated_units": [],
    }
    pending_writes = {}

    for unit_key in candidates:
        stats["checked"] += 1
        existing = _net_row_for_unit(unit_key)
        had_row = existing is not None
        if not _netsheet_row_is_sparse(existing):
            stats["unchanged"] += 1
            continue
        inventory, error = fetch_unit_inventory(unit_key)
        if error:
            stats["failed"] += 1
            stats["errors"].append(f"{unit_key}: {error}")
            continue
        merged, changed = merge_sparse_net_row(existing, unit_key, inventory)
        if not changed:
            stats["unchanged"] += 1
            continue
        pending_writes[unit_key] = merged
        stats["updated_units"].append(unit_key)
        if had_row:
            stats["backfilled"] += 1
        else:
            stats["added"] += 1

    if pending_writes:
        try:
            persist_net_sheet_updates(pending_writes)
        except OSError as exc:
            stats["errors"].append(f"Failed to write net_sheet.csv: {exc}")
            stats["failed"] += len(pending_writes)
            stats["added"] = 0
            stats["backfilled"] = 0
            stats["updated_units"] = []

    return stats

def _unit_device_info(unit):
    row = ensure_unit_net_info(unit, needed_indexes=(2, 5, 10, 11, 12))
    switch_url = ""
    fisheye_ip = ""
    pve_ip = ""
    relay_ip = ""
    scrypted_ip = ""
    if row:
        if len(row) > 2:
            switch_ip = _host_only(row[2])
            if switch_ip:
                switch_url = f"http://{switch_ip}/"
        if len(row) > 5:
            fisheye_ip = _host_only(row[5])
        if len(row) > 10:
            relay_ip = _host_only(row[10])
        if len(row) > 11:
            pve_ip = _host_only(row[11])
        if len(row) > 12:
            scrypted_ip = _host_only(row[12])
    n = unit_number(unit)
    has_pve = n is not None and n > 3300 and bool(pve_ip)
    has_relay = n is not None and n >= 3100 and bool(relay_ip)
    has_platform = n is not None and n >= 3300
    has_scrypted = bool(scrypted_ip)
    platform_url = f"https://{scrypted_ip}:5000/system/" if has_platform and scrypted_ip else ""
    scrypted_url = scrypted_open_url(unit) if has_scrypted else ""
    return switch_url, fisheye_ip, pve_ip, has_pve, has_relay, has_platform, platform_url, has_scrypted, scrypted_url

def unit_context_for_ui(unit):
    """Build device context for ad-hoc unit tools (netsheet backfill included)."""
    raw = str(unit or "").strip().upper()
    unit_key = _normalize_netsheet_unit(raw)
    if not unit_key and re.fullmatch(r"\d{3,6}", raw):
        unit_key = _normalize_netsheet_unit("RD" + raw)
    if not unit_key:
        return None, f"Invalid unit code: {unit}"
    needed_indexes = (2, 5, 10, 11, 12)
    row_before = _net_row_for_unit(unit_key)
    was_sparse = _netsheet_row_is_sparse(row_before, needed_indexes=needed_indexes)
    ensure_unit_net_info(unit_key, needed_indexes=needed_indexes)
    row_after = _net_row_for_unit(unit_key)
    backfilled = was_sparse and not _netsheet_row_is_sparse(row_after, needed_indexes=needed_indexes)
    (
        switch_url,
        fisheye_ip,
        pve_ip,
        has_pve,
        has_relay,
        has_platform,
        platform_url,
        has_scrypted,
        scrypted_url,
    ) = _unit_device_info(unit_key)
    vrm_mu, vrm_url = _vrm_info_from_subject("", unit_key)
    return {
        "ok": True,
        "unit": unit_key,
        "switch_url": switch_url,
        "fisheye_ip": fisheye_ip,
        "pve_ip": pve_ip,
        "has_pve": has_pve,
        "has_relay": has_relay,
        "has_platform": has_platform,
        "platform_url": platform_url,
        "has_scrypted": has_scrypted,
        "scrypted_url": scrypted_url,
        "compute_label": compute_host_label(unit_key),
        "vrm_mu": vrm_mu,
        "vrm_url": vrm_url,
        "backfilled": backfilled,
    }, None

def authenticated_switch_url(unit):
    info, error = switch_login_info(unit)
    if error:
        return None, error
    return info["url"], None

def switch_login_info(unit):
    """Return switch login details. Units above 3080 use /dologin.asp."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    row = ensure_unit_net_info(unit, needed_indexes=(2,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[2] if len(row) > 2 else "")
    if not ip:
        return None, f"No switch IP for {unit}"
    switchuser = os.getenv("switchuser")
    switchpass = os.getenv("switchpass")
    if not switchuser or not switchpass:
        return None, "switchuser/switchpass not set in .env"
    n = unit_number(unit)
    use_dologin = n is not None and n > 3080
    user = quote(str(switchuser), safe="")
    password = quote(str(switchpass), safe="")
    if use_dologin:
        url = f"http://{ip}/dologin.asp"
    else:
        url = f"http://{user}:{password}@{ip}/"
    return {
        "unit": unit,
        "ip": ip,
        "username": switchuser,
        "password": switchpass,
        "use_dologin": use_dologin,
        "url": url,
    }, None

def _normalize_mu_code(mu):
    text = str(mu or "").strip().upper()
    if text.startswith("SC-"):
        text = text[3:]
    text = re.sub(r"\s+", "", text)
    if re.fullmatch(r"MU\d{3,6}", text):
        return text
    return ""


def mu_trailer_from_subject(subject, unit=None):
    """Return MU trailer code (e.g. MU7027) from a termination project/issue subject."""
    parent = _parent_mu_from_subject(subject)
    if parent:
        return parent.upper()
    normalized = _normalize_mu_code(unit)
    if normalized:
        return normalized
    head = _head_unit_from_subject(subject)
    if head and head.upper().startswith("MU"):
        return head.upper()
    match = re.search(r"\bMU\s*(\d{3,6})\b", str(subject or ""), flags=re.IGNORECASE)
    if match:
        return f"MU{match.group(1)}"
    return ""


def clear_mu_coordinates(mu):
    """
    Clear latitude/longitude on SC-{MU} Component in ERP.
    Returns (result_dict, error).
    """
    doc, component_name, error = _fetch_mu_component_doc(mu)
    if error:
        return None, error

    old_lat = doc.get("latitude")
    old_lon = doc.get("longitude")

    update_payload = {"latitude": 0, "longitude": 0}
    patch_doc, error = _patch_mu_component(component_name, update_payload)
    if error:
        return None, error

    return {
        "component": component_name,
        "mu": _normalize_mu_code(mu),
        "old_latitude": old_lat,
        "old_longitude": old_lon,
        "latitude": patch_doc.get("latitude", 0),
        "longitude": patch_doc.get("longitude", 0),
    }, None


def clear_mu_coordinates_from_subject(subject, unit=None):
    """Resolve MU from subject/unit and clear its ERP coordinates."""
    mu_code = mu_trailer_from_subject(subject, unit=unit)
    if not mu_code:
        return None, "Could not determine MU trailer from subject"
    return clear_mu_coordinates(mu_code)


def _get_erp_component_doc(component_name):
    """Load Component by name. Returns (doc, error)."""
    name = str(component_name or "").strip()
    if not name:
        return None, "Missing Component name"

    url = f"{erp_base_url()}/api/resource/Component/{quote(name, safe='')}"
    headers = _erp_headers()

    try:
        get_resp = requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as exc:
        return None, f"ERP request failed: {exc}"

    if get_resp.status_code == 404:
        return None, f"Component {name} was not found in ERP"
    if not get_resp.ok:
        return None, _erp_response_error(get_resp)

    payload = get_resp.json() or {}
    doc = payload.get("data")
    if not isinstance(doc, dict):
        return None, f"ERP did not return Component {name}"
    return doc, None


def _fetch_mu_component_doc(mu):
    """Load and validate SC-{MU} Component. Returns (doc, component_name, error)."""
    mu_code = _normalize_mu_code(mu)
    if not mu_code:
        return None, "", f"Invalid MU code: {mu}"

    component_name = _sc_component_name(mu_code)
    doc, error = _get_erp_component_doc(component_name)
    if error:
        return None, "", error

    comp_type = str(doc.get("type") or "").strip().upper()
    if comp_type and comp_type != "MU":
        return None, "", f"{component_name} is type {comp_type}, not MU"

    return doc, component_name, None


def _patch_mu_component(component_name, update_payload):
    """PATCH Component fields. Returns (patched_doc, error)."""
    name = str(component_name or "").strip()
    if not name:
        return None, "Missing Component name"
    if not isinstance(update_payload, dict) or not update_payload:
        return None, "Missing Component update payload"

    url = f"{erp_base_url()}/api/resource/Component/{quote(name, safe='')}"
    headers = {
        **_erp_headers(),
        "Content-Type": "application/json",
    }
    try:
        patch_resp = requests.patch(
            url,
            headers=headers,
            json=update_payload,
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"ERP update failed: {exc}"

    if not patch_resp.ok:
        return None, _erp_response_error(patch_resp)

    patch_doc = (patch_resp.json() or {}).get("data") or {}
    return patch_doc, None


def clear_mu_site(mu):
    """
    Clear Site link on SC-{MU} Component in ERP.
    Returns (result_dict, error).
    """
    mu_code = _normalize_mu_code(mu)
    if not mu_code:
        return None, f"Invalid MU code: {mu}"

    doc, component_name, error = _fetch_mu_component_doc(mu_code)
    if error:
        return None, error

    expected_name = _sc_component_name(mu_code)
    if component_name != expected_name:
        return None, (
            f"Safety check failed: expected {expected_name}, got {component_name}"
        )

    old_site = str(doc.get("site") or "").strip()
    if _erp_field_empty(doc.get("site")):
        return {
            "component": component_name,
            "mu": mu_code,
            "old_site": "",
            "site": "",
            "unchanged": True,
        }, None

    patch_doc, error = _patch_mu_component(component_name, {"site": ""})
    if error:
        return None, error

    new_site = str(patch_doc.get("site") or "").strip()
    if not _erp_field_empty(patch_doc.get("site")):
        verify_doc, verify_error = _get_erp_component_doc(component_name)
        if verify_error:
            return None, (
                f"Site clear may have failed; re-check failed: {verify_error}"
            )
        new_site = str(verify_doc.get("site") or "").strip()
        if not _erp_field_empty(verify_doc.get("site")):
            return None, (
                f"Site link still set on {component_name}: {new_site}"
            )

    return {
        "component": component_name,
        "mu": mu_code,
        "old_site": old_site,
        "site": new_site,
        "unchanged": False,
    }, None


def clear_mu_site_from_subject(subject, unit=None):
    """Resolve MU from subject/unit and clear its ERP Site link."""
    mu_code = mu_trailer_from_subject(subject, unit=unit)
    if not mu_code:
        return None, "Could not determine MU trailer from subject"
    return clear_mu_site(mu_code)

def relay_login_info(unit):
    """Open the relay with fishuser/fishpass basic auth. Units 3100+ only."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    n = unit_number(unit)
    if n is None or n < 3100:
        return None, f"{unit} is not 3100+"
    row = ensure_unit_net_info(unit, needed_indexes=(10,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[10] if len(row) > 10 else "")
    if not ip:
        return None, f"No relay IP for {unit}"
    fishuser = (os.getenv("fishuser") or "").strip().strip('"').strip("'")
    fishpass = (os.getenv("fishpass") or "").strip().strip('"').strip("'")
    if not fishuser or not fishpass:
        return None, "fishuser/fishpass not set in .env"
    user = quote(str(fishuser), safe="")
    password = quote(str(fishpass), safe="")
    #er
    return {
        "unit": unit,
        "ip": ip,
        "username": fishuser,
        "password": fishpass,
        "url": f"http://{user}:{password}@{ip}/",
    }, None

def _pve_ssh_credentials():
    """
    SSH credentials for the PVE host shell (qm commands).
    Uses pvesshuser, or pveuser with any @pam/@pve realm suffix stripped.
    """
    load_dotenv(env_path)
    username = (
        os.getenv("pvesshuser")
        or os.getenv("pveuser")
        or ""
    ).strip().strip('"').strip("'")
    password = (os.getenv("pvepass") or "").strip().strip('"').strip("'")
    if not username or not password:
        return None, None, "Set pvesshuser (or pveuser) and pvepass in .env"
    if "@" in username:
        username = username.split("@", 1)[0]
    return username, password, None

def pve_login_info(unit):
    """Open PVE on port 8006 with pveuser/pvepass. Units above 3300 only."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    n = unit_number(unit)
    if n is None or n <= 3300:
        return None, f"{unit} is not above 3300"
    row = ensure_unit_net_info(unit, needed_indexes=(11,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[11] if len(row) > 11 else "")
    if not ip:
        return None, f"No PVE IP for {unit}"
    pveuser = (os.getenv("pveuser") or "").strip().strip('"').strip("'")
    pvepass = (os.getenv("pvepass") or "").strip().strip('"').strip("'")
    if not pveuser or not pvepass:
        return None, "pveuser/pvepass not set in .env"
    user = quote(str(pveuser), safe="")
    password = quote(str(pvepass), safe="")
    return {
        "unit": unit,
        "ip": ip,
        "username": pveuser,
        "password": pvepass,
        "url": f"https://{ip}:8006/",
        "auth_url": f"https://{user}:{password}@{ip}:8006/",
    }, None

_pve_proxy_lock = threading.Lock()
_pve_proxies = {}
_PVE_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "cookie",
}
_PVE_SKIP_RESP_HEADERS = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "content-encoding",
    "content-length",
    "set-cookie",
}

def fetch_pve_ticket(ip, username, password):
    username = (username or "").strip()
    password = password or ""
    candidates = []
    if username:
        candidates.append(username)
        if "@" not in username:
            candidates.append(f"{username}@pam")
            candidates.append(f"{username}@pve")
    endpoints = (
        f"https://{ip}:8006/api2/json/access/ticket",
        f"https://{ip}:8006/api2/extjs/access/ticket",
    )
    last_error = "PVE login failed"
    for user in candidates:
        payloads = [{"username": user, "password": password}]
        if "@" in user:
            name, realm = user.rsplit("@", 1)
            payloads.append({"username": name, "password": password, "realm": realm})
        for url in endpoints:
            for payload in payloads:
                try:
                    response = requests.post(url, data=payload, verify=False, timeout=15)
                    if response.status_code == 401:
                        last_error = (
                            f"PVE login failed: 401 authentication failure for {user}. "
                            "Set pveuser in .env as user@pam or user@pve (example: root@pam)."
                        )
                        continue
                    response.raise_for_status()
                    body = response.json() or {}
                    data = body.get("data") or body
                    ticket = data.get("ticket")
                    csrf = data.get("CSRFPreventionToken")
                    if not ticket:
                        last_error = "PVE login returned no ticket"
                        continue
                    return ticket, csrf, None
                except requests.RequestException as e:
                    last_error = f"PVE login failed: {e}"
                    continue
    return None, None, last_error

class _PVEProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        return

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_PATCH(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def do_HEAD(self):
        self._proxy(include_body=False)

    def _refresh_ticket(self):
        state = self.server.pve_state
        ticket, csrf, error = fetch_pve_ticket(state["ip"], state["username"], state["password"])
        if error:
            return error
        state["ticket"] = ticket
        state["csrf"] = csrf
        return None

    def _proxy(self, include_body=True):
        state = self.server.pve_state
        target = f"https://{state['ip']}:8006{self.path}"
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in _PVE_HOP_HEADERS
        }
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        if self.command in ("POST", "PUT", "DELETE", "PATCH") and state.get("csrf"):
            headers["CSRFPreventionToken"] = state["csrf"]

        def send_upstream():
            return requests.request(
                self.command,
                target,
                headers=headers,
                data=body,
                cookies={"PVEAuthCookie": state["ticket"]},
                verify=False,
                allow_redirects=False,
                timeout=45,
            )

        try:
            resp = send_upstream()
            if resp.status_code == 401:
                refresh_error = self._refresh_ticket()
                if not refresh_error:
                    resp = send_upstream()
        except requests.RequestException as e:
            self.send_error(502, f"PVE proxy error: {e}")
            return

        self.send_response(resp.status_code)
        local_origin = f"http://127.0.0.1:{state['port']}"
        remote_origin = f"https://{state['ip']}:8006"
        for key, value in resp.headers.items():
            if key.lower() in _PVE_SKIP_RESP_HEADERS:
                continue
            if key.lower() == "location":
                value = value.replace(remote_origin, local_origin)
            self.send_header(key, value)
        content = resp.content or b""
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "html" in ctype or "javascript" in ctype:
            content = content.replace(remote_origin.encode("utf-8"), local_origin.encode("utf-8"))
        self.send_header("Content-Length", str(len(content)))
        self.send_header(
            "Set-Cookie",
            f"PVEAuthCookie={quote(state['ticket'], safe='')}; Path=/",
        )
        self.end_headers()
        if include_body and self.command != "HEAD":
            self.wfile.write(content)

def start_pve_local_proxy(unit):
    """Log into PVE and expose it on localhost HTTP so the cert warning is avoided."""
    info, error = pve_login_info(unit)
    if error:
        return None, error
    ticket, csrf, error = fetch_pve_ticket(info["ip"], info["username"], info["password"])
    if error:
        return None, error

    with _pve_proxy_lock:
        existing = _pve_proxies.get(unit)
        if existing and existing.get("port"):
            existing["ticket"] = ticket
            existing["csrf"] = csrf
            existing["ip"] = info["ip"]
            existing["username"] = info["username"]
            existing["password"] = info["password"]
            return f"http://127.0.0.1:{existing['port']}/", None

        state = {
            "ip": info["ip"],
            "username": info["username"],
            "password": info["password"],
            "ticket": ticket,
            "csrf": csrf,
            "port": 0,
        }
        server = ThreadingHTTPServer(("127.0.0.1", 0), _PVEProxyHandler)
        server.pve_state = state
        state["port"] = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        state["server"] = server
        _pve_proxies[unit] = state
        return f"http://127.0.0.1:{state['port']}/", None

def fetch_fisheye_snapshot(unit):
    """Return (image_bytes, error). Tries Dahua snapshot CGI on ports 10080 then 80."""
    load_dotenv(env_path)
    fishuser = os.getenv("fishuser")
    fishpass = os.getenv("fishpass")
    if not fishuser or not fishpass:
        return None, "fishuser/fishpass not set in .env"

    if not net_array:
        generate_net_array()
    row = ensure_unit_net_info(unit, needed_indexes=(5,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[5] if len(row) > 5 else "")
    if not ip:
        return None, f"No fisheye IP for {unit}"

    last_error = "Snapshot failed"
    auths = (
        HTTPDigestAuth(f"{fishuser}", f"{fishpass}"),
        HTTPBasicAuth(f"{fishuser}", f"{fishpass}"),
    )
    for port in (10080, 80):
        url = f"http://{ip}:{port}/cgi-bin/snapshot.cgi?channel=1"
        for auth in auths:
            try:
                response = requests.get(url, auth=auth, timeout=15)
                response.raise_for_status()
                content_type = (response.headers.get("Content-Type") or "").lower()
                if not response.content:
                    last_error = f"Empty response from {ip}:{port}"
                    continue
                if "html" in content_type or response.content[:15].lstrip().lower().startswith(b"<"):
                    last_error = f"Non-image response from {ip}:{port}"
                    continue
                return response.content, None
            except requests.exceptions.RequestException as e:
                last_error = f"{ip}:{port} {e}"
                continue
    return None, last_error

_camera_port_cache = {}
_camera_port_lock = threading.Lock()


def _camera_port_open(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve_camera_port(host, port):
    """Netsheet cells often omit the port; fall back to the other common web port."""
    if not host or not port:
        return port
    key = f"{host}:{port}"
    with _camera_port_lock:
        cached = _camera_port_cache.get(key)
    if cached:
        return cached
    resolved = port
    extras = [item for item in (80, 10080) if item != port]
    for candidate in [port] + extras:
        if _camera_port_open(host, candidate):
            resolved = candidate
            break
    with _camera_port_lock:
        _camera_port_cache[key] = resolved
    return resolved


def _camera_host_port(value, target):
    """Parse host and port from a netsheet camera cell."""
    text = (value or "").strip()
    if not text:
        return "", None
    text = text.replace("http://", "").replace("https://", "").split("/")[0]
    default_port = 10080 if target == "fisheye" else 80
    parsed_port = None
    if ":" in text:
        host, port_text = text.rsplit(":", 1)
        try:
            parsed_port = int(port_text)
            text = host
        except ValueError:
            parsed_port = None
    host = _host_only(text) or _host_only(value)
    if not host:
        return host, None
    return host, _resolve_camera_port(host, parsed_port or default_port)

def list_unit_cameras(unit):
    """Return configured cameras for a unit (target, label, host, port — no credentials)."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    row = ensure_unit_net_info(
        unit,
        needed_indexes=tuple(column for column, _ in CAMERA_ENDPOINTS.values()),
    )
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    allowed_targets = open_camera_targets_for_unit(unit)
    cameras = []
    for target, (column, label) in CAMERA_ENDPOINTS.items():
        if target not in allowed_targets:
            continue
        cell = row[column] if len(row) > column else ""
        host, port = _camera_host_port(cell, target)
        if not host:
            continue
        cameras.append({
            "target": target,
            "label": label,
            "host": host,
            "port": port,
        })
    return cameras, None

def camera_login_info(unit, target):
    """Return camera web UI launch info (Flask Digest proxy URL)."""
    load_dotenv(env_path)
    fishuser = (os.getenv("fishuser") or "").strip().strip('"').strip("'")
    fishpass = (os.getenv("fishpass") or "").strip().strip('"').strip("'")
    if not fishuser or not fishpass:
        return None, "fishuser/fishpass not set in .env"
    target_key = str(target or "").strip().lower()
    if not target_key:
        return None, "Missing camera target"
    cameras, error = list_unit_cameras(unit)
    if error:
        return None, error
    camera = next(
        (item for item in cameras if item.get("target") == target_key),
        None,
    )
    if not camera:
        return None, f"No {target_key} configured for {unit}"
    unit_key = _normalize_netsheet_unit(unit) or str(unit).strip()
    proxy_path = (
        f"/issues/camera-proxy/"
        f"{quote(unit_key, safe='')}/"
        f"{quote(target_key, safe='')}/"
    )
    return {
        "unit": unit_key,
        "target": target_key,
        "label": camera["label"],
        "host": camera["host"],
        "port": camera["port"],
        "username": fishuser,
        "auth": "digest-or-basic",
        "camera_url": f"http://{camera['host']}:{camera['port']}/",
        "url": proxy_path,
    }, None


_camera_session_lock = threading.Lock()
_camera_sessions = {}
_CAMERA_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "authorization",
}
_CAMERA_SKIP_RESP_HEADERS = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "content-encoding",
    "content-length",
}


_CAMERA_SHIM_VERSION = "19"


def _rewrite_camera_css(content, content_type, proxy_prefix):
    """Point root-relative url(/...) assets in camera CSS back through the proxy."""
    if "css" not in str(content_type or "").lower():
        return content
    raw = content or b""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    prefix = str(proxy_prefix or "").rstrip("/")
    rewritten = re.sub(
        r'(?i)url\(\s*(["\']?)/(?!/)',
        lambda match: f"url({match.group(1)}{prefix}/",
        text,
    )
    return rewritten.encode("utf-8") if rewritten != text else raw


def _inject_camera_shim(content, content_type, proxy_prefix, camera_origin, username, password):
    """Rewrite root-relative URLs and load the camera shim (storage split + auto-login)."""
    ctype = str(content_type or "").lower()
    raw = content or b""
    if "html" not in ctype and not raw.lstrip()[:32].lower().startswith((b"<!doctype", b"<html")):
        return _rewrite_camera_css(raw, ctype, proxy_prefix)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except Exception:
            return raw
    if "work-tool-camera-shim" in text:
        return raw
    prefix = str(proxy_prefix or "").rstrip("/")
    text = re.sub(
        r'(?i)\b(src|href|action)=(["\'])/(?!/)',
        lambda match: f"{match.group(1)}={match.group(2)}{prefix}/",
        text,
    )
    origin = str(camera_origin or "")
    config = json.dumps({
        "prefix": prefix,
        "origin": origin,
        "wsOrigin": re.sub(r"(?i)^https?://", "ws://", origin) if origin else "",
        "user": str(username or ""),
        "pass": str(password or ""),
    })
    snippet = (
        f'<script id="work-tool-camera-shim">window.__workToolCamera = {config};</script>'
        f'<script src="/static/camera_shim.js?v={_CAMERA_SHIM_VERSION}"></script>'
    )
    # The shim has to run before the camera app's own scripts request anything.
    opening = re.search(r"<head[^>]*>", text, re.IGNORECASE) or re.search(
        r"<body[^>]*>", text, re.IGNORECASE
    )
    idx = opening.end() if opening else 0
    return (text[:idx] + snippet + text[idx:]).encode("utf-8")


def _inject_camera_worker_prelude(content, content_type, path, proxy_prefix, camera_origin):
    """Prepend URL rewrites to camera decoder workers so they stay on the proxy."""
    name = str(path or "").rsplit("/", 1)[-1].lower()
    ctype = str(content_type or "").lower()
    if "worker.js" not in name and "javascript" not in ctype:
        return content
    if "worker" not in name and "worker" not in ctype:
        return content
    raw = content or b""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    if "work-tool-worker-prelude" in text:
        return raw
    prefix = str(proxy_prefix or "").rstrip("/")
    ws_origin = re.sub(r"(?i)^https?://", "ws://", str(camera_origin or ""))
    config = json.dumps({"prefix": prefix, "wsOrigin": ws_origin})
    prelude = (
        "/*work-tool-worker-prelude*/(function(config){"
        "function rewrite(url){"
        "var out=String(url||'');"
        "if(out.charAt(0)!=='/'||out.charAt(1)==='/')return out;"
        "if(out===config.prefix||out.indexOf(config.prefix+'/')===0)return out;"
        "return config.prefix+out;"
        "}"
        "self.Module=self.Module||{};"
        "self.Module.locateFile=function(path){"
        "var name=String(path||'').split('/').pop();"
        "return config.prefix+(name.indexOf('ffmpegasm')===0?'/module/':'/')+name;"
        "};"
        "if(self.importScripts){var ni=self.importScripts;"
        "self.importScripts=function(){return ni.apply(self,Array.prototype.map.call(arguments,rewrite));};}"
        "if(self.fetch){var nf=self.fetch;"
        "self.fetch=function(input,init){"
        "return nf.call(self,typeof input==='string'?rewrite(input):input,init);};}"
        "if(self.XMLHttpRequest){var no=XMLHttpRequest.prototype.open;"
        "XMLHttpRequest.prototype.open=function(method,url){"
        "var args=Array.prototype.slice.call(arguments);args[1]=rewrite(url);"
        "return no.apply(this,args);};}"
        "if(self.WebSocket&&config.wsOrigin){var NS=self.WebSocket;"
        "self.WebSocket=function(url,protocols){"
        "var target=String(url||'');"
        "if(/^wss?:\\/\\/(127\\.0\\.0\\.1|localhost):(23450|23490)/i.test(target))"
        "{return {readyState:3,send:function(){},close:function(){},"
        "addEventListener:function(){},removeEventListener:function(){}};}"
        "if(target.indexOf(config.wsOrigin)!==0){"
        "var path=target.replace(/^wss?:\\/\\/[^/]*/i,'')||'/';"
        "if(path.indexOf(config.prefix+'/')===0)path=path.slice(config.prefix.length);"
        "if(/rtspoverwebsocket|httpprivateoverwebsocket/i.test(path)||path==='/')"
        "{path=/httpprivate/i.test(path)?'/httpprivateoverwebsocket':'/rtspoverwebsocket';}"
        "target=config.wsOrigin+path;}"
        "return protocols===undefined?new NS(target):new NS(target,protocols);"
        "};self.WebSocket.prototype=NS.prototype;}"
        "})(" + config + ");\n"
    )
    return (prelude + text).encode("utf-8")


def camera_snapshot(unit, target, channel=1, timeout=20):
    """Return (jpeg_bytes, error) for one camera using the authenticated proxy path."""
    status, _headers, content, error = proxy_camera_http(
        unit,
        target,
        "cgi-bin/snapshot.cgi",
        "GET",
        query_string=f"channel={int(channel)}".encode(),
        timeout=timeout,
    )
    if error:
        return None, error
    if status != 200:
        return None, f"Snapshot returned HTTP {status}"
    if not content:
        return None, "Camera returned an empty snapshot"
    if not content.startswith(b"\xff\xd8"):
        return None, "Camera returned a non-image response"
    return content, None


def cameras_launch_info(unit):
    """Build Open All Cameras launcher payload with proxy URLs."""
    cameras, error = list_unit_cameras(unit)
    if error:
        return None, error
    if not cameras:
        return None, f"No cameras configured for {unit}"
    unit_key = _normalize_netsheet_unit(unit) or str(unit).strip()
    rows = []
    for camera in cameras:
        info, info_error = camera_login_info(unit_key, camera["target"])
        if info_error:
            return None, info_error
        rows.append({
            "target": camera["target"],
            "label": camera["label"],
            "host": camera["host"],
            "port": camera["port"],
            "url": info["url"],
            "direct_url": info["camera_url"],
        })
    return {"unit": unit_key, "cameras": rows, "count": len(rows)}, None


def _camera_proxy_session(unit, target, host, port, username, password, force_auth=None):
    """Reuse a camera session; Digest by default, optional forced Basic."""
    key = f"{unit}|{target}|{host}|{port}"
    with _camera_session_lock:
        existing = _camera_sessions.get(key)
        if existing is not None and force_auth is None:
            return existing
        mode = str(force_auth or "digest").strip().lower()
        if mode not in ("digest", "basic"):
            mode = "digest"
        session = requests.Session()
        if mode == "basic":
            session.auth = HTTPBasicAuth(username, password)
        else:
            session.auth = HTTPDigestAuth(username, password)
        session.headers.update({"User-Agent": "work_tool-camera-proxy/1.0"})
        session._work_tool_auth = mode
        _camera_sessions[key] = session
        return session


def proxy_camera_http(
    unit,
    target,
    subpath,
    method,
    query_string=b"",
    headers=None,
    body=None,
    timeout=None,
):
    """
    Proxy an HTTP request to a unit camera using Digest auth, falling back to Basic.
    Returns (status_code, response_headers_dict, content_bytes, error).
    """
    info, error = camera_login_info(unit, target)
    if error:
        return None, None, None, error
    host = info["host"]
    port = info["port"]
    username = info["username"]
    load_dotenv(env_path)
    password = (os.getenv("fishpass") or "").strip().strip('"').strip("'")
    if not password:
        return None, None, None, "fishpass not set in .env"

    path = str(subpath or "").lstrip("/")
    if timeout is None:
        # The camera long-polls RPC2 for roughly a minute at a time; timing those out
        # tears down the session keepalive that live video depends on.
        timeout = 180 if path.upper().endswith("RPC2") else 60
    target_url = f"http://{host}:{port}/"
    if path:
        target_url = f"http://{host}:{port}/{path}"
    qs = query_string.decode("utf-8", errors="replace") if isinstance(query_string, (bytes, bytearray)) else str(query_string or "")
    if qs:
        target_url = f"{target_url}?{qs}"

    outbound = {}
    for key, value in (headers or {}).items():
        if str(key).lower() in _CAMERA_HOP_HEADERS:
            continue
        outbound[key] = value

    session = _camera_proxy_session(
        info["unit"],
        info["target"],
        host,
        port,
        username,
        password,
    )
    try:
        response = session.request(
            method=str(method or "GET").upper(),
            url=target_url,
            headers=outbound,
            data=body if body else None,
            allow_redirects=False,
            timeout=timeout,
        )
        if (
            response.status_code == 401
            and getattr(session, "_work_tool_auth", "digest") == "digest"
        ):
            session = _camera_proxy_session(
                info["unit"],
                info["target"],
                host,
                port,
                username,
                password,
                force_auth="basic",
            )
            response = session.request(
                method=str(method or "GET").upper(),
                url=target_url,
                headers=outbound,
                data=body if body else None,
                allow_redirects=False,
                timeout=timeout,
            )
        mem_name = path.rsplit("/", 1)[-1].lower() if path else ""
        if (
            response.status_code == 404
            and mem_name in {"ffmpegasm.js.mem", "ffmpegasm.wasm", "ffmpegasm.js"}
        ):
            # Decoder workers ask next to /module/, but cameras serve these at site root.
            for retry_name in (mem_name, f"module/{mem_name}"):
                if retry_name == path:
                    continue
                retry_url = f"http://{host}:{port}/{retry_name}"
                response = session.request(
                    method=str(method or "GET").upper(),
                    url=retry_url,
                    headers=outbound,
                    data=body if body else None,
                    allow_redirects=False,
                    timeout=timeout,
                )
                if response.status_code != 404:
                    break
    except requests.RequestException as exc:
        return None, None, None, f"Camera proxy failed: {exc}"

    proxy_prefix = (
        f"/issues/camera-proxy/"
        f"{quote(info['unit'], safe='')}/"
        f"{quote(info['target'], safe='')}"
    )
    camera_origin = f"http://{host}:{port}"
    resp_headers = {}
    for key, value in response.headers.items():
        lower = key.lower()
        if lower in _CAMERA_SKIP_RESP_HEADERS:
            continue
        if lower == "location":
            location = str(value or "")
            if location.startswith(camera_origin):
                location = proxy_prefix + location[len(camera_origin):]
            elif location.startswith("/"):
                location = proxy_prefix + location
            resp_headers[key] = location
            continue
        if lower == "set-cookie":
            # Scope cookies to this camera's proxy path so a grid of cameras on the
            # dashboard origin does not overwrite each other's sessions.
            cleaned = re.sub(r"(?i);\s*domain=[^;]*", "", str(value or ""))
            cleaned = re.sub(r"(?i);\s*path=[^;]*", "", cleaned)
            resp_headers[key] = f"{cleaned}; Path={proxy_prefix}/"
            continue
        if lower == "x-frame-options":
            # Allow same-origin Open All launcher iframes.
            continue
        resp_headers[key] = value

    body = response.content or b""
    content_type = response.headers.get("Content-Type") or resp_headers.get("Content-Type") or ""
    if str(method or "GET").upper() in ("GET", "HEAD") and response.status_code == 200:
        body = _inject_camera_shim(
            body,
            content_type,
            proxy_prefix,
            camera_origin,
            username,
            password,
        )
        body = _inject_camera_worker_prelude(
            body,
            content_type,
            path,
            proxy_prefix,
            camera_origin,
        )
        if body is not response.content:
            # Ensure browsers treat rewritten pages as HTML even if upstream omitted type.
            if b"work-tool-camera-shim" in body and "content-type" not in {
                k.lower() for k in resp_headers
            }:
                resp_headers["Content-Type"] = "text/html; charset=utf-8"
            # A cached copy of the page would skip the shim on the next visit.
            for key in [k for k in resp_headers if k.lower() in ("cache-control", "expires", "pragma", "etag", "last-modified")]:
                resp_headers.pop(key)
            resp_headers["Cache-Control"] = "no-store, max-age=0"

    return response.status_code, resp_headers, body, None


def _parse_outage_kind(issue_type):
    text = (issue_type or "").strip()
    lower = text.lower()
    if "partial" in lower:
        return "Partial"
    if "full" in lower:
        return "Full"
    return text

def _camera_targets_from_subject(subject):
    """Return camera endpoint keys explicitly referenced in a ticket subject."""
    targets = []
    checks = (
        ("fisheye", r"\bfisheye\s+(?:not|down)\b"),
        ("camera1", r"(?:\bc1\b|\bcamera\s*1\b)"),
        ("camera2", r"(?:\bc2\b|\bcamera\s*2\b)"),
        ("camera3", r"(?:\bc3\b|\bcamera\s*3\b)"),
        ("camera4", r"(?:\bc4\b|\bcamera\s*4\b)"),
    )
    for target, pattern in checks:
        if re.search(pattern, subject or "", re.IGNORECASE):
            targets.append(target)
    return targets

def _is_nuc_down_issue_subtype(subtype):
    """Exact ERP Issue Subtype spelling/capitalization: Nuc Down."""
    return str(subtype or "") == "Nuc Down"

def _subject_implies_nuc_down(subject):
    """Subject mentions NUC Down / SNUC Down (any capitalization)."""
    return bool(re.search(r"\bS?NUC\s+Down\b", str(subject or ""), re.IGNORECASE))

def _is_forced_nuc_down(subtype="", subject=""):
    return _is_nuc_down_issue_subtype(subtype) or _subject_implies_nuc_down(subject)

def _vrm_info_from_subject(subject, unit=""):
    """VRM search for RD tickets only. Prefer MU from subject; else RD unit code."""
    text = str(subject or "")
    unit_name = str(unit or "").strip()
    has_rd = bool(re.search(r"\bRD\s*\d+", text, re.IGNORECASE))
    if not has_rd and not re.match(r"^RD\d+", unit_name, re.IGNORECASE):
        return "", ""
    vrm_mu = ""
    for mu_match in re.finditer(r"\bMU\s*(\d{4})\b", text, re.IGNORECASE):
        vrm_mu = mu_match.group(1)
        break
    search = vrm_mu
    if not search:
        if re.match(r"^RD\d+", unit_name, re.IGNORECASE):
            search = unit_name.upper()
        else:
            rd_match = re.search(r"\b(RD\s*\d+)\b", text, re.IGNORECASE)
            if rd_match:
                search = re.sub(r"\s+", "", rd_match.group(1)).upper()
    if not search:
        return "", ""
    return vrm_mu, (
        f"https://vrm.victronenergy.com/installation-overview?search={search}"
    )

def _is_camera_view_subject(subject):
    """Identify camera view/position work that must not run outage validation."""
    text = subject or ""
    patterns = (
        r"\bcamera\s+views?\b",
        r"\bcamera\s+shifted\b",
        r"\bcamera\s+adjustment\b",
        r"\bc[1-4]\b[^\r\n]*(?:shifted|adjustment)\b",
        r"\bcamera\s*[1-4]\b[^\r\n]*(?:shifted|adjustment)\b",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

CAMERA_VIEW_ISSUE_TYPES = frozenset({
    "camera views",
    "camera adjustment",
})

CAMERA_VIEW_ISSUE_SUBTYPES = frozenset({
    "camera adjustment",
    "dark views",
    "blurry cameras",
    "dirty cameras",
})

def _is_camera_view_ticket(issue_type="", issue_subtype="", subject=""):
    """Route Camera Views work by ERP type/subtype or subject text."""
    type_l = str(issue_type or "").strip().lower()
    subtype_l = str(issue_subtype or "").strip().lower()
    if type_l in CAMERA_VIEW_ISSUE_TYPES:
        return True
    if subtype_l in CAMERA_VIEW_ISSUE_SUBTYPES:
        return True
    return _is_camera_view_subject(subject)

def _with_ticket_links(units, unit_issue_map, unit_meta_map=None):
    if unit_meta_map is None:
        unit_meta_map = {}
    linked = []
    for result_key in units:
        issue_id = unit_issue_map.get(result_key, "")
        meta = unit_meta_map.get(result_key, {})
        unit = meta.get("unit") or result_key
        switch_url, fisheye_ip, pve_ip, has_pve, has_relay, has_platform, platform_url, has_scrypted, scrypted_url = (
            _unit_device_info(unit)
        )
        vrm_mu = meta.get("vrm_mu") or ""
        vrm_url = meta.get("vrm_url") or ""
        if not vrm_url:
            vrm_mu, vrm_url = _vrm_info_from_subject(meta.get("subject"), unit)
        linked.append({
            "unit": unit,
            "issue_id": issue_id,
            "url": _issue_ticket_url(issue_id),
            "issue_type": meta.get("issue_type", ""),
            "outage_type": meta.get("outage_type", ""),
            "issue_subtype": meta.get("issue_subtype", ""),
            "subject": meta.get("subject", ""),
            "undiagnosed": bool(meta.get("undiagnosed")),
            "switch_url": switch_url,
            "fisheye_ip": fisheye_ip,
            "pve_ip": pve_ip,
            "has_pve": has_pve,
            "has_relay": has_relay,
            "has_platform": has_platform,
            "platform_url": platform_url,
            "has_scrypted": has_scrypted,
            "scrypted_url": scrypted_url,
            "compute_label": compute_host_label(unit),
            "is_speaker": bool(meta.get("is_speaker")),
            "speaker_up": meta.get("speaker_up"),
            "is_scrypted_outage": bool(meta.get("is_scrypted_outage")),
            "is_nuc_down": bool(meta.get("is_nuc_down")),
            "is_camera": bool(meta.get("is_camera")),
            "camera_target": meta.get("camera_target", ""),
            "camera_label": meta.get("camera_label", ""),
            "camera_up": meta.get("camera_up"),
            "is_panel_issue": bool(meta.get("is_panel_issue")),
            "panel_fisheye_up": meta.get("panel_fisheye_up"),
            "is_camera_view": bool(meta.get("is_camera_view")),
            "camera_view_status": meta.get("camera_view_status"),
            "vrm_mu": vrm_mu,
            "vrm_url": vrm_url,
            "erp_status": meta.get("erp_status", ""),
            "hold_kind": meta.get("hold_kind", ""),
            "led_status": meta.get("led_status"),
        })
    linked.sort(key=lambda item: (0 if item.get("undiagnosed") else 1, item.get("unit") or ""))
    return linked

def _force_up_steady_green(linked_units):
    """Up Steady tickets always show a green status LED."""
    for item in linked_units or []:
        item["led_status"] = "green"
    return linked_units

def _print_linked_units(label, linked_units):
    print(label)
    for item in linked_units:
        parts = [item["unit"]]
        if item.get("issue_id"):
            parts.append(item["issue_id"])
            parts.append(item.get("url") or "")
        if item.get("outage_type"):
            parts.append(item["outage_type"])
        if item.get("undiagnosed"):
            parts.append("UNDIAGNOSED (priority)")
        elif item.get("issue_subtype"):
            parts.append(item["issue_subtype"])
        print(" - ".join(p for p in parts if p))

ERP_ISSUES_URL = f"{erp_base_url()}/api/resource/Issue"
ERP_PROJECTS_URL = f"{erp_base_url()}/api/resource/Project"
ERP_ACTIVE_ISSUE_STATUSES = ("Open", "Monitoring", "On Hold")
ERP_ACTIVE_PROJECT_STATUSES = ("Open", "In Progress")
PROJECT_NOC_SUBJECT_TOKEN = "NOC"
PROJECT_PREP_SUBJECT_TOKEN = "prep"
NOC_DEPLOYMENT_PROJECT_TEMPLATE = "NOC Deployment/Activation"
NOC_TERMINATION_PROJECT_TEMPLATE = "NOC Termination"
NOC_RELOCATION_PROJECT_TEMPLATE = "NOC Unit Relocation"
DIGITAL_RD_REFURB_TEMPLATE = "Digital RD Refurb"
PHYSICAL_RD_REFURB_TEMPLATE = "Physical RD Refurb"
PHYSICAL_TRAILER_REFURB_TEMPLATE = "Physical Trailer Refurb"
ERP_SITES_URL = f"{erp_base_url()}/api/resource/Site"
ERP_TASKS_URL = f"{erp_base_url()}/api/resource/Task"
ERP_COMMENTS_URL = f"{erp_base_url()}/api/resource/Comment"
TECH_CHECK_TASK_SUBJECTS = (
    "Tech - Check router settings",
    "Tech - Check that the Down facing Camera Can Fully See the Entire Panel",
    "Tech - Speaker Test - Built in Test Message",
    "Tech - Trigger LEDs for Tech to Check (Leave LEDs ON)",
    "Tech - Check that Cameras were Cleaned by Tech",
)
TECH_CHECK_ROUTER_SUBJECT = TECH_CHECK_TASK_SUBJECTS[0]
TECH_CHECK_CANCEL_SUBJECTS = (
    "ganz upgrade verification",
    '- "Warehouse" in Ganz server',
    "GANZ channel enabled",
    "Amend Ganz User for Existing Service if Applicable",
    "Add Resources to Ganz VSGSupervisor Account",
    "Verify Time Task is Enabled (Standard Dahua ONLY)",
)
TECH_CHECK_CANCEL_COMMENT = "n/a 180RD unit"

def _erp_issue_value(issue, *field_names):
    """Return the first populated ERP field, allowing custom field prefixes."""
    for field_name in field_names:
        value = issue.get(field_name)
        if value not in (None, ""):
            return value
    normalized_names = {
        re.sub(r"[^a-z0-9]", "", field_name.lower())
        for field_name in field_names
    }
    for key, value in issue.items():
        normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if value not in (None, "") and any(
            normalized_key == name or normalized_key.endswith(name)
            for name in normalized_names
        ):
            return value
    return ""

def _normalize_erp_issue(issue):
    return {
        "issue_id": str(_erp_issue_value(issue, "name", "id")).strip(),
        "subject": str(_erp_issue_value(issue, "subject", "title")).strip(),
        "status": str(_erp_issue_value(issue, "status")).strip(),
        "issue_type": str(
            _erp_issue_value(issue, "issue_type", "issue type")
        ).strip(),
        "issue_subtype": str(
            _erp_issue_value(issue, "issue_subtype", "issue subtype")
        ).strip(),
    }

def _normalize_erp_project(project):
    subject = str(
        _erp_issue_value(project, "subject", "project_name", "title", "name")
    ).strip()
    project_id = str(_erp_issue_value(project, "name", "id")).strip()
    # Prefer a human subject when name was used as the only fallback.
    project_name = str(_erp_issue_value(project, "project_name", "subject", "title")).strip()
    if project_name and subject == project_id:
        subject = project_name
    elif project_name and not subject:
        subject = project_name
    return {
        "project_id": project_id,
        "subject": subject,
        "status": str(_erp_issue_value(project, "status")).strip(),
        "percent_complete": _parse_project_percent_complete(
            _erp_issue_value(
                project,
                "percent_complete",
                "percent complete",
                "percentage_complete",
                "completion",
            )
        ),
        "modified": str(_erp_issue_value(project, "modified")).strip(),
    }

def _parse_project_percent_complete(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip().rstrip("%").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    if number < 0:
        return None
    return number

def _format_project_percent_complete(value):
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number == int(number):
        return f"{int(number)}%"
    return f"{number:g}%"

def _project_ticket_url(project_id):
    if not project_id:
        return ""
    return f"{erp_base_url()}/app/project/{project_id}"

def _project_subject_has_noc(subject):
    return PROJECT_NOC_SUBJECT_TOKEN.lower() in str(subject or "").lower()

def _project_subject_has_prep(subject):
    return PROJECT_PREP_SUBJECT_TOKEN in str(subject or "").lower()

def _noc_deployment_name_from_prep(subject):
    text = str(subject or "").strip()
    rewritten, count = re.subn(
        r"^[^:]+:\s*Deployment\s+Prep\b",
        "NOC Deployment",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    if count:
        return rewritten
    rewritten, count = re.subn(
        r"Deployment\s+Prep\b",
        "NOC Deployment",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    return rewritten if count else text

def _noc_termination_unit_token_pattern():
    return (
        r"(?:RD|FD)\s*\d+(?:\([^)]*\))?"
        r"|"
        r"MU\s*\d+(?:\([^)]*\))?"
    )

def _parse_termination_issue_subject(subject):
    """Parse Region - Unit[/Unit...] - [Partial ]Termination[...] - Rest into units + rest."""
    return _parse_kind_issue_subject(subject, "Termination")

def _parse_relocation_issue_subject(subject):
    """Parse Region - Unit[/Unit...] - [Partial ]Relocation[...] - Rest into units + rest."""
    return _parse_kind_issue_subject(subject, "Relocation")

def _parse_kind_issue_subject(subject, kind):
    """Parse Region - Unit[/Unit...] - [Partial ]{kind}[...] - Rest into units + rest."""
    text = str(subject or "").strip()
    kind = str(kind or "").strip()
    if not kind:
        return None
    unit = _noc_termination_unit_token_pattern()
    match = re.match(
        rf"^.+?\s*-\s*"
        rf"(?P<units>(?:{unit})(?:\s*/\s*(?:{unit}))*)\s*-\s*"
        rf"(?:Partial\s+)?{re.escape(kind)}(?:\s*\([^)]*\))?\s*-\s*"
        rf"(?P<rest>.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    units = []
    seen = set()
    for part in re.split(r"\s*/\s*", match.group("units")):
        normalized = re.sub(r"\s+", "", part.strip())
        if not normalized:
            continue
        key = normalized.upper()
        if key in seen:
            continue
        seen.add(key)
        units.append(normalized)
    rest = " ".join(match.group("rest").split())
    if not units or not rest:
        return None
    return {"units": units, "rest": rest}

def _noc_termination_names_from_issue(subject):
    """Build one NOC Termination project title per unit in the issue subject.

    Examples:
      DEN - RD3023(MU5068) - Termination - Dawson Infrastructure Solutions - 434 E 56th Ave
      -> [NOC Termination - RD3023(MU5068) - Dawson Infrastructure Solutions - 434 E 56th Ave]
      SLC - MU1009 - Termination - Brighton Homes LLC - Trailside Reserve
      -> [NOC Termination - MU1009 - Brighton Homes LLC - Trailside Reserve]
      PHX - RD3249(MU7027)/RD3250(MU7042)/RD3251(MU7043)  - Termination (end of aug)- Arizona Solar One LLC - Imperial Sun Solar
      -> three NOC Termination titles, one per unit
      PHX - RD3378(MU8077) - Partial Termination - SOLV Energy - SOLV Energy - Tonopah Project
      -> [NOC Termination - RD3378(MU8077) - SOLV Energy - SOLV Energy - Tonopah Project]
    """
    parsed = _parse_termination_issue_subject(subject)
    if not parsed:
        return []
    return [
        f"NOC Termination - {unit} - {parsed['rest']}"
        for unit in parsed["units"]
    ]

def _noc_relocation_names_from_issue(subject):
    """Build one NOC Relocation project title per unit in the issue subject.

    Example:
      PHX - RD3108(MU6011) - Relocation - Ashton Woods - Aloravita 45's
      -> [NOC Relocation - RD3108(MU6011) - Ashton Woods - Aloravita 45's]
    """
    parsed = _parse_relocation_issue_subject(subject)
    if not parsed:
        return []
    return [
        f"NOC Relocation - {unit} - {parsed['rest']}"
        for unit in parsed["units"]
    ]

def _noc_termination_name_from_issue(subject):
    names = _noc_termination_names_from_issue(subject)
    return names[0] if names else ""

def fetch_erp_issues(statuses=None, page_size=200):
    """Fetch and normalize active ERP Issues using the configured token."""
    load_dotenv(env_path)
    erp_token = (os.getenv("erp_token") or "").strip().strip('"').strip("'")
    if not erp_token:
        raise RuntimeError("erp_token is not set in .env")

    if statuses is None:
        statuses = ERP_ACTIVE_ISSUE_STATUSES
    requested_statuses = [str(status).strip() for status in statuses if str(status).strip()]
    active_statuses = {status.lower() for status in requested_statuses}
    headers = {"Authorization": f"token {erp_token}"}
    raw_issues = []
    start = 0

    while True:
        response = requests.get(
            ERP_ISSUES_URL,
            headers=headers,
            params={
                "fields": json.dumps(["*"]),
                "filters": json.dumps([["status", "in", requested_statuses]]),
                "limit_start": start,
                "limit_page_length": page_size,
                "order_by": "creation asc",
            },
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"ERP Issue request failed ({response.status_code})"
            ) from exc
        payload = response.json()
        page = payload.get("data", [])
        if not isinstance(page, list):
            raise RuntimeError("ERP Issue response did not contain a data list")
        raw_issues.extend(page)
        if len(page) < page_size:
            break
        start += page_size

    normalized = []
    seen_ids = set()
    for raw_issue in raw_issues:
        issue = _normalize_erp_issue(raw_issue)
        if (
            issue["issue_id"]
            and issue["subject"]
            and issue["status"].lower() in active_statuses
            and issue["issue_id"] not in seen_ids
        ):
            normalized.append(issue)
            seen_ids.add(issue["issue_id"])
    return normalized

def _fetch_erp_project_pages(statuses=None, page_size=200, order_by="creation asc"):
    load_dotenv(env_path)
    erp_token = (os.getenv("erp_token") or "").strip().strip('"').strip("'")
    if not erp_token:
        raise RuntimeError("erp_token is not set in .env")

    if statuses is None:
        statuses = ERP_ACTIVE_PROJECT_STATUSES
    requested_statuses = [str(status).strip() for status in statuses if str(status).strip()]
    headers = {"Authorization": f"token {erp_token}"}
    raw_projects = []
    start = 0

    while True:
        response = requests.get(
            ERP_PROJECTS_URL,
            headers=headers,
            params={
                "fields": json.dumps(["*"]),
                "filters": json.dumps([["status", "in", requested_statuses]]),
                "limit_start": start,
                "limit_page_length": page_size,
                "order_by": order_by,
            },
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"ERP Project request failed ({response.status_code}): "
                f"{_erp_response_error(response)}"
            ) from exc
        payload = response.json()
        page = payload.get("data", [])
        if not isinstance(page, list):
            raise RuntimeError("ERP Project response did not contain a data list")
        raw_projects.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return raw_projects, requested_statuses

def fetch_erp_projects(statuses=None, page_size=200):
    """Fetch Open/In Progress ERP Projects whose subject contains NOC."""
    raw_projects, requested_statuses = _fetch_erp_project_pages(
        statuses=statuses,
        page_size=page_size,
        order_by="modified desc",
    )
    active_statuses = {status.lower() for status in requested_statuses}
    normalized = []
    seen_ids = set()
    for raw_project in raw_projects:
        project = _normalize_erp_project(raw_project)
        if (
            project["project_id"]
            and project["subject"]
            and project["status"].lower() in active_statuses
            and _project_subject_has_noc(project["subject"])
            and project["project_id"] not in seen_ids
        ):
            normalized.append(project)
            seen_ids.add(project["project_id"])
    return normalized

def fetch_erp_prep_projects(statuses=None, page_size=200):
    """Fetch Open/In Progress ERP Projects whose name/subject contains Prep."""
    raw_projects, requested_statuses = _fetch_erp_project_pages(
        statuses=statuses,
        page_size=page_size,
        order_by="modified desc",
    )
    active_statuses = {status.lower() for status in requested_statuses}
    normalized = []
    seen_ids = set()
    for raw_project in raw_projects:
        project = _normalize_erp_project(raw_project)
        if (
            project["project_id"]
            and project["subject"]
            and project["status"].lower() in active_statuses
            and _project_subject_has_prep(project["subject"])
            and project["project_id"] not in seen_ids
        ):
            normalized.append(project)
            seen_ids.add(project["project_id"])
    return normalized

def build_prep_project_entries(project_records):
    """Build Prep list rows without connectivity validation."""
    if not net_array:
        generate_net_array()
    entries = []
    records = list(project_records or [])
    print(f"Building Prep list for {len(records)} project(s)...")
    for project in records:
        project_id = str((project or {}).get("project_id") or "").strip()
        subject = str((project or {}).get("subject") or "").strip()
        status = str((project or {}).get("status") or "").strip()
        percent_complete = (project or {}).get("percent_complete")
        unit = _match_unit_from_subject(subject)
        if unit:
            print(f"Matched Prep project {project_id} -> {unit}")
        else:
            print(f"Prep project without net-sheet unit: {project_id} — {subject}")
        switch_url = fisheye_ip = pve_ip = ""
        has_pve = has_relay = has_platform = has_scrypted = False
        platform_url = ""
        scrypted_url = ""
        compute_label = "NUC"
        if unit:
            (
                switch_url,
                fisheye_ip,
                pve_ip,
                has_pve,
                has_relay,
                has_platform,
                platform_url,
                has_scrypted,
                scrypted_url,
            ) = _unit_device_info(unit)
            compute_label = compute_host_label(unit)
        vrm_mu, vrm_url = _vrm_info_from_subject(subject, unit)
        entries.append({
            "unit": unit,
            "project_id": project_id,
            "issue_id": "",
            "url": _project_ticket_url(project_id),
            "subject": subject,
            "erp_status": status,
            "percent_complete": percent_complete,
            "percent_complete_label": _format_project_percent_complete(percent_complete),
            "modified": str((project or {}).get("modified") or "").strip(),
            "list_kind": "prep",
            "connectivity_kind": "",
            "led_status": None,
            "switch_url": switch_url,
            "fisheye_ip": fisheye_ip,
            "pve_ip": pve_ip,
            "has_pve": has_pve,
            "has_relay": has_relay,
            "has_platform": has_platform,
            "platform_url": platform_url,
            "has_scrypted": has_scrypted,
            "scrypted_url": scrypted_url,
            "compute_label": compute_label,
            "vrm_mu": vrm_mu,
            "vrm_url": vrm_url,
            "outage_type": "",
            "issue_subtype": "",
            "undiagnosed": False,
            "is_speaker": False,
            "is_camera": False,
            "is_panel_issue": False,
            "is_camera_view": False,
            "hold_kind": "",
        })
    entries.sort(
        key=lambda item: (
            str(item.get("modified") or ""),
            str(item.get("project_id") or ""),
        ),
        reverse=True,
    )
    print(f"Prep list ready: {len(entries)}")
    return entries

def create_noc_deployment_project(prep_project_id, prep_subject=None):
    """Create an NOC Deployment project from a Prep project name + template."""
    prep_project_id = str(prep_project_id or "").strip()
    if not prep_project_id:
        return None, "Missing prep project id"
    subject = str(prep_subject or "").strip()
    if not subject:
        response = requests.get(
            f"{ERP_PROJECTS_URL}/{prep_project_id}",
            headers=_erp_headers(),
            timeout=30,
        )
        if response.status_code == 404:
            return None, f"{prep_project_id} was not found in ERP"
        if not response.ok:
            return None, _erp_response_error(response)
        doc = (response.json() or {}).get("data")
        if not isinstance(doc, dict):
            return None, f"ERP did not return Project {prep_project_id}"
        subject = _normalize_erp_project(doc).get("subject") or ""
    if not subject:
        return None, "Prep project has no subject/name"
    if not _project_subject_has_prep(subject):
        return None, "Selected project does not look like a Prep project"
    deployment_name = _noc_deployment_name_from_prep(subject)
    if deployment_name == subject:
        return None, (
            "Could not derive NOC Deployment name from Prep subject. "
            "Expected a leading 'Region: Deployment Prep' prefix."
        )
    payload = {
        "project_name": deployment_name,
        "project_template": NOC_DEPLOYMENT_PROJECT_TEMPLATE,
        "status": "Open",
    }
    response = requests.post(
        ERP_PROJECTS_URL,
        headers={**_erp_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not response.ok:
        return None, _erp_response_error(response)
    created = (response.json() or {}).get("data")
    if not isinstance(created, dict):
        return None, "ERP did not return the created Project"
    created_id = str(_erp_issue_value(created, "name", "id")).strip()
    created_name = str(
        _erp_issue_value(created, "project_name", "subject", "title") or deployment_name
    ).strip()
    if not created_id:
        return None, "ERP created Project but returned no id"
    return {
        "project_id": created_id,
        "project_name": created_name,
        "url": _project_ticket_url(created_id),
        "prep_project_id": prep_project_id,
    }, None

def create_noc_termination_project(issue_id, issue_subject=None):
    """Create NOC Termination project(s) from a Termination issue (one per unit)."""
    issue_id = str(issue_id or "").strip()
    if not issue_id:
        return None, "Missing issue id"
    subject = str(issue_subject or "").strip()
    if not subject:
        response = requests.get(
            f"{ERP_ISSUES_URL}/{issue_id}",
            headers=_erp_headers(),
            timeout=30,
        )
        if response.status_code == 404:
            return None, f"{issue_id} was not found in ERP"
        if not response.ok:
            return None, _erp_response_error(response)
        doc = (response.json() or {}).get("data")
        if not isinstance(doc, dict):
            return None, f"ERP did not return Issue {issue_id}"
        subject = _normalize_erp_issue(doc).get("subject") or ""
    if not subject:
        return None, "Issue has no subject"
    if "termination" not in subject.lower():
        return None, "Selected issue does not look like a Termination ticket"
    termination_names = _noc_termination_names_from_issue(subject)
    if not termination_names:
        return None, (
            "Could not derive NOC Termination name from issue subject. "
            "Expected 'Region - Unit[/Unit...] - Termination - Rest'."
        )
    created_projects = []
    errors = []
    for termination_name in termination_names:
        payload = {
            "project_name": termination_name,
            "project_template": NOC_TERMINATION_PROJECT_TEMPLATE,
            "status": "Open",
        }
        response = requests.post(
            ERP_PROJECTS_URL,
            headers={**_erp_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if not response.ok:
            errors.append(f"{termination_name}: {_erp_response_error(response)}")
            continue
        created = (response.json() or {}).get("data")
        if not isinstance(created, dict):
            errors.append(f"{termination_name}: ERP did not return the created Project")
            continue
        created_id = str(_erp_issue_value(created, "name", "id")).strip()
        created_name = str(
            _erp_issue_value(created, "project_name", "subject", "title")
            or termination_name
        ).strip()
        if not created_id:
            errors.append(f"{termination_name}: ERP created Project but returned no id")
            continue
        created_projects.append({
            "project_id": created_id,
            "project_name": created_name,
            "url": _project_ticket_url(created_id),
        })
    if not created_projects:
        return None, (errors[0] if errors else "Failed to create Termination project(s)")
    first = created_projects[0]
    return {
        "project_id": first["project_id"],
        "project_name": first["project_name"],
        "url": first["url"],
        "issue_id": issue_id,
        "count": len(created_projects),
        "projects": created_projects,
        "errors": errors,
    }, None

def create_noc_relocation_project(issue_id, issue_subject=None):
    """Create NOC Relocation project(s) from a Relocation issue (one per unit)."""
    issue_id = str(issue_id or "").strip()
    if not issue_id:
        return None, "Missing issue id"
    subject = str(issue_subject or "").strip()
    if not subject:
        response = requests.get(
            f"{ERP_ISSUES_URL}/{issue_id}",
            headers=_erp_headers(),
            timeout=30,
        )
        if response.status_code == 404:
            return None, f"{issue_id} was not found in ERP"
        if not response.ok:
            return None, _erp_response_error(response)
        doc = (response.json() or {}).get("data")
        if not isinstance(doc, dict):
            return None, f"ERP did not return Issue {issue_id}"
        subject = _normalize_erp_issue(doc).get("subject") or ""
    if not subject:
        return None, "Issue has no subject"
    if "relocation" not in subject.lower():
        return None, "Selected issue does not look like a Relocation ticket"
    relocation_names = _noc_relocation_names_from_issue(subject)
    if not relocation_names:
        return None, (
            "Could not derive NOC Relocation name from issue subject. "
            "Expected 'Region - Unit[/Unit...] - Relocation - Rest'."
        )
    created_projects = []
    errors = []
    for relocation_name in relocation_names:
        payload = {
            "project_name": relocation_name,
            "project_template": NOC_RELOCATION_PROJECT_TEMPLATE,
            "status": "Open",
        }
        response = requests.post(
            ERP_PROJECTS_URL,
            headers={**_erp_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if not response.ok:
            errors.append(f"{relocation_name}: {_erp_response_error(response)}")
            continue
        created = (response.json() or {}).get("data")
        if not isinstance(created, dict):
            errors.append(f"{relocation_name}: ERP did not return the created Project")
            continue
        created_id = str(_erp_issue_value(created, "name", "id")).strip()
        created_name = str(
            _erp_issue_value(created, "project_name", "subject", "title")
            or relocation_name
        ).strip()
        if not created_id:
            errors.append(f"{relocation_name}: ERP created Project but returned no id")
            continue
        created_projects.append({
            "project_id": created_id,
            "project_name": created_name,
            "url": _project_ticket_url(created_id),
        })
    if not created_projects:
        return None, (errors[0] if errors else "Failed to create Relocation project(s)")
    first = created_projects[0]
    return {
        "project_id": first["project_id"],
        "project_name": first["project_name"],
        "url": first["url"],
        "issue_id": issue_id,
        "count": len(created_projects),
        "projects": created_projects,
        "errors": errors,
    }, None

def _refurbish_date_label():
    return _arizona_now().strftime("%m/%d/%Y")

def _is_noc_termination_project_subject(subject):
    text = str(subject or "").strip()
    if not text:
        return False
    if re.search(r"noc\s+termination\b", text, flags=re.IGNORECASE):
        return True
    return bool(
        re.search(r"\btermination\b", text, flags=re.IGNORECASE)
        and not re.search(r"\bdeployment\b", text, flags=re.IGNORECASE)
    )

def _rd_unit_from_termination_project(subject, unit=None):
    rd_unit = _head_unit_from_subject(subject)
    if rd_unit:
        return rd_unit.upper(), None
    _ = unit
    return None, "Could not determine RD/FD unit from termination project subject"

def _refurbish_project_name(region, unit_token, kind, date_label):
    return f"{region} - {unit_token} - Refurbish - {kind} - {date_label}"

def _region_from_erp_site(site):
    site_id = str((site or {}).get("site_id") or "").strip()
    if not site_id:
        return None, "Missing site id"
    region = str((site or {}).get("region") or "").strip()
    if region:
        return region, None
    full_site, error = _fetch_erp_site_doc(site_id)
    if error:
        return None, error
    region = str(full_site.get("region") or "").strip()
    if not region:
        return None, f"Site {site_id} has no region set"
    return region, None

def _refurbish_project_specs(subject, unit=None):
    subject = str(subject or "").strip()
    if not subject:
        return None, "Missing project subject"
    if not _is_noc_termination_project_subject(subject):
        return None, "Selected project does not look like a Termination project"

    site, error = find_erp_site_by_project_subject(subject)
    if error:
        return None, error

    region, error = _region_from_erp_site(site)
    if error:
        return None, error

    rd_unit, error = _rd_unit_from_termination_project(subject, unit=unit)
    if error:
        return None, error

    mu_unit = mu_trailer_from_subject(subject, unit=unit)
    date_label = _refurbish_date_label()
    specs = [
        {
            "project_name": _refurbish_project_name(
                region, rd_unit, "Digital", date_label
            ),
            "project_template": DIGITAL_RD_REFURB_TEMPLATE,
        },
        {
            "project_name": _refurbish_project_name(
                region, rd_unit, "Physical", date_label
            ),
            "project_template": PHYSICAL_RD_REFURB_TEMPLATE,
        },
    ]
    if mu_unit:
        specs.append({
            "project_name": _refurbish_project_name(
                region, mu_unit, "Physical", date_label
            ),
            "project_template": PHYSICAL_TRAILER_REFURB_TEMPLATE,
        })

    return {
        "region": region,
        "rd_unit": rd_unit,
        "mu_unit": mu_unit or None,
        "site_id": site.get("site_id"),
        "site_name": site.get("site_name"),
        "date": date_label,
        "specs": specs,
    }, None

def preview_refurbish_projects_from_termination(subject, unit=None):
    """Resolve refurbish project names without creating them."""
    return _refurbish_project_specs(subject, unit=unit)

def create_refurbish_projects_from_termination(subject, unit=None):
    """Create Digital RD, Physical RD, and optional Physical Trailer refurb projects."""
    preview, error = _refurbish_project_specs(subject, unit=unit)
    if error:
        return None, error

    created_projects = []
    errors = []
    for spec in preview["specs"]:
        project_name = spec["project_name"]
        payload = {
            "project_name": project_name,
            "project_template": spec["project_template"],
            "status": "Open",
        }
        response = requests.post(
            ERP_PROJECTS_URL,
            headers={**_erp_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if not response.ok:
            errors.append(f"{project_name}: {_erp_response_error(response)}")
            continue
        created = (response.json() or {}).get("data")
        if not isinstance(created, dict):
            errors.append(f"{project_name}: ERP did not return the created Project")
            continue
        created_id = str(_erp_issue_value(created, "name", "id")).strip()
        created_name = str(
            _erp_issue_value(created, "project_name", "subject", "title")
            or project_name
        ).strip()
        if not created_id:
            errors.append(f"{project_name}: ERP created Project but returned no id")
            continue
        created_projects.append({
            "project_id": created_id,
            "project_name": created_name,
            "project_template": spec["project_template"],
            "url": _project_ticket_url(created_id),
        })

    if not created_projects:
        return None, (errors[0] if errors else "Failed to create refurbish project(s)")

    first = created_projects[0]
    return {
        "project_id": first["project_id"],
        "project_name": first["project_name"],
        "url": first["url"],
        "region": preview["region"],
        "rd_unit": preview["rd_unit"],
        "mu_unit": preview["mu_unit"],
        "count": len(created_projects),
        "projects": created_projects,
        "errors": errors,
    }, None

def _today_erp_date():
    return _arizona_now().date().isoformat()

def _project_title_rest_after_unit(subject):
    """Return the project title tail after NOC Termination/Deployment - Unit - ."""
    text = str(subject or "").strip()
    unit = _noc_termination_unit_token_pattern()
    match = re.match(
        rf"^(?:NOC\s+)?(?:Partial\s+)?(?:Termination|Deployment)\s*-\s*"
        rf"(?:{unit})(?:\s*/\s*(?:{unit}))*\s*-\s*"
        rf"(?P<rest>.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return " ".join(match.group("rest").split())
    # Fallback: drop leading "NOC Termination|Deployment - ..." via first two dashes after prefix.
    match = re.match(
        r"^(?:NOC\s+)?(?:Partial\s+)?(?:Termination|Deployment)\s*-\s*.+?\s*-\s*(?P<rest>.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return " ".join(match.group("rest").split())
    return text

def _site_name_candidates_from_project_subject(subject):
    rest = _project_title_rest_after_unit(subject)
    if not rest:
        return []
    parts = [part.strip() for part in rest.split(" - ") if part.strip()]
    candidates = []
    seen = set()

    def add_candidate(value):
        text = " ".join(str(value or "").split())
        if not text:
            return
        key = text.casefold()
        if key in seen:
            return
        seen.add(key)
        candidates.append(text)

    if parts:
        add_candidate(parts[-1])
    if len(parts) >= 2:
        add_candidate(" - ".join(parts[-2:]))
    add_candidate(rest)
    return candidates

def _normalize_erp_site(doc):
    return {
        "site_id": str(_erp_issue_value(doc, "name", "id")).strip(),
        "site_name": str(_erp_issue_value(doc, "site_name", "name")).strip(),
        "status": str(_erp_issue_value(doc, "status")).strip(),
        "region": str(_erp_issue_value(doc, "region")).strip(),
        "contract_start": str(_erp_issue_value(doc, "contract_start") or "").strip() or None,
        "contract_end": str(_erp_issue_value(doc, "contract_end") or "").strip() or None,
    }

def _search_erp_sites(filters, limit=20):
    response = requests.get(
        ERP_SITES_URL,
        headers=_erp_headers(),
        params={
            "fields": json.dumps([
                "name",
                "site_name",
                "status",
                "region",
                "contract_start",
                "contract_end",
            ]),
            "filters": json.dumps(filters),
            "limit_page_length": limit,
        },
        timeout=30,
    )
    if not response.ok:
        return None, _erp_response_error(response)
    rows = (response.json() or {}).get("data")
    if not isinstance(rows, list):
        return None, "ERP Site response did not contain a data list"
    return [_normalize_erp_site(row) for row in rows if isinstance(row, dict)], None

def find_erp_site_by_project_subject(subject, prefer_status=None):
    """Resolve a Site from a project title using the planned name cascade."""
    subject = str(subject or "").strip()
    if not subject:
        return None, "Missing project subject"
    candidates = _site_name_candidates_from_project_subject(subject)
    if not candidates:
        return None, "Could not derive a site name from the project title"

    matches = []
    seen_ids = set()
    for candidate in candidates:
        rows, error = _search_erp_sites([["site_name", "=", candidate]])
        if error:
            return None, error
        for row in rows or []:
            site_id = row.get("site_id") or ""
            if site_id and site_id not in seen_ids:
                seen_ids.add(site_id)
                matches.append(row)
        if matches:
            break

    if not matches and candidates:
        rows, error = _search_erp_sites(
            [["site_name", "like", f"%{candidates[0]}%"]],
            limit=25,
        )
        if error:
            return None, error
        for row in rows or []:
            site_id = row.get("site_id") or ""
            if site_id and site_id not in seen_ids:
                seen_ids.add(site_id)
                matches.append(row)

    if not matches:
        return None, (
            "No Site found for candidates: " + ", ".join(candidates)
        )

    prefer = str(prefer_status or "").strip().lower()
    if prefer and len(matches) > 1:
        preferred = [
            row for row in matches
            if str(row.get("status") or "").strip().lower() == prefer
        ]
        if len(preferred) == 1:
            return preferred[0], None
        if preferred:
            matches = preferred

    if len(matches) > 1:
        labels = [
            f"{row.get('site_id')} ({row.get('site_name') or '?'}"
            f" / {row.get('status') or '?'})"
            for row in matches[:8]
        ]
        return None, "Multiple Sites matched: " + "; ".join(labels)

    return matches[0], None

def _fetch_erp_site_doc(site_id):
    site_id = str(site_id or "").strip()
    if not site_id:
        return None, "Missing site id"
    response = requests.get(
        f"{ERP_SITES_URL}/{quote(site_id, safe='')}",
        headers=_erp_headers(),
        timeout=30,
    )
    if response.status_code == 404:
        return None, f"Site {site_id} was not found in ERP"
    if not response.ok:
        return None, _erp_response_error(response)
    doc = (response.json() or {}).get("data")
    if not isinstance(doc, dict):
        return None, f"ERP did not return Site {site_id}"
    return _normalize_erp_site(doc), None

def _update_erp_site_fields(site_id, fields):
    site_id = str(site_id or "").strip()
    if not site_id:
        return None, "Missing site id"
    response = requests.put(
        f"{ERP_SITES_URL}/{quote(site_id, safe='')}",
        headers={**_erp_headers(), "Content-Type": "application/json"},
        json=fields,
        timeout=30,
    )
    if not response.ok:
        return None, _erp_response_error(response)
    doc = (response.json() or {}).get("data")
    if isinstance(doc, dict):
        return _normalize_erp_site(doc), None
    return _fetch_erp_site_doc(site_id)

def terminate_erp_site_from_project(subject, site_id=None):
    """Set Site status Active->Inactive and contract_end to today."""
    site = None
    if site_id:
        site, error = _fetch_erp_site_doc(site_id)
        if error:
            return None, error
    else:
        site, error = find_erp_site_by_project_subject(subject, prefer_status="Active")
        if error:
            return None, error
    current = str((site or {}).get("status") or "").strip()
    if current.lower() != "active":
        return None, (
            f"Site {(site or {}).get('site_id')} status is {current or '(empty)'}; "
            "Terminate Site requires Active"
        )
    today = _today_erp_date()
    updated, error = _update_erp_site_fields(
        site["site_id"],
        {"status": "Inactive", "contract_end": today},
    )
    if error:
        return None, error
    return {
        **(updated or site),
        "status": "Inactive",
        "contract_end": today,
        "action": "terminate",
    }, None

def activate_erp_site_from_project(subject, site_id=None):
    """Set Site status Inactive->Active and contract_start to today."""
    site = None
    if site_id:
        site, error = _fetch_erp_site_doc(site_id)
        if error:
            return None, error
    else:
        site, error = find_erp_site_by_project_subject(subject, prefer_status="Inactive")
        if error:
            return None, error
    current = str((site or {}).get("status") or "").strip()
    if current.lower() != "inactive":
        return None, (
            f"Site {(site or {}).get('site_id')} status is {current or '(empty)'}; "
            "Activate Site requires Inactive"
        )
    today = _today_erp_date()
    updated, error = _update_erp_site_fields(
        site["site_id"],
        {"status": "Active", "contract_start": today},
    )
    if error:
        return None, error
    return {
        **(updated or site),
        "status": "Active",
        "contract_start": today,
        "action": "activate",
    }, None

def lookup_erp_site_for_project_action(subject, action):
    """Preview Site resolution for confirm dialogs."""
    prefer = "Active" if action == "terminate" else "Inactive"
    return find_erp_site_by_project_subject(subject, prefer_status=prefer)

def _is_noc_deployment_project_subject(subject):
    return bool(re.search(r"\bnoc\s+deployment\b", str(subject or ""), re.IGNORECASE))

def _unit_from_deployment_project_subject(subject):
    text = str(subject or "").strip()
    if not text:
        return ""
    unit_pat = _noc_termination_unit_token_pattern()
    match = re.match(
        rf"^(?:NOC\s+)?Deployment\s*-\s*(?P<unit>{unit_pat})\s*-",
        text,
        flags=re.IGNORECASE,
    )
    raw = ""
    if match:
        raw = re.sub(r"\s+", "", match.group("unit").strip())
    else:
        raw = _match_unit_from_subject(text)
    if not raw:
        return ""
    # Raindance subjects use the head unit (RD/FD/MU), not RD####(MU####).
    head = _head_unit_from_subject(raw)
    return head or raw

def find_open_raindance_issue(unit):
    """Find exactly one Open Issue whose subject looks like sc-{unit}-Raindance..."""
    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit for Raindance lookup"
    compact_unit = re.sub(r"\s+", "", unit.lower())
    target = f"sc-{compact_unit}-raindance"

    def matches_subject(subject):
        compact = re.sub(r"\s+", "", str(subject or "").lower())
        return target in compact

    response = requests.get(
        ERP_ISSUES_URL,
        headers=_erp_headers(),
        params={
            "fields": json.dumps(["name", "subject", "status", "modified"]),
            "filters": json.dumps([
                ["subject", "like", f"%{target}%"],
                ["status", "=", "Open"],
            ]),
            "limit_page_length": 50,
            "order_by": "modified desc",
        },
        timeout=30,
    )
    if not response.ok:
        return None, _erp_response_error(response)
    rows = (response.json() or {}).get("data")
    if not isinstance(rows, list):
        return None, "ERP Issue response did not contain a data list"

    unique = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject") or "")
        if not matches_subject(subject):
            continue
        issue_id = str(row.get("name") or "").strip()
        if not issue_id or issue_id in seen:
            continue
        seen.add(issue_id)
        unique.append({
            "issue_id": issue_id,
            "subject": subject,
            "status": str(row.get("status") or "").strip(),
            "url": _issue_ticket_url(issue_id),
        })

    if not unique:
        # Case-sensitive ERP "like" fallback: scan recent Open issues locally.
        response = requests.get(
            ERP_ISSUES_URL,
            headers=_erp_headers(),
            params={
                "fields": json.dumps(["name", "subject", "status", "modified"]),
                "filters": json.dumps([["status", "=", "Open"]]),
                "limit_page_length": 500,
                "order_by": "modified desc",
            },
            timeout=30,
        )
        if not response.ok:
            return None, _erp_response_error(response)
        for row in (response.json() or {}).get("data") or []:
            if not isinstance(row, dict):
                continue
            subject = str(row.get("subject") or "")
            if not matches_subject(subject):
                continue
            issue_id = str(row.get("name") or "").strip()
            if not issue_id or issue_id in seen:
                continue
            seen.add(issue_id)
            unique.append({
                "issue_id": issue_id,
                "subject": subject,
                "status": str(row.get("status") or "").strip(),
                "url": _issue_ticket_url(issue_id),
            })

    if not unique:
        return None, f"No Open Raindance issue found for unit {unit}"
    if len(unique) > 1:
        labels = ", ".join(
            f"{item['issue_id']} ({item['subject']})" for item in unique[:5]
        )
        return None, f"Multiple Open Raindance issues for {unit}: {labels}"
    return unique[0], None

def get_project_task(project_id, subject):
    """Return the single Task for project_id + exact subject, or an error."""
    project_id = str(project_id or "").strip()
    subject = str(subject or "").strip()
    if not project_id:
        return None, "Missing project id"
    if not subject:
        return None, "Missing task subject"
    response = requests.get(
        ERP_TASKS_URL,
        headers=_erp_headers(),
        params={
            "fields": json.dumps([
                "name",
                "subject",
                "status",
                "project",
                "completed_on",
                "description",
            ]),
            "filters": json.dumps([
                ["project", "=", project_id],
                ["subject", "=", subject],
            ]),
            "limit_page_length": 5,
        },
        timeout=30,
    )
    if not response.ok:
        return None, _erp_response_error(response)
    rows = (response.json() or {}).get("data")
    if not isinstance(rows, list):
        return None, "ERP Task response did not contain a data list"
    matches = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_project = str(row.get("project") or "").strip()
        task_id = str(row.get("name") or "").strip()
        task_subject = str(row.get("subject") or "").strip()
        if not task_id:
            continue
        if task_project != project_id:
            continue
        if task_subject != subject:
            continue
        matches.append({
            "task_id": task_id,
            "subject": task_subject,
            "status": str(row.get("status") or "").strip(),
            "project": task_project,
            "completed_on": str(row.get("completed_on") or "").strip() or None,
        })
    if not matches:
        return None, (
            f"No Task '{subject}' found on project {project_id}"
        )
    if len(matches) > 1:
        return None, (
            f"Multiple Tasks named '{subject}' on project {project_id}"
        )
    return matches[0], None

def add_task_comment(task_id, content, project_id=None):
    """Post a Comment on a single Task. Optionally re-verify project ownership."""
    task_id = str(task_id or "").strip()
    content = str(content or "").strip()
    if not task_id:
        return None, "Missing task id"
    if not content:
        return None, "Missing comment content"
    if project_id:
        response = requests.get(
            f"{ERP_TASKS_URL}/{quote(task_id, safe='')}",
            headers=_erp_headers(),
            timeout=30,
        )
        if not response.ok:
            return None, _erp_response_error(response)
        doc = (response.json() or {}).get("data")
        if not isinstance(doc, dict):
            return None, f"ERP did not return Task {task_id}"
        task_project = str(doc.get("project") or "").strip()
        if task_project != str(project_id).strip():
            return None, (
                f"Refusing comment: Task {task_id} belongs to {task_project or '(none)'}, "
                f"not {project_id}"
            )
    response = requests.post(
        ERP_COMMENTS_URL,
        headers={**_erp_headers(), "Content-Type": "application/json"},
        json={
            "comment_type": "Comment",
            "reference_doctype": "Task",
            "reference_name": task_id,
            "content": content,
        },
        timeout=30,
    )
    if not response.ok:
        return None, _erp_response_error(response)
    created = (response.json() or {}).get("data")
    comment_id = ""
    if isinstance(created, dict):
        comment_id = str(created.get("name") or "").strip()
    return {"comment_id": comment_id, "task_id": task_id}, None

def _complete_single_tech_task(project_id, subject, comment_text):
    task, error = get_project_task(project_id, subject)
    if error:
        return None, error
    if str(task.get("project") or "").strip() != str(project_id).strip():
        return None, (
            f"Refusing update: Task {task.get('task_id')} project mismatch"
        )
    _, error = add_task_comment(
        task["task_id"],
        comment_text,
        project_id=project_id,
    )
    if error:
        return None, error
    status = str(task.get("status") or "").strip()
    already_done = status.lower() == "completed"
    if not already_done:
        today = _today_erp_date()
        response = requests.put(
            f"{ERP_TASKS_URL}/{quote(task['task_id'], safe='')}",
            headers={**_erp_headers(), "Content-Type": "application/json"},
            json={
                "status": "Completed",
                "completed_on": today,
            },
            timeout=30,
        )
        if not response.ok:
            return None, _erp_response_error(response)
        # Re-verify ownership after write
        verify, verify_error = get_project_task(project_id, subject)
        if verify_error:
            return None, (
                f"Updated {task['task_id']} but re-check failed: {verify_error}"
            )
        if str(verify.get("project") or "").strip() != str(project_id).strip():
            return None, (
                f"Safety check failed after update for Task {task['task_id']}"
            )
        task = verify
        task["completed_on"] = today
        task["status"] = "Completed"
    return {
        "subject": subject,
        "task_id": task["task_id"],
        "status": task.get("status"),
        "completed_on": task.get("completed_on"),
        "already_completed": already_done,
        "ok": True,
    }, None

def _cancel_single_tech_task(project_id, subject, comment_text):
    """Cancel one task on this project only. Already-Cancelled tasks are ignored."""
    task, error = get_project_task(project_id, subject)
    if error:
        return {
            "subject": subject,
            "ok": False,
            "skipped": True,
            "error": error,
        }, None
    if str(task.get("project") or "").strip() != str(project_id).strip():
        return {
            "subject": subject,
            "task_id": task.get("task_id"),
            "ok": False,
            "skipped": True,
            "error": (
                f"Refusing update: Task {task.get('task_id')} project mismatch"
            ),
        }, None
    status = str(task.get("status") or "").strip()
    if status.lower() == "cancelled":
        return {
            "subject": subject,
            "task_id": task["task_id"],
            "status": status,
            "already_cancelled": True,
            "ok": True,
            "skipped": True,
        }, None
    _, error = add_task_comment(
        task["task_id"],
        comment_text,
        project_id=project_id,
    )
    if error:
        return {
            "subject": subject,
            "task_id": task["task_id"],
            "ok": False,
            "skipped": True,
            "error": error,
        }, None
    response = requests.put(
        f"{ERP_TASKS_URL}/{quote(task['task_id'], safe='')}",
        headers={**_erp_headers(), "Content-Type": "application/json"},
        json={"status": "Cancelled"},
        timeout=30,
    )
    if not response.ok:
        return {
            "subject": subject,
            "task_id": task["task_id"],
            "ok": False,
            "skipped": True,
            "error": _erp_response_error(response),
        }, None
    verify, verify_error = get_project_task(project_id, subject)
    if verify_error:
        return {
            "subject": subject,
            "task_id": task["task_id"],
            "ok": False,
            "skipped": True,
            "error": (
                f"Updated {task['task_id']} but re-check failed: {verify_error}"
            ),
        }, None
    if str(verify.get("project") or "").strip() != str(project_id).strip():
        return {
            "subject": subject,
            "task_id": task["task_id"],
            "ok": False,
            "skipped": True,
            "error": (
                f"Safety check failed after update for Task {task['task_id']}"
            ),
        }, None
    return {
        "subject": subject,
        "task_id": verify["task_id"],
        "status": "Cancelled",
        "already_cancelled": False,
        "ok": True,
        "skipped": False,
    }, None

def preview_project_tech_checks(project_id, project_subject):
    """Read-only preview for the Tech Checks (180 Unit) confirm modal."""
    project_id = str(project_id or "").strip()
    project_subject = str(project_subject or "").strip()
    if not project_id:
        return None, "Missing project id"
    if not _is_noc_deployment_project_subject(project_subject):
        return None, "Tech Checks is only available for NOC Deployment projects"
    unit = _unit_from_deployment_project_subject(project_subject)
    if not unit:
        return None, "Could not parse unit from deployment project title"
    raindance, error = find_open_raindance_issue(unit)
    if error:
        return None, error
    tasks = []
    for subject in TECH_CHECK_TASK_SUBJECTS:
        task, task_error = get_project_task(project_id, subject)
        if task_error:
            if subject == TECH_CHECK_ROUTER_SUBJECT:
                return None, task_error
            tasks.append({
                "subject": subject,
                "ok": False,
                "error": task_error,
            })
            continue
        tasks.append({
            "subject": subject,
            "task_id": task["task_id"],
            "status": task.get("status"),
            "ok": True,
        })
    cancel_tasks = []
    for subject in TECH_CHECK_CANCEL_SUBJECTS:
        task, task_error = get_project_task(project_id, subject)
        if task_error:
            cancel_tasks.append({
                "subject": subject,
                "ok": False,
                "error": task_error,
            })
            continue
        cancel_tasks.append({
            "subject": subject,
            "task_id": task["task_id"],
            "status": task.get("status"),
            "ok": True,
        })
    return {
        "project_id": project_id,
        "subject": project_subject,
        "unit": unit,
        "raindance": raindance,
        "tasks": tasks,
        "task_subjects": list(TECH_CHECK_TASK_SUBJECTS),
        "cancel_tasks": cancel_tasks,
        "cancel_subjects": list(TECH_CHECK_CANCEL_SUBJECTS),
        "cancel_comment": TECH_CHECK_CANCEL_COMMENT,
    }, None

def complete_project_tech_checks(project_id, project_subject):
    """Complete Tech Checks, then cancel 180-unit N/A tasks on one project only."""
    preview, error = preview_project_tech_checks(project_id, project_subject)
    if error:
        return None, error
    raindance = preview["raindance"]
    comment_text = f"PASSED: {raindance['url']}"
    results = []

    # Router first — abort entirely if it fails before any later writes.
    router_result, router_error = _complete_single_tech_task(
        project_id,
        TECH_CHECK_ROUTER_SUBJECT,
        comment_text,
    )
    if router_error:
        return None, f"Router tech check failed; no tasks were completed: {router_error}"
    results.append(router_result)

    for subject in TECH_CHECK_TASK_SUBJECTS[1:]:
        result, task_error = _complete_single_tech_task(
            project_id,
            subject,
            comment_text,
        )
        if task_error:
            results.append({
                "subject": subject,
                "ok": False,
                "error": task_error,
            })
            return {
                "project_id": project_id,
                "unit": preview["unit"],
                "raindance_issue_id": raindance["issue_id"],
                "raindance_url": raindance["url"],
                "comment": comment_text,
                "results": results,
                "cancel_results": [],
                "partial": True,
                "error": (
                    f"Stopped after failure on '{subject}': {task_error}"
                ),
            }, None
        results.append(result)

    cancel_results = []
    cancel_errors = []
    for subject in TECH_CHECK_CANCEL_SUBJECTS:
        cancel_result, _ = _cancel_single_tech_task(
            project_id,
            subject,
            TECH_CHECK_CANCEL_COMMENT,
        )
        cancel_results.append(cancel_result)
        if not cancel_result.get("ok"):
            cancel_errors.append(
                f"{subject}: {cancel_result.get('error') or 'unknown error'}"
            )

    partial = bool(cancel_errors)
    error_text = None
    if cancel_errors:
        error_text = (
            "Tech checks completed; some cancel targets were skipped: "
            + "; ".join(cancel_errors)
        )
    return {
        "project_id": project_id,
        "unit": preview["unit"],
        "raindance_issue_id": raindance["issue_id"],
        "raindance_url": raindance["url"],
        "comment": comment_text,
        "cancel_comment": TECH_CHECK_CANCEL_COMMENT,
        "results": results,
        "cancel_results": cancel_results,
        "partial": partial,
        "error": error_text,
    }, None

def _subject_mentions_unit(subject, unit):
    """True when subject contains unit (MU3003 or MU 3003)."""
    subject_text = str(subject or "")
    unit_text = str(unit or "").strip().upper()
    if not unit_text:
        return False
    if unit_text in subject_text.upper():
        return True
    match = re.fullmatch(r"([A-Z]{2,4})(\d{3,6})", unit_text)
    if not match:
        return False
    prefix, number = match.group(1), match.group(2)
    return bool(
        re.search(
            rf"\b{re.escape(prefix)}\s*{re.escape(number)}\b",
            subject_text,
            flags=re.IGNORECASE,
        )
    )

def _match_unit_from_subject(subject):
    """Return the first net-sheet unit found in subject (same rules as issues)."""
    text = str(subject or "").strip()
    if not text:
        return ""
    if not net_array:
        generate_net_array()
    has_head_unit = bool(re.search(r"\b(?:RD|FD)\s*\d+", text, re.IGNORECASE))
    candidate_rows = sorted(
        net_array,
        key=lambda row: (
            0
            if has_head_unit
            and row
            and str(row[0]).upper().startswith(("RD", "FD"))
            else 1
        ),
    )
    for net_row in candidate_rows:
        unit = net_row[0]
        if (
            _subject_mentions_unit(text, unit)
            and (unit not in false_mu_array or not has_head_unit)
        ):
            return unit
    fallback = _normalize_netsheet_unit(_head_unit_from_subject(text))
    return fallback or ""

def _connectivity_category_led(category):
    if category == "false_positives":
        return "green"
    if category in ("nuc_down", "scrypted_outage"):
        return "yellow"
    if category in ("truly_down", "stale_vpn"):
        return "red"
    return None

def validate_project_records(project_records):
    """Run connectivity-only validation for NOC projects; return Projects list entries."""
    if not net_array:
        generate_net_array()
    entries = []
    records = list(project_records or [])
    print(f"Validating {len(records)} NOC project(s)...")
    total = len(records)
    for index, project in enumerate(records, 1):
        project_id = str((project or {}).get("project_id") or "").strip()
        subject = str((project or {}).get("subject") or "").strip()
        status = str((project or {}).get("status") or "").strip()
        percent_complete = (project or {}).get("percent_complete")
        print(f"__PROGRESS__ {index} {total} {project_id or 'project'}")
        unit = _match_unit_from_subject(subject)
        if not unit:
            print(
                f"Skipping project without matchable unit in subject: "
                f"{project_id or '(no id)'} — {subject or '(no subject)'}"
            )
            continue
        print(f"Matched project {project_id} -> {unit} ({subject})")
        category, output, error = validate_unit_status(unit)
        if output:
            for line in str(output).splitlines():
                if line:
                    print(line)
        if error:
            print(error)
            led_status = "red"
            category = category or "truly_down"
        else:
            led_status = _connectivity_category_led(category) or "red"
        switch_url, fisheye_ip, pve_ip, has_pve, has_relay, has_platform, platform_url, has_scrypted, scrypted_url = (
            _unit_device_info(unit)
        )
        vrm_mu, vrm_url = _vrm_info_from_subject(subject, unit)
        entries.append({
            "unit": unit,
            "project_id": project_id,
            "issue_id": "",
            "url": _project_ticket_url(project_id),
            "subject": subject,
            "erp_status": status,
            "percent_complete": percent_complete,
            "percent_complete_label": _format_project_percent_complete(percent_complete),
            "modified": str((project or {}).get("modified") or "").strip(),
            "connectivity_kind": category or "",
            "led_status": led_status,
            "switch_url": switch_url,
            "fisheye_ip": fisheye_ip,
            "pve_ip": pve_ip,
            "has_pve": has_pve,
            "has_relay": has_relay,
            "has_platform": has_platform,
            "platform_url": platform_url,
            "has_scrypted": has_scrypted,
            "scrypted_url": scrypted_url,
            "compute_label": compute_host_label(unit),
            "vrm_mu": vrm_mu,
            "vrm_url": vrm_url,
            "outage_type": "",
            "issue_subtype": "",
            "undiagnosed": False,
            "is_speaker": False,
            "is_camera": False,
            "is_panel_issue": False,
            "is_camera_view": False,
            "hold_kind": "",
        })
    entries.sort(
        key=lambda item: (
            str(item.get("modified") or ""),
            str(item.get("project_id") or ""),
        ),
        reverse=True,
    )
    print(f"Projects list ready: {len(entries)} validated")
    return entries

ARIZONA_TZ = timezone(timedelta(hours=-7))

# Named ERP field presets for list command-menu buttons.
# Add another entry here, then attach it to a list in issues_results.html.
ISSUE_FIELD_PRESETS = {
    "dirty_panels": {
        "label": "Dirty Panels",
        "list_id": "panel_issues",
        "issue_type": "Maintenance",
        "issue_subtype": "Dirty Panels",
        "working_team": "CXT",
        "owner_team": "CXT",
        "who_is_working_env": "cxtmanager",
        "user_group": "CXT",
        "set_component": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": True,
    },
    "panels_closed": {
        "label": "Panels closed",
        "list_id": "panel_issues",
        "issue_type": "Maintenance",
        "issue_subtype": "Panels closed",
        "working_team": "CXT",
        "owner_team": "CXT",
        "who_is_working_env": "cxtmanager",
        "user_group": "CXT",
        "set_component": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": True,
    },
    "camera_adjustment": {
        "label": "Camera Adjustment",
        "list_id": "camera_view",
        "issue_type": "Camera Views",
        "issue_subtype": "Camera Adjustment",
        "working_team": "NOC",
        "owner_team": "NOC",
        "who_is_working_env": "nocmanager",
        "set_component": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
    "dark_views": {
        "label": "Dark Views",
        "list_id": "camera_view",
        "issue_type": "Camera Views",
        "issue_subtype": "Dark Views",
        "working_team": "NOC",
        "owner_team": "NOC",
        "who_is_working_env": "nocmanager",
        "set_component": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
    "blurry_cameras": {
        "label": "Blurry cameras",
        "list_id": "camera_view",
        "issue_type": "Camera Views",
        "issue_subtype": "Blurry cameras",
        "working_team": "NOC",
        "owner_team": "NOC",
        "who_is_working_env": "nocmanager",
        "set_component": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
    "dirty_cameras": {
        "label": "Dirty Cameras",
        "list_id": "camera_view",
        "issue_type": "Camera Views",
        "issue_subtype": "Dirty Cameras",
        "working_team": "NOC",
        "owner_team": "NOC",
        "who_is_working_env": "nocmanager",
        "set_component": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
    "weather": {
        "label": "Weather",
        "list_id": "false_positives",
        "issue_type": "Unit Outage - Full",
        "issue_subtype": "Weather",
        "working_team": "NOC",
        "owner_team": "NOC",
        "who_is_working_env": "nocmanager",
        "set_component": True,
        "set_site": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
    "unit_unplugged": {
        "label": "Unit Unplugged",
        "list_id": "false_positives",
        "issue_type": "Unit Outage - Full",
        "issue_subtype": "Unit Unplugged",
        "working_team": "CXT",
        "owner_team": "NOC",
        "who_is_working_env": "cxtmanager",
        "progress": "Waiting on Customer Feedback (Email)",
        "set_component": True,
        "set_site": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
    "recording_drive_error": {
        "label": "Recording Drive Error",
        "list_id": "false_positives",
        "issue_type": "Storage Error",
        "issue_subtype": "Recording drive error",
        "working_team": "NOC",
        "owner_team": "NOC",
        "who_is_working_env": "nocmanager",
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
    "nuc_down": {
        "label": "NUC Down",
        "list_id": "nuc_down",
        "issue_type": "Unit Outage - Partial",
        "issue_subtype": "Nuc Down",
        "working_team": "NOC",
        "owner_team": "NOC",
        "who_is_working_env": "nocmanager",
        "set_component": True,
        "set_site": True,
        "set_incident_now": True,
        "set_followup_today": True,
        "assign_user_group": False,
    },
}

def _erp_headers():
    load_dotenv(env_path)
    erp_token = (os.getenv("erp_token") or "").strip().strip('"').strip("'")
    if not erp_token:
        raise RuntimeError("erp_token is not set in .env")
    return {"Authorization": f"token {erp_token}"}

def _erp_field_empty(value):
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False

def _sc_component_name(unit):
    raw = str(unit or "").strip()
    if not raw:
        return ""
    if raw.upper().startswith("SC-"):
        raw = raw[3:]
    return f"SC-{raw}"


def _parent_mu_from_subject(subject):
    match = re.search(
        r"\bRD\s*\d+\s*\(\s*MU\s*(\d+)\s*\)",
        str(subject or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return f"MU{match.group(1)}"


def _parent_component_from_erp(unit, cache):
    """Return ERP parent Component link (e.g. SC-MU7027) for unit, or '' if none."""
    doc, _found_name, error = _lookup_component_doc(unit, cache)
    if error:
        return "", error
    if not doc:
        return "", None
    return str(doc.get("parent_component") or "").strip(), None


def _head_unit_from_subject(subject):
    text = str(subject or "")
    rd_fd = re.search(r"\b(RD|FD)\s*(\d+)\b", text, flags=re.IGNORECASE)
    if rd_fd:
        return f"{rd_fd.group(1).upper()}{rd_fd.group(2)}"
    mu = re.search(r"\b(MU)\s*(\d+)\b", text, flags=re.IGNORECASE)
    if mu:
        return f"{mu.group(1).upper()}{mu.group(2)}"
    return ""

def _arizona_now():
    return datetime.now(ARIZONA_TZ)

def _erp_response_error(response):
    try:
        payload = response.json()
    except ValueError:
        return (response.text or f"HTTP {response.status_code}")[:400]
    messages = payload.get("_server_messages")
    if messages:
        try:
            parsed = json.loads(messages) if isinstance(messages, str) else messages
            if isinstance(parsed, list) and parsed:
                first = parsed[0]
                if isinstance(first, str):
                    first = json.loads(first)
                if isinstance(first, dict) and first.get("message"):
                    return str(first["message"])
        except (TypeError, ValueError):
            pass
    return str(
        payload.get("exception")
        or payload.get("exc_type")
        or (response.text or f"HTTP {response.status_code}")[:400]
    )

def _fetch_erp_issue_doc(issue_id):
    response = requests.get(
        f"{erp_base_url()}/api/resource/Issue/{issue_id}",
        headers=_erp_headers(),
        timeout=30,
    )
    if response.status_code == 404:
        return None, f"{issue_id} was not found in ERP"
    if not response.ok:
        return None, _erp_response_error(response)
    doc = (response.json() or {}).get("data")
    if not isinstance(doc, dict):
        return None, f"ERP did not return Issue {issue_id}"
    return doc, None


def _fetch_erp_issue_component_site_map(issue_ids):
    ids = []
    seen = set()
    for issue_id in issue_ids or []:
        name = str(issue_id or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        ids.append(name)
    found = {}
    headers = _erp_headers()
    for start in range(0, len(ids), 200):
        chunk = ids[start:start + 200]
        print(
            f"Add Missing Components/Sites: loading {len(chunk)} Issue records "
            f"from ERP ({start + 1}-{start + len(chunk)} of {len(ids)})"
        )
        response = requests.get(
            f"{erp_base_url()}/api/resource/Issue",
            headers=headers,
            params={
                "fields": json.dumps(["name", "component", "site"]),
                "filters": json.dumps([["name", "in", chunk]]),
                "limit_page_length": len(chunk),
            },
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(_erp_response_error(response))
        for row in (response.json() or {}).get("data") or []:
            name = str((row or {}).get("name") or "").strip()
            if name:
                found[name] = row
    return found

ADD_MISSING_ERP_CHUNK = 200
ADD_MISSING_PUT_WORKERS = 4


def _component_lookup_names(name, try_bare=False):
    candidates = []
    sc_name = _sc_component_name(name)
    if sc_name:
        candidates.append(sc_name)
    raw = str(name or "").strip()
    if try_bare and raw and sc_name.upper() != raw.upper():
        candidates.append(raw)
    return candidates


def _fetch_erp_component_site_map(names, cache, headers=None, quiet=False):
    """Batch-load Component name/site into cache. Missing names are cached as None."""
    headers = headers or _erp_headers()
    to_fetch = []
    seen = set()
    for name in names or []:
        key = str(name or "").strip()
        if not key or key in seen or key in cache:
            continue
        seen.add(key)
        to_fetch.append(key)
    if not to_fetch:
        return
    if not quiet:
        print(
            f"Add Missing Components/Sites: prefetching {len(to_fetch)} "
            "Component records from ERP"
        )
    for start in range(0, len(to_fetch), ADD_MISSING_ERP_CHUNK):
        chunk = to_fetch[start:start + ADD_MISSING_ERP_CHUNK]
        response = requests.get(
            f"{erp_base_url()}/api/resource/Component",
            headers=headers,
            params={
                "fields": json.dumps(["name", "site"]),
                "filters": json.dumps([["name", "in", chunk]]),
                "limit_page_length": len(chunk),
            },
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(_erp_response_error(response))
        found_in_chunk = set()
        for row in (response.json() or {}).get("data") or []:
            name = str((row or {}).get("name") or "").strip()
            if name:
                cache[name] = row
                found_in_chunk.add(name)
        for name in chunk:
            if name not in found_in_chunk:
                cache[name] = None


def resolve_shield_site_id(unit, subject=""):
    """Resolve Shield site ID from the unit's Component, or parent MU for RD(MU) subjects.

    When there is no ticket subject (ad-hoc unit commands), parent MU is read from
    ERP Component.parent_component instead of the subject line. If the unit has no
    parent component, the site on the unit's own Component record is used.
    """
    unit_name = str(unit or "").strip() or _head_unit_from_subject(subject)
    if not unit_name:
        return "", "No unit found in ticket"
    subject_text = str(subject or "").strip()
    parent_source = _parent_mu_from_subject(subject_text) if subject_text else ""
    cache = {}
    if not parent_source and not subject_text:
        parent_component, lookup_error = _parent_component_from_erp(unit_name, cache)
        if lookup_error:
            return "", lookup_error
        parent_source = parent_component
    site_source = parent_source or unit_name
    try:
        _fetch_erp_component_site_map(
            _component_lookup_names(site_source, try_bare=bool(parent_source)),
            cache,
            quiet=True,
        )
    except Exception as exc:
        return "", str(exc)
    site, found_name = _site_from_prefetched_component(
        site_source,
        cache,
        try_bare=bool(parent_source),
    )
    if not site:
        return "", f"Component {found_name or site_source} has no Site"
    return site, None


def _site_from_prefetched_component(name, cache, try_bare=False):
    candidates = _component_lookup_names(name, try_bare=try_bare)
    for candidate in candidates:
        doc = cache.get(candidate)
        if doc:
            site = str(doc.get("site") or "").strip()
            if site:
                return site, candidate
            return "", candidate
    return "", (candidates[0] if candidates else str(name or "").strip())


def _put_issue_component_site(issue_id, payload, headers):
    response = requests.put(
        f"{erp_base_url()}/api/resource/Issue/{issue_id}",
        headers=headers,
        json=payload,
        timeout=30,
    )
    if not response.ok:
        return issue_id, None, _erp_response_error(response)
    return issue_id, payload, None


def _component_exists(component):
    response = requests.get(
        f"{erp_base_url()}/api/resource/Component/{component}",
        headers=_erp_headers(),
        timeout=30,
    )
    return response.ok


def _fetch_erp_component_doc(name, cache):
    key = str(name or "").strip()
    if not key:
        return None, "missing Component name"
    if key in cache:
        return cache[key], None
    response = requests.get(
        f"{erp_base_url()}/api/resource/Component/{quote(key, safe='')}",
        headers=_erp_headers(),
        timeout=30,
    )
    if response.status_code == 404:
        cache[key] = None
        return None, None
    if not response.ok:
        return None, _erp_response_error(response)
    doc = (response.json() or {}).get("data")
    if not isinstance(doc, dict):
        return None, f"ERP did not return Component {key}"
    cache[key] = doc
    return doc, None


def _lookup_component_doc(name, cache, try_bare=False):
    sc_name = _sc_component_name(name)
    candidates = []
    if sc_name:
        candidates.append(sc_name)
    raw = str(name or "").strip()
    if try_bare and raw and sc_name.upper() != raw.upper():
        candidates.append(raw)
    last_error = None
    for candidate in candidates:
        doc, error = _fetch_erp_component_doc(candidate, cache)
        if error:
            last_error = f"{candidate}: {error}"
            continue
        if doc:
            return doc, candidate, None
    return None, (candidates[0] if candidates else raw), last_error

def _user_group_member_names(group_name):
    response = requests.get(
        f"{erp_base_url()}/api/resource/User Group Member",
        headers=_erp_headers(),
        params={
            "fields": json.dumps(["user"]),
            "filters": json.dumps([["parent", "=", group_name]]),
            "limit_page_length": 500,
        },
        timeout=30,
    )
    if not response.ok:
        return [], _erp_response_error(response)
    users = []
    for row in (response.json() or {}).get("data") or []:
        user = str((row or {}).get("user") or "").strip()
        if user and user not in users:
            users.append(user)
    return users, None

def _issue_already_assigned(doc):
    raw = (doc or {}).get("_assign")
    if not raw:
        return False
    if isinstance(raw, list):
        return any(str(item).strip() for item in raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text or text in ("[]", "null"):
            return False
        try:
            parsed = json.loads(text)
        except ValueError:
            return True
        if isinstance(parsed, list):
            return any(str(item).strip() for item in parsed)
        return bool(parsed)
    return True

def _assign_issue_to_user_group(issue_id, users):
    response = requests.post(
        f"{erp_base_url()}/api/method/frappe.desk.form.assign_to.add",
        headers=_erp_headers(),
        json={
            "assign_to": users,
            "doctype": "Issue",
            "name": issue_id,
            "notify": 0,
        },
        timeout=30,
    )
    if not response.ok:
        return _erp_response_error(response)
    return None

def set_issue_preset_fields(preset_id, issue_id, unit, subject=""):
    """Fill empty ERP Issue fields from a named preset. Never overwrites set values."""
    preset = ISSUE_FIELD_PRESETS.get(str(preset_id or "").strip())
    if not preset:
        return None, f"Unknown field preset: {preset_id}"
    issue_id = str(issue_id or "").strip()
    if not issue_id:
        return None, "Missing issue_id"
    doc, error = _fetch_erp_issue_doc(issue_id)
    if error:
        return None, error

    now = _arizona_now()
    desired = {}
    if preset.get("issue_type"):
        desired["issue_type"] = preset["issue_type"]
    if preset.get("issue_subtype"):
        desired["issue_subtype"] = preset["issue_subtype"]
    if preset.get("set_incident_now"):
        desired["incident_date"] = now.strftime("%Y-%m-%d %H:%M:%S")
    if preset.get("set_followup_today"):
        desired["next_followup"] = now.strftime("%Y-%m-%d")
    if preset.get("working_team"):
        desired["working_team"] = preset["working_team"]
    if preset.get("owner_team"):
        desired["owner_team"] = preset["owner_team"]
    if preset.get("progress"):
        desired["progress"] = preset["progress"]

    env_name = str(preset.get("who_is_working_env") or "").strip()
    who = (os.getenv(env_name) or "").strip().strip('"').strip("'") if env_name else ""
    unit = str(unit or "").strip()
    subject = str(subject or "").strip()
    component = _sc_component_name(unit) if preset.get("set_component") else ""
    set_fields = []
    skipped = []
    errors = []
    payload = {}

    for field_name, value in desired.items():
        if _erp_field_empty(doc.get(field_name)):
            payload[field_name] = value
        else:
            skipped.append({"field": field_name, "reason": "already set"})

    if env_name:
        if who:
            if _erp_field_empty(doc.get("who_is_working")):
                payload["who_is_working"] = who
            else:
                skipped.append({"field": "who_is_working", "reason": "already set"})
        else:
            skipped.append({
                "field": "who_is_working",
                "reason": f"{env_name} is not set in .env",
            })

    if preset.get("set_component"):
        if component:
            if _erp_field_empty(doc.get("component")):
                if _component_exists(component):
                    payload["component"] = component
                else:
                    errors.append(f"Component {component} was not found in ERP")
                    skipped.append({"field": "component", "reason": "not found in ERP"})
            else:
                skipped.append({"field": "component", "reason": "already set"})
        else:
            skipped.append({"field": "component", "reason": "missing unit"})

    if preset.get("set_site"):
        if _erp_field_empty(doc.get("site")):
            if not unit:
                skipped.append({"field": "site", "reason": "missing unit"})
            else:
                site_id, site_error = resolve_shield_site_id(unit, subject)
                if site_error:
                    errors.append(site_error)
                    skipped.append({"field": "site", "reason": site_error})
                elif site_id:
                    payload["site"] = site_id
                else:
                    skipped.append({"field": "site", "reason": "no site found"})
        else:
            skipped.append({"field": "site", "reason": "already set"})

    if payload:
        response = requests.put(
            f"{erp_base_url()}/api/resource/Issue/{issue_id}",
            headers=_erp_headers(),
            json=payload,
            timeout=30,
        )
        if not response.ok:
            return None, _erp_response_error(response)
        set_fields.extend(payload.keys())

    user_group = str(preset.get("user_group") or "").strip()
    if preset.get("assign_user_group") and user_group:
        if _issue_already_assigned(doc):
            skipped.append({"field": "assigned_user_group", "reason": "already assigned"})
        else:
            users, group_error = _user_group_member_names(user_group)
            if group_error:
                errors.append(group_error)
                skipped.append({"field": "assigned_user_group", "reason": group_error})
            elif not users:
                skipped.append({
                    "field": "assigned_user_group",
                    "reason": f"User Group {user_group} has no members",
                })
            else:
                assign_error = _assign_issue_to_user_group(issue_id, users)
                if assign_error:
                    errors.append(assign_error)
                    skipped.append({"field": "assigned_user_group", "reason": assign_error})
                else:
                    set_fields.append("assigned_user_group")

    current_type = str(payload.get("issue_type") or doc.get("issue_type") or "").strip()
    current_subtype = str(
        payload.get("issue_subtype") or doc.get("issue_subtype") or ""
    ).strip()
    return {
        "preset_id": str(preset_id).strip(),
        "preset_label": preset["label"],
        "list_id": preset.get("list_id") or "",
        "issue_id": issue_id,
        "component": component,
        "set_fields": set_fields,
        "skipped": skipped,
        "errors": errors,
        "issue_type": current_type,
        "issue_subtype": current_subtype,
        "outage_type": _parse_outage_kind(current_type),
        "undiagnosed": not bool(current_subtype),
    }, None

def add_missing_issue_components(tickets):
    """Fill empty Issue.component and/or Issue.site. Never overwrite existing values."""
    updated = []
    skipped = []
    errors = []
    component_cache = {}
    pending = []
    seen = set()
    erp_headers = _erp_headers()
    for ticket in tickets or []:
        issue_id = str((ticket or {}).get("issue_id") or "").strip()
        unit = str((ticket or {}).get("unit") or "").strip()
        subject = str((ticket or {}).get("subject") or "").strip()
        if not unit:
            unit = _head_unit_from_subject(subject)
        if not issue_id or not unit or issue_id in seen:
            continue
        seen.add(issue_id)
        unit_component = _sc_component_name(unit)
        if not unit_component:
            skipped.append({
                "issue_id": issue_id,
                "reason": "missing unit",
            })
            continue
        pending.append({
            "issue_id": issue_id,
            "unit": unit,
            "subject": subject,
            "unit_component": unit_component,
        })
    print(
        f"Add Missing Components/Sites: checking {len(pending)} tickets"
    )
    try:
        issue_docs = _fetch_erp_issue_component_site_map(
            [item["issue_id"] for item in pending]
        )
    except Exception as exc:
        return {
            "checked": len(seen),
            "updated": [],
            "component_set": 0,
            "site_set": 0,
            "skipped": skipped,
            "errors": [f"Failed to load Issues from ERP: {exc}"],
        }

    work_items = []
    component_names = set()
    for item in pending:
        issue_id = item["issue_id"]
        doc = issue_docs.get(issue_id)
        if not isinstance(doc, dict):
            errors.append(f"{issue_id}: was not found in ERP")
            continue
        need_component = _erp_field_empty(doc.get("component"))
        need_site = _erp_field_empty(doc.get("site"))
        if not need_component and not need_site:
            skipped.append({
                "issue_id": issue_id,
                "reason": "already set",
                "component": str(doc.get("component") or "").strip(),
                "site": str(doc.get("site") or "").strip(),
            })
            continue
        if need_component:
            component_names.add(item["unit_component"])
        if need_site:
            parent_mu = _parent_mu_from_subject(item["subject"])
            site_source = parent_mu or item["unit"]
            for name in _component_lookup_names(
                site_source,
                try_bare=bool(parent_mu),
            ):
                component_names.add(name)
        work_items.append({
            **item,
            "need_component": need_component,
            "need_site": need_site,
        })

    try:
        _fetch_erp_component_site_map(
            component_names,
            component_cache,
            headers=erp_headers,
        )
    except Exception as exc:
        return {
            "checked": len(seen),
            "updated": [],
            "component_set": 0,
            "site_set": 0,
            "skipped": skipped,
            "errors": [f"Failed to load Components from ERP: {exc}"],
        }

    puts = []
    total = len(work_items)
    for index, item in enumerate(work_items, 1):
        issue_id = item["issue_id"]
        unit = item["unit"]
        subject = item["subject"]
        unit_component = item["unit_component"]
        need_component = item["need_component"]
        need_site = item["need_site"]
        print(
            f"Add Missing Components/Sites: {index}/{total} {issue_id} "
            f"needs "
            + " and ".join(
                part for part, needed in (
                    ("component", need_component),
                    ("site", need_site),
                ) if needed
            )
        )
        payload = {}
        if need_component:
            component_doc = component_cache.get(unit_component)
            if not component_doc:
                errors.append(
                    f"{issue_id}: Component {unit_component} was not found in ERP"
                )
            else:
                payload["component"] = unit_component
        if need_site:
            parent_mu = _parent_mu_from_subject(subject)
            site_source = parent_mu or unit
            site, found_name = _site_from_prefetched_component(
                site_source,
                component_cache,
                try_bare=bool(parent_mu),
            )
            site_doc = component_cache.get(found_name)
            if not site_doc:
                errors.append(
                    f"{issue_id}: Component {found_name or site_source} was not found in ERP"
                )
            elif not site:
                errors.append(
                    f"{issue_id}: Component {found_name} has no Site"
                )
            else:
                payload["site"] = site
        if payload:
            puts.append({
                "issue_id": issue_id,
                "unit": unit,
                "payload": payload,
            })

    if puts:
        print(
            f"Add Missing Components/Sites: updating {len(puts)} tickets "
            f"({ADD_MISSING_PUT_WORKERS} workers)"
        )
        with ThreadPoolExecutor(max_workers=ADD_MISSING_PUT_WORKERS) as pool:
            futures = {
                pool.submit(
                    _put_issue_component_site,
                    put["issue_id"],
                    put["payload"],
                    erp_headers,
                ): put
                for put in puts
            }
            for future in as_completed(futures):
                put = futures[future]
                try:
                    issue_id, payload, error = future.result()
                except Exception as exc:
                    errors.append(f"{put['issue_id']}: {exc}")
                    continue
                if error:
                    errors.append(f"{issue_id}: {error}")
                    continue
                updated.append({
                    "issue_id": issue_id,
                    "unit": put["unit"],
                    **payload,
                })

    return {
        "checked": len(seen),
        "updated": updated,
        "component_set": sum(1 for item in updated if item.get("component")),
        "site_set": sum(1 for item in updated if item.get("site")),
        "skipped": skipped,
        "errors": errors,
    }

def validate_issue_records(issue_records):
    """Validate normalized ERP issue records through the established pipeline."""
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8-sig",
            suffix=".csv",
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name
            writer = csv.writer(temp_file)
            writer.writerow(["ID", "Subject", "Issue Type", "Issue Subtype", "Status"])
            for issue in issue_records:
                writer.writerow([
                    issue.get("issue_id", ""),
                    issue.get("subject", ""),
                    issue.get("issue_type", ""),
                    issue.get("issue_subtype", ""),
                    issue.get("status", ""),
                ])
        return validate_issues_report(temp_path)
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass

def validate_issues_report(issue_path=None):
    if issue_path is None:
        issue_path = os.path.join(os.path.expanduser("~"), "Downloads", "Issue.csv")
    issue_items = []
    unit_issue_map = {}
    unit_meta_map = {}
    false_positives = []
    nuc_down = []
    stale_vpn = []
    truly_down = []
    scrypted_outage = []
    speaker_outage = []
    camera_outage = []
    panel_issues = []
    camera_view = []
    on_hold = []
    monitoring_hours_tickets = []
    termination_tickets = []
    relocation_tickets = []
    discarded_tickets = []
    has_type_subtype = False
    id_col = 0
    subject_col = 1
    type_col = None
    subtype_col = None
    status_col = None

    try:
        with open(issue_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
            linereader = csv.reader(csvfile)
            for row_number, line in enumerate(linereader, 1):
                if not line or len(line) < 2:
                    continue
                header_cells = [(c or "").strip() for c in line]
                header_lower = [c.lower() for c in header_cells]
                if "subject" in header_lower:
                    subject_col = header_lower.index("subject")
                    if "id" in header_lower:
                        id_col = header_lower.index("id")
                    if "status" in header_lower:
                        status_col = header_lower.index("status")
                    if "issue type" in header_lower and "issue subtype" in header_lower:
                        type_col = header_lower.index("issue type")
                        subtype_col = header_lower.index("issue subtype")
                        has_type_subtype = True
                        print(
                            f"Detected Issue Type (col {type_col}) and "
                            f"Issue Subtype (col {subtype_col}) headers"
                        )
                    else:
                        print("Issue Type / Issue Subtype headers not found — skipping subtype annotations")
                    continue

                subject_cell = (line[subject_col] if len(line) > subject_col else "") or ""
                subject_cell = subject_cell.strip()
                if not subject_cell:
                    continue
                issue_id = ((line[id_col] if len(line) > id_col else "") or "").strip()
                erp_status = ""
                if status_col is not None and len(line) > status_col:
                    erp_status = (line[status_col] or "").strip()
                subject_lower = subject_cell.lower()
                issue_type = ""
                issue_subtype = ""
                outage_type = ""
                undiagnosed = False
                if has_type_subtype:
                    issue_type = ((line[type_col] if len(line) > type_col else "") or "").strip()
                    issue_subtype = ((line[subtype_col] if len(line) > subtype_col else "") or "").strip()
                    outage_type = _parse_outage_kind(issue_type)
                    undiagnosed = not issue_subtype
                if "suspend" in subject_lower or "suspend" in issue_subtype.lower():
                    print(f"Discarding Suspend ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Suspend ticket",
                    })
                    continue
                if "raindance" in subject_lower:
                    print(f"Discarding RainDance ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "RainDance ticket",
                    })
                    continue
                if issue_type.lower() == "unit relocation" or "relocation" in subject_lower:
                    print(f"Discarding Unit Relocation ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Unit Relocation",
                    })
                    continue
                if "footage" in subject_lower or issue_type.lower() == "footage request":
                    print(f"Discarding Footage Request ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Footage Request",
                    })
                    continue
                if "unit swap" in issue_subtype.lower():
                    print(f"Discarding Unit Swap ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Unit Swap subtype",
                    })
                    continue
                if "head swap" in subject_lower or "trailer swap" in subject_lower:
                    reason = "Head Swap ticket" if "head swap" in subject_lower else "Trailer Swap ticket"
                    print(f"Discarding {reason}: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": reason,
                    })
                    continue
                if (
                    "missing" in subject_lower
                    and issue_type.lower() == "maintenance"
                    and not _is_camera_view_ticket(
                        issue_type, issue_subtype, subject_cell
                    )
                ):
                    print(f"Discarding Missing hardware ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Missing hardware",
                    })
                    continue
                if "site note" in subject_lower:
                    print(f"Discarding Site Note ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Site Note ticket",
                    })
                    continue
                if "top talker" in subject_lower:
                    print(f"Discarding Top Talker ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Top Talker ticket",
                    })
                    continue
                if "statement of services" in subject_lower:
                    print(f"Discarding Statement of Services ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Statement of Services ticket",
                    })
                    continue
                if "additional features" in issue_subtype.lower():
                    print(f"Discarding Additional Features ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Additional Features subtype",
                    })
                    continue
                if "deployment" in issue_type.lower():
                    print(f"Discarding Deployment ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Deployment issue type",
                    })
                    continue
                if "time lapse" in subject_lower:
                    print(f"Discarding Time Lapse ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Time Lapse ticket",
                    })
                    continue
                if "thermal plates" in subject_lower:
                    print(f"Discarding Thermal plates ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Thermal plates ticket",
                    })
                    continue
                if "monitoring hours" in subject_lower:
                    print(f"Monitoring Hours ticket (no validation): {subject_cell}")
                    if not net_array:
                        generate_net_array()
                    unit = _match_unit_from_subject(subject_cell)
                    switch_url = fisheye_ip = pve_ip = platform_url = ""
                    has_pve = has_relay = has_platform = has_scrypted = False
                    scrypted_url = ""
                    compute_label = "NUC"
                    if unit:
                        (
                            switch_url,
                            fisheye_ip,
                            pve_ip,
                            has_pve,
                            has_relay,
                            has_platform,
                            platform_url,
                            has_scrypted,
                            scrypted_url,
                        ) = _unit_device_info(unit)
                        compute_label = compute_host_label(unit)
                    vrm_mu, vrm_url = _vrm_info_from_subject(subject_cell, unit)
                    monitoring_hours_tickets.append({
                        "unit": unit,
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "issue_type": issue_type,
                        "outage_type": outage_type,
                        "issue_subtype": issue_subtype,
                        "subject": subject_cell,
                        "undiagnosed": undiagnosed,
                        "switch_url": switch_url,
                        "fisheye_ip": fisheye_ip,
                        "pve_ip": pve_ip,
                        "has_pve": has_pve,
                        "has_relay": has_relay,
                        "has_platform": has_platform,
                        "platform_url": platform_url,
                        "has_scrypted": has_scrypted,
                        "scrypted_url": scrypted_url,
                        "compute_label": compute_label,
                        "is_speaker": False,
                        "speaker_up": None,
                        "is_camera": False,
                        "camera_target": "",
                        "camera_label": "",
                        "camera_up": None,
                        "is_panel_issue": False,
                        "panel_fisheye_up": None,
                        "is_camera_view": False,
                        "camera_view_status": None,
                        "vrm_mu": vrm_mu,
                        "vrm_url": vrm_url,
                        "erp_status": erp_status,
                        "hold_kind": "",
                        "led_status": None,
                    })
                    continue
                if "relocation" in subject_lower:
                    print(f"Relocation ticket (no validation): {subject_cell}")
                    if not net_array:
                        generate_net_array()
                    unit = _match_unit_from_subject(subject_cell)
                    switch_url = fisheye_ip = pve_ip = platform_url = ""
                    has_pve = has_relay = has_platform = has_scrypted = False
                    scrypted_url = ""
                    compute_label = "NUC"
                    if unit:
                        (
                            switch_url,
                            fisheye_ip,
                            pve_ip,
                            has_pve,
                            has_relay,
                            has_platform,
                            platform_url,
                            has_scrypted,
                            scrypted_url,
                        ) = _unit_device_info(unit)
                        compute_label = compute_host_label(unit)
                    vrm_mu, vrm_url = _vrm_info_from_subject(subject_cell, unit)
                    relocation_tickets.append({
                        "unit": unit,
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "issue_type": issue_type,
                        "outage_type": outage_type,
                        "issue_subtype": issue_subtype,
                        "subject": subject_cell,
                        "undiagnosed": undiagnosed,
                        "switch_url": switch_url,
                        "fisheye_ip": fisheye_ip,
                        "pve_ip": pve_ip,
                        "has_pve": has_pve,
                        "has_relay": has_relay,
                        "has_platform": has_platform,
                        "platform_url": platform_url,
                        "has_scrypted": has_scrypted,
                        "scrypted_url": scrypted_url,
                        "compute_label": compute_label,
                        "is_speaker": False,
                        "speaker_up": None,
                        "is_camera": False,
                        "camera_target": "",
                        "camera_label": "",
                        "camera_up": None,
                        "is_panel_issue": False,
                        "panel_fisheye_up": None,
                        "is_camera_view": False,
                        "camera_view_status": None,
                        "vrm_mu": vrm_mu,
                        "vrm_url": vrm_url,
                        "erp_status": erp_status,
                        "hold_kind": "",
                        "led_status": None,
                    })
                    continue
                if "termination" in subject_lower:
                    print(f"Termination ticket (no validation): {subject_cell}")
                    if not net_array:
                        generate_net_array()
                    unit = _match_unit_from_subject(subject_cell)
                    switch_url = fisheye_ip = pve_ip = platform_url = ""
                    has_pve = has_relay = has_platform = has_scrypted = False
                    scrypted_url = ""
                    compute_label = "NUC"
                    if unit:
                        (
                            switch_url,
                            fisheye_ip,
                            pve_ip,
                            has_pve,
                            has_relay,
                            has_platform,
                            platform_url,
                            has_scrypted,
                            scrypted_url,
                        ) = _unit_device_info(unit)
                        compute_label = compute_host_label(unit)
                    vrm_mu, vrm_url = _vrm_info_from_subject(subject_cell, unit)
                    termination_tickets.append({
                        "unit": unit,
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "issue_type": issue_type,
                        "outage_type": outage_type,
                        "issue_subtype": issue_subtype,
                        "subject": subject_cell,
                        "undiagnosed": undiagnosed,
                        "switch_url": switch_url,
                        "fisheye_ip": fisheye_ip,
                        "pve_ip": pve_ip,
                        "has_pve": has_pve,
                        "has_relay": has_relay,
                        "has_platform": has_platform,
                        "platform_url": platform_url,
                        "has_scrypted": has_scrypted,
                        "scrypted_url": scrypted_url,
                        "compute_label": compute_label,
                        "is_speaker": False,
                        "speaker_up": None,
                        "is_camera": False,
                        "camera_target": "",
                        "camera_label": "",
                        "camera_up": None,
                        "is_panel_issue": False,
                        "panel_fisheye_up": None,
                        "is_camera_view": False,
                        "camera_view_status": None,
                        "vrm_mu": vrm_mu,
                        "vrm_url": vrm_url,
                        "erp_status": erp_status,
                        "hold_kind": "",
                        "led_status": None,
                    })
                    continue
                if re.search(r"\brd(?:\s+head)?\s+loose\b", subject_cell, re.IGNORECASE):
                    print(f"Discarding RD/RD head loose ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "RD or RD head loose ticket",
                    })
                    continue
                if "add thermal bracket" in subject_lower:
                    print(f"Discarding Add Thermal Bracket ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Add Thermal Bracket ticket",
                    })
                    continue
                if issue_subtype.lower() == "maintenance" and "panel" not in subject_lower:
                    print(f"Discarding non-panel Maintenance ticket: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "Maintenance subtype without Panel in subject",
                    })
                    continue
                if not re.search(r"\b(?:RD|FD|MU)\s*\d+", subject_cell, re.IGNORECASE):
                    print(f"Discarding ticket without RD, FD, or MU in subject: {subject_cell}")
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "No RD, FD, or MU unit in subject",
                    })
                    continue
                is_speaker = "speaker" in subject_lower
                is_scrypted_outage = issue_subtype.lower() == "scrypted down"
                is_nuc_down = _is_forced_nuc_down(issue_subtype, subject_cell)
                is_panel_issue = "panel" in subject_lower
                is_camera_view = _is_camera_view_ticket(
                    issue_type, issue_subtype, subject_cell
                )
                camera_targets = _camera_targets_from_subject(subject_cell)
                has_head_unit = bool(
                    re.search(r"\b(?:RD|FD)\s*\d+", subject_cell, re.IGNORECASE)
                )
                speaker_assume_down = bool(
                    is_speaker
                    and re.search(r"\bFD\s*\d+", subject_cell, re.IGNORECASE)
                )
                candidate_rows = sorted(
                    net_array,
                    key=lambda row: (
                        0
                        if has_head_unit
                        and row
                        and str(row[0]).upper().startswith(("RD", "FD"))
                        else 1
                    ),
                )
                ticket_matched = False

                def _register_ticket_unit(unit):
                    nonlocal ticket_matched
                    result_key = f"{issue_id or row_number}::{unit}"
                    if (
                        not _subject_mentions_unit(subject_cell, unit)
                        or result_key in unit_meta_map
                        or (unit in false_mu_array and has_head_unit)
                    ):
                        return
                    ticket_matched = True
                    issue_items.append((result_key, unit))
                    unit_issue_map[result_key] = issue_id
                    vrm_mu, vrm_url = _vrm_info_from_subject(subject_cell, unit)
                    unit_meta_map[result_key] = {
                        "unit": unit,
                        "subject": subject_cell,
                        "issue_type": issue_type,
                        "outage_type": outage_type,
                        "issue_subtype": issue_subtype,
                        "undiagnosed": undiagnosed,
                        "erp_status": erp_status,
                        "is_speaker": is_speaker,
                        "speaker_up": None,
                        "speaker_assume_down": speaker_assume_down,
                        "is_scrypted_outage": is_scrypted_outage,
                        "is_nuc_down": is_nuc_down,
                        "camera_targets": camera_targets,
                        "is_panel_issue": is_panel_issue,
                        "panel_fisheye_up": None,
                        "is_camera_view": is_camera_view,
                        "camera_view_status": None,
                        "vrm_mu": vrm_mu,
                        "vrm_url": vrm_url,
                    }
                    extra = ""
                    if has_type_subtype:
                        if undiagnosed:
                            extra = f" [{outage_type or 'Unknown'} | UNDIAGNOSED — priority]"
                        else:
                            extra = f" [{outage_type or 'Unknown'} | {issue_subtype}]"
                    print(f'Matched {unit} ({issue_id}) in {subject_cell}{extra}')

                for net_row in candidate_rows:
                    unit = net_row[0]
                    if ticket_matched:
                        break
                    _register_ticket_unit(unit)
                    if ticket_matched:
                        break
                if not ticket_matched:
                    fallback_unit = _normalize_netsheet_unit(
                        _head_unit_from_subject(subject_cell)
                    )
                    if fallback_unit:
                        _register_ticket_unit(fallback_unit)
                if not ticket_matched:
                    print(
                        f"No net-sheet or subject match for ticket: {subject_cell}"
                    )
                    discarded_tickets.append({
                        "issue_id": issue_id,
                        "url": _issue_ticket_url(issue_id),
                        "subject": subject_cell,
                        "reason": "No matching unit in net sheet",
                    })
    except Exception as e:
        print(f'Task failed: {e}')
        return [], [], [], [], [], [], [], [], [], [], [], [], [], []

    print(
        f"Discarded {len(discarded_tickets)} tickets without a unit; "
        f"Monitoring Hours list: {len(monitoring_hours_tickets)}; "
        f"Termination list: {len(termination_tickets)}; "
        f"Relocation list: {len(relocation_tickets)}; "
        f"validating {len(issue_items)} units..."
    )
    total_units = len(issue_items)
    print(f"__PROGRESS__ 0 {total_units} starting")
    for index, (result_key, unit) in enumerate(issue_items, 1):
        print(f"__PROGRESS__ {index} {total_units} {unit}")
        if unit_meta_map.get(result_key, {}).get("is_camera_view"):
            print(f"Validating Camera View unit: {unit}")
            camera_view_result, camera_view_error = validate_camera_view_status(unit)
            if camera_view_error:
                print(camera_view_error)
                unit_meta_map[result_key]["camera_view_status"] = "red"
            else:
                print(camera_view_result["router_output"])
                print(camera_view_result["compute_output"])
                unit_meta_map[result_key]["camera_view_status"] = camera_view_result["status"]
                print(
                    f"Camera View validation: {unit} — "
                    f"{camera_view_result['status']}"
                )
            camera_view.append(result_key)
            continue
        if unit_meta_map.get(result_key, {}).get("is_panel_issue"):
            print(f"Checking {unit}'s Fisheye for Panel issues ticket...")
            code, panel_output = _safe_ping_result(ping_camera(unit, "fisheye"))
            print(panel_output)
            panel_fisheye_up = _ping_reachable(panel_output)
            unit_meta_map[result_key]["panel_fisheye_up"] = panel_fisheye_up
            state = "up" if panel_fisheye_up else "down"
            print(f"Fisheye is {state} for Panel issues ticket: {unit}")
            panel_issues.append(result_key)
            continue
        if unit_meta_map.get(result_key, {}).get("is_scrypted_outage"):
            print(
                f"Issue Subtype Scrypted Down — routing to Scrypted outage: {unit}"
            )
            code, scrypt_output = _safe_ping_result(ping_scrypted(unit))
            if scrypt_output:
                print(scrypt_output)
            scrypted_up = _ping_reachable(scrypt_output)
            if not scrypted_up and nuc_scrypted_same_ip(unit):
                print(
                    f"Shared NUC/Scrypted IP unreachable — "
                    f"routing to Offline compute: {unit}"
                )
                unit_meta_map[result_key]["led_status"] = "yellow"
                unit_meta_map[result_key]["compute_label"] = compute_host_label(unit)
                nuc_down.append(result_key)
                continue
            unit_meta_map[result_key]["led_status"] = (
                "green" if scrypted_up else "yellow"
            )
            state = "up" if scrypted_up else "down"
            print(f"Scrypted is {state}: {unit}")
            scrypted_outage.append(result_key)
            continue
        if unit_meta_map.get(result_key, {}).get("is_nuc_down"):
            label = compute_host_label(unit)
            print(
                f"Nuc Down ticket — routing to Offline compute "
                f"(ping {label} only): {unit}"
            )
            code, compute_output = _safe_ping_result(ping_compute(unit))
            if compute_output:
                print(compute_output)
            compute_up = _ping_reachable(compute_output)
            unit_meta_map[result_key]["led_status"] = (
                "green" if compute_up else "yellow"
            )
            unit_meta_map[result_key]["compute_label"] = label
            state = "up" if compute_up else "down"
            print(f"{label} is {state}: {unit}")
            nuc_down.append(result_key)
            continue
        if unit_meta_map.get(result_key, {}).get("is_speaker"):
            if unit_meta_map[result_key].get("speaker_assume_down"):
                print(
                    f"Skipping speaker validation for FD ticket; "
                    f"marking speaker down: {unit}"
                )
                unit_meta_map[result_key]["speaker_up"] = False
                speaker_outage.append(result_key)
                continue
            print(f"Checking {unit}'s speaker...")
            code, speaker_output = _safe_ping_result(ping_speaker(unit))
            print(speaker_output)
            speaker_up = _ping_reachable(speaker_output)
            unit_meta_map[result_key]["speaker_up"] = speaker_up
            state = "up" if speaker_up else "down"
            print(f"Speaker is {state}: {unit}")
            speaker_outage.append(result_key)
            continue
        camera_targets = unit_meta_map.get(result_key, {}).get("camera_targets") or []
        if camera_targets:
            for target in camera_targets:
                camera_key = f"{result_key}::{target}"
                camera_meta = dict(unit_meta_map[result_key])
                camera_meta.update({
                    "is_camera": True,
                    "camera_target": target,
                    "camera_label": CAMERA_ENDPOINTS[target][1],
                    "camera_up": None,
                })
                unit_meta_map[camera_key] = camera_meta
                unit_issue_map[camera_key] = unit_issue_map.get(result_key, "")
                print(f"Checking {unit}'s {camera_meta['camera_label']}...")
                code, camera_output = _safe_ping_result(ping_camera(unit, target))
                print(camera_output)
                camera_up = _ping_reachable(camera_output)
                unit_meta_map[camera_key]["camera_up"] = camera_up
                state = "up" if camera_up else "down"
                print(f"{camera_meta['camera_label']} is {state}: {unit}")
                camera_outage.append(camera_key)
            continue
        _validate_unit_connectivity(
            unit,
            false_positives,
            nuc_down,
            stale_vpn,
            truly_down,
            scrypted_outage,
            result_value=result_key,
        )
    print(f"__PROGRESS__ {total_units} {total_units} complete")

    hold_led_by_kind = {
        "false_positives": "green",
        "nuc_down": "yellow",
        "scrypted_outage": "yellow",
        "stale_vpn": "red",
        "truly_down": "red",
    }

    def _move_on_hold(category_name, items):
        remaining = []
        for result_key in items:
            meta = unit_meta_map.get(result_key) or {}
            if str(meta.get("erp_status") or "").strip().lower() != "on hold":
                remaining.append(result_key)
                continue
            meta["hold_kind"] = category_name
            if category_name in hold_led_by_kind and not meta.get("led_status"):
                meta["led_status"] = hold_led_by_kind[category_name]
            if category_name == "camera_view" and not meta.get("led_status"):
                meta["led_status"] = meta.get("camera_view_status") or "red"
            unit_meta_map[result_key] = meta
            on_hold.append(result_key)
            print(
                f"On Hold: {meta.get('unit') or result_key} "
                f"({unit_issue_map.get(result_key, '')}) — validated as {category_name}"
            )
        return remaining

    false_positives = _move_on_hold("false_positives", false_positives)
    nuc_down = _move_on_hold("nuc_down", nuc_down)
    stale_vpn = _move_on_hold("stale_vpn", stale_vpn)
    truly_down = _move_on_hold("truly_down", truly_down)
    scrypted_outage = _move_on_hold("scrypted_outage", scrypted_outage)
    speaker_outage = _move_on_hold("speaker_outage", speaker_outage)
    camera_outage = _move_on_hold("camera_outage", camera_outage)
    panel_issues = _move_on_hold("panel_issues", panel_issues)
    camera_view = _move_on_hold("camera_view", camera_view)

    false_positives = _force_up_steady_green(
        _with_ticket_links(false_positives, unit_issue_map, unit_meta_map)
    )
    nuc_down = _with_ticket_links(nuc_down, unit_issue_map, unit_meta_map)
    stale_vpn = _with_ticket_links(stale_vpn, unit_issue_map, unit_meta_map)
    truly_down = _with_ticket_links(truly_down, unit_issue_map, unit_meta_map)
    scrypted_outage = _with_ticket_links(scrypted_outage, unit_issue_map, unit_meta_map)
    speaker_outage = _with_ticket_links(speaker_outage, unit_issue_map, unit_meta_map)
    camera_outage = _with_ticket_links(camera_outage, unit_issue_map, unit_meta_map)
    panel_issues = _with_ticket_links(panel_issues, unit_issue_map, unit_meta_map)
    camera_view = _with_ticket_links(camera_view, unit_issue_map, unit_meta_map)
    on_hold = _with_ticket_links(on_hold, unit_issue_map, unit_meta_map)

    _print_linked_units("Up Steady:", false_positives)
    _print_linked_units("Offline compute (router up):", nuc_down)
    _print_linked_units("Potentially stale VPN (3000-3199 only):", stale_vpn)
    _print_linked_units("Down Full:", truly_down)
    _print_linked_units("Scrypted outage (router+PVE up, Scrypted down):", scrypted_outage)
    _print_linked_units("Speaker outage:", speaker_outage)
    _print_linked_units("Camera outage:", camera_outage)
    _print_linked_units("Panel issues:", panel_issues)
    _print_linked_units("Camera View:", camera_view)
    _print_linked_units("On Hold:", on_hold)
    monitoring_hours_tickets.sort(
        key=lambda item: (0 if item.get("undiagnosed") else 1, item.get("unit") or "", item.get("issue_id") or "")
    )
    termination_tickets.sort(
        key=lambda item: (0 if item.get("undiagnosed") else 1, item.get("unit") or "", item.get("issue_id") or "")
    )
    relocation_tickets.sort(
        key=lambda item: (0 if item.get("undiagnosed") else 1, item.get("unit") or "", item.get("issue_id") or "")
    )
    _print_linked_units("Monitoring Hours:", monitoring_hours_tickets)
    _print_linked_units("Termination:", termination_tickets)
    _print_linked_units("Relocation:", relocation_tickets)
    print(f"Miscellaneous tickets: {len(discarded_tickets)}")
    for item in discarded_tickets:
        print(
            f"{item['issue_id']} - {item['subject']}"
            if item.get("issue_id")
            else item["subject"]
        )
    return (
        false_positives,
        nuc_down,
        stale_vpn,
        truly_down,
        scrypted_outage,
        speaker_outage,
        camera_outage,
        panel_issues,
        camera_view,
        on_hold,
        monitoring_hours_tickets,
        termination_tickets,
        relocation_tickets,
        discarded_tickets,
    )

def ping_speaker_status(unit):
    """Ping a unit's speaker and return its current status plus raw output."""
    if not net_array:
        generate_net_array()
    if not ensure_unit_net_info(unit, needed_indexes=(4,)):
        return None, "", f"Unit {unit} not found in net sheet"
    code, output = _safe_ping_result(ping_speaker(unit))
    if code is None and not output:
        return None, "", f"No speaker endpoint configured for {unit}"
    return _ping_reachable(output), output, None

def _start_bounce_tool(unit, executable_name, row_index, endpoint_label):
    """Launch a trusted network utility with one endpoint IP argument."""
    if not net_array:
        generate_net_array()
    row = ensure_unit_net_info(unit, needed_indexes=(row_index,))
    if not row:
        return None, f"Unit {unit} not found in net sheet"
    endpoint_ip = _host_only(row[row_index] if len(row) > row_index else "")
    if not endpoint_ip:
        return None, f"No {endpoint_label} IP configured for {unit}"

    executable_path = os.path.join(SENTRA_NETWORK_TOOL_DIR, executable_name)
    if not os.path.isfile(executable_path):
        return None, f"Network utility not found: {executable_path}"
    try:
        process = subprocess.Popen(
            [executable_path, endpoint_ip],
            cwd=SENTRA_NETWORK_TOOL_DIR,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        return None, f"Unable to start {executable_name}: {exc}"
    return {
        "unit": unit,
        "ip": endpoint_ip,
        "pid": process.pid,
        "process": process,
    }, None

def bounce_switch(unit):
    """Start bounceswitch.exe with the unit relay IP from net-sheet row[10]."""
    return _start_bounce_tool(unit, "bounceswitch.exe", 10, "relay")

def bounce_speaker(unit):
    """Start speaker_reboot.exe with the speaker IP from net-sheet row[4]."""
    return _start_bounce_tool(unit, "speaker_reboot.exe", 4, "speaker")

def ping_camera_status(unit, target):
    """Ping one camera endpoint and return its current status plus raw output."""
    if not net_array:
        generate_net_array()
    endpoint = CAMERA_ENDPOINTS.get(target)
    if not endpoint:
        return None, "", f"Unknown camera target: {target}"
    if not ensure_unit_net_info(unit, needed_indexes=(endpoint[0],)):
        return None, "", f"Unit {unit} not found in net sheet"
    code, output = _safe_ping_result(ping_camera(unit, target))
    if code is None and not output:
        return None, "", f"No {endpoint[1]} endpoint configured for {unit}"
    return _ping_reachable(output), output, None

def ping_compute_status(unit):
    """Ping the unit's NUC/PVE endpoint and return its current status."""
    if not net_array:
        generate_net_array()
    needed = (11,) if uses_pve(unit) else (3,)
    if not ensure_unit_net_info(unit, needed_indexes=needed):
        return None, "", "", f"Unit {unit} not found in net sheet"
    label = compute_host_label(unit)
    code, output = _safe_ping_result(ping_compute(unit))
    if code is None and not output:
        return None, label, "", f"No {label} endpoint configured for {unit}"
    return _ping_reachable(output), label, output, None

def ping_scrypted_status(unit):
    """Ping the unit's Scrypted endpoint and return its current status."""
    if not net_array:
        generate_net_array()
    if not ensure_unit_net_info(unit, needed_indexes=(12,)):
        return None, "", f"Unit {unit} not found in net sheet"
    code, output = _safe_ping_result(ping_scrypted(unit))
    if code is None and not output:
        return None, "", f"No Scrypted endpoint configured for {unit}"
    return _ping_reachable(output), output, None

def ping_pve_status(unit):
    """Ping the unit's PVE endpoint and return its current status."""
    if not net_array:
        generate_net_array()
    if not ensure_unit_net_info(unit, needed_indexes=(11,)):
        return None, "", f"Unit {unit} not found in net sheet"
    code, output = _safe_ping_result(ping_pve(unit))
    if code is None and not output:
        return None, "", f"No PVE endpoint configured for {unit}"
    return _ping_reachable(output), output, None

def validate_unit_status(unit):
    """Run standard validation and return its list key plus console output."""
    if not net_array:
        generate_net_array()
    if not ensure_unit_net_info(unit):
        return None, "", f"Unit {unit} not found in net sheet"

    output_lines = []
    false_positives = []
    nuc_down = []
    stale_vpn = []
    truly_down = []
    scrypted_outage = []
    _validate_unit_connectivity(
        unit,
        false_positives,
        nuc_down,
        stale_vpn,
        truly_down,
        scrypted_outage,
        log=output_lines.append,
    )
    output = "\n".join(str(line) for line in output_lines if line is not None)
    categories = (
        ("false_positives", false_positives),
        ("nuc_down", nuc_down),
        ("stale_vpn", stale_vpn),
        ("truly_down", truly_down),
        ("scrypted_outage", scrypted_outage),
    )
    for category, items in categories:
        if items:
            return category, output, None
    return None, output, f"Validation produced no result for {unit}"

def validate_unit_full(unit):
    """Full ping of router, compute, speaker, cameras, and Scrypted (if IP exists)."""
    if not net_array:
        generate_net_array()
    if not ensure_unit_net_info(unit):
        return None, f"Unit {unit} not found in net sheet"

    lines = []
    endpoints = []
    compute_label = compute_host_label(unit)

    def _record(name, up, output):
        endpoints.append({"name": name, "up": bool(up), "checked": True})
        if output:
            lines.append(output)
        lines.append(f"{name}: {'up' if up else 'down'}")

    lines.append(f"Full validate {unit} — checking router...")
    _code, router_output = _safe_ping_result(ping_router(unit))
    router_up = _ping_reachable(router_output)
    _record("Router", router_up, router_output)

    lines.append(f"Checking {compute_label}...")
    missing_compute = _missing_netsheet_ip_message(
        unit, (11,) if uses_pve(unit) else (3,)
    )
    _code, compute_output = _safe_ping_result(
        ping_compute(unit),
        missing_message=missing_compute,
    )
    compute_up = _ping_reachable(compute_output)
    _record(compute_label, compute_up, compute_output)

    is_fd = is_fd_unit(unit)
    compute_unreachable = not compute_up
    fd_continue_past_compute = is_fd and router_up and compute_unreachable
    if fd_continue_past_compute:
        lines.append(
            f"FD unit — {compute_label} unreachable or missing; "
            "continuing with speaker/camera/Scrypted checks..."
        )

    # Core path: both down = full down. Either down = offline compute.
    if not router_up and not compute_up:
        return {
            "unit": unit,
            "led_status": "red",
            "category": "truly_down",
            "move_to": "truly_down",
            "multi_down": False,
            "sort_priority": 0,
            "compute_label": compute_label,
            "down_kinds": ["compute", "router"],
            "endpoints": endpoints,
            "output": "\n".join(lines),
        }, None

    if (not router_up or not compute_up) and not fd_continue_past_compute:
        return {
            "unit": unit,
            "led_status": "yellow",
            "category": "nuc_down",
            "move_to": "nuc_down",
            "multi_down": False,
            "sort_priority": 0,
            "compute_label": compute_label,
            "down_kinds": ["compute"],
            "endpoints": endpoints,
            "output": "\n".join(lines),
        }, None

    # Both core up — check peripherals that exist in the net sheet.
    row = _net_row_for_unit(unit)
    speaker_down = False
    camera_down = False
    scrypted_down = False
    first_camera = None

    speaker_ip = ""
    if row and len(row) > 4:
        speaker_ip = str(row[4] or "").strip()
    if speaker_ip:
        lines.append("Checking Speaker...")
        _code, speaker_output = _safe_ping_result(ping_speaker(unit))
        speaker_up = _ping_reachable(speaker_output)
        _record("Speaker", speaker_up, speaker_output)
        speaker_down = not speaker_up

    for target, (column, label) in CAMERA_ENDPOINTS.items():
        camera_ip = ""
        if row and len(row) > column:
            camera_ip = str(row[column] or "").strip()
        if not camera_ip:
            continue
        lines.append(f"Checking {label}...")
        _code, camera_output = _safe_ping_result(ping_camera(unit, target))
        camera_up = _ping_reachable(camera_output)
        _record(label, camera_up, camera_output)
        if not camera_up:
            camera_down = True
            if first_camera is None:
                first_camera = {
                    "camera_target": target,
                    "camera_label": label,
                    "camera_up": False,
                }

    scrypted_ip = ""
    if row and len(row) > 12:
        scrypted_ip = _host_only(row[12])
    if scrypted_ip:
        lines.append("Checking Scrypted...")
        _code, scrypt_output = _safe_ping_result(ping_scrypted(unit))
        scrypted_up = _ping_reachable(scrypt_output)
        _record("Scrypted", scrypted_up, scrypt_output)
        scrypted_down = not scrypted_up

    down_kinds = []
    if scrypted_down:
        if nuc_scrypted_same_ip(unit) and not fd_continue_past_compute:
            # Shared NUC/Scrypted host is compute, not a separate Scrypted outage.
            lines.append(
                "Shared NUC/Scrypted IP unreachable — treating as offline compute"
            )
            return {
                "unit": unit,
                "led_status": "yellow",
                "category": "nuc_down",
                "move_to": "nuc_down",
                "multi_down": False,
                "sort_priority": 0,
                "compute_label": compute_label,
                "down_kinds": ["compute"],
                "endpoints": endpoints,
                "output": "\n".join(lines),
                "speaker_up": (False if speaker_down else True) if speaker_ip else None,
                "is_speaker": False,
            }, None
        down_kinds.append("scrypted")
    if camera_down:
        down_kinds.append("camera")
    if speaker_down:
        down_kinds.append("speaker")

    checked = [ep for ep in endpoints if ep.get("checked")]
    up_count = sum(1 for ep in checked if ep.get("up"))
    down_count = len(checked) - up_count

    if down_count == 0:
        led_status = "green"
        category = "false_positives"
        move_to = ""
        multi_down = False
        sort_priority = 99
    elif up_count == 0:
        led_status = "red"
        category = "truly_down"
        move_to = "truly_down"
        multi_down = False
        sort_priority = 0
    else:
        multi_down = len(down_kinds) > 1
        led_status = "orange" if multi_down else "yellow"
        # Priority: compute (already handled) -> scrypted -> camera -> speaker
        if "scrypted" in down_kinds:
            category = "scrypted_outage"
            move_to = "scrypted_outage"
            sort_priority = 1
        elif "camera" in down_kinds:
            category = "camera_outage"
            move_to = "camera_outage"
            sort_priority = 2
        elif "speaker" in down_kinds:
            category = "speaker_outage"
            move_to = "speaker_outage"
            sort_priority = 3
        else:
            category = "false_positives"
            move_to = ""
            sort_priority = 99

    result = {
        "unit": unit,
        "led_status": led_status,
        "category": category,
        "move_to": move_to,
        "multi_down": multi_down,
        "sort_priority": sort_priority,
        "compute_label": compute_label,
        "down_kinds": down_kinds,
        "endpoints": endpoints,
        "output": "\n".join(lines),
        "speaker_up": (False if speaker_down else True) if speaker_ip else None,
        "is_speaker": bool(speaker_ip and speaker_down and category == "speaker_outage"),
    }
    if first_camera and category == "camera_outage":
        result.update({
            "is_camera": True,
            "camera_target": first_camera["camera_target"],
            "camera_label": first_camera["camera_label"],
            "camera_up": False,
        })
    return result, None

def revalidate_list_entry(list_id, item):
    """Run the list-specific check for one ticket and return its destination list."""
    unit = str((item or {}).get("unit") or "").strip()
    if not unit:
        return None, {}, "", "Missing unit"

    if list_id in ("false_positives", "truly_down"):
        category, output, error = validate_unit_status(unit)
        if error:
            return None, {}, output, error
        fields = {}
        if category == "false_positives":
            fields["led_status"] = "green"
        elif category in ("truly_down", "stale_vpn"):
            fields["led_status"] = "red"
        elif category in ("nuc_down", "scrypted_outage"):
            fields["led_status"] = "yellow"
        return category, fields, output, None

    if list_id == "nuc_down":
        compute_up, label, output, error = ping_compute_status(unit)
        if error:
            return None, {}, output, error
        fields = {
            "led_status": "green" if compute_up else "yellow",
            "compute_label": label,
        }
        # Forced Nuc Down tickets stay in Offline compute regardless of ping.
        if item.get("is_nuc_down"):
            return "nuc_down", fields, output, None
        if not compute_up:
            return "nuc_down", fields, output, None
        category, more_output, error = validate_unit_status(unit)
        combined = "\n".join(part for part in (output, more_output) if part)
        if error:
            return "nuc_down", fields, combined, None
        if category == "false_positives":
            fields["led_status"] = "green"
        return category, fields, combined, None

    if list_id == "scrypted_outage":
        scrypted_up, output, error = ping_scrypted_status(unit)
        if error:
            return None, {}, output, error
        if not scrypted_up and nuc_scrypted_same_ip(unit):
            fields = {
                "led_status": "yellow",
                "compute_label": compute_host_label(unit),
            }
            return "nuc_down", fields, output, None
        fields = {"led_status": "green" if scrypted_up else "yellow"}
        category = "false_positives" if scrypted_up else "scrypted_outage"
        if category == "false_positives":
            fields["led_status"] = "green"
        return category, fields, output, None

    if list_id == "stale_vpn":
        result, error = validate_stale_vpn_status(unit)
        if error:
            return None, {}, "", error
        fields = {
            "led_status": result.get("status"),
            "compute_label": result.get("compute_label"),
        }
        output = "\n".join(
            part for part in (result.get("router_output"), result.get("compute_output"))
            if part
        )
        if result.get("status") == "green":
            category = "false_positives"
            fields["led_status"] = "green"
        elif result.get("router_up") and not result.get("compute_up"):
            category = "nuc_down"
        else:
            category = "stale_vpn"
        return category, fields, output, None

    if list_id == "speaker_outage":
        speaker_up, output, error = ping_speaker_status(unit)
        if error:
            return None, {}, output, error
        return "speaker_outage", {"speaker_up": speaker_up}, output, None

    if list_id == "camera_outage":
        target = str((item or {}).get("camera_target") or "").strip()
        camera_up, output, error = ping_camera_status(unit, target)
        if error:
            return None, {}, output, error
        return "camera_outage", {"camera_up": camera_up}, output, None

    if list_id == "panel_issues":
        fisheye_up, output, error = ping_camera_status(unit, "fisheye")
        if error:
            return None, {}, output, error
        return "panel_issues", {"panel_fisheye_up": fisheye_up}, output, None

    if list_id == "camera_view":
        result, error = validate_camera_view_status(unit)
        if error:
            return None, {}, "", error
        fields = {
            "camera_view_status": result.get("status"),
            "led_status": result.get("status"),
            "compute_label": result.get("compute_label"),
        }
        output = "\n".join(
            part for part in (result.get("router_output"), result.get("compute_output"))
            if part
        )
        return "camera_view", fields, output, None

    if list_id == "on_hold":
        kind = str((item or {}).get("hold_kind") or "").strip()
        if not kind or kind == "on_hold":
            if item.get("is_speaker"):
                kind = "speaker_outage"
            elif item.get("is_scrypted_outage"):
                kind = "scrypted_outage"
            elif item.get("is_nuc_down"):
                kind = "nuc_down"
            elif item.get("is_camera"):
                kind = "camera_outage"
            elif item.get("is_panel_issue"):
                kind = "panel_issues"
            elif item.get("is_camera_view"):
                kind = "camera_view"
            else:
                kind = "truly_down"
        category, fields, output, error = revalidate_list_entry(kind, item)
        if fields is None:
            fields = {}
        fields = dict(fields)
        fields["hold_kind"] = category or kind
        hold_led = {
            "false_positives": "green",
            "nuc_down": "yellow",
            "scrypted_outage": "yellow",
            "stale_vpn": "red",
            "truly_down": "red",
        }
        if fields["hold_kind"] in hold_led:
            fields["led_status"] = hold_led[fields["hold_kind"]]
        elif fields.get("camera_view_status"):
            fields["led_status"] = fields["camera_view_status"]
        return "on_hold", fields, output, error

    return None, {}, "", f"List {list_id} cannot be revalidated"

def validate_stale_vpn_status(unit):
    """Check router and the unit-appropriate compute endpoint for stale VPN status."""
    if not net_array:
        generate_net_array()
    if not ensure_unit_net_info(unit, needed_indexes=(1, 3, 11)):
        return None, f"Unit {unit} not found in net sheet"

    compute_label = compute_host_label(unit)
    router_code, router_output = _safe_ping_result(ping_router(unit))
    compute_code, compute_output = _safe_ping_result(ping_compute(unit))
    if router_code is None and not router_output:
        return None, f"No router endpoint configured for {unit}"
    if compute_code is None and not compute_output:
        return None, f"No {compute_label} endpoint configured for {unit}"

    router_up = _ping_reachable(router_output)
    compute_up = _ping_reachable(compute_output)
    if router_up and compute_up:
        status = "green"
    elif not router_up and compute_up:
        status = "yellow"
    else:
        status = "red"
    return {
        "unit": unit,
        "router_up": router_up,
        "compute_up": compute_up,
        "compute_label": compute_label,
        "status": status,
        "router_output": router_output,
        "compute_output": compute_output,
    }, None

def validate_camera_view_status(unit):
    """Validate router/compute reachability for a Camera View ticket."""
    if not net_array:
        generate_net_array()
    if not ensure_unit_net_info(unit, needed_indexes=(1, 3, 11)):
        return None, f"Unit {unit} not found in net sheet"

    compute_label = compute_host_label(unit)
    router_code, router_output = _safe_ping_result(ping_router(unit))
    compute_code, compute_output = _safe_ping_result(ping_compute(unit))
    if router_code is None and not router_output:
        return None, f"No router endpoint configured for {unit}"
    if compute_code is None and not compute_output:
        return None, f"No {compute_label} endpoint configured for {unit}"

    router_up = _ping_reachable(router_output)
    compute_up = _ping_reachable(compute_output)
    if router_up and compute_up:
        status = "green"
    elif router_up and not compute_up:
        status = "yellow"
    else:
        status = "red"
    return {
        "unit": unit,
        "router_up": router_up,
        "compute_up": compute_up,
        "compute_label": compute_label,
        "status": status,
        "router_output": router_output,
        "compute_output": compute_output,
    }, None

def _read_spreadsheet_rows(report_path):
    rows = []
    if report_path.lower().endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError:
            print("openpyxl is required to read .xlsx files. Install with: pip install openpyxl")
            raise
        wb = openpyxl.load_workbook(report_path, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            rows.append(["" if cell is None else str(cell) for cell in row])
        wb.close()
    else:
        with open(report_path, "r", newline="", encoding="utf-8-sig") as csvfile:
            for line in csv.reader(csvfile):
                rows.append(line)
    return rows

def check_missing_recovery_emails(report_path=None):
    if report_path is None:
        report_path = os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            "Shield NOC Outage Issues with no initial email - ART.xlsx",
        )
    units_to_check = []
    unit_issue_map = {}
    unit_email_state = {}
    back_up = []
    nuc_down = []
    stale_vpn = []
    truly_down = []
    needs_recovery_email = []
    needs_initial_email = []
    potential_false_positive = []
    pending_recovery = []
    email_status_up_to_date = []

    try:
        rows = _read_spreadsheet_rows(report_path)
    except Exception as e:
        print(f'Task failed: {e}')
        return needs_recovery_email, needs_initial_email, potential_false_positive, pending_recovery, email_status_up_to_date

    header_idx = None
    for i, row in enumerate(rows):
        if any(str(cell).strip().lower() == "recovery email" for cell in row):
            header_idx = i
            break
    if header_idx is None:
        print("Could not find 'Recovery Email' column header in report")
        return needs_recovery_email, needs_initial_email, potential_false_positive, pending_recovery, email_status_up_to_date

    def _match_units_from_subject(subject):
        matched = []
        for net_row in net_array:
            unit = net_row[0]
            if unit in subject and unit not in false_mu_array:
                matched.append(unit)
        has_rd = any(unit.upper().startswith("RD") for unit in matched)
        units = []
        for unit in matched:
            # Skip trailer MU when an RD head unit is already in the subject (e.g. RD3556(MU2001))
            if unit.upper().startswith("MU") and has_rd:
                continue
            units.append(unit)
        return units

    for row in rows[header_idx + 1:]:
        if len(row) < 7:
            continue
        issue_id = (row[1] or "").strip()
        subject = (row[3] or "").strip()
        outage_email = (row[5] or "").strip()
        recovery_email = (row[6] or "").strip()
        if not subject or not issue_id:
            continue

        matched_units = _match_units_from_subject(subject)
        if outage_email and recovery_email:
            for unit in matched_units:
                if unit not in email_status_up_to_date:
                    email_status_up_to_date.append(unit)
                    unit_issue_map[unit] = issue_id
                    print(f'Email status up to date for {unit} ({issue_id}): {subject}')
            continue

        # Skip if recovery email already sent without also having outage email handled above
        if recovery_email:
            continue

        for unit in matched_units:
            if unit not in units_to_check:
                units_to_check.append(unit)
                unit_issue_map[unit] = issue_id
                unit_email_state[unit] = {
                    "has_outage_email": bool(outage_email),
                    "has_recovery_email": bool(recovery_email),
                }
                if not outage_email and not recovery_email:
                    print(f'No initial or recovery email for {unit} ({issue_id}): {subject}')
                else:
                    print(f'Outage email sent, no recovery email for {unit} ({issue_id}): {subject}')

    print(f'Checking {len(units_to_check)} units for missing email actions...')
    for unit in units_to_check:
        _validate_unit_connectivity(unit, back_up, nuc_down, stale_vpn, truly_down)

    categorized = set()

    for unit in back_up:
        state = unit_email_state.get(unit, {})
        if state.get("has_outage_email") and not state.get("has_recovery_email"):
            needs_recovery_email.append(unit)
            categorized.add(unit)
        elif not state.get("has_outage_email") and not state.get("has_recovery_email"):
            potential_false_positive.append(unit)
            categorized.add(unit)

    for unit in truly_down:
        state = unit_email_state.get(unit, {})
        if not state.get("has_outage_email") and not state.get("has_recovery_email"):
            needs_initial_email.append(unit)
            categorized.add(unit)

    for unit in units_to_check:
        if unit not in categorized:
            pending_recovery.append(unit)

    needs_recovery_email = _with_ticket_links(needs_recovery_email, unit_issue_map)
    needs_initial_email = _with_ticket_links(needs_initial_email, unit_issue_map)
    potential_false_positive = _with_ticket_links(potential_false_positive, unit_issue_map)
    pending_recovery = _with_ticket_links(pending_recovery, unit_issue_map)
    email_status_up_to_date = _with_ticket_links(email_status_up_to_date, unit_issue_map)

    _print_linked_units(
        "Needs recovery email (outage email sent, unit back up):",
        needs_recovery_email,
    )
    _print_linked_units(
        "Needs initial outage email (no emails sent, unit fully down):",
        needs_initial_email,
    )
    _print_linked_units(
        "Potential false positive (no emails sent, unit back up):",
        potential_false_positive,
    )
    _print_linked_units(
        "Pending recovery (remainder):",
        pending_recovery,
    )
    _print_linked_units(
        "Email status up to date (outage and recovery emails sent):",
        email_status_up_to_date,
    )
    return needs_recovery_email, needs_initial_email, potential_false_positive, pending_recovery, email_status_up_to_date

def validate_reports_mesh():
    nuc_down = []
    stale_vpn = []
    missing2 = []
    scrypted_outage = []

    print('Checking connectivity on missing units...')
    print('Current missing list:', missing)
    for unit in missing:
            for row in net_array:
                if unit == row[0] and unit not in false_mu:
                    _validate_unit_connectivity(
                        unit,
                        false_positive,
                        nuc_down,
                        stale_vpn,
                        missing2,
                        scrypted_outage,
                    )
                    break
                                
    print("New adjusted missing list:")
    for line in missing:
        if (
            line not in false_positive
            and line != "Agent Name"
            and line not in nuc_down
            and line not in stale_vpn
            and line not in scrypted_outage
        ):
            print(line)
    print("Offline NUCs")
    for line in nuc_down:
        print(line)
    print("Potentially stale VPNs (3000-3199)")
    for line in stale_vpn:
        print(line)
    print("Scrypted outages")
    for line in scrypted_outage:
        print(line)
    return missing2, nuc_down, stale_vpn, scrypted_outage

def compare_zabbix():
    zabbix_path = os.path.join(os.path.expanduser('~'), "Downloads", "zbx_problems_export.csv")
    mesh_outage = os.path.join(os.path.expanduser("~"), "Downloads", "filtered_mesh_vpn.csv")
    mesh_array = []
    zabbix_array = []
    missing = []
    try:
        with open(zabbix_path, 'r', newline='') as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                if row[4][:2].lower() == 'rd' or row[4][:2].lower() == 'mu' or row[4][:2].lower() == 'fd':
                    print(f'Appended {row[4]}')
                    zabbix_array.append(row[4])
    
    except Exception as e:
        print(f'Task failed: {e}')    
        return
    try:
        with open(mesh_outage, 'r', newline='') as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                mesh_array.append(row[0])
    except Exception as e:
        print(f'Task failed: {e}')        
        return

    zablen = len(zabbix_array)
    meshlen = len(mesh_array)
    print(f'Zabbix list length: {zablen} \n Mesh list length: {meshlen}')
    for zab in zabbix_array:
        found = False
        for mesh in mesh_array:
            if zab[:6] in mesh:
                found = True
                break
        if not found:
            missing.append(zab)
            missing_zab.append(zab)
    #for line in missing:
        #print(line)
    for line in missing_zab:
        print(line)

    lenmis = len(missing)
    print(f'{lenmis} Units discovered on zabbix that werent found on mesh')
    
def compare_reports(issue_path, mesh_path):
    missing.clear()
    mesh_array = []
    erp_array = []
    
    try:
        with open(mesh_path, 'r', newline='') as csvfile:
            linereader = csv.reader(csvfile)
            for line in linereader:
                if line and len(line) > 0:
                    mesh_array.append(line[0])
    except Exception as e:
        print(f'Task failed: {e}')
        return
    try:
        with open(issue_path, 'r', newline='') as csvfile:
            linereader = csv.reader(csvfile)
            for line in linereader:
                #print(line[1])
                if line and len(line) > 1 and line[1] != 'Subject':
                    erp_array.append(line[1])
    except Exception as e:
        print(f'Task failed: {e}')
        return

    for mesh in mesh_array:
        found = False
        for line in erp_array:
            if mesh in line:
                found = True
                print(f'Found {mesh} in {line}')
                break
        if not found and mesh not in false_mu_array:
            missing.append(mesh)
        
    print('\nMissing units: ')
    for row in missing:
        if row != 'Agent Name':
            print(row)
    #print('Deleting old reports')
    #clear_old_reports()
    #print('reports cleared, validating new report..')
    return missing
    #validate_reports_mesh()

def print_net_array():
    for row in net_array:
        print(row)
    print(netsheet)

def generate_false_mu():
    false_mu_array.clear()
    with open(false_mu, "r", newline='') as csvfile:
        linereader = csv.reader(csvfile)
        for row in linereader:
            false_mu_array.append(row[0])
        print('Loaded false positive MU list')

def generate_net_array():
    net_array.clear()
    with open(netsheet, "r", newline='') as csvfile:
        linereader = csv.reader(csvfile)
        for row in linereader:
            #print("Row read:", row, "Length:", len(row))
            if len(row) >= 1 and len(row[0]) == 6:
                net_array.append(row)
    generate_false_mu()
        



    
def naming_conventions():
    print("Adjusting naming conventions...")
    for row in all_battery_units:
        if row["name"][:3] != "SC-":
            row["name"] = "SC-" + row["name"]

    print('Mapping trailers to head units...')
    rd_battery_map()

def get_rd_battery(unit):
    found = False
    for row in all_battery_units_mapped:
        #print(row)
        if unit[-4:] == row['name'][-4:]:
            print('Matched, fetching battery health')
            unit_battery_health(row['trailer'])
            found = True
            break
    if found != True:
        print('Unit not found.')
        

def low_battery_fisheye_screenshotter():
    
    if len(low_battery_units) < 1:
        too_low = input('List is empty. Load low battery units? (Y/N)' )
        if too_low.lower()[:1] == 'y':
            low_battery_rd_fisheye_tool()
        elif too_low.lower()[:1] == 'n':
            print('Okey dokey')
            return

    print("Fisheye starting")
    timestamp = datetime.now().strftime("%Y-%m-%d")
    save_dir = r"C:\Temp"
    fish_dir = f"{timestamp}_fisheye_screenshots"
    time_path = os.path.join(save_dir, fish_dir)
    os.makedirs(time_path, exist_ok=True)    
    for row in net_array:
        for unit in rd_down:
            if row[0][-4:] == unit["name"][-4:]:
                #rdpath = os.path.join(save_dir, row[0])
                #os.makedirs(rdpath, exist_ok=True)
                print(f'{row[0]} found in netsheet. Fisheye ip address is: {row[5]}')
                combination = {
                    "Unit:": row[0],
                    "Fisheye IP:": row[5]
                }
                fisheyes.append(combination)

                print("Screenshotting...")
                try:
                    #rdpath = os.path.join(save_dir, row[0])
                    #os.makedirs(rdpath, exist_ok=True)
                    url = f"http://{row[5]}/cgi-bin/snapshot.cgi?channel=1"

                    fishuser = os.getenv("fishuser")
                    fishpass = os.getenv("fishpass")

                    response = requests.get(url, auth=HTTPDigestAuth(f"{fishuser}",f"{fishpass}"), timeout=30)
                    response.raise_for_status()

                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    filename = row[0] + "_" + timestamp + ".jpg"
                    filepath = os.path.join(time_path, filename)

                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    print(f"Saved to {filepath}")
                    
                except requests.exceptions.RequestException as e:
                    print(f"Failed:  {row[5]} {e}")
                    #print("Removing empty directory")
                    #os.remove(filepath)
    return

def reboot_nuc(nuc):
    """SSH to the unit NUC and run shutdown /r /t 1."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    unit = str(nuc or "").strip()
    if not unit:
        return False, "Missing unit"
    if uses_pve(unit):
        return False, f"{unit} uses PVE — use Reboot Scrypted instead"
    row = ensure_unit_net_info(unit, needed_indexes=(3,))
    if not row:
        return False, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[3] if len(row) > 3 else "")
    if not ip:
        return False, f"No NUC IP for {unit}"
    username = (os.getenv("nucuser") or "").strip().strip('"').strip("'")
    password = (os.getenv("nucpass") or "").strip().strip('"').strip("'")
    if not username or not password:
        return False, "nucuser/nucpass not set in .env"

    command = r"shutdown /r /t 1"
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
        _stdin, stdout, stderr = client.exec_command(command, timeout=60)
        error = stderr.read().decode("utf-8", errors="replace").strip()
        output = stdout.read().decode("utf-8", errors="replace").strip()
        if error:
            return False, error
        print("Restarting")
        if output:
            print(output)
        return True, "Restarting"
    except paramiko.AuthenticationException:
        return False, (
            f"NUC SSH authentication failed for {username}@{ip}. "
            "Check nucuser and nucpass in .env."
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        client.close()

def nuc_uptime(nuc):
    """SSH to the unit NUC and return system boot info stdout."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    unit = str(nuc or "").strip()
    if not unit:
        return False, "Missing unit", ""
    if uses_pve(unit):
        return False, f"{unit} uses PVE — NUC uptime is not available", ""
    row = ensure_unit_net_info(unit, needed_indexes=(3,))
    if not row:
        return False, f"Unit {unit} not found in net sheet", ""
    ip = _host_only(row[3] if len(row) > 3 else "")
    if not ip:
        return False, f"No NUC IP for {unit}", ""
    username = (os.getenv("nucuser") or "").strip().strip('"').strip("'")
    password = (os.getenv("nucpass") or "").strip().strip('"').strip("'")
    if not username or not password:
        return False, "nucuser/nucpass not set in .env", ""

    command = 'cmd /c "systeminfo | findstr \"System Boot Info\""'
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
        _stdin, stdout, stderr = client.exec_command(command, timeout=60)
        error = stderr.read().decode("utf-8", errors="replace").strip()
        output = stdout.read().decode("utf-8", errors="replace").strip()
        if error and not output:
            return False, error, ""
        return True, output, output
    except paramiko.AuthenticationException:
        return False, (
            f"NUC SSH authentication failed for {username}@{ip}. "
            "Check nucuser and nucpass in .env."
        ), ""
    except Exception as exc:
        return False, str(exc), ""
    finally:
        client.close()

def reboot_scrypted(scrypted):
    """SSH to the unit PVE host and reboot VM 101 (Scrypted/NUC guest)."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    unit = str(scrypted or "").strip()
    if not unit:
        return False, "Missing unit"
    row = ensure_unit_net_info(unit, needed_indexes=(11,))
    if not row:
        return False, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[11] if len(row) > 11 else "")
    if not ip:
        return False, f"No PVE IP for {unit}"
    username, password, cred_error = _pve_ssh_credentials()
    if cred_error:
        return False, cred_error

    command = "qm reboot 101"
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
        _stdin, stdout, stderr = client.exec_command(command, timeout=60)
        error = stderr.read().decode("utf-8", errors="replace").strip()
        output = stdout.read().decode("utf-8", errors="replace").strip()
        if error:
            return False, error
        print("Restarting...")
        if output:
            print(output)
        return True, "Restarting"
    except paramiko.AuthenticationException:
        return False, (
            f"PVE SSH authentication failed for {username}@{ip}. "
            "SSH uses the Linux user only (usually root), not root@pam — "
            "@pam is for the web UI/API. Set pvesshuser=root and pvepass in .env."
        )
    except Exception as exc:
        print(f"Exception caught: {exc}")
        return False, str(exc)
    finally:
        client.close()
def reboot_pve(pve):
    """SSH to the unit PVE host and reboot VM 101 (Scrypted/NUC guest)."""
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    unit = str(pve or "").strip()
    if not unit:
        return False, "Missing unit"
    row = ensure_unit_net_info(unit, needed_indexes=(11,))
    if not row:
        return False, f"Unit {unit} not found in net sheet"
    ip = _host_only(row[11] if len(row) > 11 else "")
    if not ip:
        return False, f"No PVE IP for {unit}"
    username, password, cred_error = _pve_ssh_credentials()
    if cred_error:
        return False, cred_error

    command = "reboot"
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
        _stdin, stdout, stderr = client.exec_command(command, timeout=60)
        error = stderr.read().decode("utf-8", errors="replace").strip()
        output = stdout.read().decode("utf-8", errors="replace").strip()
        if error:
            return False, error
        print("Restarting...")
        if output:
            print(output)
        return True, "Restarting"
    except paramiko.AuthenticationException:
        return False, (
            f"PVE SSH authentication failed for {username}@{ip}. "
            "SSH uses the Linux user only (usually root), not root@pam — "
            "@pam is for the web UI/API. Set pvesshuser=root and pvepass in .env."
        )
    except Exception as exc:
        print(f"Exception caught: {exc}")
        return False, str(exc)
    finally:
        client.close()

def chkdsk(nuc, drive, read_only=True):
    """
    SSH to the unit NUC and run chkdsk.
    read_only=True runs `chkdsk X:` (no /F). Returns (ok, message, output).
    """
    load_dotenv(env_path)
    if not net_array:
        generate_net_array()
    unit = str(nuc or "").strip()
    if not unit:
        return False, "Missing unit", ""
    if uses_pve(unit):
        return False, f"{unit} uses PVE — chkdsk is only available for NUC units", ""

    drive_letter = str(drive or "").strip().upper().replace("\\", "").replace("/", "")
    if drive_letter.endswith(":"):
        drive_letter = drive_letter[:-1]
    if len(drive_letter) != 1 or not ("A" <= drive_letter <= "Z"):
        return False, "Drive must be a single letter (A-Z)", ""

    row = ensure_unit_net_info(unit, needed_indexes=(3,))
    if not row:
        return False, f"Unit {unit} not found in net sheet", ""
    ip = _host_only(row[3] if len(row) > 3 else "")
    if not ip:
        return False, f"No NUC IP for {unit}", ""

    username = (os.getenv("nucuser") or "").strip().strip('"').strip("'")
    password = (os.getenv("nucpass") or "").strip().strip('"').strip("'")
    if not username or not password:
        return False, "nucuser/nucpass not set in .env", ""

    if read_only:
        command = f"chkdsk {drive_letter}:"
    else:
        command = f"chkdsk {drive_letter}: /F"

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
        _stdin, stdout, stderr = client.exec_command(command, timeout=900)
        stdout.channel.settimeout(900)
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace").strip()
        combined = "\n".join(
            part for part in (output.strip(), error) if part
        )
        if "No further action is required" in output:
            return True, f"chkdsk passed for {drive_letter}: (read-only)", combined
        if error and not output.strip():
            return False, error, combined
        return True, f"chkdsk finished for {drive_letter}: (review output)", combined
    except paramiko.AuthenticationException:
        return False, (
            f"NUC SSH authentication failed for {username}@{ip}. "
            "Check nucuser and nucpass in .env."
        ), ""
    except Exception as exc:
        return False, str(exc), ""
    finally:
        client.close()

def install_checker():
    idUser = os.getenv("idUser")
    api_token = os.getenv("victron_token")
    url = f"https://vrmapi.victronenergy.com/v2/users/{idUser}/installations"
    headers = {
        "idUser": f"{idUser}",
        "X-Authorization": f"Token {api_token}"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        while True:
            unit = str(input("Input MUXXXX or type 'quit' to exit: "))
            data = response.json()
            if unit.lower() == "quit":
                main()
            
            for record in data.get("records"):
                exists = False
                if record.get("name")[-4:] == unit[-4:] or record.get("name")[-4:] == unit[-4:]:
                    print('Unit is added to VRM')
                    print(f"Site ID for {unit} is {record.get('idSite')}")
                    #print(record)
                    siteId = record.get('idSite')
                    exists = True        
                    url2 = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/system-overview"
                    response2 = requests.get(url2, headers=headers)
                    data2 = response2.json()
                    for device in data2["records"]["devices"]:
                        if device["name"] == "Gateway":
                            lastseen = device["lastConnection"]
                            lastseen = datetime.fromtimestamp(lastseen).strftime("%H:%M:%S on %m/%d/%Y")
                            print(f'victron last seen at {lastseen}') 
                    break

            if exists == False:
                print('Unit was not found.')
    else:
        print("Response text: ", response.text)

def all_unit_battery_health():
    global all_battery_units, low_battery_units, depleted_battery_units, all_battery_units_mapped
    all_battery_units.clear()
    low_battery_units.clear()
    depleted_battery_units.clear()
    all_battery_units_mapped.clear()

    if response.status_code == 200:
        print('Loading trailers...')
        data = response.json()
        for record in data.get("records"):
            unitname = record.get("name")
            siteid = record.get("idSite")
            headers2 = {
                "idSite": f"{siteid}",
                "X-Authorization": f"Token {api_token}"
                }
            try:
                response2 = requests.get(f"https://vrmapi.victronenergy.com/v2/installations/{siteid}/diagnostics", headers=headers2)
            except Exception as e:
                print(f"Failed as {e}")
            data2 = response2.json()
            records = data2.get("records", {})
            
            for record in records:
                    formval = record.get("formattedValue")
                    if isinstance(formval, str) and len(formval) > 1 and formval.split(":")[0][-1] == "%" and record.get("description") == "Battery SOC":
                        #print(f"{unitname} battery life at {formval}. Adding unit to all batteries list")
                        combined = {
                            "name": unitname,
                            "battery": formval
                        }
                        all_battery_units.append(combined)
                        formlength = len(formval)
                        #print(formlength)
                        if formlength == 6:
                            percentage = int(formval[:2])
                            if percentage <= 20:
                                #print(f"Unit battery is low, adding to battery list")
                                combined = {
                                    "name": unitname,
                                    "battery": formval  
                                }
                                low_battery_units.append(combined)

                        if formlength == 5:
                            percentage = int(formval[:1])
                            if percentage > 0:
                                #print("Unit battery is low, adding to low battery list")
                                combined = {
                                    "name": unitname,
                                    "battery": formval   
                                }
                                low_battery_units.append(combined)
                            elif percentage == 0:
                                #print("Battery is depleted, adding to depleted battery list")
                                combined = {
                                    "name": unitname,
                                    "battery": formval,
                                }
                                depleted_battery_units.append(combined)               
    naming_conventions()
    

def unit_battery_health(unit):
    if response.status_code == 200:
        #while True:
            data = response.json()
            if unit.lower() == "quit":
                main()
            for record in data.get("records"):
                unitname = record.get("name").lower()
                if unitname[-4:] == unit[-4:]:
                    siteid = record.get("idSite")
                    headers2 = {
                        "idSite": f"{siteid}",
                        "X-Authorization": f"Token {api_token}"
                    }

                    response2 = requests.get(f"https://vrmapi.victronenergy.com/v2/installations/{siteid}/diagnostics", headers=headers2)
                    data2 = response2.json()
                    records = data2.get("records", {})
                    for record in records:
                        #print(record)
                        if record.get("idSite") == siteid:
                            formval = record.get("formattedValue")
                            if isinstance(formval, str) and len(formval) > 1 and formval.split(":")[0][-1] == "%" and record.get("description") == "Battery SOC":
                                print(f"{unitname} battery life at {formval}")


    else:
        print("Response text:", response.text)

def rd_battery_map():
    for row in all_battery_units:
        url = f"{erp_base_url()}/api/resource/Component"
        erp_token = os.getenv("erp_token")
        headers = {
            "Authorization": f"token {erp_token}"
        }

        params = {
            "fields": '["name"]',
            "filters": f'[["parent_component","=","{row["name"]}"]]',
            "limit_page_length": 0
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        for doc in data.get("data", []):
            rd_unit = doc["name"]
            full_unit = {
                "name": rd_unit,
                "trailer": row["name"]
            }
            all_battery_units_mapped.append(full_unit)
    return

def low_battery_rd_fisheye_tool():
    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    print("Low battery units: ")
    for row in low_battery_units:
        if row["name"][:3] != 'SC-':
            row["name"] = "SC-" + row["name"]
            print(f'Adjusted {row["name"]}')
        battery = row["battery"]
        print(f"{row['name']} - {battery}")
        erp_token = os.getenv("erp_token")
        url = f"{erp_base_url()}/api/resource/Component"
        headers = {
            "Authorization": f"token {erp_token}"
        }

        params = {
            "fields": '["name"]',
            "filters": f'[["parent_component","=","{row["name"]}"]]',
            "limit_page_length": 0
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        for doc in data.get("data", []):
            rd_unit = doc["name"]
            print(rd_unit)
            full_unit = {
                "name": rd_unit,
                "trailer": row["name"]
            }
            print(f'Adding {full_unit["name"]} to RD low list')
            rd_down.append(full_unit)
    print('RD List:')
    for rd in rd_down:
        print(f"{rd['name']} - {rd['trailer']}")

def low_battery_list():
    print("Low battery units: ")
    for row in low_battery_units:
        name = row["name"]
        battery = row["battery"]
        print(f"{row['name']} - {row['battery']}")
    
def depleted_battery_list():
    print("Depleted battery units: ")
    for row in depleted_battery_units:
        name = row["name"]
        battery = row["battery"]
        print(f"{row['name']} - {row['battery']}")
    
def all_battery_list():
    print("All battery units: ")
    for row in all_battery_units:
        name = row["name"]
        battery = row["battery"]
        print(f"{row['name']} - {row['battery']}")

if __name__ == "__main__":
    main()
    #thank you for reading

