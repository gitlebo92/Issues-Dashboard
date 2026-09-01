import os
import requests
from requests.auth import HTTPBasicAuth

username = os.getenv("myemail")
password = os.getenv("mypass")

ART_DATA_URL = "https://art.sentracam.com/art/selectReportParameters?reportId=152"

payload = {
    "reportFormat": "csv"
}

# 1. Use POST instead of GET
# 2. Pass 'data=payload' (or 'params=payload' if ART expects query params)
response = requests.post(
    url=ART_DATA_URL,
    data=payload,
    auth=HTTPBasicAuth(username, password),
    timeout=30
)

print("Status Code:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print("Raw Response:", response.text)