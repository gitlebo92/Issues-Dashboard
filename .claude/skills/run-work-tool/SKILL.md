---
name: run-work-tool
description: Start, run, drive, screenshot and test the work_tool Issues Dashboard (Flask, Windows). Use when asked to run or launch the dashboard/sandbox, click through a unit's command menu, check a route or button works in the real app, take a screenshot of the UI, run the tests, or restart the live IssuesDashboard service.
---

The Issues Dashboard is a Flask app (`flask_endpoints.py`). Agents drive it with
`.claude/skills/run-work-tool/driver.py`: it starts/stops the **sandbox on :5001** in
the background, and its `drive` command runs a headless system Chrome (Python
Playwright) from a stdin script — nav / fill / click / screenshot / eval.

All paths are relative to `Dev/work_tool/`. Commands are Git Bash (the Bash tool).

**Never drive :5000.** That is the live `IssuesDashboard` Windows service other
techs are using; the driver refuses to start on it.

## Prerequisites

Python 3.12 at `C:\Program Files\Python312`, Google Chrome installed, `.env` and
`net_sheet.csv` present (both gitignored — copied from the old PC, not in git).

```bash
python -m pip install --user -r requirements.txt playwright
```

No `playwright install`: the driver uses the installed Chrome (`channel="chrome"`).

## Run (agent path)

```bash
python .claude/skills/run-work-tool/driver.py start    # -> up: http://127.0.0.1:5001 (pid ..., log ...)
python .claude/skills/run-work-tool/driver.py status   # exit 0 when / returns 200
```

One real flow — the ad-hoc unit menu (search a unit, Open > Shield > Open Site):

```bash
python .claude/skills/run-work-tool/driver.py drive <<'EOF'
nav /
wait-for #sandbox_banner
fill #list_search RD3565
wait-for #unit_tools .command-menu[open]
screenshot unit_menu
click #unit_tools details.command-submenu > summary:text-is("Open")
click #unit_tools details.command-submenu > summary:text-is("Shield")
screenshot-el shield_menu #unit_tools .command-menu-items
eval document.querySelector('#unit_tools a.action-btn[href*="/issues/shield/"]').getAttribute('href')
nav /issues/shield/RD3565
text body
console-errors
EOF
```

Screenshots -> `%TEMP%\work_tool_driver\shots\` (`SHOT_DIR` overrides); a failing
command saves `error.png` there and exits 1. Server log ->
`%TEMP%\work_tool_driver\server.log`. **Read the screenshot** before calling it done.

| drive command | does |
|---|---|
| `nav <path>` | goto `http://127.0.0.1:5001<path>` (or a full URL) |
| `wait-for <sel>` / `wait-text <text>` | wait until visible (30s, `DRIVER_TIMEOUT_MS`) |
| `click` / `hover <sel>`, `fill <sel> <text>`, `press <key>` | act |
| `text <sel>`, `count <sel>`, `eval <js>` | print what's there |
| `screenshot [name]`, `screenshot-el <name> <sel>` | viewport 1600x1000 / one element |
| `console-errors` | JS errors **and** every HTTP >= 400 with its URL |
| `sleep <s>` | last resort — prefer `wait-for` |

Stop:

```bash
python .claude/skills/run-work-tool/driver.py stop     # -> stopped :5001
```

## Direct invocation (no server)

Most changes are in `work_tool/` functions; call them directly. Importing loads
`.env`, so these hit real ERP/devices (read-only functions only — check before
calling anything that writes):

```bash
python -c "import work_tool as wt; print(wt.resolve_dashboard_site_id('RD3565', ''))"
```

## Test

```bash
python -m unittest discover -s tests 2>&1 >/dev/null | grep -E '^(Ran|OK|FAILED|FAIL:|ERROR:)'
```

-> `Ran 233 tests` / `OK`. The suite prints pages of dashboard stdout; the filter
keeps the verdict. Pure functions only — no network.

## Live service (:5000)

`IssuesDashboard` = NSSM service running `python flask_endpoints.py` as SYSTEM,
auto-start, restarts on crash, logs `data/live/service_std{out,err}.log`. Ship a
change by restarting it (PowerShell, admin):

```powershell
Restart-Service IssuesDashboard
```

## Gotchas

- **Loading `/` starts the shared validation job** — it pulls ERP tickets and pings
  ~100 units for real (`#status` reads "Running validation..."). Read-only, but it's
  live network traffic; the page is usable immediately, don't wait for it to finish.
- **Searching a unit with no ticket auto-opens its ad-hoc menu** in `#unit_tools`
  (`.command-menu[open]`) — no click on the unit button needed.
- **Use `summary:text-is("Open")`, not `text=Open`** — "Open" substring-matches
  "Open Site", "Open Mesh", ... and you click the wrong thing.
- **Open-menu buttons are `<a target="_blank">`.** Clicking spawns a tab the driver
  doesn't follow — `eval` the `href` and `nav` to it instead.
- **Expected `http 400`s on units without VRM/MU** (warehoused, ACRD):
  `/issues/power-status|shading-status|dead-panel-status/<unit>` fire when the menu
  opens. Not a regression. Compare against a deployed unit before chasing them.
  The lone `console: ... 404` with no matching `http 404:` line is `/favicon.ico`
  (the app has none).
- **Sandbox is two python.exe processes** (Werkzeug reloader parent + server child).
  `driver.py stop` uses `taskkill /T` on both; killing only the port's PID lets the
  parent exit noisily, killing only the parent can orphan the listener.
- **Sandbox auto-reloads on `.py` edits** but static JS/CSS just need a page reload
  (cache-busted by mtime).
- **The service can't see `--user` packages** (it runs as SYSTEM). A new requirement
  must also be installed system-wide for the live service:
  `PYTHONNOUSERSITE=1 python -m pip install -r requirements.txt` from an admin shell —
  plain `pip install` skips it as "already satisfied" by the user copy.
- **Windows console is cp1252**; server messages contain em dashes. The driver
  forces UTF-8 on its own output; your own `python -c` prints may show `�` —
  cosmetic.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'flask'` / `'dotenv'`** (tests error out):
  requirements not installed for this Python — run the Prerequisites line.
- **`python -s -c "import flask"` fails right after a successful-looking
  `pip install`**: pip saw the user-site copy and installed nothing system-wide —
  rerun with `PYTHONNOUSERSITE=1` (SYSTEM gotcha above).
- **Flap tests fail with `4 != 3` / a scrambled timeline**: events recorded in the
  same clock tick sorted arbitrarily; fixed by ordering on `(ts, id)` in
  `unit_history.py`. If it reappears, a new query dropped the `id` tie-break.
