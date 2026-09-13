# work_tool

Internal Flask dashboard for NOC / field ops: ERP outage verification, unit health checks, camera launch, router/switch tools, and related helpers.

Screenshots below were taken from a live local instance.

> **ERP writes are disabled by default** (`DISABLE_ERP_WRITES=1`). Mutating actions stay visible but inactive (Set Fields, Create Project, Terminate/Activate Site, Clear MU, Tech Checks, Add Missing Components). **Resolve (R)** is local-only and stays enabled. Set `DISABLE_ERP_WRITES=0` only when you intentionally need writes. Open / Validate / Ping / Snapshot / cameras remain read-oriented.

---

## Setup (coworkers)

1. Get access to the **private** GitHub repo.
2. Clone the repo.
3. Copy `.env.example` → `.env` and fill in credentials.
4. **Never commit** `.env`, `net_sheet.csv`, `uploads/`, or exported CSVs.
5. Install Python packages used by `flask_endpoints.py` / `work_tool.py`.
6. Copy a local `net_sheet.csv` from an existing install (gitignored).
7. Optionally set `SENTRA_NETWORK_TOOL_V19_DIR` to your v19 tool folder.

```bat
run_live.bat      rem http://127.0.0.1:5000 — daily use
run_sandbox.bat   rem http://127.0.0.1:5001 — dev/test (auto-reload)
```

| How it runs | URL | Purpose |
|-------------|-----|---------|
| **`IssuesDashboard` Windows service** | http://&lt;this machine&gt;:5000 | **The live instance.** Starts automatically and stays running. Restart the service to pick up code changes. |
| `run_live.bat` | http://127.0.0.1:5000 | Same thing by hand — only when the service is stopped, or they will fight over the port. |
| `run_sandbox.bat` | http://127.0.0.1:5001 | Dev/test (own `data/sandbox/`) |

> **The service does not read `run_live.bat`.** It launches `flask_endpoints.py`
> directly, so anything the live instance needs must come from a code default
> or from `.env` (which is loaded at import). Setting an environment variable
> in `run_live.bat` has no effect on the service.

With `PAUSE_AUTOMATED_TASKS=1` (default on both bats), scheduled 4:00/4:05/4:10 jobs and 30‑minute ERP polling stay off. Manual **Pull Issues**, validate, Open menus, etc. still work.

With `DISABLE_ERP_WRITES=1` (default when unset), ERP-mutating actions (Set Fields, Create Project, Terminate/Activate Site, Clear MU, Tech Checks, Add Missing Components) stay visible but disabled; matching POST routes return 403. **Resolve (R)** is local-only and stays enabled. Set `DISABLE_ERP_WRITES=0` to allow writes.

---

## 1. Issues Dashboard (home)

Open **http://127.0.0.1:5000/** — the Issues Dashboard is the home page (navbar + ticket lists + stdout).

![Issues report](docs/screenshots/02-issues-report.png)

**Navbar:** **Issues Dashboard** (home) · **Recovery Email Check** (`/recovery_email`)

### Layout

- **Left — Stdout:** Live validation / ping / carrier / SSH-style logs. Search + Clear.
- **Right — Lists:** Tickets grouped by category. Filter search, **All lists / One list**, **Pull Issues**, **Clear checkboxes**.
- **Header counters:** Resolved today / Worked / Skipped (local workflow tracking).
- **Per-row LEDs:** Green / yellow / orange / red compute (and speaker/camera LEDs where relevant).
- **Weather icons:** Between the LED and the ticket link. Metro weather from the subject region code (`LAX` / `OAK` / `HOU` / `PHX` / `SLC` / `DEN`) via Open-Meteo — **no ERP**. Fresh fetch on page load; auto-refresh every **30 minutes**. Distinct icons for clear / partly cloudy / mostly cloudy / rain / thunder / etc. **Click an icon** (or **Weather → Weather (Current)**) for precise site/trailer weather → stdout + icon update. Toolbar **Update Weather** force-refreshes all region icons.
- **R / W / S:** Resolved / Worked / Skipped checkboxes (local UI state only; Resolve does not post to ERP).
- **All lists / One list:** **All lists** shows everything. **One list** reveals the category dropdown, which now takes **several lists at once** — tick Offline compute and Down Full and see both — with each list's ticket count beside it. The button reads the list name when one is ticked, "3 lists selected" for several. **Select all** / **Clear** sit at the bottom of the menu, empty lists are dimmed, and completed lists show their count in green. Switching to **Projects** swaps the menu for the project lists, and each panel keeps its own selection.
- **Quick actions:** A short row of buttons on every ticket — **Validate**, **Uptime** (switch/Robofiber), **VRM**, **Mesh**, **Snap** — promoted out of the nested command menus. Edit the `QUICK_ACTIONS` array near the top of `templates/issues_results.html` to change which appear, reorder them, or set it to `[]` to remove the row.
- **Busy flag:** An amber pill appears on a ticket when that unit is locked by another action (Security Update Fix, a reboot, Restart All Services), refreshed every 20 seconds from `/issues/busy-units`. Shows the action and its phase so two people don't collide on one unit.
- **Toasts:** Failures appear as non-blocking toasts in the bottom-right instead of `alert()` dialogs. Errors stay until dismissed; other messages fade after six seconds. Every message is still written to stdout and the status line.

### Issue list categories

| List | Meaning |
|------|---------|
| **Up Steady** | Validated reachable / false positive path |
| **Offline compute** | NUC / compute side soft-down |
| **Scrypted outage** | Scrypted path issues |
| **Speaker outage** | Speaker tickets |
| **Camera outage** | Camera tickets |
| **Down Full** | Fully down (includes former stale-VPN range behavior) |
| **Panel issues** | Panel / fisheye panel tickets |
| **Camera View** | Router + compute reachability view |
| **On Hold** | Held tickets (with hold kind) |
| **Monitoring Hours / Termination / Relocation** | Specialty buckets |

Each list (except a few write-heavy specialty buckets) has **Revalidate** to re-check tickets in that list only.

To narrow the view, switch to **One list** and tick one or more lists in the dropdown.

### Projects panel

Switch the toolbar dropdown from **Issues** → **Projects**.

![Projects panel](docs/screenshots/06-projects-panel.png)

Shows ERP-ish project buckets such as **Open**, **In Progress**, and **Deployment Prep**, with the same unit command menus and connectivity LEDs. **Pull Projects** refreshes project data (read). Task Controls that write stay visible but disabled when `DISABLE_ERP_WRITES=1` (default).

### Unit search / Unit tools

Type a unit into the list filter even if it is not on the current report. Matching tickets filter in place; with no ticket match you get an ad-hoc **Unit tools** row for the same command menus.

---

## 2. Per-unit command menu

Click the unit button (left of the LED) to open **Commands**.

![Command menu](docs/screenshots/03-command-menu.png)

### Search commands

The menu holds around 87 actions across nested submenus, four levels deep at worst. A **Search commands** box sits at the top and is focused as soon as the menu opens, so you can type instead of clicking through the tree.

- Typing filters the actions live and opens whichever submenus contain a match — `reb` surfaces Reboot Scrypted, Reboot PVE and Reboot NUC together, from three different submenus.
- Matching a submenu's own name reveals everything inside it: `cameras` shows every camera action.
- **Enter** runs the action when the search has narrowed to exactly one.
- **Escape** clears the search; press it again to close the menu.
- Clearing the box restores the menu exactly as it was, with the submenus closed.

### Validate

| Action | Behavior |
|--------|----------|
| **Validate (Quick)** | Category / connectivity re-check (`/issues/validate-unit/...`). On NUC-down lists may ping compute only. |
| **Validate (Full)** | Deeper multi-endpoint check (`/issues/validate-unit-full/...`) → LED colors (green/yellow/orange/red), optional list move. |

LED colors (compute). Each light also carries a glyph — ✓ up, ! warning, × down — so state is readable without relying on hue:

- **Green ✓** — up / steady  
- **Yellow !** — soft down / still unreachable compute or Scrypted  
- **Orange ×** — multi-down  
- **Red ×** — fully down  

### Weather

Top-level **Weather** submenu on the unit command menu:

- **Weather (Current)** — site address GPS (ERP Site), else trailer (MU) coordinates → Open-Meteo → stdout + icon update. Same as clicking the weather icon.
- **Weather (History)** — opens timeanddate historic weather for the subject region city (`PHX`→phoenix, `DEN`→denver, `LAX`→los-angeles, `OAK`→oakland, `HOU`→houston, `SLC`→salt-lake-city).

Region list icons stay metro-level and ERP-free; **Weather (Current)** / icon click is the precise site/trailer path.

### Router

- **Get Carrier** — SIM ICCID → carrier via v19 inventory  
- **Quick Validate** — router-oriented check  
- **Ping Router** / **Long Ping Router** — ICMP (long ping streams to stdout). **Ping Router** (fixed mode) also reports min/avg/max and jitter, parsed from the four echoes it already sends — no extra packets and no extra time. **Quick Validate** stops at the first reply and is unchanged.

### Diagnostics

Read-only checks. None of them change anything on the device, so none take the per-unit lock.

| Action | Behavior |
|--------|----------|
| **Run All Diagnostics** | Every applicable check below in one pass, reported as a single list of problems |
| **Camera Reachability** | Pings every camera, the fisheye and the speaker at once and prints a ✓/× table |
| **Service Status** | *(PVE units)* Which of the sixteen platform services (15 sentracam-* daemons + docker) are actually active — run this **before** Restart All Services |
| **PVE Host Resources** | *(PVE units)* Memory, swap, root disk, load average and VM 101 state |
| **NVMe Health (PVE)** | *(PVE units)* `smartctl -a` on the boot drive — wear, spare, errors, temperature. Lives under Linux → Scrypted |
| **Unit History** | Recorded validations for this unit and how many times it has flapped in the last week |

### Cameras

- **Fisheye Snapshot** — grab snapshot into the UI  
- **Open All Cameras** — multi-tile launch page  
- **Open Camera N / Open Fisheye** — single camera (when netsheet has IPs)

### Open (external / proxied UIs)

In-app **Open** menu with **Shield** and **ERP** expanded.

![Open menu — Shield & ERP](docs/screenshots/11-open-shield-erp-buttons.png)

**Shield** (opens `shield.{workTLD}` in a new tab — may require login):

![Shield open buttons](docs/screenshots/12-shield-open-buttons.png)

| Button | Opens |
|--------|--------|
| **Open Site** | Shield site page for the ticket’s site ID |
| **Open RD Component** | Shield component `SC-{unit}` (RD/FD/MU as applicable) |
| **Open Trailer Component** | Attached MU/trailer component, or disabled when none (e.g. ACRD) |

**ERP** (opens `erp.{workTLD}` — may require login):

![ERP open buttons](docs/screenshots/13-erp-open-buttons.png)

| Button | Opens |
|--------|--------|
| **Open Event Records** | ERP event-record list filtered to the unit |
| **Open Site Page** | ERP site page |
| **Open RD Component** | ERP component `SC-{unit}` |
| **Open Trailer Component** | Attached trailer/MU component when present |

**Also under Open**

- Open Mesh  
- Open Raindance  
- Open Switch (digest/basic redirect when IP known)  
- Open PVE  
- Open Platform  
- Open Relay (3100+)  
- Open Scrypted  
- Open VRM  

These open browser tabs / redirects. They do **not** write ERP fields by themselves. Destination Shield/ERP pages are behind company auth; docs show the in-app Open buttons rather than live destination pages.

### Switch

- Bounce ports / uptime / log helpers when switch IP exists (see menu items on a unit with a switch).

### Linux / NUC (when unit supports them)

- **NUC:** reboot, uptime, chkdsk (read-only)  
- **Linux → Scrypted:** Set No Audio, Reboot Scrypted / Reboot PVE, Check Patch Version, Update Patch Version

### Disabled ERP Write Functions

With `DISABLE_ERP_WRITES=1` (default), these stay **visible but disabled** in the UI, and matching POST routes return 403:

- **Set Fields** (ERP field writes)  
- **Create Deployment / Termination / Relocation / Refurbish** projects  
- **Terminate Site** / **Activate Site**  
- **Clear MU Coordinates** / **Clear MU Site**  
- **Tech Checks (180 Unit)** confirm  
- **Add Missing Components** (manual and scheduled)

**Resolve (R)** is local-only and is **not** blocked by this flag. Set `DISABLE_ERP_WRITES=0` in `.env` to re-enable the write actions above.

**Note:** **Update Patch Version** is separate from this gate (not an ERP ticket write); treat it carefully when enabled.

---

## 3. Camera launch grid

From **Cameras → Open All Cameras** (or `/issues/cameras-launch/<UNIT>`).

![Camera launch grid](docs/screenshots/05-cameras-launch.png)

- Grid of proxied camera UIs (Dahua H5 / Hikvision with shim).  
- Controls: **Columns**, **Zoom**, **Height**, **IE mode**, **Reload all**, **Open all in tabs**.  
- Per tile: Log out / Reload / Open tab.  
- ACRD / unit rules decide which cameras appear (e.g. fisheye + C1–C3, no C4 when no MU).  
- Live/PTZ/Smart Event drawing depends on vendor; Hikvision ActiveX needs Edge IE mode via **Open tab** / IE mode workflows.

---

## 4. Recovery Email Check

From the Issues Dashboard navbar → **Recovery Email Check** (`/recovery_email`).

The live service pulls ART report **153** (*Shield: NOC: Outage Issues with no initial email*) about once an hour (htmlDataTable → local `.xlsx`; native ART xlsx export fails server-side). Uses `myemail` / `mypass` from `.env`. Honors `PAUSE_AUTOMATED_TASKS`.

On the page:

- **Check cached ART report** — run against the last hourly download
- **Download from ART & Check** — refresh now, then run
- Optional manual `.xlsx` / `.csv` upload

### Results dashboard

Lists use **status lights** (same LED language as Issues) next to each list name and ticket row.

**Search (same idea as Issues Dashboard):**

- **Stdout:** search box + Clear above the console (filters / highlights matching lines).
- **Lists:** filter box above the result lists (unit / subject / ticket id); empty lists hide while filtering.
- **Worked checkboxes:** local-only (browser storage). Mark tickets you’ve handled; **Clear worked** resets them. Does not write to ERP.

![Recovery Email results](docs/screenshots/14-recovery-email-results.png)

| List | LED | Meaning |
|------|-----|---------|
| **Needs recovery email** | Yellow | Outage email sent, recovery empty, unit back up |
| **Needs initial outage email** | Red | No outage/recovery email, unit fully down |
| **Potential false positive** | Purple | No outage/recovery email, unit back up |
| **Pending recovery** | Blue | Checked units not in the lists above |
| **Email status up to date** | Green | Outage and recovery emails both sent |

Example run (ART spreadsheet): recovery (1), initial (0), false positive (1), pending (12), up to date (7).

### Per-unit command menus

Each unit row has the same style of **unit command button** as the Issues Dashboard:

| Menu | Actions |
|------|---------|
| **Validate** | Quick / Full (writes to stdout on this page) |
| **Cameras** | Fisheye snapshot, Open All, individual cameras |
| **Open** | Shield, ERP, Mesh, Raindance, Switch, PVE / Relay / Platform / Scrypted when available, VRM for RD units |

Ticket subject from the spreadsheet is carried into the menu so Shield/ERP/VRM resolve more accurately. ERP write actions are not offered on this page.

---

## API Endpoints & Route Documentation

All HTTP routes are defined in `flask_endpoints.py` (there is no separate `app.py`). Base URL examples use the live instance: `http://127.0.0.1:5000`.

### Conventions

| Item | Behavior |
|------|----------|
| JSON errors | Usually `{"ok": false, "error": "<message>"}` with `400` / `403` / `404` / `409` / `502` |
| ERP write guard | When `DISABLE_ERP_WRITES=1` (default), mutating POSTs return **403** with `{"ok": false, "error": "ERP writes are disabled (set DISABLE_ERP_WRITES=0 in .env to enable)."}` |
| Automation pause | `PAUSE_AUTOMATED_TASKS=1` / sandbox skips background ERP poll unless `force` + `manual` |
| Shared job id | Issues Dashboard uses job id `"shared"` |
| SSE | `Content-Type: text/event-stream` — lines like `data: {"type":"log","line":"..."}\n\n` |

---

### Pages & legacy redirects

#### `GET /`

**Description:** Issues Dashboard home. Starts the shared validation job if needed.

**Request:** None.

**Response:**
- `200` — HTML (`issues_results.html`) with `job_id`, `work_tld`, `mesh_base_url`, `raindance_base_url`, `automation_paused`, `erp_writes_disabled`

#### `GET /victron` · `GET|POST /victron/results`

**Description:** Retired Victron UI — shows “page moved”.

**Request:** None.

**Response:** `200` — HTML (`page_moved.html`)

#### `GET /outage_filter` · `GET|POST /outage_filter/results`

**Description:** Retired Outage Filter — shows “page moved”.

**Request:** None.

**Response:** `200` — HTML (`page_moved.html`)

#### `GET /linux` · `GET|POST /linux/results` · `GET /linux/watch/<job_id>` · `GET /linux/stream/<job_id>`

**Description:** Retired Linux diagnostic tool — shows “page moved”.

**Request:** Path `job_id` where present.

**Response:** `200` — HTML (`page_moved.html`)

#### `GET /zabbix`

**Description:** Retired Zabbix UI — shows “page moved”.

**Request:** None.

**Response:** `200` — HTML (`page_moved.html`)

#### `GET /issues`

**Description:** Legacy issues entry — shows “page moved”.

**Request:** None.

**Response:** `200` — HTML (`page_moved.html`)

#### `POST /issues/results`

**Description:** Ensures the shared issues job exists, then redirects to home.

**Request:** None (body ignored).

**Response:** `302` → `/`

#### `GET /issues/watch`

**Description:** Legacy shared watch URL — shows “page moved”.

**Request:** None.

**Response:** `200` — HTML (`page_moved.html`)

#### `GET /issues/watch/<job_id>`

**Description:** Issues Dashboard for a specific stream job.

**Request:** Path `job_id`.

**Response:**
- `200` — HTML (`issues_results.html`)
- `404` — plain text `Unknown job`

---

### Issues job streaming & state

#### `GET /issues/stream/<job_id>`

**Description:** Server-Sent Events stream of validation logs, progress, and completion for a job.

**Request:** Path `job_id`.

**Response:**
- `200` — `text/event-stream`
```json
{"type": "log", "line": "Validating RD1234..."}
{"type": "progress", "current": 3, "total": 40, "unit": "RD1234"}
{"type": "done", "results": { "false_positives": [], "truly_down": [] }}
```
- `404` — plain text `Unknown job`

#### `GET /issues/state/<job_id>`

**Description:** Cursor-based event history and optional results snapshot for dashboard sync / reconnect.

**Request:**
- Path: `job_id`
- Query: `cursor` (int, default `0`), `version` (int, default `0`)

**Response:**
- `200`
```json
{
  "ok": true,
  "events": [],
  "cursor": 12,
  "done": true,
  "version": 3,
  "validation_run_id": "abc",
  "results": null,
  "resolved_today": { "date": "2026-09-08", "count": 2, "issue_ids": ["ISS-1", "ISS-2"] }
}
```
(`results` is a full copy only when the client `version` differs from the job version; otherwise `null`.)
- `400` — `{"ok": false, "error": "Invalid state cursor"}`
- `404` — `{"ok": false, "error": "Unknown job"}`

#### `POST /issues/poll/<job_id>`

**Description:** Incremental ERP refresh for Open/Monitoring/On Hold issues or Open/In Progress projects on a finished job.

**Request body (JSON):**
```json
{ "force": true, "manual": true, "scope": "issues" }
```
| Field | Type | Notes |
|-------|------|-------|
| `force` | bool | Bypass ~30‑minute throttle |
| `manual` | bool | With `force`, also bypasses `PAUSE_AUTOMATED_TASKS` |
| `scope` | string | `issues` (default) or `projects` |

**Response:**
- `200` success — includes `ok`, `scope`, `new_count`, `removed_count`, `restored_count`, `updated_count`, `project_count`, `results`, `logs`, `resolved_today` (issues may include `fetched_count` / `snapshot`)
- `200` skipped / paused / busy — `ok: true` with `skipped` / `paused` / `busy` and zero counts
- `404` — unknown job
- `409` — initial validation still running
- `502` — `{"ok": false, "scope": "issues", "error": "...", "logs": []}`

#### `GET /issues/resolved`

**Description:** Today’s local resolved-ticket tracker (browser/UI workflow; not an ERP write).

**Request:** None.

**Response:** `200`
```json
{ "ok": true, "date": "2026-09-08", "count": 2, "issue_ids": ["ISS-1", "ISS-2"] }
```

#### `POST /issues/resolved`

**Description:** Mark an issue resolved locally and remove it from shared-job lists.

**Request body (JSON):**
```json
{ "issue_id": "ISS-123" }
```

**Response:**
- `200` — `{ "ok": true, "added": true, "date": "...", "count": 3, "issue_ids": [...] }`
- `400` — missing `issue_id`

---

### Cameras & device UI

#### `GET /issues/cameras/<unit>`

**Description:** List configured cameras for a unit (from netsheet).

**Request:** Path `unit` (e.g. `RD3076`).

**Response:**
- `200` — `{"ok": true, "unit": "RD3076", "cameras": [{"target": "camera1", "label": "Camera 1", ...}]}`
- `404` — `{"ok": false, "error": "..."}`

#### `GET /issues/cameras-launch/<unit>`

**Description:** Multi-camera iframe launcher (proxied Dahua/Hikvision grid).

**Request:** Path `unit`.

**Response:**
- `200` — HTML (`camera_launch.html`)
- `404` — same template with error context

#### `POST /issues/open-camera-urls`

**Description:** Open camera URLs in browser tabs (optional IE mode on the client/server path).

**Request body (JSON):**
```json
{ "urls": ["http://10.191.4.182:11000/"], "ie_mode": true }
```

**Response:**
- `200` — `{"ok": true, "ie_mode": true, "opened": 1, "urls": [...], ...}`
- `400` — `{"ok": false, "error": "..."}`

#### `GET /issues/camera-snapshot/<unit>/<target>`

**Description:** Authenticated JPEG snapshot via camera proxy.

**Request:** Path `unit`, `target` (`fisheye` / `camera1`–`camera4`).

**Response:**
- `200` — `image/jpeg` (`Cache-Control: no-store`)
- `502` — plain-text error

#### `GET /issues/camera/<unit>/<target>`

**Description:** Redirect helper page into the camera login/proxy flow.

**Request:** Path `unit`, `target`.

**Response:**
- `200` — HTML (`camera_redirect.html`)
- `404` — plain-text error

#### `GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS /issues/camera-proxy/<unit>/<target>/`  
#### `GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS /issues/camera-proxy/<unit>/<target>/<path:subpath>`

**Description:** HTTP reverse proxy to a unit camera (Digest/Basic auth, HTML shim injection). Live WebSockets go direct to the camera, not through Flask.

**Request:** Path `unit`, `target`, optional `subpath`; query string, headers (minus `Host`), and body are forwarded.

**Response:** Upstream status/headers/body (HEAD returns empty body). Proxy failure → plain text `502`.

#### `404` handler — `camera_proxy_root_fallback`

**Description:** If a camera UI requests a root-relative asset (`/module/...`) and the `Referer` is a camera-proxy page, redirect into that camera’s proxy prefix.

**Response:** `302` to `/issues/camera-proxy/<unit>/<target><path>` when applicable; otherwise the normal 404.

#### `GET /issues/fisheye/<unit>`

**Description:** Fisheye JPEG snapshot for the unit.

**Request:** Path `unit`.

**Response:** `200` `image/jpeg`, or plain-text `502`.

#### `GET /issues/switch/<unit>`

**Description:** Switch UI redirect page.

**Request:** Path `unit`.

**Response:** `200` HTML (`switch_redirect.html`), or plain-text `502`.

#### `GET /issues/relay/<unit>`

**Description:** Relay UI redirect page.

**Request:** Path `unit`.

**Response:** `200` HTML (`relay_redirect.html`), or plain-text `502`.

#### `GET /issues/pve/<unit>`

**Description:** Start local PVE proxy and redirect to it.

**Request:** Path `unit`.

**Response:** `302` to proxy URL, or plain-text `502`.

---

### Shield / ERP / Raindance link helpers

#### `GET /issues/shield/<unit>`

**Description:** Resolve and redirect to the Shield site page for the unit.

**Request:** Path `unit`; query `subject` (optional, improves site match).

**Response:** `302` Shield URL; `404` if site cannot be resolved; `502` if `workTLD` missing.

#### `GET /issues/shield-component/<unit>`

**Description:** Redirect to the Shield component page for the unit.

**Request:** Path `unit`.

**Response:** `302`, or `404` (`Unit or workTLD is missing`).

#### `GET /issues/attached-mu/<unit>`

**Description:** Resolve attached MU (trailer) for an RD unit.

**Request:** Path `unit`; query `subject` (optional).

**Response:** `200`
```json
{ "unit": "RD3076", "mu": "MU1234", "url": "https://..." }
```

#### `GET /issues/site-page/<unit>`

**Description:** Redirect to the ERP site page for the unit.

**Request:** Path `unit`; query `subject` (optional).

**Response:** `302` ERP URL; `404` / `502` on resolve failure.

#### `GET /issues/event-records/<unit>`

**Description:** Redirect to ERP event-records for the unit.

**Request:** Path `unit`.

**Response:** `302`, or `404` if unit/`workTLD` missing.

---

### Connectivity — pings, bounce, Robofiber, long ping

#### `POST /issues/ping-speaker/<unit>`

**Description:** ICMP/reachability check for the unit speaker.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "RD3076", "speaker_up": true, "output": "..."}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/ping-camera/<unit>/<target>`

**Description:** Ping a specific camera endpoint.

**Request:** Path `unit`, `target`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "target": "camera1", "camera_up": true, "output": "..."}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/ping-compute/<unit>`

**Description:** Ping NUC/SNUC/compute host for the unit.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "label": "NUC", "compute_up": true, "output": "..."}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/ping-scrypted/<unit>`

**Description:** Ping Scrypted host for the unit.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "scrypted_up": true, "output": "..."}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/ping-pve/<unit>`

**Description:** Ping PVE host for the unit.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "pve_up": true, "output": "..."}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/bounce-switch/<unit>`

**Description:** Run `bounceswitch.exe` against the unit relay IP (streaming log).

**Request:** Path `unit`; empty body.

**Response:**
- `200` — streaming `text/plain` process output
- `500` — `{"ok": false, "error": "..."}`

#### `POST /issues/bounce-speaker/<unit>`

**Description:** Run speaker reboot utility (streaming log).

**Request:** Path `unit`; empty body.

**Response:** Same pattern as bounce-switch (`text/plain` stream or `500` JSON).

#### `POST /issues/robofiber-uptime/<unit>`

**Description:** Read Robofiber/switch uptime for the unit.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "ip": "...", "switch_type": "...", "uptime": "...", ...}`
- `400` — `{"ok": false, "error": "..."}`

#### `POST /issues/robofiber-logs-link/<unit>`

**Description:** Resolve Robofiber logs link for the unit.

**Request:** Path `unit`; empty body.

**Response:** `200` `{"ok": true, ...}` or `400` `{"ok": false, "error": "..."}`.

#### `POST /issues/robofiber-logs-month/<unit>`

**Description:** Fetch/open Robofiber month logs for the unit.

**Request:** Path `unit`; empty body.

**Response:** `200` `{"ok": true, ...}` or `400` `{"ok": false, "error": "..."}`.

#### `POST /issues/ping-router/<unit>`

**Description:** One-shot router ping (quick or fixed mode).

**Request:**
- Path: `unit`
- JSON or query: `mode` — `quick` (default) or `fixed`

**Response:**
- `200`
```json
{
  "ok": true,
  "unit": "RD3076",
  "ip": "10.x.x.x",
  "mode": "quick",
  "label": "Router",
  "reachable": true,
  "returncode": 0,
  "output": "..."
}
```
- `400` — `{"ok": false, "error": "..."}`

#### `POST /issues/ping-router-long/<unit>`

**Description:** Start a long-running router ping job.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "job_id": "<hex>", "unit": "...", "ip": "...", "max_seconds": 300}`
- `400` — `{"ok": false, "error": "..."}`

#### `GET /issues/ping-router-long/<job_id>/stream`

**Description:** Stream stdout from a long router ping job.

**Request:** Path `job_id`.

**Response:** `200` — streaming `text/plain`.

#### `POST /issues/ping-router-long/<job_id>/stop`

**Description:** Stop a long router ping job.

**Request:** Path `job_id`; empty body.

**Response:**
- `200` — `{"ok": true, "message": "...", ...}`
- `404` — `{"ok": false, "error": "..."}`

---

### Unit operations (carrier, weather, patch, reboot, chkdsk)

#### `POST /issues/scrypted-no-audio/<unit>`

**Description:** Diagnose/fix Scrypted “no audio” for the unit.

**Request:** Path `unit`; empty body.

**Response:** `200` `{"ok": true, ...}` or `400` `{"ok": false, "error": "..."}`.

#### `POST /issues/check-patch/<unit>`

**Description:** SSH check of Scrypted/Linux patch package date vs expected.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "host": "...", "package": "...", "date": "...", "expected_date": "...", "up_to_date": true, "raw": "..."}`
- `400` — `{"ok": false, "error": "..."}`

#### `POST /issues/carrier/<unit>`

**Description:** Lookup cell carrier from v19 SIM ICCID prefix.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "carrier": "Verizon", "sims": [...], ...}`
- `400` — `{"ok": false, "error": "..."}`

#### `POST /issues/weather/<unit>`

**Description:** Current weather from site GPS (ERP) with trailer MU fallback (Open-Meteo).

**Request body (JSON):**
```json
{ "subject": "PHX - RD3076 - ..." }
```
(`subject` may also be passed as a query parameter.)

**Response:**
- `200` — `{"ok": true, "unit": "...", "temperature_label": "92°F", "conditions": "Clear", "icon": "sun", "message": "...", ...}`
- `400` — `{"ok": false, "error": "..."}`

#### `POST /issues/weather-bulk`

**Description:** Metro weather for subject region codes (`LAX` / `OAK` / `HOU` / `PHX` / `SLC` / `DEN`). No ERP.

**Request body (JSON):**
```json
{ "regions": ["PHX", "DEN"], "force": true }
```

**Response:**
- `200` — `{"ok": true, "regions": { "PHX": { "temperature_label": "...", "icon": "sun", ... } }}`
- `400` — if `regions` is not a list, or Open-Meteo/tool error

#### `POST /issues/reboot-scrypted/<unit>` · `POST /issues/reboot-snuc/<unit>`

**Description:** Reboot Scrypted / SNUC (same handler; dual path).

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "RD3076", "message": "Restarting"}`
- `400` — `{"ok": false, "error": "..."}`

#### `POST /issues/reboot-pve/<unit>`

**Description:** Reboot PVE host for the unit.

**Request:** Path `unit`; empty body.

**Response:** Same shape as reboot-scrypted (`200` / `400`).

#### `POST /issues/reboot-nuc/<unit>`

**Description:** Reboot Windows NUC for the unit.

**Request:** Path `unit`; empty body.

**Response:** Same shape as reboot-scrypted (`200` / `400`).

#### `POST /issues/nuc-uptime/<unit>`

**Description:** Query NUC uptime over SSH/WMI-style path.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "message": "...", "output": "..."}`
- `400` — `{"ok": false, "error": "..."}`

#### `POST /issues/chkdsk/<unit>`

**Description:** Run read-only `chkdsk` on a NUC drive.

**Request body (JSON) or query:**
```json
{ "drive": "C:" }
```

**Response:**
- `200` — `{"ok": true, "unit": "...", "drive": "C:", "message": "...", "output": "..."}`
- `400` — `{"ok": false, "error": "...", "output": "..."}` (fields vary)

#### `POST /issues/update-patch/<unit>`

**Description:** SSH install/update patch package on the unit (uses `.env` command).

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "host": "...", "exit_code": 0, "output": "...", ...}`
- `400` — may include `error`, `output`, `stderr`, `exit_code`, `host`

#### `GET /issues/unit-context/<unit>`

**Description:** Aggregate unit context (netsheet / ERP helpers) for menus.

**Request:** Path `unit`.

**Response:** `200` tool payload with `ok: true`, or `400` `{"ok": false, "error": "..."}`.

#### `POST /issues/pve-nvme-health/<unit>`

**Description:** Read-only NVMe SMART health from the unit's PVE host via `smartctl -a`. PVE units only (`entry.hasPve`). Reports only — does not start a self-test.

**Request:**
- Path: `unit`
- JSON or query: `device` — optional, defaults to `/dev/nvme0n1`. Must match `/dev/...`; anything else is refused before the SSH connection is made.

**Response:**
- `200`
```json
{
  "ok": true,
  "unit": "RD3400",
  "host": "10.x.x.x",
  "device": "/dev/nvme0n1",
  "status": "ok",
  "reasons": [],
  "summary": "NVMe on RD3400 looks healthy — 3% used, 100% spare, 41C, 15203h powered on",
  "model": "SAMSUNG MZVL2512HCJQ-00BL7",
  "overall_health": "PASSED",
  "critical_warning": "0x00",
  "percentage_used": 3,
  "available_spare": 100,
  "temperature_c": 41,
  "media_errors": 0,
  "output": "<raw smartctl output>"
}
```
- `400` — `{"ok": false, "error": "..."}` for an unknown unit, missing PVE IP, SSH/auth failure, a refused device path, or `smartctl` not installed (the message names `apt-get install -y smartmontools`).

`status` is `ok` / `warn` / `fail`. **fail** on a non-PASSED self-assessment, a non-zero critical warning, any media/data-integrity errors, or available spare at/below its threshold. **warn** on ≥80% of rated endurance used or a drive at ≥70 °C.

---

### Read-only diagnostics

None of these change anything on the device, so none take the per-unit lock and none are affected by `DISABLE_ERP_WRITES`. All appear under **Commands → Diagnostics** on the unit menu.

#### `POST /issues/service-status/<unit>`

**Description:** Which platform services are actually active on the unit's Scrypted box. The read that should come *before* Restart All Services — it names the one service that died instead of restarting all thirteen blind. PVE units only.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "host": "...", "status": "fail", "summary": "1 of 13 services not active on RD3400: web", "services": [{"name": "acme-web.service", "short": "web", "state": "failed", "sub_state": "failed", "ok": false}], "down": ["web"], "output": "..."}`
- `400` — unknown unit, no Scrypted IP, SSH failure, or `company` not set in `.env`

`status` is `ok` when every service is active, `fail` when any is not.

#### `POST /issues/pve-resources/<unit>`

**Description:** Memory, swap, root disk, load average and VM 101 state on the PVE host. Answers "is the host wedged, or is only the guest down?" PVE units only.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — includes `mem_used_percent`, `mem_used_mb`, `mem_total_mb`, `swap_used_mb`, `root_disk` (`{size, used, available, use_percent, mount}`), `load_1m` / `load_5m` / `load_15m`, `vm101_status`, plus `status`, `reasons`, `summary`, `sections` and raw `output`.
- `400` — unknown unit, no PVE IP, or SSH failure

**fail** on memory ≥90%, root filesystem ≥90% full, or VM 101 not running. **warn** on root ≥80% full or swap ≥50% used.

#### `POST /issues/camera-matrix/<unit>`

**Description:** Ping every configured camera, the fisheye and the speaker for a unit in one pass. Pings run concurrently, so the whole matrix costs about as long as the slowest single endpoint.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "status": "warn", "summary": "...", "endpoints": [{"target": "fisheye", "label": "Fisheye", "host": "10.x.x.x", "reachable": true}], "down": ["Camera 2"], "reachable_count": 4, "total": 5}`
- `400` — unknown unit, or no camera/speaker IPs in the net sheet

**ok** when everything answers, **fail** when nothing does (check the switch or router first), **warn** in between.

#### `POST /issues/run-diagnostics/<unit>`

**Description:** Every read-only check that applies to the unit, in one call — full connectivity validation, the camera matrix, and on PVE units the service roll-up, host resources and NVMe health. Checks run sequentially on purpose: they SSH into the same two hosts, and five concurrent sessions during an outage invites sshd rate-limiting.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "status": "fail", "summary": "2 issue(s) found on RD3400", "problems": ["Platform services: ...", "NVMe health: ..."], "checks": {"connectivity": {"label": "...", "ok": true, "status": "ok", "result": {...}}, ...}, "has_pve": true}`
- `400` — only when the unit itself cannot be resolved

Individual checks fail independently: one erroring (no PVE, `smartctl` missing, SSH refused) records its error under `checks.<key>.error` and the rest still run.

---

### Validation history

Every validation the dashboard runs is recorded to SQLite (`data/<env>/unit_history.db`), so flap detection costs no extra packets.

**Disk use is bounded.** A row costs about 104 bytes including both indexes. Retention is `UNIT_HISTORY_KEEP_DAYS` (default 90), and `prune()` — which runs at startup — also enforces a hard ceiling of 200,000 rows and then VACUUMs, returning the freed space to the filesystem. The write-ahead log is checkpointed every 256 pages, so it stays around 1 MB. **The database cannot exceed roughly 21 MB** regardless of how heavily the dashboard is used.

#### `GET /issues/unit-history/<unit>`

**Description:** Recorded validations for a unit, newest first, plus its recent flap summary.

**Request:** Path `unit`; query `days` (default `30`), `limit` (default `200`).

**Response:**
- `200`
```json
{
  "ok": true,
  "unit": "RD3076",
  "days": 30,
  "entries": [
    {"ts": 1789170398.1, "when": "2026-09-11 14:06:38", "kind": "validate_full",
     "category": "false_positives", "led": "green", "healthy": true, "detail": null}
  ],
  "summary": {"unit": "RD3076", "days": 7, "checks": 41, "down_checks": 12,
              "transitions": 6, "last_seen": "...", "currently_healthy": true}
}
```
- `400` — `days` or `limit` not an integer

`transitions` counts healthy↔unhealthy flips, which is what separates a unit that is simply down (one transition, still down) from one that keeps bouncing.

#### `GET /issues/history-stats`

**Description:** Row count, unit count, date range and size on disk of the history database.

**Response:** `200` — `{"ok": true, "path": "...", "events": 12043, "units": 118, "first": "...", "last": "...", "bytes": 1359872, "size_mb": 1.3, "bytes_per_event": 113, "max_events": 200000}`

#### `POST /issues/history-compact`

**Description:** Prune to the retention window and hand the freed disk back to the OS. Runs at startup too; this is the on-demand version for when you want the space back now.

**Response:** `200` — `{"ok": true, "deleted": 4210, "freed_mb": 0.8, ...stats fields...}`; `500` on VACUUM failure.

#### `GET /issues/flap-report`

**Description:** Units flapping most in the window, worst first — the fleet-wide view.

**Request:** Query `days` (default `7`), `min_transitions` (default `3`).

**Response:**
- `200` — `{"ok": true, "days": 7, "min_transitions": 3, "units": [{"unit": "RD3076", "checks": 41, "down_checks": 12, "transitions": 6, "last_seen": "...", "currently_healthy": false}]}`
- `400` — `days` or `min_transitions` not an integer

---

### Per-unit lock, status, and notes

#### `GET /issues/unit-status/<unit>`

**Description:** Combined busy/lock state and note for a unit, including the Security Update Fix wizard's phase and saved log. This is what lets the wizard survive a page refresh.

**Request:** Path `unit`; query `token` (optional — when it matches the in-flight job, `is_owner` comes back true).

**Response:** `200`
```json
{
  "ok": true,
  "busy": true,
  "note": "waiting on site visit 9/14",
  "note_updated_at": "2026-09-11T14:02:11",
  "action": "Security Update Fix",
  "phase": "step2_done",
  "version": "0000:00:02.0",
  "started_at": 1789170398.1,
  "log": ["..."],
  "is_owner": true
}
```
When the unit is free, only `ok`, `busy: false`, `note` and `note_updated_at` are present.

#### `POST /issues/unit-lock/<unit>/clear`

**Description:** Force-clear a stuck unit lock regardless of token — escape hatch when a job died mid-run.

**Request:** Path `unit`; empty body.

**Response:** `200` — `{"ok": true, "cleared": true}` (`cleared: false` when the unit was not locked).

#### `GET /issues/busy-units`

**Description:** Every unit currently locked, for the dashboard's busy indicator.

**Request:** None.

**Response:** `200` — `{"ok": true, "units": [{"unit": "...", "action": "...", "phase": "...", "started_at": 1789170398.1}]}`.

#### `GET /issues/unit-note/<unit>`

**Description:** Read the shared free-text note for a unit. Persisted to JSON in the data dir, so it survives restarts and is visible to everyone on the dashboard. Not an ERP write.

**Request:** Path `unit`.

**Response:** `200` — `{"ok": true, "unit": "...", "text": "...", "updated_at": "..."}`.

#### `POST /issues/unit-note/<unit>`

**Description:** Replace the note for a unit.

**Request body (JSON):** `{ "text": "waiting on site visit 9/14" }`

**Response:** `200` — `{"ok": true, "unit": "...", "updated_at": "..."}`.

---

### Scrypted security update fix (guided, multi-step)

Five steps of one wizard, run in order against a PVE unit. Step 1 acquires the per-unit lock and returns a `token`; steps 2–5 must present it (as JSON `token` or `?token=`) and return **409** if the lock was lost or the session expired. Each step records its phase server-side, so `GET /issues/unit-status/<unit>` can restore the wizard after a page refresh.

#### `POST /issues/security-update-fix/step1/<unit>`

**Description:** Stop VM 101, read and save its `hostpci0` value, then remove passthrough and set standard VGA so the guest boots without the GPU.

**Response:** `200` — `{"ok": true, "unit": "...", "token": "<hex>", "version": "0000:00:02.0", ...}`; `400` on failure; `409` if the unit is already locked.

#### `POST /issues/security-update-fix/step2/<unit>`

**Description:** Inside the guest: hold the kernel packages, blacklist them from unattended upgrades, and confirm the running kernel.

**Response:** `200` `{"ok": true, ...}`; `400`; `409` on a lost lock.

#### `POST /issues/security-update-fix/shutdown/<unit>`

**Description:** Shut the guest down cleanly before passthrough is restored.

**Response:** `200` `{"ok": true, ...}`; `400` / `409`.

#### `POST /issues/security-update-fix/finish/<unit>`

**Description:** Restore `hostpci0` from the saved value and start VM 101 again.

**Request body (JSON):** `{ "version": "0000:00:02.0" }` (normally carried through from step 1).

**Response:** `200` `{"ok": true, ...}`; `400` / `409`.

#### `POST /issues/security-update-fix/verify/<unit>`

**Description:** Confirm the GPU came back — checks VGA presence and that the `i915` driver loaded, with `dmesg` context.

**Response:** `200` — `{"ok": true, "drivers_loaded": true, ...}`; `400` / `409`.

#### `POST /issues/restart-services/<unit>`

**Description:** Restart all sixteen platform services on the unit's Scrypted box — `docker` first (the sentracam-* daemons depend on it), then database, watchdog, web, metadata, images, indexer, capture, rtsp, smtp, alarms, events, onvif, monitor, snmp, cache. Also the wizard's optional final step.

**Request:** Path `unit`. Body `{ "token": "<hex>" }` when handed off from the Security Update Fix wizard (reuses that job's lock and ends it); empty body acquires a fresh lock.

**Response:** `200` — `{"ok": true, "unit": "...", "message": "Restarted all platform services on ..."}`; `400` on failure; `409` if the unit is busy or the handed-off token no longer matches.

---

### Validation & list revalidation

#### `POST /issues/validate-unit/<unit>`

**Description:** Quick per-unit connectivity validation; may update shared-job list membership.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "category": "false_positives", "output": "..."}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/validate-unit-full/<unit>`

**Description:** Full per-unit validation (broader endpoint checks).

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "category": "...", "endpoints": {...}, ...}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/validate-stale-vpn/<unit>`

**Description:** Validate router/compute path used by stale-VPN style tickets.

**Request:** Path `unit`; empty body.

**Response:**
- `200` — `{"ok": true, "unit": "...", "router_up": true, "compute_up": false, "compute_label": "NUC", "status": "...", ...}`
- `404` — `{"ok": false, "error": "..."}`

#### `POST /issues/validate-camera-view/<unit>`

**Description:** Validate camera-view (router + compute) category for a unit.

**Request:** Path `unit`; empty body.

**Response:** `200` result + `ok`, or `404` `{"ok": false, "error": "..."}`.

#### `POST /issues/revalidate-list/<list_id>`

**Description:** Re-check every ticket currently in one Issues list and move rows as needed.

**Request:** Path `list_id` (e.g. `false_positives`, `truly_down`, `scrypted_outage`, …). Empty body.

**Disallowed lists:** `discarded_tickets`, `monitoring_hours`, `termination`, `relocation`.

**Response:**
- `200`
```json
{
  "ok": true,
  "list_id": "truly_down",
  "checked": 12,
  "moved": 2,
  "moves": [
    {
      "issue_id": "ISS-1",
      "unit": "RD3076",
      "camera_target": "",
      "from": "truly_down",
      "to": "false_positives",
      "fields": {}
    }
  ],
  "logs": ["..."]
}
```
- `400` — disallowed / unknown list
- `409` — shared job not ready or busy
- `500` — `{"ok": false, "error": "...", "logs": []}`

---

### ERP mutating actions (`DISABLE_ERP_WRITES`)

Unless noted, these return **403** when ERP writes are disabled.

#### `POST /issues/set-fields/<preset_id>/<issue_id>`

**Description:** Apply a Set Fields preset to an ERP issue; may move the ticket between dashboard lists.

**Request body (JSON):**
```json
{
  "unit": "RD3076",
  "subject": "PHX - RD3076 - ...",
  "source_list_id": "truly_down"
}
```

**Response:**
- `200` — `{"ok": true, "move_to_list": "nuc_down", "issue_type": "...", ...}`
- `400` — validation/tool error
- `403` — ERP writes disabled

#### `POST /issues/add-missing-components`

**Description:** Scan ERP and add missing components/sites (scheduled job counterpart).

**Request:** Empty body.

**Response:**
- `200` — `{"ok": true, "checked": 10, "updated": 2, "skipped": 8, "errors": [], ...}`
- `403` — ERP writes disabled
- `409` — not ready / busy
- `502` — tool failure

#### `POST /issues/sync-netsheet`

**Description:** Sync netsheet rows from Sentra Network Tool v19 (manual). **Not** gated by `DISABLE_ERP_WRITES`.

**Request:** Empty body.

**Response:**
- `200` — `{"ok": true, "checked": 100, "added": 1, "backfilled": 0, "unchanged": 99, "failed": 0, "errors": [], "updated_units": []}`
- `409` — shared job not ready / busy
- `502` — exception

#### `POST /issues/create-deployment-project`

**Description:** Create an NOC Deployment project from a Prep project.

**Request body (JSON):**
```json
{ "project_id": "PRJ-123", "subject": "PHX - RD3076 - Prep ..." }
```

**Response:** `200` `{"ok": true, ...}`; `400` / `403` on failure / writes disabled.

#### `POST /issues/create-termination-project`

**Description:** Create a Termination project from an issue.

**Request body (JSON):**
```json
{ "issue_id": "ISS-123", "subject": "DEN - RD3076 - Termination ..." }
```

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

#### `POST /issues/create-relocation-project`

**Description:** Create a Relocation project from an issue.

**Request body (JSON):**
```json
{ "issue_id": "ISS-123", "subject": "PHX - RD3076 - Relocation ..." }
```

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

#### `POST /issues/lookup-site`

**Description:** Resolve ERP site metadata for terminate/activate flows. **Not** write-gated.

**Request body (JSON):**
```json
{ "subject": "PHX - RD3076 - ...", "action": "terminate" }
```
`action` ∈ `terminate` | `activate`.

**Response:** `200` `{"ok": true, ...site fields...}` or `400`.

#### `POST /issues/terminate-site`

**Description:** Terminate an ERP site.

**Request body (JSON):**
```json
{ "subject": "PHX - RD3076 - ...", "site_id": "SITE-1" }
```

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

#### `POST /issues/activate-site`

**Description:** Activate an ERP site.

**Request body (JSON):**
```json
{ "subject": "PHX - RD3076 - ...", "site_id": "SITE-1" }
```

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

#### `POST /issues/clear-mu-coordinates`

**Description:** Clear MU GPS coordinates in ERP.

**Request body (JSON):**
```json
{ "subject": "...", "unit": "RD3076", "mu": "MU1234" }
```
(`subject` / `unit` / `mu` — provide what the UI has; tool resolves MU.)

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

#### `POST /issues/clear-mu-site`

**Description:** Clear MU↔site link in ERP.

**Request body (JSON):** Same shape as clear-mu-coordinates.

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

#### `POST /issues/refurbish-projects/preview`

**Description:** Preview Refurbish project specs from a Termination subject (read-only preview; still write-gated in handler).

**Request body (JSON):**
```json
{ "subject": "DEN - RD3076 - Termination ...", "unit": "RD3076" }
```

**Response:** `200` `{"ok": true, "region": "DEN", "rd_unit": "RD3076", "specs": [...], ...}`; `400` / `403`.

#### `POST /issues/refurbish-projects`

**Description:** Create Refurbish projects from a Termination subject.

**Request body (JSON):** Same as preview.

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

#### `POST /issues/tech-checks/preview`

**Description:** Preview Tech Checks (180 Unit) tasks for an NOC Deployment project.

**Request body (JSON):**
```json
{ "project_id": "PRJ-123", "subject": "..." }
```

**Response:** `200` `{"ok": true, ...}`; `400` (missing project / not NOC Deployment / tool error); `403` if writes disabled.

#### `POST /issues/tech-checks`

**Description:** Run Tech Checks (180 Unit) create/cancel task workflow.

**Request body (JSON):** Same as preview.

**Response:** `200` `{"ok": true, ...}`; `400` / `403`.

---

### Recovery Email Check

#### `GET /recovery_email`

**Description:** Recovery Email Check form (ART cache status + upload).

**Request:** None.

**Response:** `200` — HTML (`recovery_email.html`) with `art_report_ready`, `art_report_mtime`.

#### `POST /recovery_email/results`

**Description:** Start a recovery-email classification job from ART cache, fresh ART download, or uploaded spreadsheet.

**Request:** `multipart/form-data` or form fields:
| Field | Values |
|-------|--------|
| `source` | `upload` (default), `art`, `art_cached` |
| `report_file` | Required when `source=upload` (`.xlsx` / `.csv`) |

**Response:**
- `302` → `/recovery_email/watch/<job_id>`
- `400` — `Missing report file`
- `502` — `ART download failed: ...`

#### `GET /recovery_email/watch/<job_id>`

**Description:** Live results page for a recovery-email job.

**Request:** Path `job_id`.

**Response:** `200` HTML (`recovery_email_results.html`), or `404` `Unknown job`.

#### `GET /recovery_email/stream/<job_id>`

**Description:** SSE stream for recovery-email job logs and final lists.

**Request:** Path `job_id`.

**Response:** `200` `text/event-stream`. Done payload includes:
`needs_recovery_email`, `needs_initial_email`, `potential_false_positive`, `pending_recovery`, `email_status_up_to_date`.

---

### Route index (quick reference)

| Method(s) | Path |
|-----------|------|
| GET | `/` |
| GET | `/victron` |
| GET, POST | `/victron/results` |
| GET | `/outage_filter` |
| GET, POST | `/outage_filter/results` |
| GET | `/linux` |
| GET, POST | `/linux/results` |
| GET | `/linux/watch/<job_id>` |
| GET | `/linux/stream/<job_id>` |
| GET | `/zabbix` |
| GET | `/issues` |
| POST | `/issues/results` |
| GET | `/issues/watch` |
| GET | `/issues/watch/<job_id>` |
| GET | `/issues/stream/<job_id>` |
| GET | `/issues/state/<job_id>` |
| POST | `/issues/poll/<job_id>` |
| GET, POST | `/issues/resolved` |
| GET | `/issues/cameras/<unit>` |
| GET | `/issues/cameras-launch/<unit>` |
| POST | `/issues/open-camera-urls` |
| GET | `/issues/camera-snapshot/<unit>/<target>` |
| GET | `/issues/camera/<unit>/<target>` |
| GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS | `/issues/camera-proxy/<unit>/<target>/` |
| GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS | `/issues/camera-proxy/<unit>/<target>/<path:subpath>` |
| GET | `/issues/fisheye/<unit>` |
| POST | `/issues/ping-speaker/<unit>` |
| POST | `/issues/bounce-switch/<unit>` |
| POST | `/issues/robofiber-uptime/<unit>` |
| POST | `/issues/robofiber-logs-link/<unit>` |
| POST | `/issues/robofiber-logs-month/<unit>` |
| POST | `/issues/bounce-speaker/<unit>` |
| POST | `/issues/ping-router/<unit>` |
| POST | `/issues/ping-router-long/<unit>` |
| GET | `/issues/ping-router-long/<job_id>/stream` |
| POST | `/issues/ping-router-long/<job_id>/stop` |
| POST | `/issues/ping-camera/<unit>/<target>` |
| POST | `/issues/ping-compute/<unit>` |
| POST | `/issues/ping-scrypted/<unit>` |
| POST | `/issues/scrypted-no-audio/<unit>` |
| POST | `/issues/ping-pve/<unit>` |
| POST | `/issues/set-fields/<preset_id>/<issue_id>` |
| POST | `/issues/add-missing-components` |
| POST | `/issues/sync-netsheet` |
| POST | `/issues/check-patch/<unit>` |
| POST | `/issues/carrier/<unit>` |
| POST | `/issues/weather/<unit>` |
| POST | `/issues/weather-bulk` |
| POST | `/issues/reboot-scrypted/<unit>` |
| POST | `/issues/reboot-snuc/<unit>` |
| POST | `/issues/reboot-pve/<unit>` |
| POST | `/issues/reboot-nuc/<unit>` |
| POST | `/issues/nuc-uptime/<unit>` |
| POST | `/issues/chkdsk/<unit>` |
| POST | `/issues/update-patch/<unit>` |
| POST | `/issues/create-deployment-project` |
| POST | `/issues/create-termination-project` |
| POST | `/issues/create-relocation-project` |
| POST | `/issues/lookup-site` |
| POST | `/issues/terminate-site` |
| POST | `/issues/activate-site` |
| POST | `/issues/clear-mu-coordinates` |
| POST | `/issues/clear-mu-site` |
| POST | `/issues/refurbish-projects/preview` |
| POST | `/issues/refurbish-projects` |
| POST | `/issues/tech-checks/preview` |
| POST | `/issues/tech-checks` |
| POST | `/issues/validate-unit/<unit>` |
| POST | `/issues/validate-unit-full/<unit>` |
| POST | `/issues/revalidate-list/<list_id>` |
| POST | `/issues/validate-stale-vpn/<unit>` |
| POST | `/issues/validate-camera-view/<unit>` |
| GET | `/issues/unit-context/<unit>` |
| POST | `/issues/pve-nvme-health/<unit>` |
| POST | `/issues/service-status/<unit>` |
| POST | `/issues/pve-resources/<unit>` |
| POST | `/issues/camera-matrix/<unit>` |
| POST | `/issues/run-diagnostics/<unit>` |
| GET | `/issues/unit-history/<unit>` |
| GET | `/issues/flap-report` |
| GET | `/issues/history-stats` |
| POST | `/issues/history-compact` |
| GET | `/issues/unit-status/<unit>` |
| POST | `/issues/unit-lock/<unit>/clear` |
| GET | `/issues/busy-units` |
| GET, POST | `/issues/unit-note/<unit>` |
| POST | `/issues/security-update-fix/step1/<unit>` |
| POST | `/issues/security-update-fix/step2/<unit>` |
| POST | `/issues/security-update-fix/shutdown/<unit>` |
| POST | `/issues/security-update-fix/finish/<unit>` |
| POST | `/issues/security-update-fix/verify/<unit>` |
| POST | `/issues/restart-services/<unit>` |
| GET | `/issues/shield/<unit>` |
| GET | `/issues/shield-component/<unit>` |
| GET | `/issues/attached-mu/<unit>` |
| GET | `/issues/site-page/<unit>` |
| GET | `/issues/event-records/<unit>` |
| GET | `/issues/switch/<unit>` |
| GET | `/issues/relay/<unit>` |
| GET | `/issues/pve/<unit>` |
| GET | `/recovery_email` |
| POST | `/recovery_email/results` |
| GET | `/recovery_email/watch/<job_id>` |
| GET | `/recovery_email/stream/<job_id>` |

---

## Environment variables (summary)

See `.env.example` for the full list. Common ones:

| Variable | Purpose |
|----------|---------|
| `erp_token` | ERP API |
| `victron_token` / `idUser` | Victron VRM |
| `workTLD` | Domain for ERP / Shield / Scrypted URLs |
| `fishuser` / `fishpass` | Camera / relay auth |
| `switchuser` / `switchpass` | Switch UI |
| `nucuser` / `nucpass` | NUC SSH |
| `pveuser` / `pvepass` / `pvesshuser` | PVE web + SSH |
| `scryptuserweb` / `scryptuserssh` / `scryptpass` | Scrypted |
| `MESH_BASE_URL` / `RAINDANCE_BASE_URL` | Optional Open menu bases |
| `SENTRA_NETWORK_TOOL_V19_DIR` | Path to `Sentra_Network_toolv19` |
| `PAUSE_AUTOMATED_TASKS` | `1` pauses schedulers / auto poll |
| `DISABLE_ERP_WRITES` | `1` (default) leaves ERP write buttons visible but disabled; POST routes return 403. Set `0` to allow writes. Resolve (R) is local-only and stays enabled. |
| `WORK_TOOL_ENV` / `WORK_TOOL_PORT` | live vs sandbox |
| `WORK_TOOL_BIND` | Interface to bind. Defaults to `0.0.0.0` so the dashboard is reachable at the machine's LAN IP, which is how the NOC uses it. Set `127.0.0.1` to restrict it to the local machine. Put this in `.env` — the service reads `.env`, not `run_live.bat`. |
| `myemail` / `mypass` | ART form login (Recovery Email hourly report) |
| `company` | Service-name prefix on the Scrypted box (`acme` → `acme-web.service`). Required by Restart All Services and Service Status. |
| `UNIT_HISTORY_KEEP_DAYS` | Days of validation history to keep in `data/<env>/unit_history.db` (default `90`). A hard 200,000-row ceiling applies regardless. |
| `ART_DATA_URL` | Optional ART report URL (default reportId=153) |
| `ART_REPORT_REFRESH_SECONDS` | ART spreadsheet refresh interval (default `3600`) |
