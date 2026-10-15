"""
Throwaway script for testing new diagnostics.py functions in isolation.
Run/debug THIS file (not diagnostics.py directly) from the repo root
(Dev\\work_tool) so `import zabbix_tool` etc. resolve.

Netsheet columns (net_sheet.csv):
0 Unit/Site  1 Router IP  2 Switch IP  3 NUC IP   4 Speaker IP
5 Fisheye    6 Camera 1   7 Camera 2   8 Camera 3 9 Camera 4
10 Relay     11 PVE       12 Scrypted
"""
import asyncio
from scrypted_sdk import connect_scrypted_client
import paramiko
import work_tool
import os
import requests
import time
from requests.auth import HTTPDigestAuth
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

UNIT = "RD3071"
UNIT2 = "RD3417"  # change to whatever unit you're testing against


async def get_rooms_scrypted(unit):
    username, password = work_tool._scrypted_web_credentials()
    tld = work_tool.work_tld()
    base_url = f"https://{unit.lower()}.{tld}"
    loop = asyncio.get_running_loop()
    transport, sdk = await connect_scrypted_client(loop, base_url, username, password)
    states =  sdk.systemManager.getSystemState()
    C1_180_ROOM = None
    C1_PTZ_ROOM = None
    C2_180_ROOM = None
    C2_PTZ_ROOM = None
    FISHEYE_ROOM = None

    rooms = {}
    for device_id, state in states.items():
        if "SC" in state["name"]["value"] and "AA" not in state["name"]["value"] and "TT" not in state["name"]["value"]:    
            print(f"{state["name"]}")
            print(f"Device ID: {device_id}")
            print(f"Room: {state["room"]}")

            rooms[f"{device_id}"] = {
                "name":state["name"]["value"],
                "room":state["room"]["value"]
            }

            for key, value in rooms.items():
                print(key)
                print(value["name"])
                print(value["room"])
                if "C1-180" in value["name"]:
                    C1_180_ROOM = value["room"]
                    print(f"Saved SC-{unit}-C1-180 Room: {value["room"]} ")
                if "C1-PTZ" in value["name"]:
                    C1_PTZ_ROOM = value["room"]
                    print(f"Saved SC-{unit}-C1-PTZ Room: {value["room"]} ")
                if "C2-180" in value["name"]:
                    C2_180_ROOM = value["room"]
                    print(f"Saved SC-{unit}-C2-180 Room: {value["room"]} ")
                if "C2-PTZ" in value["name"]:
                    C2_PTZ_ROOM = value["room"]
                    print(f"Saved SC-{unit}-C2-PTZ Room: {value["room"]} ")
                if "Fisheye" in value["name"]:
                    FISHEYE_ROOM = value["room"]
                    print(f"Saved SC-{unit}-Fisheye Room: {value["room"]} ")

    return rooms, C1_180_ROOM, C1_PTZ_ROOM, C2_180_ROOM, C2_PTZ_ROOM, FISHEYE_ROOM
        

def ram_folder_populating(unit):

    unit = str(unit or "").strip()
    if not unit:
        return None, "Missing unit"
    row, scrypted_ip, error = work_tool._scrypted_ssh_target(unit)
    if error:
        return None, error

    username, password = work_tool._scrypted_ssh_credentials()

    scrypted_ssh_client = paramiko.SSHClient()
    scrypted_ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    cmd = f"echo {password} | sudo -S bash -c 'cd /mnt/ram/cameras && ls -lha'"


    # fisheye_room = None
    # c1_180_room = None
    # c1_ptz_room = None
    # c2_180_room= None
    # c2_ptz_room= None
    #rooms, c1_180_room, c1_ptz_room, c2_180_room, c2_ptz_room, fisheye_room = asyncio.run(get_rooms_scrypted(unit))
    folder_rooms = []
    try:
        scrypted_ssh_client.connect(hostname=scrypted_ip, username=username, password=password, timeout=30)
        stdin, stdout, stderr = scrypted_ssh_client.exec_command(cmd, timeout=30)
        output = stdout.read().decode("utf-8")
        errors = stderr.read().decode("utf-8")

        if errors:
            print(f"{errors}")
            pass
        output = output.splitlines()
        for line in output:
            parts = line.split()
            if len(parts) == 9:
                folder_room = parts[8]
                if len(folder_room) > 2:
                    print(folder_room)
                    folder_rooms.append(folder_room)
        for folder_room in folder_rooms:
            counter = 0
            cmd2 = f"echo {password} | sudo -S bash -c 'ls /mnt/ram/cameras/{folder_room}/fullsize'"
            try:
                stdin2, stdout2, stderr2 = scrypted_ssh_client.exec_command(cmd2)
                errors2 = stderr2.read().decode("utf-8")
                output2 = stdout2.read().decode("utf-8")
                if errors2:
                    print(errors2)
                output2 = output2.splitlines()
                for line in output2:
                    counter+=1
                    print(line)
                    if counter == 5:
                        break
                if counter > 4:
                    print(f"{folder_room} is successfully populating RAM drive")
                else:
                    print(f"{folder_room} is failing to populate RAM drive")
            except Exception as e:
                print(e)
    except Exception as e:
        print(e)
    finally:
        scrypted_ssh_client.close()


async def create_cameras_scrypted(unit):
    rows, error = work_tool.camera_rooms(unit)
    by_target = {row["target"]: row["room"] for row in rows}
    FISHEYE_ROOM = by_target.get("fisheye")
    C1_180_ROOM = by_target.get("camera1")
    C1_PTZ_ROOM = by_target.get("camera1-ptz")
    C2_180_ROOM = by_target.get("camera2")
    C2_PTZ_ROOM = by_target.get("camera2-ptz")
    username, password = work_tool._scrypted_web_credentials()
    tld = work_tool.work_tld()
    base_url = f"https://{unit.lower()}.{tld}"
    loop = asyncio.get_running_loop()
    transport, sdk = await connect_scrypted_client(loop, base_url, username, password)
    try:
        await sdk.deviceManager.createDeviceState({
            "nativeId": "101",
            "name": f"SC-{unit}-FISHEYE",
            "username": username,
            "password": password,
            "room": FISHEYE_ROOM
        })
        await sdk.deviceManager.createDeviceState({
            "nativeId": "102",
            "name": f"SC-{unit}-C1-180",
            "username": username,
            "password": password,
            "room": C1_180_ROOM
        })
        await sdk.deviceManager.createDeviceState({
            "nativeId": "103",
            "name": f"SC-{unit}-C1-PTZ",
            "username": username,
            "password": password,
            "room": C1_PTZ_ROOM
        })
        await sdk.deviceManager.createDeviceState({
            "nativeId": "104",
            "name": f"SC-{unit}-C2-180",
            "username": username,
            "password": password,
            "room": C2_180_ROOM
        })
        await sdk.deviceManager.createDeviceState({
            "nativeId": "105",
            "name": f"SC-{unit}-C2-PTZ",
            "username": username,
            "password": password,
            "room": C2_PTZ_ROOM
        })
    except Exception as e:
        print(e)
    finally:
        transport.close()

def find_cameras(UNIT):
    camera_array = []
    camera_dict = {}
    router_ip = work_tool.get_router_ip(UNIT)
    #print(router_ip)
    port = 10000
    routeruser = os.getenv("routeruser")
    routerpass = os.getenv("routerpass")
    routerSshObject = paramiko.SSHClient()
    routerSshObject.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cmd1 = "/ip dhcp-server lease print"
    try:
        routerSshObject.connect(hostname=router_ip, port=port, username=routeruser, password=routerpass, timeout=30)
        stdin, stdout, stderr = routerSshObject.exec_command(cmd1, timeout=30)
        errors = stderr.read().decode("utf-8")
        output = stdout.read().decode("utf-8")
        if errors:
            print(errors)
        if output:
            output = output.splitlines()
            for line in output:
                if "FC:5F:49" in line:
                    camera_array.append(line.split(" "))

            for i in range(len(camera_array)):
                j = 0
                print(camera_array[i])
                while j < len(camera_array):
                        if j == i:
                            j += 1
                            continue

                        i_octet = int(camera_array[i][1].split(".")[3])
                        j_octet = int(camera_array[j][1].split(".")[3])
                        print(f"camera array[{i}] octet = {i_octet}")
                        print(f"camera array[{j}] octet = {j_octet}")

                        if i_octet < j_octet:
                            curr_pos = camera_array[i]
                            next_pos = camera_array[j]
                            camera_array[i] = next_pos
                            camera_array[j] = curr_pos
                        j += 1
        for i in range(len(camera_array)):    
            cam_name = camera_array[i][5]
            cam_ip = camera_array[i][1]
            camera_dict[cam_name]=cam_ip
        for key, value in camera_dict.items():
            print(key,value)
    except Exception as e:
        print(e)
    finally:
        routerSshObject.close()

def read_component(UNIT):
    workTLD = os.getenv("workTLD")
    erp_token = os.getenv("erp_token")
    endpoint = f"https://erp.{workTLD}/api/resource/Component/SC-{UNIT}"
    headers = work_tool._erp_headers()

    response = requests.get(url=endpoint, headers=headers)
    data = response.json()
    return data

def dst_fix(UNIT):
    is_http = True
    fishuser = os.getenv("fishuser")
    fishpass = os.getenv("fishpass")
    pveuser = os.getenv("pvesshuser")
    pvepass = os.getenv("pvepass")
    fiship = work_tool.get_fisheye_ip(UNIT)
    pveip = work_tool.get_pve_ip(UNIT)
    dst_endpoint = f"http://{fiship}:80/cgi-bin/configManager.cgi?action=getConfig&name=Locales"
    dst_endpoint_put = f"http://{fiship}:80/cgi-bin/configManager.cgi?action=setConfig&Locales.DSTEnable=false"
    dst_endpoint_put_back = f"http://{fiship}:80/cgi-bin/configManager.cgi?action=setConfig&Locales.DSTEnable=true"
    
    try:
        response = requests.get(url=dst_endpoint, auth=HTTPDigestAuth(username=fishuser, password=fishpass))
        print(response.text)
    except Exception as e:
        print("Request failed likely wrong port, set is_http == False")
        print(e)
        is_http = False
    if is_http == False:
        dst_endpoint = f"http://{fiship}:10080/cgi-bin/configManager.cgi?action=getConfig&name=Locales"
        dst_endpoint_put = f"http://{fiship}:10080/cgi-bin/configManager.cgi?action=setConfig&Locales.DSTEnable=false"
        dst_endpoint_put_back = f"http://{fiship}:10080/cgi-bin/configManager.cgi?action=setConfig&Locales.DSTEnable=true"


    try:
        response2 = requests.get(url=dst_endpoint_put,auth=HTTPDigestAuth(username=fishuser,password=fishpass))
        print(response2.text)
        print(response2.status_code)
        print("Disabled DST")
        if response2.status_code == 200:
            cmd = "vm restart 101"
            scryptSsh = paramiko.SSHClient()
            scryptSsh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                print("Restarting scrypted...")
                scryptSsh.connect(hostname=pveip, username=pveuser, password=pvepass)
                stdin, stdout, stderr = scryptSsh.exec_command(cmd)
                errors = stderr
                output = stdout
                if errors:
                    print(errors)
                if output:
                    print(output)
                print("Scrypted restarted, waiting 30 seconds for scrypted to come back online")
                time.sleep(30)
                # try:
                #     response = requests.get(url=dst_endpoint, auth=HTTPDigestAuth(username=fishuser, password=fishpass))
                #     print(response.text)
                # except Exception as e:
                #     print(e)
                print("Re-enabling DST")
                try:
                    response3 = requests.get(url=dst_endpoint_put_back, auth=HTTPDigestAuth(username=fishuser, password=fishpass))
                    print(response3.text)
                    if response3.status_code == 200:
                        print("Reenabled DST")
                except Exception as e:
                    print(e)
            except Exception as e:
                print(e)
            finally:
                scryptSsh.close()
    except Exception as e:
        print(e)
    try:
        response = requests.get(url=dst_endpoint, auth=HTTPDigestAuth(username=fishuser, password=fishpass))
        print(response.text)
    except Exception as e:
        print(e)

def dst_fix_all(cam_list):
    for unit in cam_list:
        print(f"fixing {unit}...")
        dst_fix(unit)
        print("Fixed")

def restart_nuc(UNIT):
    nuc_ip = work_tool.get_nuc_ip(UNIT)
    nucSshObject = paramiko.SSHClient()
    nucSshObject.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    username = os.getenv("nucuser")
    password = os.getenv("nucpass")

    cmd = r"shutdown /r /t 1"

    try:
        nucSshObject.connect(hostname=nuc_ip, username=username, password=password, timeout=30)
        print('Connected. Restarting...')
        stdin, stdout, stderr = nucSshObject.exec_command(cmd)
        errors = stderr.read().decode("utf-8")
        output = stdout.read().decode("utf-8")
        if errors:
            print(errors)
        if output:
            print(output)
    except Exception as e:
        print(e)
    finally:
        nucSshObject.close()

def verify_security_fix(UNIT):
    scrypted_ip = work_tool._scrypted_ip(UNIT)
    username = os.getenv("scryptuser")




def main():
    row = work_tool.ensure_unit_net_info(UNIT, needed_indexes=(3,))
    if not row:
        print(f"{UNIT} not found in net sheet")
        return
    # find_cameras(UNIT)
    # read_component(UNIT)
    # restart_nuc(UNIT)
    # dst_fix(UNIT2)
    cam_list = work_tool.get_all_empty_folder_units()
    dst_fix_all(cam_list)
if __name__ == "__main__":
    main()
