"""CLI: download ART report 153 (NOC outage / recovery email) to the cache path."""
from dotenv import load_dotenv

load_dotenv()

import work_tool

path, error = work_tool.download_art_noc_outage_report()
if error:
    raise SystemExit(f"ART download failed: {error}")
print(f"Saved: {path}")
