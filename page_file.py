"""
Pull RAM and page file metrics from NUC hosts in Zabbix (e.g. RD3396-NUC).

Requires in .env (same as zabbix_tool.py):
  zab_url   - Zabbix JSON-RPC endpoint, e.g. https://zabbix.example.com/api_jsonrpc.php
  zab_token - Zabbix API token

Usage:
  python page_file.py
  python page_file.py --csv nuc_memory.csv
  python page_file.py --discover FD2002-NUC
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

load_dotenv()

# Preferred Zabbix item keys (Windows agent / Zabbix templates).
PREFERRED_KEYS = {
    "ram_total": "vm.memory.size[total]",
    "ram_used": "vm.memory.size[used]",
    "ram_util_pct": "vm.memory.util",
    "pagefile_total": "system.swap.size[,total]",
    "pagefile_free": "system.swap.free",
    "pagefile_free_pct": "system.swap.pfree",
    "pagefile_used_pct": 'perf_counter_en["\\Paging file(_Total)\\% Usage"]',
}

@dataclass
class HostMetrics:
    host: str
    unit: str
    values: dict[str, str | None] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


class ZabbixClient:
    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self._id = 0

    def call(self, method: str, params: dict) -> list | dict:
        self._id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "auth": self.token,
            "id": self._id,
        }
        response = requests.post(self.url, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"Zabbix API error: {err.get('message', err)}")
        return data.get("result", [])


def is_nuc_host(hostname: str) -> bool:
    host = hostname.upper()
    return "-SNUC" not in host and (host.endswith("-NUC") or host.endswith("NUC"))


def unit_from_host(hostname: str) -> str:
    host = hostname.upper()
    if host.endswith("-NUC"):
        return host[:-4]
    if host.endswith("NUC"):
        return host[:-3]
    return host.split("-", 1)[0]


BYTE_METRICS = ("ram_total", "ram_used", "pagefile_total", "pagefile_free")
PCT_METRICS = ("ram_util_pct", "pagefile_free_pct", "pagefile_used_pct")


def fmt_bytes(value: str | None, *, empty: str = "N/A") -> str:
    if value in (None, ""):
        return empty
    try:
        nbytes = int(float(value))
    except ValueError:
        return value
    if nbytes >= 1024 ** 4:
        return f"{nbytes / (1024 ** 4):.2f} TB"
    if nbytes >= 1024 ** 3:
        return f"{nbytes / (1024 ** 3):.2f} GB"
    return f"{nbytes / (1024 ** 2):.2f} MB"


def fmt_pct(value: str | None, *, empty: str = "N/A") -> str:
    if value in (None, ""):
        return empty
    try:
        return f"{float(value):.1f}%"
    except ValueError:
        return value


def fmt_metric(metric: str, value: str | None, *, empty: str = "N/A") -> str:
    if metric in BYTE_METRICS:
        return fmt_bytes(value, empty=empty)
    if metric in PCT_METRICS:
        return fmt_pct(value, empty=empty)
    return value or empty


def get_nuc_hosts(client: ZabbixClient) -> list[dict]:
    hosts = client.call(
        "host.get",
        {
            "output": ["hostid", "host", "name"],
            "filter": {"status": 0},
            "search": {"host": "*-NUC"},
            "searchWildcardsEnabled": True,
        },
    )
    matched = [h for h in hosts if is_nuc_host(h.get("host", ""))]
    return sorted(matched, key=lambda h: h.get("host", ""))


KEY_TO_METRIC = {v: k for k, v in PREFERRED_KEYS.items()}
METRIC_KEYS = list(PREFERRED_KEYS.values())
HOST_CHUNK_SIZE = 50


def fetch_metric_items(client: ZabbixClient, hostids: list[str]) -> list[dict]:
    if not hostids:
        return []
    return client.call(
        "item.get",
        {
            "output": ["hostid", "key_", "lastvalue"],
            "hostids": hostids,
            "filter": {"key_": METRIC_KEYS},
            "monitored": True,
        },
    )


def collect_metrics(client: ZabbixClient, hosts: list[dict]) -> list[HostMetrics]:
    results: list[HostMetrics] = []
    for i in range(0, len(hosts), HOST_CHUNK_SIZE):
        chunk = hosts[i : i + HOST_CHUNK_SIZE]
        items_by_host: dict[str, dict[str, str | None]] = {
            host["hostid"]: {} for host in chunk
        }
        for item in fetch_metric_items(client, [host["hostid"] for host in chunk]):
            hostid = item.get("hostid")
            key = item.get("key_")
            metric = KEY_TO_METRIC.get(key)
            if hostid and metric:
                items_by_host.setdefault(hostid, {})[metric] = item.get("lastvalue")

        for host in chunk:
            hostname = host["host"]
            row = HostMetrics(host=hostname, unit=unit_from_host(hostname))
            host_values = items_by_host.get(host["hostid"], {})
            for metric in PREFERRED_KEYS:
                if metric in host_values:
                    row.values[metric] = host_values[metric]
                else:
                    row.missing.append(metric)
            results.append(row)

    return results


def print_report(rows: list[HostMetrics]) -> None:
    if not rows:
        print("No NUC hosts found in Zabbix.")
        return

    print(
        f"{'Unit':<10} {'Host':<22} {'RAM Total':>10} {'RAM Used':>10} "
        f"{'RAM %':>8} {'Page Total':>11} {'Page Free':>11} {'Pg %Free':>8} {'Pg %Used':>8}"
    )
    print("-" * 108)
    for row in rows:
        print(
            f"{row.unit:<10} {row.host:<22} "
            f"{fmt_bytes(row.values.get('ram_total')):>10} "
            f"{fmt_bytes(row.values.get('ram_used')):>10} "
            f"{fmt_pct(row.values.get('ram_util_pct')):>8} "
            f"{fmt_bytes(row.values.get('pagefile_total')):>11} "
            f"{fmt_bytes(row.values.get('pagefile_free')):>11} "
            f"{fmt_pct(row.values.get('pagefile_free_pct')):>8} "
            f"{fmt_pct(row.values.get('pagefile_used_pct')):>8}"
        )
        if row.missing:
            print(f"  missing items: {', '.join(row.missing)}")


def write_csv(path: str, rows: list[HostMetrics]) -> None:
    fieldnames = [
        "unit",
        "host",
        "ram_total",
        "ram_used",
        "ram_util_pct",
        "pagefile_total",
        "pagefile_free",
        "pagefile_free_pct",
        "pagefile_used_pct",
        "missing_items",
    ]
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "unit": row.unit,
                    "host": row.host,
                    **{
                        metric: fmt_metric(metric, row.values.get(metric), empty="")
                        for metric in PREFERRED_KEYS
                    },
                    "missing_items": ";".join(row.missing),
                }
            )


def discover_host(client: ZabbixClient, hostname: str) -> None:
    hosts = client.call(
        "host.get",
        {
            "output": ["hostid", "host", "name"],
            "filter": {"host": hostname},
        },
    )
    if not hosts:
        print(f"Host not found: {hostname}")
        return

    host = hosts[0]
    items = client.call(
        "item.get",
        {
            "output": ["name", "key_", "lastvalue", "units"],
            "hostids": host["hostid"],
            "monitored": True,
            "sortfield": "name",
        },
    )
    keywords = ("memory", "swap", "page", "ram")
    print(f"Items on {hostname} matching memory/page/swap:")
    for item in items:
        text = f"{item.get('name', '')} {item.get('key_', '')}".lower()
        if any(word in text for word in keywords):
            print(
                f"  {item.get('key_')} = {item.get('lastvalue')} {item.get('units', '')} "
                f"({item.get('name')})"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull RAM and page file stats from Zabbix NUC hosts.")
    parser.add_argument("--csv", metavar="PATH", help="Write results to CSV")
    parser.add_argument("--discover", metavar="HOST", help="List memory/pagefile item keys for one host")
    args = parser.parse_args()

    url = os.getenv("zab_url")
    token = os.getenv("zab_token")
    if not url or not token:
        print("Set zab_url and zab_token in your .env file.", file=sys.stderr)
        return 1

    client = ZabbixClient(url, token)

    if args.discover:
        discover_host(client, args.discover)
        return 0

    hosts = get_nuc_hosts(client)
    rows = collect_metrics(client, hosts)
    print_report(rows)

    if args.csv:
        write_csv(args.csv, rows)
        print(f"\nWrote {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
