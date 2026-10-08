# work_tool — working notes for Claude

Internal Flask dashboard for NOC / field ops: ERP outage verification, unit
health checks, camera launch, router/switch/PVE tools. Read `README.md` for
what the UI does and for the full route reference; this file is about how to
work on the code without breaking a live NOC tool.

## Shape of the codebase

| File | Role |
|------|------|
| `work_tool/` | All domain logic, as a package. **Import it as `work_tool` exactly as before** — `__init__.py` re-exports every name, public and private, so `work_tool.<anything>` still resolves. |
| `work_tool/_core.py` | The un-split remainder (~8,800 lines). ERP client, netsheet/inventory, cameras, validation, SSH device ops, ART/recovery, the CLI `main()`. |
| `work_tool/locks.py` | Per-unit busy registry and shared unit notes. Zero dependencies on core. |
| `work_tool/weather.py` | Open-Meteo lookups, WMO mapping, region coordinates. |
| `work_tool/diagnostics.py` | The read-only diagnostics and the shared `_ssh_read` helper. |
| `work_tool/security_update.py` | The guided Scrypted GPU-passthrough fix and platform service restarts. |
| `work_tool/recovery_email.py` | Turns the Recovery Email Check's five lists into one email status per unit, for the Graphs modal's email pill. |
| `work_tool/project_progress.py` | The Project Progress check: classifies each NOC project as NOC done (>= 83.3%, green), stalled (>10% and <82%, unchanged in ERP for over 2 days) or not started (<= 10%, same), and converts ERP's America/Boise timestamps by hand (no tzdata on the service). |
| `work_tool/fd_cameras.py` | FD camera discovery from the unit's MikroTik router (SSH port 10000, read-only DHCP lease listing; cameras found by lease comment, cached 1 h / failures 5 min). This is the camera source for FD units everywhere: `list_unit_cameras` (Open Cameras, snapshots, grid, proxy, test emails) and Validate (Full) use it, falling back to the net sheet when the router can't be read. Router cameras are lowercase `fd:<name>` targets that `ping_camera` resolves; FD camera-outage tickets use them when the subject names a site camera, is generic, or names a number unique on the site. |
| `flask_endpoints.py` | Every HTTP route. There is no `app.py`. Routes stay thin and delegate into `work_tool`. |
| `templates/issues_results.html` | The dashboard's markup, plus a small inline `<script>` that injects Jinja values (`jobId`, `erpWritesDisabled`, ...). |
| `static/issues_results.js` | All dashboard JavaScript (~17k lines). This is where buttons and command menus live. |
| `static/issues_results.css` | All dashboard styles, with the `:root` palette at the top. Both static files are cache-busted by mtime (`_static_asset_version`). |
| `static/camera_shim.js` | Injected into proxied camera UIs (Dahua H5 / Hikvision). |
| `unit_history.py` | SQLite-backed per-unit validation history (`data/<env>/unit_history.db`). Append-only; every function fails soft and never raises into a validation run. |
| `zabbix_tool.py`, `page_file.py`, `art_get.py`, `issues.py` | Standalone helpers/CLIs, not imported by the web app (except `zabbix_tool`). |
| `work_tool_refactored.py` | A never-imported preview refactor. Do not edit it or wire code to it without deciding to adopt it. |

## Guardrails — check these before writing anything that touches ERP

- **`DISABLE_ERP_WRITES` defaults to `1`.** Mutating ERP actions stay visible
  but disabled in the UI and their POST routes return 403. When adding a route
  that writes to ERP, gate it with `erp_writes_disabled()` and
  `_erp_writes_blocked_response()` like its neighbours. Resolve (R) is local
  only and deliberately not gated.
- **`PAUSE_AUTOMATED_TASKS=1` in both `run_live.bat` and `run_sandbox.bat`.**
  The 4:00/4:05/4:10 AM jobs stay off. Don't "fix" a scheduler that looks
  idle — it is paused on purpose. Everything else in the background is a
  deliberate exception: the 30-minute ERP ticket/project pull and the hourly
  ART report refresh (Andrew's request, 2026-09-15), the fleet report polls
  (Units Unplugged/Shaded Units/Dead Panels/VRM Disconnected/Battery
  Outlook/Power vs Cell) and the Power & Infra Alerts (Zabbix+VRM) poll.
  The polls are read-only with no
  side effects, and a tech shouldn't have to hit Refresh by hand after every
  service restart just to see them populate, so they run regardless of this
  flag (see `_run_fleet_check` / `_run_scheduled_power_infra_alerts` in
  `flask_endpoints.py`). The hourly recovery email status check is the
  same kind of exception: it runs right after each hourly ART report
  download, only pings units and reads the spreadsheet (it never sends an
  email), and feeds the Graphs modal's email pill and the row's ✉ glyph — see
  `_run_recovery_email_status_check` and `work_tool/recovery_email.py`.
  The Up Steady re-check is another (Andrew's request, 2026-10-08):
  nothing else re-pings a ticket already on the board, so a unit that
  dropped after startup sat green in Up Steady. Every 30 minutes
  (`UP_STEADY_REVALIDATE_SECONDS`) `_revalidate_up_steady_loop` runs the
  same logic as the list's Revalidate button, and after each email check
  `_revalidate_up_steady_from_email_check` re-checks right away any Up
  Steady unit that check found down. Both go through
  `_revalidate_shared_list`, so list placement has one rule.
  None of them start in sandbox at all though — their
  whole scheduler is skipped there (`WORK_TOOL_ENV != "sandbox"` at the
  `_start_arizona_validation_scheduler()` call sites), so this doesn't add
  any VRM/Zabbix load to a dev sandbox.
- **Startup runs in a fixed order, not on timers** (Andrew's request,
  2026-10-02): initial ping sweep -> weather (Battery Outlook) -> Power vs
  Cell -> the reports (ART report + recovery email check, the fleet
  reports, Power & Infra Alerts) -> the Camera Outage Report + per-unit
  camera find, last. Each stage holds its first pass on a
  `threading.Event` the stage before it sets (`wait_for_stage` /
  `marks_stage` on `make_fleet_report`, `_wait_for_startup_stage` for the
  hand-written loops), capped at `STARTUP_STAGE_TIMEOUT_SECONDS`. A new
  background report belongs in the reports stage: give it
  `wait_for_stage=STARTUP_STAGE_POWER_VS_CELL` and
  `marks_stage=_startup_report_event()` (so the camera job waits for it
  too), not a fixed startup delay.
- **The live instance is a Windows service, `IssuesDashboard`.** It runs
  :5000 continuously, starts automatically, and launches
  `flask_endpoints.py` **directly — it never reads `run_live.bat`**. So a
  setting the live instance needs must be a code default or live in `.env`
  (loaded at import). Putting it in a `.bat` changes nothing for the service.
  Andrew restarts the service and refreshes to pick up changes.
- **The app binds `0.0.0.0` by default** and people reach it at the machine's
  LAN IP. Do not "harden" this to loopback: it silently breaks the service and
  presents as "the app won't start". `WORK_TOOL_BIND` narrows it if ever needed.
- **Develop against sandbox.** `run_sandbox.bat` serves :5001 with auto-reload
  and its own `data/sandbox/`. Stop the service before running `run_live.bat`
  by hand, or they fight over :5000. Sandbox forces `automated_tasks_paused()`
  to True.

## Netsheet columns

`net_sheet.csv` is gitignored and is the source of truth for device IPs.
Rows are addressed by index, so these numbers matter:

```
0 Unit/Site   1 Router IP   2 Switch IP   3 NUC IP    4 Speaker IP
5 Fisheye     6 Camera 1    7 Camera 2    8 Camera 3  9 Camera 4
10 Relay      11 PVE        12 Scrypted
```

`net_array` is loaded once at import by `ensure_net_array()`, which never
raises — a missing net sheet leaves it empty and individual units report
"not found in net sheet" instead of taking the dashboard down. **Never read
`net_array` directly in a new function.** Use `_net_row_for_unit(unit)` for a
plain lookup, or `ensure_unit_net_info(unit, needed_indexes=(11,))` when a
blank cell should be backfilled from v19/ERP first.

## Unit conventions

- Units are `RD####`, `FD####`, `MU####`, `SC-` prefixed in ERP components.
- `uses_pve(unit)` — unit number >= 3300 runs PVE with Scrypted in VM 101;
  below that it is a Windows NUC. In the dashboard JS this is `entry.hasPve`.
- ACRD units (`is_acrd_unit`) are RD/FD heads with no MU trailer: fisheye plus
  Camera 1–3, never Camera 4.
- Subjects look like `PHX - RD3076 - ...`; the leading token is the region code
  and drives the metro weather icons.

## The work_tool package

`work_tool.py` became `work_tool/` — same public surface, smaller files.
`__init__.py` copies every name out of each submodule into the package
namespace, including underscore-prefixed helpers, because callers and tests
reach for those. `flask_endpoints.py` needed **no changes at all**, and a
parity check confirmed 0 of the 468 previously-exposed names went missing.

Two rules keep it working:

- **Put new code in the module it belongs to, not `_core`.** `_core` is the
  un-split remainder, not the default home.
- **Never rebind shared module-level state from a submodule.** `net_array` and
  the lock registry are shared because they are only ever *mutated in place*
  (`.clear()`, `.append()`), so every module holds the same object. Rebinding
  one (`net_array = [...]`) would silently give that module a private copy.
  Use `_net_row_for_unit()` / `ensure_unit_net_info()` and you cannot get this
  wrong.

Cameras, ERP projects and the PVE helpers were deliberately **not** split:
core calls into them in several places, so cutting them creates import cycles
that can't be verified without running the app. The one cycle that did appear
— the CLI `main()` calling into `security_update` — is handled with a deferred
import inside `main()`.

## Adding a per-unit command button

Three edits, in this order:

1. **`work_tool/`** (the submodule it belongs to, not `_core`) — a function returning `(info_dict, error)` for reads
   (see `get_unit_patch_version`, `pve_nvme_health`) or `(ok, message)` for
   actions (see `reboot_pve`). Resolve the IP with `ensure_unit_net_info`,
   pass `timeout=` to paramiko `connect` *and* `exec_command`, and `close()`
   in a `finally`.
2. **`flask_endpoints.py`** — a thin route returning
   `jsonify({"ok": True, **info})` or `400` with `{"ok": False, "error": ...}`.
   Disruptive actions go through `_run_locked_quick_action`, which takes the
   per-unit lock; read-only diagnostics do not need it.
3. **`static/issues_results.js`** — for a read-only check, add it to
   `appendDiagnosticsCommandMenu` via `appendDiagnosticButton`, which wraps
   the whole fetch/log/report pattern: you supply a label, endpoint and an
   optional `detailLines(data)` formatter. Device-specific actions go in
   `appendScryptedLinuxMenuItems` / `appendNucMenuItems`; anything that
   interrupts service goes in the "Power / Disruptive Actions" submenu and
   needs a `confirmMessage`.

## List filtering

`selectedIssueLists` / `selectedProjectLists` are Sets of list ids, and
`applyListFilters()` is the single choke point that decides section
visibility. Filtering applies only when **One list** is active *and* the Set
is non-empty — `filteringEnabled() && selectedLists.size > 0` — so an empty
selection falls back to showing everything rather than blanking the page.

`renderListCategoryMenu()` builds the checkbox menu (panel switch + startup
only); `syncListControls()` refreshes the toggle buttons, the dropdown label
and every checkbox and count, and is called on every filter pass. Per-list
complete state lives in `listCompleteState`, set by `setListComplete()`.

The stats strip (`renderStatsStrip`) is a read-only summary — it is not a
filter. Don't wire click handlers onto it.

## Colour

Every colour resolves through CSS custom properties declared in a `:root`
block: at the top of `static/issues_results.css` for the dashboard, and at the
top of each other template's own `<style>`. **There are no colour
literals outside `:root`** — a repaint is a change to those values and nothing
else. Names are roles (`--bg-panel`, `--border-strong`, `--text-muted`,
`--accent`, `--ok`, `--danger`), never colours, so the names survive a repaint.
`rgba()` tints reference companion `--<role>-rgb` triplets so they stay in sync.

The theme is "Cold Cathode": a light blue-teal instrument panel on near-black.
Three things carry it beyond hue — the cool near-black ground, a single
monospace stack for the whole UI, and flat 2-3px corners via `--radius-sm` /
`--radius` / `--radius-pill`. Prose is a cool neutral and is deliberately NOT
tinted with the accent; the accent belongs on buttons, links, headings and
borders. Two earlier attempts failed exactly there — one recoloured everything
violet, the other made body text amber, which reads as a yellow wash.

The accent hue is chosen so the chrome never competes with a status light
(nearest status is 31.5 dE away), which is what lets the statuses stay
conventional green/yellow/orange/red. Status colours were picked by
measurement, not taste — see `docs/palette.md`. If you change one, re-run those
checks; green/yellow/orange/red are only ~11-12 dE apart under deuteranopia
even now, which is why the lights also carry the glyphs. `--led-idle` is a
neutral grey so the "no reading" light never reads as UI furniture.

Command menus come from `createCommandMenuElement()`, and the submenus inside
them from the `appendXCommandMenu` builders (`appendValidateCommandMenu`,
`appendWeatherCommandMenu`, `appendCamerasCommandMenu`,
`appendOpenCommandMenu`, `appendDiagnosticsCommandMenu`,
`appendRouterCommandMenu`, `appendArtMenu`, `appendSwitchCommandMenu`,
`appendSetFieldsCommandMenu`, `appendLinuxCommandMenus`). The Power vs Cell
Graphs modal's right-hand rail calls the same builders
(`renderGraphsDeviceMenu`), so an action added to one of them shows up on the
ticket row's menu and in the modal with no extra work — keep it that way: the
row's unit button opens the modal, and its ▾ quick menu is only a shortcut
(Andrew's request, 2026-10-03), so the modal must stay a superset of it.

Both places also get a **Search commands** box (`createCommandSearch()`;
`ensureCommandMenuSearch()` re-inserts it in the row menu, whose panel gets
rebuilt by the multi-unit chooser). `filterCommandMenu()` walks the live DOM
on each keystroke rather than any registry, so a new action is searchable
with no extra work. Keep new actions as `.action-btn` elements inside
`.command-submenu-items` and give them a label worth typing; that is the
whole contract.

The shared per-unit note box is built by `createUnitNotesBox()` /
`loadUnitNote()` and used by both the row menu and the modal rail; reuse
those rather than building another notes UI.

To promote an action onto every ticket row, add an entry to the
`QUICK_ACTIONS` array instead — it is one object with a label, a tooltip, an
optional `show(entry)` gate, and either `run(entry, btn)` or `href(entry)`.

Results are written to the shared stdout pane with
`consoleLines.push(...)` + `renderConsole(true)`, and to `statusEl.textContent`.
For anything the user must not miss, also call `notify(message, kind)` —
every toast fades on its own (`"error"` ones after `TOAST_ERROR_AUTO_DISMISS_MS`,
slower than the rest, and only if nobody moused over it first) unless the
caller passes `{ persist: true }`. **Do not use
`window.alert`**: it blocks the whole tab, which is painful while a long ping
is streaming, and the message is already on screen twice.

The console is capped at `CONSOLE_MAX_LINES` (5,000) and trimmed in chunks,
because `renderConsole` rebuilds the whole buffer on each call.

## Validation history

`validate_unit_status` and `validate_unit_full` are thin wrappers over
`_validate_unit_status_impl` / `_validate_unit_full_impl` that record the
result to `unit_history`. **Call the wrappers, not the impls**, so new code
keeps feeding the flap report. `flap_summary()` counts healthy↔unhealthy
transitions rather than failures, which is what separates a unit that is
simply down from one that keeps bouncing. Recording costs no extra packets —
it reuses validations the dashboard already runs.

This is a storage-constrained work PC, so the file is bounded on two axes:
`UNIT_HISTORY_KEEP_DAYS` (90) and a hard 200,000-row ceiling, both applied by
`prune()` at startup. **`VACUUM` is what actually returns disk to the OS — a
`DELETE` alone never shrinks the file — and it cannot run inside a
transaction, which sqlite3 opens implicitly.** `_vacuum()` handles that; don't
re-implement pruning without it. `tests/test_diagnostics.py` has a regression
test for exactly this.

## Per-unit lock

`unit_busy_start / touch / end / force_clear` in `work_tool/locks.py` stop two
people (or two tabs) running conflicting actions on one unit, and double as
the server-side job store for the multi-step Security Update Fix wizard. The
caller gets a token it must present to touch or end the job. It is a live
lock, not an audit trail — nothing is kept once a job ends.

## House style

- Interpolating anything into a remote shell command means `shlex.quote` plus
  a whitelist check on the input (see `pve_nvme_health`'s device path guard).
- Every `requests` call passes `timeout=`. No exceptions.
- Nothing network-bound, blocking, or credential-dependent at module import.
- Errors surface as readable sentences for a NOC tech at 3 AM, naming the fix
  ("Set pvesshuser=root and pvepass in .env"), not a bare exception string.

## Never commit

`.env`, `net_sheet.csv`, `map_sheet.csv`, `false_mu.csv`, `nuc_memory.csv`,
`filtered_mesh_vpn*.csv`, `resolved_today.json`, `uploads/`, `data/sandbox/`,
or any `.xlsx` export. All are in `.gitignore` — keep it that way. Screenshots
in `docs/` are blurred before committing.

## Tests

`python -m unittest discover -s tests -v` — pure-function coverage only
(subject/netsheet/patch/weather/SMART parsing). No network, SSH or ERP.
Add cases here when you touch a parser; everything else needs the sandbox.
