import csv


erp_link = "https://erp.sentracam.com/app/task/"
issues_array = []


with open(r"C:/Users/andrew.leibowitz/Documents/PY_WORK_NEW_FINAL/Dev/work_tool/filtered_mesh_vpn_test.csv", "r") as csvfile:
    linereader = csv.reader(csvfile)
    for line in linereader:
        issues_array.append(line[0])

    for i, issue in enumerate(issues_array):
        issues_array[i] = erp_link + str(issue)
        
		

print(issues_array)
