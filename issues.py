import csv
import os

from dotenv import load_dotenv

load_dotenv()
_work_tld = (os.getenv("workTLD") or "").strip().strip('"').strip("'")
_pcuser = (os.getenv("pcuser") or "").strip().strip('"').strip("'")
erp_link = f"https://erp.{_work_tld}/app/task/"
issues_array = []


with open(fr"C:/Users/{_pcuser}/Documents/PY_WORK_NEW_FINAL/Dev/work_tool/filtered_mesh_vpn_test.csv", "r") as csvfile:
    linereader = csv.reader(csvfile)
    for line in linereader:
        issues_array.append(line[0])

    for i, issue in enumerate(issues_array):
        issues_array[i] = erp_link + str(issue)
        
		

print(issues_array)
