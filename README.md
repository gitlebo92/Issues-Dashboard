# work_tool

Flask dashboard for NOC outage verification: ERP issue validation, unit health checks, command menus (Open, Linux, Switch), and stdout streaming.

Start from the project directory:

```bat
run_live.bat      rem http://127.0.0.1:5000 — daily use
run_sandbox.bat   rem http://127.0.0.1:5001 — dev/test (auto-reload)
```

Copy `.env.example` to `.env` and fill in credentials before first run.

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

Set in `.bat` files or `.env`:

| Variable | Description |
|----------|-------------|
| `WORK_TOOL_ENV` | `live` or `sandbox` |
| `WORK_TOOL_PORT` | `5000` or `5001` |
| `WORK_TOOL_DATA_DIR` | Optional; sandbox defaults to `data/sandbox` |
| `WORK_TOOL_URL` | Optional; camera launch base URL |
| `PAUSE_AUTOMATED_TASKS` | `1` to disable scheduled jobs and auto ERP poll |

**PVE / NUC reboot credentials:**
- SNUC (PVE host SSH): `pvesshuser` + `pvepass` — Linux user only (`root`), not `root@pam`
- NUC SSH: `nucuser` + `nucpass`
- PVE web UI: `pveuser=root@pam` + `pvepass`
