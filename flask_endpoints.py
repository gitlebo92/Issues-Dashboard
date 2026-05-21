from flask import Flask, request, jsonify, render_template
import os
import requests
import work_tool
from datetime import datetime
import time
import json

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def dedupe(lst):
    return list(dict.fromkeys(lst))

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")
@app.route("/victron", methods=["GET"])
def victron_form():
    return render_template("vrm.html")
@app.route("/outage_filter", methods=["GET"])
def outage_form():
    return render_template("outage.html")
@app.route("/zabbix", methods=["GET"])
def zabbix_form():
    return render_template("zabbix.html")
@app.route("/victron/results", methods=["POST"])
def install_checker():
    idUser = os.getenv("idUser")
    api_token = os.getenv("victron_token")
    url = f"https://vrmapi.victronenergy.com/v2/users/{idUser}/installations"
    headers = {
        "idUser": f"{idUser}",
        "X-Authorization": f"Token {api_token}"
    }
    unit = request.form.get("unit")
    if not unit:
        return "No unit provided"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return "VRM request failed" 
    data = response.json()
    battery_instance = None
    solar_instance = None
    voltage = None
    amps = None
    temp = None
    ftemp = None
    high_volt_alarm = None
    low_volt_alarm = None
    for record in data.get("records", []):
        if (record.get("name") or "")[-4:] == unit[-4:]:
            print('Unit is added to VRM')
            print(f"Site ID for {unit} is {record.get('idSite')}")
            siteId = record.get('idSite')
            url2 = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/system-overview"
            response2 = requests.get(url2, headers=headers)
            data2 = response2.json()
            for device in data2.get("records", {}).get("devices", []):
                if device["name"] == "Gateway":
                    lastseen = device.get("lastConnection")
                    if isinstance(lastseen, (int, float)):
                        lastseen = datetime.fromtimestamp(lastseen).strftime("%H:%M:%S on %m/%d/%Y") 

                elif "battery" in device.get("name").lower():
                    battery_instance = device.get("instance")
                    print("battery instance: " + str(battery_instance))
                elif "solar charger" in device.get("name").lower():
                    solar_instance = device.get("instance")
                    print("solar instance: " + str(solar_instance))
            if battery_instance is not None:
                url_battery = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/widgets/BatterySummary?instance={battery_instance}"
                battery_response = requests.get(url_battery, headers=headers)
                battery_data = battery_response.json()
                print("--- BATTERY DATA (SOC, Voltage, etc.) ---")
                print(json.dumps(battery_data, indent=2))
                for instance in battery_data.get("records", {}).get("data", {}).values():
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Voltage":
                        voltage = instance["valueFormattedWithUnit"]
                            
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Current":
                        print('hit')
                        amps = instance["valueFormattedWithUnit"]
                        print(f'amps: {amps}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Temperature":
                        print('hit')
                        temp = float(instance["valueFormattedValueOnly"])
                        ftemp = temp * 1.8 + 32
                        ftemp = round(ftemp, 2)
                        ftemp = str(ftemp) + " \u00b0F"
                        print(f'temp: {ftemp}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Alarms/LowVoltage":
                        print('hit')
                        low_volt_alarm = instance["valueFormattedWithUnit"]
                        print(f'Low voltage alarm status: {low_volt_alarm}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Alarms/HighVoltage":
                        print('hit')
                        high_volt_alarm = instance["valueFormattedWithUnit"]
                        print(f'High voltage alarm status: {high_volt_alarm}')

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Soc":
                        print('hit')
                        soc = instance["valueFormattedWithUnit"]
                        print(f'State of Charge: {soc}')


                return render_template("result.html",
                unit=unit,
                siteId=siteId,
                lastseen=lastseen,
                soc=soc,
                voltage=voltage,
                amps=amps,
                ftemp=ftemp,
                high_volt_alarm=high_volt_alarm,
                low_volt_alarm=low_volt_alarm
                
                )
                print("No Battery instance found in system overview.")

            if solar_instance is not None:
                url_solar = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/widgets/SolarChargerSummary?instance={solar_instance}"
                solar_response = requests.get(url_solar, headers=headers)
                solar_data = solar_response.json()
                #print("--- SOLAR DATA (Watts, Yield, etc.) ---")
                #print(json.dumps(solar_data, indent=2))
            else:
                print("No Solar Charger instance found in system overview.")

            return "Gateway not found"                
    return "Unit not found in VRM"
@app.route("/outage_filter/results", methods=["POST"])
def outage_filter():
    #net_array = []
    #false_mu = []
    work_tool.generate_false_mu()
    work_tool.generate_net_array()
    print("Generated")
    mesh_outage = request.files.get("mesh_file")
    issues = request.files.get("issue_file")

    if not mesh_outage or not issues:
        return "Missing Files", 400
    mesh_path = os.path.join(UPLOAD_FOLDER, mesh_outage.filename)
    issue_path = os.path.join(UPLOAD_FOLDER, issues.filename)
    local_mesh = r"C:\Users\andrew.leibowitz\Downloads\filtered_mesh_vpn.csv"
    local_issue = r"C:\Users\andrew.leibowitz\Downloads\Issue.csv"
    mesh_outage.save(mesh_path)
    issues.save(issue_path)
    mesh_outage.close()
    issues.close()
    work_tool.compare_reports(issue_path, mesh_path)
    work_tool.clear_old_reports(mesh_path, issue_path)

    missing2, nuc_down, stale_vpn = work_tool.validate_reports_mesh()
    try:
        os.remove(local_issue)
        os.remove(local_mesh)
        print("removed local files")
    except Exception as e:
        print(f"{e}: Failed, continuing with validation")
    return jsonify({
    "message": "Filtered outage report",
    "missing": missing2,
    "nuc_down": nuc_down,
    "stale_vpn": stale_vpn
}), 200
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)