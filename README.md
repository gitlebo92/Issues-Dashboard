# work_tool

Flask dashboard for NOC outage verification: ERP issue validation, unit health checks, command menus (Open, Linux, Switch), and stdout streaming.

## Setup (coworkers)

1. Get access to the **private** GitHub repo from the owner.
2. Clone the repo.
3. Copy `.env.example` → `.env` and fill in credentials (ERP, Victron, cameras, SSH, etc.).
4. **Never commit `.env`** or netsheet/upload CSVs.
5. Install Python deps if needed (`pip install -r requirements.txt` when present, or the packages imported by `flask_endpoints.py` / `work_tool.py`).
6. Place local data files as needed (`net_sheet.csv` is gitignored — copy from your existing install).

Start from the project directory:

```bat
run_live.bat      rem http://127.0.0.1:5000 — daily use
run_sandbox.bat   rem http://127.0.0.1:5001 — dev/test (auto-reload)
```

## Live vs sandbox

| Script | URL | Purpose |
|--------|-----|---------|
| `run_live.bat` | http://127.0.0.1:5000 | Production dashboard — manual Pull Issues; automation paused |
| `run_sandbox.bat` | http://127.0.0.1:5001 | Dev/test — code changes without restarting live |

Both use the same `.env` (ERP, netsheet, credentials). Sandbox keeps its own `data/sandbox/` for uploads and resolved-today tracking so live state is not affected.

**Paused on both (by default):**
- 4:00 / 4:05 / 4:10 AM scheduled tasks
- 30-minute automatic ERP polling

Manual actions (Pull Issues, validate, Open menus, reboot NUC/SNUC, etc.) still work.

### Typical workflow

1. Leave `run_live.bat` running for daily use.
2. Start `run_sandbox.bat` when developing; test at **:5001**.
3. When ready, **restart** `run_live.bat` (browser refresh alone does not load new code).
4. Hard-refresh the browser (Ctrl+F5) if the UI looks stale.

### Environment variables

Set in `.bat` files or `.env` — see `.env.example` for the full list.

| Variable | Description |
|----------|-------------|
| `WORK_TOOL_ENV` | `live` or `sandbox` |
| `WORK_TOOL_PORT` | `5000` or `5001` |
| `WORK_TOOL_DATA_DIR` | Optional; sandbox defaults to `data/sandbox` |
| `WORK_TOOL_URL` | Optional; camera launch base URL |
| `PAUSE_AUTOMATED_TASKS` | `1` to disable scheduled jobs and auto ERP poll |
| `workTLD` | Company domain used for ERP/Shield/Scrypted URLs |
| `MESH_BASE_URL` | Optional MeshCentral filter URL prefix |
| `RAINDANCE_BASE_URL` | Optional Raindance unit URL prefix |
| `SENTRA_NETWORK_TOOL_V19_DIR` | Optional path to `Sentra_Network_toolv19` |

**PVE / NUC reboot credentials:**
- SNUC (PVE host SSH): `pvesshuser` + `pvepass` — Linux user only (`root`), not `root@pam`
- NUC SSH: `nucuser` + `nucpass`
- PVE web UI: `pveuser=root@pam` + `pvepass`

## Secrets policy

- Commit `.env.example` only.
- Do not commit `.env`, `net_sheet.csv`, `uploads/`, or exported CSVs.
- Rotate any token that was ever committed to an older clone of this project.
