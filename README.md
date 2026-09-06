# work_tool

Internal Flask dashboard for NOC / field ops: ERP outage verification, unit health checks, camera launch, router/switch tools, and related helpers.

Screenshots below were taken from a live local instance. **Sensitive ticket text, unit IDs, customer/site names, and stdout are blurred.** Menu labels and chrome are left readable on purpose.

> **Do not click ERP write actions** while exploring (Create Deployment, Terminate/Activate Site, Clear MU*, Tech Checks commit, Update Patch Version, Set Fields writes, Resolve→ERP). Everything documented as “Open / Validate / Ping / Snapshot” is read-oriented.

---

## Setup (coworkers)

1. Get access to the **private** GitHub repo.
2. Clone the repo.
3. Copy `.env.example` → `.env` and fill in credentials.
4. **Never commit** `.env`, `net_sheet.csv`, `uploads/`, or exported CSVs.
5. Install Python packages used by `flask_endpoints.py` / `work_tool.py` (and `Pillow` only if regenerating docs screenshots).
6. Copy a local `net_sheet.csv` from an existing install (gitignored).
7. Optionally set `SENTRA_NETWORK_TOOL_V19_DIR` to your v19 tool folder.

```bat
run_live.bat      rem http://127.0.0.1:5000 — daily use
run_sandbox.bat   rem http://127.0.0.1:5001 — dev/test (auto-reload)
```

| Script | URL | Purpose |
|--------|-----|---------|
| `run_live.bat` | http://127.0.0.1:5000 | Production dashboard |
| `run_sandbox.bat` | http://127.0.0.1:5001 | Dev/test (own `data/sandbox/`) |

With `PAUSE_AUTOMATED_TASKS=1` (default on both bats), scheduled 4:00/4:05/4:10 jobs and 30‑minute ERP polling stay off. Manual **Pull Issues**, validate, Open menus, etc. still work.

---

## 1. System Dashboard (hub)

![System Dashboard](docs/screenshots/01-dashboard-hub.png)

Landing page at `/`. Links into the main tools:

| Link | Route | What it does |
|------|-------|----------------|
| **Unit Outage Verification Tool** | `/issues` → `/issues/watch` | Primary NOC report (lists, LEDs, command menus) |
| **Victron VRM Checker** | `/victron` | Look up a MU/unit on Victron VRM |
| **Outage Filter** | `/outage_filter` | Compare Mesh CSV vs Issue CSV for false positives |
| **Recovery Email Check** | `/recovery_email` | Classify Shield NOC spreadsheet rows for outage/recovery email state |
| **Linux Diagnostic Tool** | `/linux` | SSH diagnostic stream for a unit |

---

## 2. Unit Outage Verification Report

Start from **Unit Outage Verification Tool** → **Start ERP Issue Verification**, or open `/issues/watch` if a shared job is already running.

![Issues report (blurred)](docs/screenshots/02-issues-report.png)

### Layout

- **Left — Stdout:** Live validation / ping / carrier / SSH-style logs. Search + Clear.
- **Right — Lists:** Tickets grouped by category. Filter search, **All lists / One list**, **Pull Issues**, **Clear checkboxes**.
- **Header counters:** Resolved today / Worked / Skipped (local workflow tracking).
- **Per-row LEDs:** Green / yellow / orange / red compute (and speaker/camera LEDs where relevant).
- **R / W / S:** Resolved / Worked / Skipped checkboxes (local UI state; Resolve can also hit ERP — treat **R** carefully).

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

### Projects panel

Switch the toolbar dropdown from **Issues** → **Projects**.

![Projects panel (blurred)](docs/screenshots/06-projects-panel.png)

Shows ERP-ish project buckets such as **Open**, **In Progress**, and **Deployment Prep**, with the same unit command menus and connectivity LEDs. **Pull Projects** refreshes project data (read). Avoid Task Controls that write (Terminate / Activate / Clear MU / Tech Checks commit).

### Same unit on multiple tickets

If a unit appears more than once (e.g. three tickets), **Validate (Quick/Full)** updates the **status LED on every occurrence** of that unit across lists. Tickets are not auto-moved just because a sibling was validated.

### Unit search / Unit tools

Type a unit into the list filter even if it is not on the current report. Matching tickets filter in place; with no ticket match you get an ad-hoc **Unit tools** row for the same command menus.

---

## 3. Per-unit command menu

Click the unit button (left of the LED) to open **Commands**.

![Command menu (blurred)](docs/screenshots/03-command-menu.png)

### Validate

| Action | Behavior |
|--------|----------|
| **Validate (Quick)** | Category / connectivity re-check (`/issues/validate-unit/...`). On NUC-down lists may ping compute only. |
| **Validate (Full)** | Deeper multi-endpoint check (`/issues/validate-unit-full/...`) → LED colors (green/yellow/orange/red), optional list move. |

LED colors (compute):

- **Green** — up / steady  
- **Yellow** — soft down / still unreachable compute or Scrypted  
- **Orange** — multi-down  
- **Red** — fully down  

### Router

- **Get Carrier** — SIM ICCID → carrier via v19 inventory  
- **Quick Validate** — router-oriented check  
- **Ping Router** / **Long Ping Router** — ICMP (long ping streams to stdout)

### Cameras

- **Fisheye Snapshot** — grab snapshot into the UI  
- **Open All Cameras** — multi-tile launch page  
- **Open Camera N / Open Fisheye** — single camera (when netsheet has IPs)

### Open (external / proxied UIs)

In-app **Open** menu with **Shield** and **ERP** expanded. Button labels are unblurred; ticket/unit context elsewhere on the page is blurred.

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

These open browser tabs / redirects. They do **not** write ERP fields by themselves. Destination Shield/ERP pages are behind company auth, so docs show the in-app buttons rather than live site forms.

### Switch

- Bounce ports / uptime / log helpers when switch IP exists (see menu items on a unit with a switch).

### Linux / NUC (when unit supports them)

- **NUC:** reboot, uptime, chkdsk (read-only), Check Patch Version  
- **Linux → Scrypted:** Set No Audio, Reboot Scrypted / Reboot PVE (destructive — use carefully; not ERP writes, but they reboot gear)

### Avoid while documenting / training

- **Set Fields** (ERP field writes)  
- **Create Deployment Project**, **Create Refurbish**  
- **Terminate Site** / **Activate Site**  
- **Clear MU Coordinates** / **Clear MU Site**  
- **Tech Checks (180 Unit)** confirm  
- **Update Patch Version**  
- Checking **R** if your flow posts resolve to ERP  

---

## 4. Camera launch grid

From **Cameras → Open All Cameras** (or `/issues/cameras-launch/<UNIT>`).

![Camera launch grid (blurred)](docs/screenshots/05-cameras-launch.png)

- Grid of proxied camera UIs (Dahua H5 / Hikvision with shim).  
- Controls: **Columns**, **Zoom**, **Height**, **IE mode**, **Reload all**, **Open all in tabs**.  
- Per tile: Log out / Reload / Open tab.  
- ACRD / unit rules decide which cameras appear (e.g. fisheye + C1–C3, no C4 when no MU).  
- Live/PTZ/Smart Event drawing depends on vendor; Hikvision ActiveX needs Edge IE mode via **Open tab** / IE mode workflows.

---

## 5. Other hub tools

### Linux Diagnostic Tool

![Linux tool](docs/screenshots/07-linux-tool.png)

Enter a unit → **Check** → streamed SSH diagnostic stdout.

### Victron VRM Checker

![Victron tool](docs/screenshots/08-victron-tool.png)

Enter MU/unit → **Check** against Victron VRM APIs (`idUser` + `victron_token`).

### Outage Filter

![Outage Filter](docs/screenshots/09-outage-filter.png)

Upload Mesh CSV + Issue CSV → **Run Filter** to classify false positives vs real outages (can take 1–3 minutes).

### Recovery Email Check

![Recovery Email](docs/screenshots/10-recovery-email.png)

Upload Shield NOC outage spreadsheet → classify rows that need initial outage email, recovery email, false positive, pending, or already up to date.

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
| `WORK_TOOL_ENV` / `WORK_TOOL_PORT` | live vs sandbox |

---

## Secrets policy

- Commit `.env.example` and blurred docs screenshots only.  
- Do not commit `.env`, netsheets, uploads, or raw unblurred ops screenshots.  
- Rotate any token that ever appeared in an older git history of a different clone.

---

## Regenerating screenshots

Screenshots live in `docs/screenshots/`. They were captured with the Cursor browser tools against a local `:5000` instance (gowitness is optional; not required). Before capture, inject CSS blur on `.ticket-label`, unit command buttons, and `.console`, and **do not** press ERP write confirmations.
