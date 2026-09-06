import csv
import os

from dotenv import load_dotenv

load_dotenv()
_work_tld = (os.getenv("workTLD") or "").strip().strip('"').strip("'")
erp_link = f"https://erp.{_work_tld}/app/task/"
issues_array = []

# Prefer MESH_CSV / local test file next to this script (portable for coworkers).
_mesh_csv = (os.getenv("MESH_CSV") or "").strip().strip('"').strip("'")
if not _mesh_csv:
    _mesh_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "filtered_mesh_vpn_test.csv")

with open(_mesh_csv, "r", newline="") as csvfile:
    linereader = csv.reader(csvfile)
    for line in linereader:
        if line:
            issues_array.append(line[0])

    for i, issue in enumerate(issues_array):
        issues_array[i] = erp_link + str(issue)

print(issues_array)
