from flask import Flask, request, jsonify, render_template
import os
import requests
import work_tool
from datetime import datetime

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
                    return render_template("result.html",
                    unit=unit,
                    siteId=siteId,
                    lastseen=lastseen
                    )
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

    mesh_outage.save(mesh_path)
    issues.save(issue_path)
    work_tool.compare_reports(issue_path, mesh_path)
    work_tool.clear_old_reports(mesh_path, issue_path)
    missing2, nuc_down, stale_vpn = work_tool.validate_reports_mesh()
    return jsonify({
    "message": "Filtered outage report",
    "missing": missing2,
    "nuc_down": nuc_down,
    "stale_vpn": stale_vpn
}), 200
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)