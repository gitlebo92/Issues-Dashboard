# work_tool — working notes for Claude

Internal Flask dashboard for NOC / field ops: ERP outage verification, unit
health checks, camera launch, router/switch/PVE tools. Read `README.md` for
what the UI does and for the full route reference; this file is about how to
work on the code without breaking a live NOC tool.

## Shape of the codebase

| File | Role |
|------|------|
| `work_tool.py` | All domain logic — ERP client, netsheet/inventory, camera proxy, SSH device ops, weather, validation, ART/recovery. ~10k lines, ~310 top-level functions. |
| `flask_endpoints.py` | Every HTTP route. There is no `app.py`. Routes stay thin and delegate into `work_tool`. |
| `templates/issues_results.html` | The entire dashboard UI and its JavaScript, in one file. This is where buttons and command menus live. |
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
  The 4:00/4:05/4:10 AM jobs and the 30-minute ERP poll stay off. Don't
  "fix" a scheduler that looks idle — it is paused on purpose.
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

## Adding a per-unit command button

Three edits, in this order:

1. **`work_tool.py`** — a function returning `(info_dict, error)` for reads
   (see `get_unit_patch_version`, `pve_nvme_health`) or `(ok, message)` for
   actions (see `reboot_pve`). Resolve the IP with `ensure_unit_net_info`,
   pass `timeout=` to paramiko `connect` *and* `exec_command`, and `close()`
   in a `finally`.
2. **`flask_endpoints.py`** — a thin route returning
   `jsonify({"ok": True, **info})` or `400` with `{"ok": False, "error": ...}`.
   Disruptive actions go through `_run_locked_quick_action`, which takes the
   per-unit lock; read-only diagnostics do not need it.
3. **`templates/issues_results.html`** — for a read-only check, add it to
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

Every colour in every template resolves through CSS custom properties declared
in a `:root` block at the top of that file's `<style>`. **There are no colour
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

Every command menu gets a search box from `createCommandMenuElement()` (the
shared factory both menu builders use), so a new action is searchable with no
extra work — `filterCommandMenu()` walks the live DOM rather than any
registry. Keep new actions as `.action-btn` elements inside
`.command-submenu-items` and give them a label worth typing; that is the whole
contract.

To promote an action onto every ticket row, add an entry to the
`QUICK_ACTIONS` array instead — it is one object with a label, a tooltip, an
optional `show(entry)` gate, and either `run(entry, btn)` or `href(entry)`.

Results are written to the shared stdout pane with
`consoleLines.push(...)` + `renderConsole(true)`, and to `statusEl.textContent`.
For anything the user must not miss, also call `notify(message, kind)` —
`"error"` toasts stay until dismissed, everything else fades. **Do not use
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

`unit_busy_start / touch / end / force_clear` in `work_tool.py` stop two
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
