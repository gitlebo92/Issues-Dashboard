"""
Agent driver for the work_tool Issues Dashboard (Windows).

    python .claude/skills/run-work-tool/driver.py start      # sandbox :5001, background
    python .claude/skills/run-work-tool/driver.py status
    python .claude/skills/run-work-tool/driver.py drive < script.txt
    python .claude/skills/run-work-tool/driver.py stop

`drive` runs a headless *system* Chrome (Playwright channel="chrome", so no
browser download) and reads one command per line from stdin:

    nav <path-or-url>          go to BASE + path (default BASE http://127.0.0.1:5001)
    wait-for <selector>        wait until visible (Playwright selector syntax)
    wait-text <text>           wait until that text is visible anywhere
    click <selector>
    fill <selector> <text>     fill input (fires input events)
    press <key>                e.g. Enter, Escape
    hover <selector>
    sleep <seconds>
    text <selector>            print innerText of the first match
    count <selector>           print number of matches
    eval <js expression>       print the JSON result
    screenshot [name]          full page -> SHOT_DIR/<name>.png
    screenshot-el <name> <sel> crop to one element (name first: selectors have spaces)
    console-errors             print JS console errors / page errors seen so far

Lines starting with # are comments. Any failing command exits non-zero after
saving SHOT_DIR/error.png. Never point this at :5000 — that is the live
IssuesDashboard service other techs are using.
"""
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

UNIT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PORT = int(os.getenv("WORK_TOOL_PORT") or 5001)
BASE = os.getenv("DRIVER_BASE") or f"http://127.0.0.1:{PORT}"
STATE_DIR = os.path.join(tempfile.gettempdir(), "work_tool_driver")
SHOT_DIR = os.getenv("SHOT_DIR") or os.path.join(STATE_DIR, "shots")
PID_FILE = os.path.join(STATE_DIR, "server.pid")
LOG_FILE = os.path.join(STATE_DIR, "server.log")


def _port_open(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _http_status(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def _listener_pids(port):
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
            pids.add(int(parts[4]))
    return pids


def cmd_start():
    if PORT == 5000:
        sys.exit("Refusing to start on :5000 — that's the live IssuesDashboard service.")
    if _port_open(PORT):
        print(f"already listening on :{PORT} -> {BASE}")
        return
    os.makedirs(STATE_DIR, exist_ok=True)
    env = dict(os.environ)
    # Same as run_sandbox.bat.
    env.update({
        "WORK_TOOL_ENV": "sandbox",
        "WORK_TOOL_PORT": str(PORT),
        "WORK_TOOL_DATA_DIR": os.path.join(UNIT_DIR, "data", "sandbox"),
        "PAUSE_AUTOMATED_TASKS": "1",
        "WORK_TOOL_BIND": "127.0.0.1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    log = open(LOG_FILE, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "flask_endpoints.py"],
        cwd=UNIT_DIR, env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            sys.exit(f"server exited with {proc.returncode}; see {LOG_FILE}")
        if _http_status(BASE + "/") == 200:
            print(f"up: {BASE}  (pid {proc.pid}, log {LOG_FILE})")
            return
        time.sleep(1)
    sys.exit(f"server did not answer on {BASE} within 90s; see {LOG_FILE}")


def cmd_stop():
    pids = set(_listener_pids(PORT))
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pids.add(int(f.read().strip() or 0))
        os.remove(PID_FILE)
    pids.discard(0)
    for pid in pids:
        # /T: the Werkzeug reloader parent and its serving child are separate
        # python.exe processes; kill the whole tree or the parent respawns it.
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    for _ in range(20):
        if not _port_open(PORT):
            print(f"stopped :{PORT}")
            return
        time.sleep(0.5)
    sys.exit(f":{PORT} still listening after kill (pids {sorted(pids)})")


def cmd_status():
    code = _http_status(BASE + "/")
    print(f"{BASE}/ -> {code}")
    if code == 200 and os.path.exists(LOG_FILE):
        print(f"log: {LOG_FILE}")
    sys.exit(0 if code == 200 else 1)


def cmd_drive(lines):
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_default_timeout(int(os.getenv("DRIVER_TIMEOUT_MS") or 30000))
        page.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        # Console "Failed to load resource" lines carry no URL; record them here.
        page.on("response", lambda r: r.status >= 400 and errors.append(
            f"http {r.status}: {r.request.method} {r.url.replace(BASE, '')}"))
        shot_n = 0
        try:
            for raw in lines:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                cmd, _, rest = line.partition(" ")
                rest = rest.strip()
                print(f"> {line}", flush=True)
                if cmd == "nav":
                    page.goto(rest if rest.startswith("http") else BASE + rest, wait_until="domcontentloaded")
                elif cmd == "wait-for":
                    page.locator(rest).first.wait_for(state="visible")
                elif cmd == "wait-text":
                    page.get_by_text(rest).first.wait_for(state="visible")
                elif cmd == "click":
                    page.locator(rest).first.click()
                elif cmd == "hover":
                    page.locator(rest).first.hover()
                elif cmd == "fill":
                    # A selector with spaces must be quoted: fill "input[name=a b]" text
                    if rest.startswith(("'", '"')):
                        parts = shlex.split(rest)
                        sel, text = parts[0], " ".join(parts[1:])
                    else:
                        sel, _, text = rest.partition(" ")
                    page.locator(sel).first.fill(text)
                elif cmd == "press":
                    page.keyboard.press(rest)
                elif cmd == "sleep":
                    time.sleep(float(rest or 1))
                elif cmd == "text":
                    print(page.locator(rest).first.inner_text())
                elif cmd == "count":
                    print(page.locator(rest).count())
                elif cmd == "eval":
                    print(json.dumps(page.evaluate(rest), default=str)[:4000])
                elif cmd == "screenshot":
                    shot_n += 1
                    path = os.path.join(SHOT_DIR, f"{rest or f'shot{shot_n}'}.png")
                    page.screenshot(path=path, full_page=False)
                    print(f"saved {path}")
                elif cmd == "screenshot-el":
                    name, _, sel = rest.partition(" ")
                    path = os.path.join(SHOT_DIR, f"{name}.png")
                    page.locator(sel).first.screenshot(path=path)
                    print(f"saved {path}")
                elif cmd == "console-errors":
                    print("\n".join(errors) if errors else "(no console errors)")
                else:
                    raise ValueError(f"unknown command: {cmd}")
        except Exception as exc:
            path = os.path.join(SHOT_DIR, "error.png")
            try:
                page.screenshot(path=path)
            except Exception:
                pass
            print(f"FAILED: {exc}\n(screenshot: {path})", file=sys.stderr)
            browser.close()
            sys.exit(1)
        browser.close()


def main():
    # Windows consoles default to cp1252; server messages use em dashes.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "status":
        cmd_status()
    elif cmd == "drive":
        cmd_drive(sys.stdin.read().splitlines())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
