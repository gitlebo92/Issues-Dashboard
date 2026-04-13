import requests
import os
import sys
from dotenv import load_dotenv

def file_path(relative_path):
    try:
        BASEDIR = getattr(sys, 'frozen', False)
    except:
        BASEDIR = os.path.abspath('.')
    return os.path.join(BASEDIR, relative_path)

def file_path_two(relative_path):
    fullpath = os.path.join(os.path.dirname(sys.executable), relative_path) if getattr(sys, "frozen", False) else os.path.join(os.path.abspath('.'), relative_path)
    return fullpath

envpath = file_path_two('.env')
load_dotenv(envpath)

class Zabbix_Tool_Kit:
    def __init__(self):
        self.zbx_key = os.getenv("zab_token")
        self.url = os.getenv("zab_url")

    def grab_groupid(self):
        unit = input('Query Zabbix for unit ICMP status: ')
        host_list = []
        payload_hosts = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": ["hostid", "host"],
                "selectHostGroups": "extend",
            },
            "auth": self.zbx_key,
            "id": 1
        }

        response_hosts = requests.post(url=self.url, json=payload_hosts)
        response_hosts = response_hosts.json()
        data = response_hosts.get("result", [])
        for h in data:
            if h["host"][:6] == unit:
                print(f'Found host {h}')
                host_list.append(h)
                #print(h)
                break

        for item in host_list:
            for grp in item["hostgroups"]:
                gid = grp
                break
            print(f'Found gid: {gid["groupid"]}')
            #print(item["hostid"], item["hostgroups"])
            host_dict = {unit: gid["groupid"]}
            return unit, host_dict
        
        if not data:
            print('Not found')

    def grab_triggerids(self, unit, host_dict):

        trigger_id = []
        payload_problems = {
            "jsonrpc": "2.0",
            "method": "event.get",
            "params": {
                "output": ["eventid", "severity", "objectid"],
                "selectRelatedObject": ["triggerid", "description"],
                "groupids": host_dict[unit],
                "filter": {
                    "severity": 4,
                }                
            },
            "auth": self.zbx_key,
            "id": 1
        }

        response_problems = requests.post(url=self.url, json=payload_problems)
        response_problems = response_problems.json()
        
        data = response_problems.get("result", [])
        #print('Response problem =', response_problems)
        print('data =',data)
        if len(data) < 1:
            print("No events found")
            return
        
        for event in data:
             if "relatedObject" in event:
                trigger_id.append(event["relatedObject"]["triggerid"])
                print(f'Added {event["relatedObject"]["triggerid"]} to trigger id array for host matching...')
                print(f'{unit} - ' + f'{event["relatedObject"]["description"]}')

        return trigger_id

    def query_zabbix_events(self):
        unit, host_dict = self.grab_groupid()
        return self.grab_triggerids(unit, host_dict)            

if __name__ == '__main__':
    zbx = Zabbix_Tool_Kit()
    check = zbx.query_zabbix_events()

    