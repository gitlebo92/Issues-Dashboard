import requests
import csv
import os
import sys
import subprocess
import zabbix_tool
import multiprocessing
import paramiko
from requests.auth import HTTPDigestAuth
from datetime import datetime
from dotenv import load_dotenv

multiprocessing.freeze_support()
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

env_path = resource_path(".env")

load_dotenv(env_path)

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
            #print("netsheet path:", netsheet)
            #print("Exists:", os.path.exists(netsheet))
            #print("ENV PATH:", env_path)
            print("USERNAME:", username)
            #print("IDUSER:", idUser)

            generate_net_array()
            #print("Net array generated.")
            initialize_program = input(
                '\n\r\n\r *****IMPORTANT*****\n\r This tool is multifunctional. In order to use the battery health functions, you need to load the battery metrics from victron.\n\r '\
                'You can load the battery health now but it takes 2-4 minutes as it makes API calls to victron.\n\r '
                'The program doesnt necessarily need the victron information to run \n\r Only hit yes if youd like to load battery health. Initialize program with victron loaded? (Y/N) '

            )
            if initialize_program.lower()[:1] == "y":
                counter += 1
                all_unit_battery_health()
                with open(mapsheet, 'w', newline='') as csvfile:
                    fieldnames = ["name", "trailer"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_battery_units_mapped)
                    print('CSV file generated.')
                    print('Initialization complete. ')
            else:
                counter += 1
                print('Populating mapped unit array from csv...')
                with open(mapsheet, "r", newline='') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        all_battery_units_mapped.append(row)
                    reader
                continue    

        
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
        cmd = input("Enter a number 1-14: ")
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

def ping_router(unit):
    for row in net_array:
        if unit.upper() == row[0].upper():
                router = row[1]
                result = subprocess.run(['ping', '-n', '4', '-w', '1000',  router], text=True, capture_output=True)
                return result.returncode, result.stdout       

def ping_speaker(unit):
    for row in net_array:
        if unit.upper() == row[0].upper():
                speaker = row[4]
                result = subprocess.run(['ping', '-n', '4', '-w', '1000',  speaker], text=True, capture_output=True)
                return result.returncode, result.stdout 
    
def ping_switch(unit):
    for row in net_array:
        if unit.upper() == row[0].upper():
                switch = row[2]
                result = subprocess.run(['ping', '-n', '4', '-w', '1000',  switch], text=True, capture_output=True)
                return result.returncode, result.stdout 
    
def ping_nuc(unit):
    for row in net_array:
        if unit.upper() == row[0].upper():
                nuc = row[3]
                result = subprocess.run(['ping', '-n', '4', '-w', '1000',  nuc], text=True, capture_output=True)
                return result.returncode, result.stdout

def uses_pve(unit):
    try:
        return int(unit[-4:]) >= 3300
    except ValueError:
        return False

def unit_number(unit):
    try:
        return int(str(unit).strip()[-4:])
    except (TypeError, ValueError):
        return None

def in_potential_stale_vpn_range(unit):
    """Units 3000-3199 inclusive may be potentially stale VPN when both router and NUC are down."""
    n = unit_number(unit)
    return n is not None and 3000 <= n <= 3199

def _ping_reachable(output):
    return bool(output) and "Reply from" in output and "TTL=" in output and "expired" not in output

def ping_compute(unit):
    return ping_pve(unit) if uses_pve(unit) else ping_nuc(unit)

def compute_host_label(unit):
    return "PVE" if uses_pve(unit) else "NUC"

def ping_pve(unit):
    for row in net_array:
        if unit.upper() == row[0].upper():
                pve = row[11]
                result = subprocess.run(['ping', '-n', '4', '-w', '1000',  pve], text=True, capture_output=True)
                return result.returncode, result.stdout 
def ping_scrypted(unit):
    for row in net_array:
        if unit.upper() == row[0].upper():
                scrypted = row[12]
                result = subprocess.run(['ping', '-n', '4', '-w', '1000',  scrypted], text=True, capture_output=True)
                return result.returncode, result.stdout 

def check_patch_version(unit):
    username = os.getenv("scryptuser")
    password = os.getenv("scryptpass")
    command3env = os.getenv("install")
    command = (
    "sudo -S sed -nE 's/.*Version:[[:space:]]*(sentracam-watch-[0-9]{8}-[0-9]{6}\\.tar\\.gz).*/\\1/p' "
    "$(ls -t /var/log/sentracam/install-*.log | head -1) | head -1")
    command2 = (
        f"sudo -S bash -c '{command3env}' "
    )
    for row in net_array:
        if unit.upper()[-4:] == row[0].upper()[-4:]:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                print(f'Checking patch version for {unit}')
                client.connect(hostname=row[12], port=22, username=username, password=password)
                stdin, stdout, stderr = client.exec_command(command)
                stdin.write(f"{password}\n")
                stdin.flush()
                result = stdout.read().decode('utf-8')
                if result[16:24] != "20260728":
                    print(f'Patch version is not 20260728, it is {result[16:24]}')
                    run_update = input(f'Run update? (Y/N)')
                    if run_update.lower()[:1] == "y":
                        print("Updating...")
                        stdin, stdout, stderr = client.exec_command(command2)
                        stdin.write(f"{password}\n")
                        stdin.flush()
                        result2 = stdout.read().decode('utf-8')
                        print(f'Update result: {result2}')
                    else:
                        print("Skipping update")
                else:
                    print(f'Patch version is 20260728, up to date')
            except Exception as e:
                print(f'Error checking patch version for {unit}: {e}')

def check_all_patches():
    patch_array = []
    username = os.getenv("scryptuser")
    password = os.getenv("scryptpass")
    command = (
    "sudo -S sed -nE 's/.*Version:[[:space:]]*(sentracam-watch-[0-9]{8}-[0-9]{6}\\.tar\\.gz).*/\\1/p' "
    "$(ls -t /var/log/sentracam/install-*.log | head -1) | head -1")
    for row in net_array:
        rdnum = int(row[0].strip()[-4:])
        if rdnum >= 3300:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                print(f'Checking patch version for {row[0]}')
                client.connect(hostname=row[12], port=22, username=username, password=password)
                stdin, stdout, stderr = client.exec_command(command)
                stdin.write(f"{password}\n")
                stdin.flush()
                result = stdout.read().decode('utf-8')
                if result[16:24] != "20260728":
                    print(f'Patch version is not 20260728, it is {result[16:24]}. Appended to array')
                    patch_array.append(row[0])
                else:
                    print(f'Patch version is 20260728, up to date')
            except Exception as e:
                print(f'Error checking patch version for {row[0]}: {e}')
    for line in patch_array:
        print(f'{line} is not up to date')
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

def _safe_ping_result(result):
    if result is None:
        return None, ""
    return result

def _validate_unit_connectivity(
    unit,
    false_positives,
    nuc_down,
    stale_vpn,
    truly_down,
    scrypted_outage=None,
    proxmox_outage=None,
):
    if scrypted_outage is None:
        scrypted_outage = []
    if proxmox_outage is None:
        proxmox_outage = []

    print(f'Checking {unit}...')
    code, output = _safe_ping_result(ping_router(unit))
    print(output)
    router_up = _ping_reachable(output)

    # Units >= 3300: router -> PVE only (never NUC). Scrypted only if both are up.
    if uses_pve(unit):
        print(f"3300+ unit — checking PVE (skipping NUC)..")
        code, pve_output = _safe_ping_result(ping_pve(unit))
        print(pve_output)
        pve_up = _ping_reachable(pve_output)

        if router_up and not pve_up:
            print(f"Router up, PVE down — offline compute: {unit}")
            nuc_down.append(unit)
            return

        if router_up and pve_up:
            print(f"Router and PVE up, checking Scrypted..")
            code, scrypt_output = _safe_ping_result(ping_scrypted(unit))
            print(scrypt_output)
            if _ping_reachable(scrypt_output):
                print(f"Router, PVE, and Scrypted are online — unit fully up: {unit}")
                false_positives.append(unit)
            else:
                print(f"Router and PVE up, Scrypted down — Scrypted outage: {unit}")
                scrypted_outage.append(unit)
            return

        if not router_up and not pve_up:
            print(f"Router and PVE down — unit fully down (skipping Scrypted): {unit}")
            truly_down.append(unit)
            return

        # Router down, PVE up
        print(f"Router down, PVE up on {unit}")
        truly_down.append(unit)
        return

    # Pre-3300 units
    if router_up:
        host = compute_host_label(unit)
        print(f"Router is up, {code}: {unit} checking {host.lower()}..")
        code, output = _safe_ping_result(ping_compute(unit))
        print(output)
        if _ping_reachable(output):
            print(f"Both {host} and Router are online {code}, false positive: {unit}")
            false_positives.append(unit)
        else:
            print(f"{host} is down, router is up. Bounce {host}.")
            nuc_down.append(unit)
        return

    # Router down (pre-3300)
    host = compute_host_label(unit)
    print(f'Router is down {code}, checking {host}')
    if in_potential_stale_vpn_range(unit):
        compute_result = ping_nuc(unit)
        host_checked = "NUC"
    else:
        compute_result = ping_compute(unit)
        host_checked = host
    code, output = _safe_ping_result(compute_result)
    print(output)
    if _ping_reachable(output):
        # Classic stale VPN (router down, compute up) — only for the 3000-3199 band
        if in_potential_stale_vpn_range(unit):
            print(f"{host_checked} is up {code}, router is down, potentially stale VPN on {unit}")
            stale_vpn.append(unit)
        else:
            print(f"{host_checked} is up {code}, router is down on {unit} (outside potential-stale range)")
            truly_down.append(unit)
    else:
        # Both unreachable: band 3000-3199 => potentially stale VPN; else truly down
        if in_potential_stale_vpn_range(unit):
            print(f"Router and NUC unreachable on {unit} (3000-3199) — potentially stale VPN")
            stale_vpn.append(unit)
        else:
            print(f"{host_checked} and router are offline. {code}")
            truly_down.append(unit)

def _issue_ticket_url(issue_id):
    if not issue_id:
        return ""
    return f"https://erp.sentracam.com/app/issue/{issue_id}"

def _with_ticket_links(units, unit_issue_map):
    linked = []
    for unit in units:
        issue_id = unit_issue_map.get(unit, "")
        linked.append({
            "unit": unit,
            "issue_id": issue_id,
            "url": _issue_ticket_url(issue_id),
        })
    return linked

def _print_linked_units(label, linked_units):
    print(label)
    for item in linked_units:
        if item.get("issue_id"):
            print(f'{item["unit"]} - {item["issue_id"]} - {item["url"]}')
        else:
            print(item["unit"])

def validate_issues_report(issue_path=None):
    if issue_path is None:
        issue_path = os.path.join(os.path.expanduser("~"), "Downloads", "Issue.csv")
    issue_units = []
    unit_issue_map = {}
    false_positives = []
    nuc_down = []
    stale_vpn = []
    truly_down = []
    scrypted_outage = []
    proxmox_outage = []

    try:
        with open(issue_path, 'r', newline='') as csvfile:
            linereader = csv.reader(csvfile)
            for line in linereader:
                if not line or len(line) < 2 or line[1] == 'Subject':
                    continue
                issue_id = (line[0] or "").strip()
                for net_row in net_array:
                    unit = net_row[0]
                    if unit in line[1] and unit not in issue_units and unit not in false_mu_array:
                        issue_units.append(unit)
                        unit_issue_map[unit] = issue_id
                        print(f'Matched {unit} ({issue_id}) in {line[1]}')
    except Exception as e:
        print(f'Task failed: {e}')
        return [], [], [], [], [], []

    print(f'Validating {len(issue_units)} units from issues report...')
    for unit in issue_units:
        _validate_unit_connectivity(
            unit,
            false_positives,
            nuc_down,
            stale_vpn,
            truly_down,
            scrypted_outage,
            proxmox_outage,
        )

    false_positives = _with_ticket_links(false_positives, unit_issue_map)
    nuc_down = _with_ticket_links(nuc_down, unit_issue_map)
    stale_vpn = _with_ticket_links(stale_vpn, unit_issue_map)
    truly_down = _with_ticket_links(truly_down, unit_issue_map)
    scrypted_outage = _with_ticket_links(scrypted_outage, unit_issue_map)
    proxmox_outage = _with_ticket_links(proxmox_outage, unit_issue_map)

    _print_linked_units("False positives (router and compute online):", false_positives)
    _print_linked_units("Offline compute (router up):", nuc_down)
    _print_linked_units("Potentially stale VPN (3000-3199 only):", stale_vpn)
    _print_linked_units("Truly down (router and compute offline):", truly_down)
    _print_linked_units("Scrypted outage (router+PVE up, Scrypted down):", scrypted_outage)
    _print_linked_units("Proxmox outage:", proxmox_outage)
    return false_positives, nuc_down, stale_vpn, truly_down, scrypted_outage, proxmox_outage

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
    proxmox_outage = []

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
                        proxmox_outage,
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
            and line not in proxmox_outage
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
    print("Proxmox outages")
    for line in proxmox_outage:
        print(line)
    return missing2, nuc_down, stale_vpn, scrypted_outage, proxmox_outage

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
    with open(false_mu, "r", newline='') as csvfile:
        linereader = csv.reader(csvfile)
        for row in linereader:
            false_mu_array.append(row[0])
        print('Loaded false positive MU list')

def generate_net_array():
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
        url = "https://erp.sentracam.com/api/resource/Component"
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
        url = "https://erp.sentracam.com/api/resource/Component"
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

