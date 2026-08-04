from flask import Flask, request, jsonify, render_template, Response, redirect, url_for
import os
import requests
import work_tool
from datetime import datetime
import time
import json
import uuid
import threading
import queue
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

issue_jobs = {}
stream_jobs = issue_jobs  # shared job store for streamed validations

def dedupe(lst):
    return list(dict.fromkeys(lst))

class JobStdout:
    """Tee stdout into a per-job queue so the browser can stream it. This endpoint was created by Cursor reusing code I wrote from work tool"""
    def __init__(self, job_id, original):
        self.job_id = job_id
        self.original = original
        self._buf = ""

    def write(self, text):
        if self.original:
            self.original.write(text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            job = stream_jobs.get(self.job_id)
            if job is not None:
                job["queue"].put({"type": "log", "line": line})
        return len(text)

    def flush(self):
        if self.original:
            self.original.flush()

def _run_issues_validation(job_id, issue_path):
    import sys
    job = stream_jobs[job_id]
    original_stdout = sys.stdout
    sys.stdout = JobStdout(job_id, original_stdout)
    try:
        work_tool.generate_false_mu()
        work_tool.generate_net_array()
        false_positives, nuc_down, stale_vpn, truly_down, scrypted_outage, proxmox_outage = work_tool.validate_issues_report(issue_path)
        job["results"] = {
            "false_positives": false_positives,
            "nuc_down": nuc_down,
            "stale_vpn": stale_vpn,
            "truly_down": truly_down,
            "scrypted_outage": scrypted_outage,
            "proxmox_outage": proxmox_outage,
        }
        job["queue"].put({"type": "done", "results": job["results"]})
    except Exception as e:
        job["queue"].put({"type": "log", "line": f"ERROR: {e}"})
        job["queue"].put({"type": "done", "results": {
            "false_positives": [],
            "nuc_down": [],
            "stale_vpn": [],
            "truly_down": [],
            "scrypted_outage": [],
            "proxmox_outage": [],
        }})
    finally:
        sys.stdout = original_stdout
        try:
            os.remove(issue_path)
        except Exception as e:
            print(f"Failed to remove upload: {e}")
        job["done"] = True

def _run_recovery_email_check(job_id, report_path):
    import sys
    job = stream_jobs[job_id]
    original_stdout = sys.stdout
    sys.stdout = JobStdout(job_id, original_stdout)
    try:
        work_tool.generate_false_mu()
        work_tool.generate_net_array()
        needs_recovery_email, needs_initial_email, potential_false_positive, pending_recovery, email_status_up_to_date = work_tool.check_missing_recovery_emails(report_path)
        job["results"] = {
            "needs_recovery_email": needs_recovery_email,
            "needs_initial_email": needs_initial_email,
            "potential_false_positive": potential_false_positive,
            "pending_recovery": pending_recovery,
            "email_status_up_to_date": email_status_up_to_date,
        }
        job["queue"].put({"type": "done", "results": job["results"]})
    except Exception as e:
        job["queue"].put({"type": "log", "line": f"ERROR: {e}"})
        job["queue"].put({"type": "done", "results": {
            "needs_recovery_email": [],
            "needs_initial_email": [],
            "potential_false_positive": [],
            "pending_recovery": [],
            "email_status_up_to_date": [],
        }})
    finally:
        sys.stdout = original_stdout
        try:
            os.remove(report_path)
        except Exception as e:
            print(f"Failed to remove upload: {e}")
        job["done"] = True

def _sse_stream(job_id):
    job = stream_jobs.get(job_id)
    if job is None:
        return "Unknown job", 404

    def event_stream():
        while True:
            try:
                event = job["queue"].get(timeout=1)
            except queue.Empty:
                if job["done"]:
                    break
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "done":
                break

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")
@app.route("/victron", methods=["GET"])
def victron_form():
    return render_template("vrm.html")
@app.route("/outage_filter", methods=["GET"])
def outage_form():
    return render_template("outage.html")
@app.route("/issues", methods=["GET"])
def issues_form():
    return render_template("issues.html")
@app.route("/issues/results", methods=["POST"])
def issues_results():
    issues = request.files.get("issue_file")
    if not issues:
        return "Missing Issue CSV", 400
    job_id = uuid.uuid4().hex
    issue_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{issues.filename}")
    issues.save(issue_path)
    issues.close()
    stream_jobs[job_id] = {
        "queue": queue.Queue(),
        "done": False,
        "results": None,
    }
    thread = threading.Thread(target=_run_issues_validation, args=(job_id, issue_path), daemon=True)
    thread.start()
    return redirect(url_for("issues_watch", job_id=job_id))

@app.route("/issues/watch/<job_id>", methods=["GET"])
def issues_watch(job_id):
    if job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template("issues_results.html", job_id=job_id)

@app.route("/issues/stream/<job_id>", methods=["GET"])
def issues_stream(job_id):
    return _sse_stream(job_id)

@app.route("/recovery_email", methods=["GET"])
def recovery_email_form():
    return render_template("recovery_email.html")

@app.route("/recovery_email/results", methods=["POST"])
def recovery_email_results():
    report = request.files.get("report_file")
    if not report:
        return "Missing report file", 400
    job_id = uuid.uuid4().hex
    report_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{report.filename}")
    report.save(report_path)
    report.close()
    stream_jobs[job_id] = {
        "queue": queue.Queue(),
        "done": False,
        "results": None,
    }
    thread = threading.Thread(target=_run_recovery_email_check, args=(job_id, report_path), daemon=True)
    thread.start()
    return redirect(url_for("recovery_email_watch", job_id=job_id))

@app.route("/recovery_email/watch/<job_id>", methods=["GET"])
def recovery_email_watch(job_id):
    if job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template("recovery_email_results.html", job_id=job_id)

@app.route("/recovery_email/stream/<job_id>", methods=["GET"])
def recovery_email_stream(job_id):
    return _sse_stream(job_id)

def _run_linux_diagnostic(job_id, unit):
    import sys
    job = stream_jobs[job_id]
    original_stdout = sys.stdout
    sys.stdout = JobStdout(job_id, original_stdout)
    try:
        work_tool.generate_false_mu()
        work_tool.generate_net_array()
        result = work_tool.run_linux_diagnostic(unit)
        job["results"] = result
        job["queue"].put({"type": "done", "results": result})
    except Exception as e:
        job["queue"].put({"type": "log", "line": f"ERROR: {e}"})
        job["queue"].put({"type": "done", "results": {
            "unit": unit or "",
            "hostname": "",
            "connected": False,
            "output": "",
            "error": str(e),
        }})
    finally:
        sys.stdout = original_stdout
        job["done"] = True

@app.route("/zabbix", methods=["GET"])
def zabbix_form():
    return render_template("zabbix.html")
@app.route("/linux", methods=["GET"])
def linux_form():
    return render_template("linux.html")
@app.route("/linux/results", methods=["POST"])
def linux_results():
    unit = (request.form.get("unit") or "").strip()
    if not unit:
        return "No unit provided", 400
    job_id = uuid.uuid4().hex
    stream_jobs[job_id] = {
        "queue": queue.Queue(),
        "done": False,
        "results": None,
    }
    thread = threading.Thread(target=_run_linux_diagnostic, args=(job_id, unit), daemon=True)
    thread.start()
    return redirect(url_for("linux_watch", job_id=job_id))

@app.route("/linux/watch/<job_id>", methods=["GET"])
def linux_watch(job_id):
    if job_id not in stream_jobs:
        return "Unknown job", 404
    return render_template("linux_results.html", job_id=job_id)

@app.route("/linux/stream/<job_id>", methods=["GET"])
def linux_stream(job_id):
    return _sse_stream(job_id)
@app.route("/victron/results", methods=["POST"])
def install_checker():
    idUser = (os.getenv("idUser") or "").strip()
    api_token = (os.getenv("victron_token") or "").strip()
    if not idUser or not api_token:
        return (
            "VRM credentials missing: set idUser and victron_token in work_tool/.env",
            500,
        )
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
        return f"VRM request failed: {response.status_code}" 
    data = response.json()
    battery_instance = None
    solar_instance = None
    voltage = None
    current = None
    amps = None
    temp = None
    ftemp = None
    high_volt_alarm = None
    low_volt_alarm = None
    today_yield = None
    yesterday_yield = None
    soc=None

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
                # print(json.dumps(battery_data, indent=2))
                for instance in battery_data.get("records", {}).get("data", {}).values():
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Voltage":
                        voltage = instance["valueFormattedWithUnit"]
                            
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/Dc/0/Current":
                        print('hit')
                        current = instance["valueFormattedWithUnit"]
                        print(f'amps: {current}')

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

            if solar_instance is not None:
                url_solar = f"https://vrmapi.victronenergy.com/v2/installations/{siteId}/widgets/SolarChargerSummary?instance={solar_instance}"
                solar_response = requests.get(url_solar, headers=headers)
                solar_data = solar_response.json()
                #print(json.dumps(solar_data, indent=2))
                for instance in solar_data.get("records", {}).get("data", {}).values():
                    if isinstance(instance, dict) and instance.get("dbusPath") == "/History/Daily/0/Yield":
                        today_yield = instance.get("valueFormattedWithUnit")
                        print(today_yield)

                    if isinstance(instance, dict) and instance.get("dbusPath") == "/History/Daily/1/Yield":
                        yesterday_yield = instance.get("valueFormattedWithUnit")
                        print('hit yesterday')
                        print(yesterday_yield)

                    if isinstance(instance, dict) and instance.get("dataAttributeName") == "Battery watts":
                        print('hit watts')
                        watts = instance.get("valueFormattedWithUnit")
                        print(watts)

                return render_template("result.html",
                unit=unit,
                siteId=siteId,
                lastseen=lastseen,
                soc=soc,
                watts=watts,
                voltage=voltage,
                current=current,
                ftemp=ftemp,
                high_volt_alarm=high_volt_alarm,
                low_volt_alarm=low_volt_alarm,
                today_yield=today_yield,
                yesterday_yield=yesterday_yield
                )

            else:
                print("No Solar Charger instance found in system overview.")

            return "Gateway not found"                
    return "Unit not found in VRM"
@app.route("/outage_filter/results", methods=["POST"])
def outage_filter():
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

    missing2, nuc_down, stale_vpn, scrypted_outage, proxmox_outage = work_tool.validate_reports_mesh()
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
    "stale_vpn": stale_vpn,
    "scrypted_outage": scrypted_outage,
    "proxmox_outage": proxmox_outage,
}), 200
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)