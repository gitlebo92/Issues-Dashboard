"""
Preview refactor of work_tool.py — same behavior, cleaner structure.

This file is standalone; work_tool.py is unchanged. To adopt later you would
wire flask_endpoints.py to import from here (or split further into modules).
"""

from __future__ import annotations

import csv
import multiprocessing
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import requests
import zabbix_tool
from dotenv import load_dotenv
from requests.auth import HTTPDigestAuth

multiprocessing.freeze_support()

# ---------------------------------------------------------------------------
# Net sheet column indices 
# ---------------------------------------------------------------------------
COL_UNIT = 0
COL_ROUTER = 1
COL_SWITCH = 2
COL_NUC = 3
COL_SPEAKER = 4
COL_FISHEYE = 5
COL_PVE = 11
COL_SCRYPTED = 12

PING_HOST_BY_SUFFIX = {
    "router": COL_ROUTER,
    "switch": COL_SWITCH,
    "speaker": COL_SPEAKER,
    "nuc": COL_NUC,
    "pve": COL_PVE,
    "vm": COL_SCRYPTED,
}


# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


@dataclass
class Config:
    username: str | None
    id_user: str | None
    api_token: str | None
    netsheet: str
    mapsheet: str
    false_mu: str
    downloads: str = field(default_factory=lambda: os.path.join(os.path.expanduser("~"), "Downloads"))

    @classmethod
    def load(cls) -> Config:
        load_dotenv(resource_path(".env"))
        return cls(
            username=os.getenv("username"),
            id_user=os.getenv("idUser"),
            api_token=os.getenv("victron_token"),
            netsheet=resource_path("net_sheet.csv"),
            mapsheet=resource_path("map_sheet.csv"),
            false_mu=resource_path("false_mu.csv"),
        )

    @property
    def victron_installations_url(self) -> str:
        return f"https://vrmapi.victronenergy.com/v2/users/{self.id_user}/installations"

    def victron_headers(self) -> dict[str, str]:
        return {
            "idUser": f"{self.id_user}",
            "X-Authorization": f"Token {self.api_token}",
        }


# ---------------------------------------------------------------------------
# Mutable runtime state 
# ---------------------------------------------------------------------------
@dataclass
class AppState:
    counter: int = 0
    net_array: list[list[str]] = field(default_factory=list)
    false_mu_array: list[str] = field(default_factory=list)
    all_battery_units: list[dict[str, str]] = field(default_factory=list)
    all_battery_units_mapped: list[dict[str, str]] = field(default_factory=list)
    low_battery_units: list[dict[str, str]] = field(default_factory=list)
    depleted_battery_units: list[dict[str, str]] = field(default_factory=list)
    rd_down: list[dict[str, str]] = field(default_factory=list)
    fisheyes: list[dict[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    missing_zab: list[str] = field(default_factory=list)
    false_positive: list[str] = field(default_factory=list)
    _victron_response: requests.Response | None = None

    def victron_response(self, cfg: Config) -> requests.Response:
        if self._victron_response is None:
            self._victron_response = requests.get(
                cfg.victron_installations_url, headers=cfg.victron_headers()
            )
        return self._victron_response


cfg = Config.load()
state = AppState()
toolkit = zabbix_tool.Zabbix_Tool_Kit()


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------
def clear_terminal() -> None:
    os.system("cls")


def unit_suffix(unit: str) -> str:
    return unit[-4:].lower()


def uses_pve(unit: str) -> bool:
    try:
        return int(unit[-4:]) >= 3300
    except ValueError:
        return False


def ping_compute(unit: str) -> tuple[int, str]:
    return ping_pve(unit) if uses_pve(unit) else ping_nuc(unit)


def compute_host_label(unit: str) -> str:
    return "PVE" if uses_pve(unit) else "NUC"


def is_ping_success(output: str) -> bool:
    return "Reply from" in output and "TTL=" in output and "expired" not in output


def find_net_row(unit: str) -> list[str] | None:
    target = unit.upper()
    for row in state.net_array:
        if row[COL_UNIT].upper() == target:
            return row
    return None


def ping_host(unit: str, column: int) -> tuple[int, str]:
    row = find_net_row(unit)
    if not row or column >= len(row):
        return 1, ""
    host = row[column]
    result = subprocess.run(
        ["ping", "-n", "4", "-w", "1000", host],
        text=True,
        capture_output=True,
    )
    return result.returncode, result.stdout


def ping_router(unit: str) -> tuple[int, str]:
    return ping_host(unit, COL_ROUTER)


def ping_switch(unit: str) -> tuple[int, str]:
    return ping_host(unit, COL_SWITCH)


def ping_speaker(unit: str) -> tuple[int, str]:
    return ping_host(unit, COL_SPEAKER)


def ping_nuc(unit: str) -> tuple[int, str]:
    return ping_host(unit, COL_NUC)


def ping_pve(unit: str) -> tuple[int, str]:
    return ping_host(unit, COL_PVE)


def ping_scrypted(unit: str) -> tuple[int, str]:
    return ping_host(unit, COL_SCRYPTED)


# ---------------------------------------------------------------------------
# Net sheet & false-MU loading
# ---------------------------------------------------------------------------
def generate_false_mu() -> None:
    with open(cfg.false_mu, "r", newline="") as csvfile:
        for row in csv.reader(csvfile):
            state.false_mu_array.append(row[0])
    print("Loaded false positive MU list")


def generate_net_array() -> None:
    state.net_array.clear()
    with open(cfg.netsheet, "r", newline="") as csvfile:
        for row in csv.reader(csvfile):
            if len(row) >= 1 and len(row[0]) == 6:
                state.net_array.append(row)
    generate_false_mu()


def save_map_sheet() -> None:
    with open(cfg.mapsheet, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["name", "trailer"])
        writer.writeheader()
        writer.writerows(state.all_battery_units_mapped)


def load_map_sheet_from_csv() -> None:
    state.all_battery_units_mapped.clear()
    with open(cfg.mapsheet, "r", newline="") as csvfile:
        for row in csv.DictReader(csvfile):
            state.all_battery_units_mapped.append(row)


# ---------------------------------------------------------------------------
# Victron / battery health
# ---------------------------------------------------------------------------
def _parse_battery_soc(formval: str) -> int | None:
    if len(formval) == 6:
        return int(formval[:2])
    if len(formval) == 5:
        return int(formval[:1])
    return None


def _classify_battery(unitname: str, formval: str) -> None:
    entry = {"name": unitname, "battery": formval}
    state.all_battery_units.append(entry)
    percentage = _parse_battery_soc(formval)
    if percentage is None:
        return
    if len(formval) == 6 and percentage <= 20:
        state.low_battery_units.append(entry)
    elif len(formval) == 5:
        if percentage > 0:
            state.low_battery_units.append(entry)
        elif percentage == 0:
            state.depleted_battery_units.append(entry)


def rd_battery_map() -> None:
    erp_token = os.getenv("erp_token")
    headers = {"Authorization": f"token {erp_token}"}
    for row in state.all_battery_units:
        params = {
            "fields": '["name"]',
            "filters": f'[["parent_component","=","{row["name"]}"]]',
            "limit_page_length": 0,
        }
        response = requests.get(
            "https://erp.sentracam.com/api/resource/Component",
            headers=headers,
            params=params,
        )
        for doc in response.json().get("data", []):
            state.all_battery_units_mapped.append(
                {"name": doc["name"], "trailer": row["name"]}
            )


def naming_conventions() -> None:
    print("Adjusting naming conventions...")
    for row in state.all_battery_units:
        if row["name"][:3] != "SC-":
            row["name"] = "SC-" + row["name"]
    print("Mapping trailers to head units...")
    rd_battery_map()


def all_unit_battery_health() -> None:
    state.all_battery_units.clear()
    state.low_battery_units.clear()
    state.depleted_battery_units.clear()
    state.all_battery_units_mapped.clear()

    response = state.victron_response(cfg)
    if response.status_code != 200:
        return

    print("Loading trailers...")
    data = response.json()
    for record in data.get("records", []):
        unitname = record.get("name")
        siteid = record.get("idSite")
        headers2 = {
            "idSite": f"{siteid}",
            "X-Authorization": f"Token {cfg.api_token}",
        }
        try:
            response2 = requests.get(
                f"https://vrmapi.victronenergy.com/v2/installations/{siteid}/diagnostics",
                headers=headers2,
            )
            data2 = response2.json()
        except Exception as e:
            print(f"Failed as {e}")
            continue

        for diag in data2.get("records", {}):
            formval = diag.get("formattedValue")
            if (
                isinstance(formval, str)
                and len(formval) > 1
                and formval.split(":")[0][-1] == "%"
                and diag.get("description") == "Battery SOC"
            ):
                _classify_battery(unitname, formval)

    naming_conventions()


def unit_battery_health(unit: str) -> None:
    response = state.victron_response(cfg)
    if response.status_code != 200:
        print("Response text:", response.text)
        return

    for record in response.json().get("records", []):
        unitname = record.get("name", "").lower()
        if unitname[-4:] != unit[-4:].lower():
            continue
        siteid = record.get("idSite")
        headers2 = {
            "idSite": f"{siteid}",
            "X-Authorization": f"Token {cfg.api_token}",
        }
        response2 = requests.get(
            f"https://vrmapi.victronenergy.com/v2/installations/{siteid}/diagnostics",
            headers=headers2,
        )
        for diag in response2.json().get("records", {}):
            formval = diag.get("formattedValue")
            if (
                isinstance(formval, str)
                and len(formval) > 1
                and formval.split(":")[0][-1] == "%"
                and diag.get("description") == "Battery SOC"
            ):
                print(f"{unitname} battery life at {formval}")
        return


def get_rd_battery(unit: str) -> None:
    for row in state.all_battery_units_mapped:
        if unit_suffix(unit) == unit_suffix(row["name"]):
            print("Matched, fetching battery health")
            unit_battery_health(row["trailer"])
            return
    print("Unit not found.")


def _print_battery_list(title: str, units: list[dict[str, str]]) -> None:
    print(title)
    for row in units:
        print(f"{row['name']} - {row['battery']}")


def low_battery_list() -> None:
    _print_battery_list("Low battery units: ", state.low_battery_units)


def depleted_battery_list() -> None:
    _print_battery_list("Depleted battery units: ", state.depleted_battery_units)


def all_battery_list() -> None:
    _print_battery_list("All battery units: ", state.all_battery_units)


def install_checker() -> None:
    response = requests.get(cfg.victron_installations_url, headers=cfg.victron_headers())
    if response.status_code != 200:
        print("Response text: ", response.text)
        return

    while True:
        unit = str(input("Input MUXXXX or type 'quit' to exit: "))
        if unit.lower() == "quit":
            return

        data = response.json()
        for record in data.get("records", []):
            if unit_suffix(record.get("name", "")) != unit_suffix(unit):
                continue

            print("Unit is added to VRM")
            site_id = record.get("idSite")
            print(f"Site ID for {unit} is {site_id}")

            overview = requests.get(
                f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/system-overview",
                headers=cfg.victron_headers(),
            ).json()
            for device in overview["records"]["devices"]:
                if device["name"] == "Gateway":
                    lastseen = datetime.fromtimestamp(device["lastConnection"]).strftime(
                        "%H:%M:%S on %m/%d/%Y"
                    )
                    print(f"victron last seen at {lastseen}")
            return

        print("Unit was not found.")


# ---------------------------------------------------------------------------
# Outage / mesh / zabbix validation
# ---------------------------------------------------------------------------
def clear_old_reports(mesh_path: str, issue_path: str) -> None:
    print("Attempting clear here~~~~~~~~~~~")
    try:
        os.remove(mesh_path)
        os.remove(issue_path)
        print("Cleared old reports")
    except Exception as e:
        print(f"Failed to remove: {e}")
    print("Beginning outage validation")


def compare_reports(issue_path: str, mesh_path: str) -> list[str]:
    state.missing.clear()
    mesh_array: list[str] = []
    erp_array: list[str] = []

    try:
        with open(mesh_path, "r", newline="") as csvfile:
            for line in csv.reader(csvfile):
                if line:
                    mesh_array.append(line[0])
    except Exception as e:
        print(f"Task failed: {e}")
        return state.missing

    try:
        with open(issue_path, "r", newline="") as csvfile:
            for line in csv.reader(csvfile):
                if line and len(line) > 1 and line[1] != "Subject":
                    erp_array.append(line[1])
    except Exception as e:
        print(f"Task failed: {e}")
        return state.missing

    for mesh in mesh_array:
        found = any(mesh in line for line in erp_array)
        if found:
            print(f"Found {mesh} in issue report")
        elif mesh not in state.false_mu_array:
            state.missing.append(mesh)

    print("\nMissing units: ")
    for row in state.missing:
        if row != "Agent Name":
            print(row)
    return state.missing


def validate_reports_mesh() -> tuple[list[str], list[str], list[str]]:
    nuc_down: list[str] = []
    stale_vpn: list[str] = []
    missing2: list[str] = []

    print("Checking connectivity on missing units...")
    print("Current missing list:", state.missing)
    for unit in state.missing:
        for row in state.net_array:
            if unit != row[COL_UNIT] or unit in state.false_mu_array:
                continue

            host = compute_host_label(unit)
            print("matched" + unit)
            code, output = ping_router(unit)
            print(output)

            if is_ping_success(output):
                print(f"Router is up, {code}: {unit} checking {host.lower()}..")
                code, output = ping_compute(unit)
                print(output)
                if is_ping_success(output):
                    print(f"Both {host} and Router are online {code}, removing {unit} from missing array")
                    state.false_positive.append(unit)
                else:
                    print(f"{host} is down, router is up. Bounce {host}.")
                    nuc_down.append(unit)
                break

            print(f"Router is down {code}, checking {host}")
            code, output = ping_compute(unit)
            print(output)
            if is_ping_success(output):
                print(f"{host} is up {code}, router is down, reset VPN connection on {unit}")
                stale_vpn.append(unit)
            else:
                print(f"{host} and router are offline. {code}")
                missing2.append(unit)

    print("New adjusted missing list:")
    for line in state.missing:
        if (
            line not in state.false_positive
            and line != "Agent Name"
            and line not in nuc_down
            and line not in stale_vpn
        ):
            print(line)
    print("Offline NUCs")
    for line in nuc_down:
        print(line)
    print("Stale VPNs")
    for line in stale_vpn:
        print(line)
    return missing2, nuc_down, stale_vpn


def compare_zabbix() -> None:
    zabbix_path = os.path.join(cfg.downloads, "zbx_problems_export.csv")
    mesh_outage = os.path.join(cfg.downloads, "filtered_mesh_vpn.csv")
    mesh_array: list[str] = []
    zabbix_array: list[str] = []

    try:
        with open(zabbix_path, "r", newline="") as csvfile:
            for row in csv.reader(csvfile):
                prefix = row[4][:2].lower()
                if prefix in ("rd", "mu", "fd"):
                    print(f"Appended {row[4]}")
                    zabbix_array.append(row[4])
    except Exception as e:
        print(f"Task failed: {e}")
        return

    try:
        with open(mesh_outage, "r", newline="") as csvfile:
            for row in csv.reader(csvfile):
                mesh_array.append(row[0])
    except Exception as e:
        print(f"Task failed: {e}")
        return

    print(f"Zabbix list length: {len(zabbix_array)} \n Mesh list length: {len(mesh_array)}")
    for zab in zabbix_array:
        if not any(zab[:6] in mesh for mesh in mesh_array):
            state.missing_zab.append(zab)

    for line in state.missing_zab:
        print(line)
    print(f"{len(state.missing_zab)} Units discovered on zabbix that werent found on mesh")


def _host_suffix(host: str) -> str:
    for length, suffix in ((6, "router"), (6, "switch"), (7, "speaker"), (3, "pve"), (3, "nuc"), (2, "vm")):
        if host[-length:].lower() == suffix:
            return suffix
    return ""


def validate_reports_zab() -> None:
    false_positives: list[str] = []
    for host in state.missing_zab:
        print(host)
        suffix = _host_suffix(host)
        column = PING_HOST_BY_SUFFIX.get(suffix)
        if column is None:
            continue

        unit = host[:6]
        code, output = ping_host(unit, column)
        for line in output.splitlines():
            print(line)
        if is_ping_success(output):
            print(f"False positive unit: {code}: {host}")
            false_positives.append(host)

    if false_positives:
        print("False positives: ")
        for line in false_positives:
            print(line)


# ---------------------------------------------------------------------------
# Fisheye tools
# ---------------------------------------------------------------------------
def file_search(unit: str, root: str = r"C:\Temp") -> list[str]:
    results: list[str] = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if unit.lower() in filename.lower():
                print(f"Found snapshot: {filename}")
                results.append(os.path.join(dirpath, filename))
    for file in results:
        print(file)
    return results


def low_battery_rd_fisheye_tool() -> None:
    print("Low battery units: ")
    erp_token = os.getenv("erp_token")
    headers = {"Authorization": f"token {erp_token}"}

    for row in state.low_battery_units:
        if row["name"][:3] != "SC-":
            row["name"] = "SC-" + row["name"]
            print(f"Adjusted {row['name']}")
        print(f"{row['name']} - {row['battery']}")

        params = {
            "fields": '["name"]',
            "filters": f'[["parent_component","=","{row["name"]}"]]',
            "limit_page_length": 0,
        }
        response = requests.get(
            "https://erp.sentracam.com/api/resource/Component",
            headers=headers,
            params=params,
        )
        for doc in response.json().get("data", []):
            full_unit = {"name": doc["name"], "trailer": row["name"]}
            print(f"Adding {full_unit['name']} to RD low list")
            state.rd_down.append(full_unit)

    print("RD List:")
    for rd in state.rd_down:
        print(f"{rd['name']} - {rd['trailer']}")


def low_battery_fisheye_screenshotter() -> None:
    if not state.low_battery_units:
        too_low = input("List is empty. Load low battery units? (Y/N)")
        if too_low.lower()[:1] == "y":
            low_battery_rd_fisheye_tool()
        else:
            print("Okey dokey")
            return

    print("Fisheye starting")
    timestamp = datetime.now().strftime("%Y-%m-%d")
    time_path = os.path.join(r"C:\Temp", f"{timestamp}_fisheye_screenshots")
    os.makedirs(time_path, exist_ok=True)

    fishuser = os.getenv("fishuser")
    fishpass = os.getenv("fishpass")

    for row in state.net_array:
        for unit in state.rd_down:
            if row[COL_UNIT][-4:] != unit["name"][-4:]:
                continue

            print(f"{row[COL_UNIT]} found in netsheet. Fisheye ip address is: {row[COL_FISHEYE]}")
            state.fisheyes.append({"Unit:": row[COL_UNIT], "Fisheye IP:": row[COL_FISHEYE]})
            print("Screenshotting...")
            try:
                url = f"http://{row[COL_FISHEYE]}/cgi-bin/snapshot.cgi?channel=1"
                response = requests.get(
                    url, auth=HTTPDigestAuth(fishuser, fishpass), timeout=30
                )
                response.raise_for_status()
                shot_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = row[COL_UNIT] + "_" + shot_time + ".jpg"
                filepath = os.path.join(time_path, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print(f"Saved to {filepath}")
            except requests.exceptions.RequestException as e:
                print(f"Failed:  {row[COL_FISHEYE]} {e}")


# ---------------------------------------------------------------------------
# CLI — command registry
# ---------------------------------------------------------------------------
def _cmd_compare_mesh() -> None:
    issue_path = os.path.join(cfg.downloads, "Issue.csv")
    mesh_path = os.path.join(cfg.downloads, "filtered_mesh_vpn.csv")
    compare_reports(issue_path, mesh_path)
    validate_reports_mesh()


def _cmd_refresh_map_sheet() -> None:
    all_unit_battery_health()
    save_map_sheet()


def _cmd_rd_battery_loop() -> None:
    while True:
        unit = str(input("Input RDXXXX to fetch battery. Unit must be 3300 or greater: "))
        if unit.lower() == "quit":
            break
        get_rd_battery(unit)


def _cmd_zabbix_query() -> None:
    try:
        toolkit.query_zabbix_events()
    except Exception:
        print("No zabbix events found")


MENU: dict[str, tuple[str, Callable[[], None]]] = {
    "1": ("Check if unit is installed in VRM", install_checker),
    "2": ("Check individual trailer battery health using its MU#", lambda: unit_battery_health(str(input("Input MUXXXX: ")))),
    "3": ("Print low battery list", low_battery_list),
    "4": ("Print depleted battery list", depleted_battery_list),
    "5": ("Print all battery list", all_battery_list),
    "6": ("Check individual trailer battery health using its RD#", _cmd_rd_battery_loop),
    "7": ("Compare mesh and issue reports", _cmd_compare_mesh),
    "8": ("Update unit battery array and create or update map sheet", _cmd_refresh_map_sheet),
    "9": ("Print unit map sheet", lambda: [print(f'{r["name"]} - {r["trailer"]}') for r in state.all_battery_units_mapped]),
    "10": ("Search C:\\Temp for fisheye snapshots", lambda: file_search(input("Enter unit to search for in C:\\Temp: "))),
    "11": ("Update unit battery health list", all_unit_battery_health),
    "12": ("Screenshot fisheye on low battery units", lambda: (low_battery_rd_fisheye_tool(), low_battery_fisheye_screenshotter())),
    "13": ("Compare Zabbix and mesh outages", lambda: (compare_zabbix(), validate_reports_zab())),
    "14": ("Query Zabbix for outage events for a specific unit", _cmd_zabbix_query),
}


def print_menu() -> None:
    print("Command menu: ")
    for key, (label, _) in MENU.items():
        print(f"{key}. {label}")


def run_first_time_setup() -> None:
    print("")
    print("USERNAME:", cfg.username)
    generate_net_array()

    initialize = input(
        "\n\r\n\r *****IMPORTANT*****\n\r This tool is multifunctional. In order to use the battery health functions, "
        "you need to load the battery metrics from victron.\n\r "
        "You can load the battery health now but it takes 2-4 minutes as it makes API calls to victron.\n\r "
        "The program doesnt necessarily need the victron information to run \n\r "
        "Only hit yes if youd like to load battery health. Initialize program with victron loaded? (Y/N) "
    )
    if initialize.lower()[:1] == "y":
        all_unit_battery_health()
        save_map_sheet()
        print("CSV file generated.")
        print("Initialization complete. ")
    else:
        print("Populating mapped unit array from csv...")
        load_map_sheet_from_csv()


def main() -> None:
    while True:
        if state.counter < 1:
            run_first_time_setup()
            state.counter += 1
            if not state.all_battery_units_mapped and state.counter == 1:
                continue

        print_menu()
        cmd = input("Enter a number 1-14: ").strip().lower()

        if cmd in ("quit", "exit"):
            sys.exit()
        if cmd in ("cls", "clr", "clear"):
            clear_terminal()
            continue

        handler = MENU.get(cmd)
        if handler:
            _, action = handler
            action()
        else:
            print("Invalid command. Please enter a number one through fourteen.")


if __name__ == "__main__":
    main()
