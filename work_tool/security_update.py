"""
The guided Scrypted GPU-passthrough security update fix, and platform service restarts.

Split out of the original single-file work_tool.py. Everything here is
re-exported by work_tool/__init__.py, so each name is still reachable as
`work_tool.<name>` exactly as before.
"""

import time
import requests
import csv
import os
import sys
import re
import json
import asyncio
import subprocess
import tempfile
import shlex
import zabbix_tool
import unit_history
import multiprocessing
import paramiko
import threading
import socket
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from urllib.parse import quote
import urllib3

from ._core import (  # noqa: F401  (re-exported dependencies)
    _host_only,
    _net_row_for_unit,
    _pve_ssh_credentials,
    _scrypted_ip,
    _scrypted_ssh_credentials,
    ensure_unit_net_info,
    env_path,
    username,
)


@contextmanager
def _ssh_client(host, username, password, timeout=30):
    """
    Open an SSH connection the way every security_update_web_* step does
    (AutoAddPolicy, no agent/keys, an explicit timeout) — factored out
    after the SSH-timeout fix (2026-09-23) had to be applied by hand to
    12 near-identical connect() calls in this file; a future change to
    this setup now only needs to happen once. Closes the connection on
    the way out regardless of what the caller did inside the `with`.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host, username=username, password=password,
            timeout=timeout, allow_agent=False, look_for_keys=False,
        )
        yield client
    finally:
        client.close()


def _ssh_exec(client, command, timeout=30):
    """
    Run one command over an already-open connection from _ssh_client.
    Returns (output, errors, exit_status) as decoded text/int — the
    read-and-decode boilerplate every step below repeated on its own.
    Callers that need to run more than one command over the same
    connection (e.g. a script, then a follow-up reboot) call this more
    than once inside the same `with _ssh_client(...) as client:` block.
    """
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    output = stdout.read().decode("utf-8")
    errors = stderr.read().decode("utf-8")
    exit_status = stdout.channel.recv_exit_status()
    return output, errors, exit_status


def _bash_script(commands):
    """Wrap a list of shell commands as the `bash << 'EOF' ... EOF` heredoc
    every multi-command step below sends over SSH."""
    return "bash << 'EOF'\n" + "\n".join(commands) + "\nEOF"


def security_update_fix_part_1(unit):
    load_dotenv(env_path)
    pveSshUsername = os.getenv("pvesshuser")
    pveSshPass = os.getenv("pvepass")
    ip = None
    version = None
    errors = ""
    commands = [
        "set -e",
        "qm stop 101",
        "qm config 101 | grep hostpci",
        "qm set 101 --delete hostpci0",
        "qm set 101 --vga std"
    ]

    pvescript = "\n".join(commands)

    row = _net_row_for_unit(unit)
    if row is None or len(row) <= 11 or not str(row[11]).strip():
        print(f"No PVE IP for {unit} in net sheet")
        return None, unit
    ip = row[11]

    pveSshClient = paramiko.SSHClient()
    pveSshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        pveSshClient.connect(hostname=ip, username=pveSshUsername, password=pveSshPass, timeout=30)
        stdin, stdout, stderr = pveSshClient.exec_command(f"bash << 'EOF'\n{pvescript}\nEOF", timeout=30)
        output = stdout.read().decode("utf-8").strip()
        errors = stderr.read().decode("utf-8").strip()
        output = output.splitlines()
        if errors:
            print(f"stderr: {errors}")
        for line in output:
            print(line)
            if "hostpci" in line and "delete" not in line:
                parts = line.split(":", 1)
                version = parts[1].strip()
                print(f"version: {version}")
        if version is None:
            print(f"Could not find hostpci configuration for {unit}")
            return None, unit
        return version, unit
    except Exception as e:
        print(f"failed: {e} also {errors}")
        return None, unit
    finally:
        pveSshClient.close()
def security_update_fix_step_2(unit):
    load_dotenv(env_path)
    scryptSshUsername = os.getenv("scryptuserssh")
    scryptSshPass = os.getenv("scryptpass")
    scryptSshPassQ = shlex.quote(scryptSshPass or "")
    ip = None
    errors = ""
    unattended_fix_cmd = f"""
    if ! grep -q '"linux-image";' /etc/apt/apt.conf.d/50unattended-upgrades; then
        echo {scryptSshPassQ} | sudo -S sed -i 's|^Unattended-Upgrade::Package-Blacklist {{|Unattended-Upgrade::Package-Blacklist {{\\n\\t"linux-image";\\n\\t"linux-headers";\\n\\t"linux-generic";\\n\\t"linux-modules";\\n\\t"linux-tools";|' /etc/apt/apt.conf.d/50unattended-upgrades
    fi
    """
    # See security_update_web_step2's identical fix for why this can't be a
    # hardcoded build number — purges every installed 6.8.0-*-generic
    # kernel package except the one held below (138, known-good).
    purge_kernels_cmd = (
        "PURGE_PKGS=$(dpkg-query -W -f='${Package}\\n' "
        "'linux-image-6.8.0-*-generic' 'linux-headers-6.8.0-*-generic' 2>/dev/null "
        "| grep -v -- '-138-generic' || true); "
        f"if [ -n \"$PURGE_PKGS\" ]; then echo {scryptSshPassQ} | sudo -S apt purge -y $PURGE_PKGS; "
        "else echo 'No non-6.8.0-138-generic kernel packages installed to purge'; fi"
    )
    commands = [
            "set -e",
            purge_kernels_cmd,
            f"echo {scryptSshPassQ} | sudo -S apt install -f -y",
            f"echo {scryptSshPassQ} | sudo -S apt-mark hold linux-image-6.8.0-138-generic linux-headers-6.8.0-138-generic",
            f"echo {scryptSshPassQ} | sudo -S sed -i 's|^GRUB_DEFAULT=.*|GRUB_DEFAULT=0|' /etc/default/grub",
            f"echo {scryptSshPassQ} | sudo -S update-grub",
            "ls /boot/vmlinuz-* /boot/initrd.img-*",
            f"echo {scryptSshPassQ} | sudo -S dpkg -l | grep -E '^i[^i]' || true",
            f"echo {scryptSshPassQ} | sudo -S apt-mark showhold",
            unattended_fix_cmd,
            f"echo {scryptSshPassQ} | sudo -S grep -A8 'Package-Blacklist' /etc/apt/apt.conf.d/50unattended-upgrades || true",
            f"echo {scryptSshPassQ} | sudo -S unattended-upgrade --dry-run --debug 2>&1 | grep -i 'blacklist\\|linux-' || true"
        ]
    scryptedscript = "\n".join(commands)

    row = _net_row_for_unit(unit)
    if row is None or len(row) <= 12 or not str(row[12]).strip():
        print(f"No Scrypted IP for {unit} in net sheet")
        return unit
    ip = row[12]

    scryptedSshClient = paramiko.SSHClient()
    scryptedSshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        scryptedSshClient.connect(hostname=ip, username=scryptSshUsername, password=scryptSshPass, timeout=30)
        stdin, stdout, stderr = scryptedSshClient.exec_command(f"bash << 'EOF'\n{scryptedscript}\nEOF", timeout=30)
        output = stdout.read().decode("utf-8")
        errors = stderr.read().decode("utf-8")

        if errors:
            print(f"errors: {errors}")
            

        output = output.splitlines()
        for line in output:
            print(line)

        print(f"Rebooting {unit}...")

        scryptedSshClient.exec_command(
            f"echo {scryptSshPassQ} | sudo -S reboot", timeout=30)
        return unit
    except Exception as e:
        print(f"exception: {e}")
        return unit
    finally:
        scryptedSshClient.close()
def security_update_fix_step_3(unit, version):
    load_dotenv(env_path)
    scryptSshUsername = os.getenv("scryptuserssh")
    scryptSshPass = os.getenv("scryptpass")
    scryptSshPassQ = shlex.quote(scryptSshPass or "")
    pveSshUsername = os.getenv("pvesshuser")
    pveSshPass = os.getenv("pvepass")
    scrypt_ip = None
    pve_ip = None
    errors = ""
    errors2 = ""
    commands = [
        "set -e",
        f"echo {scryptSshPassQ} | sudo -S uname -r "
    ]
    commands2 = [
        "set -e",
        f"qm set 101 --hostpci0 {version}",
        "qm start 101"
    ]
    cmdscript = "\n".join(commands)
    cmdscript2 = "\n".join(commands2)
    row = _net_row_for_unit(unit)
    if row is None or len(row) <= 12:
        print(f"Unit {unit} not found in net sheet")
        return None, unit
    scrypt_ip = row[12]
    pve_ip = row[11]
    if not str(scrypt_ip).strip() or not str(pve_ip).strip():
        print(f"Missing Scrypted or PVE IP for {unit} in net sheet")
        return None, unit

    scryptSshClient = paramiko.SSHClient()
    scryptSshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pveSshClient = paramiko.SSHClient()
    pveSshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:

        scryptSshClient.connect(hostname=scrypt_ip, username=scryptSshUsername, password=scryptSshPass, timeout=30)
        stdin, stdout, stderr = scryptSshClient.exec_command(f"bash << 'EOF'\n{cmdscript}\nEOF", timeout=30)
        output = stdout.read().decode("utf-8")
        errors = stderr.read().decode("utf-8")

        output = output.splitlines()
        if errors:
            print(f"errors: {errors}")


        for line in output:
            print(line)
        print("Shutting down...")

        scryptSshClient.exec_command(f"echo {scryptSshPassQ} | sudo -S shutdown -h now", timeout=30)
        scryptSshClient.close()

        input("Once unit has fully shut down press enter to continue: ")
        try:
            print(f"Set hostpci version to: {version}")
            pveSshClient.connect(hostname=pve_ip, username=pveSshUsername, password=pveSshPass, timeout=30)
            stdin2, stdout2, stderr2 = pveSshClient.exec_command(f"bash << 'EOF'\n{cmdscript2}\nEOF", timeout=30)
            output2 = stdout2.read().decode("utf-8")
            output2 = output2.splitlines()
            errors2 = stderr2.read().decode("utf-8")
            if errors2:
                print(f"errors: {errors2}")
            for line in output2:
                print(line)
        except Exception as e:
            print(f"Excepted error: {e}")
            return None, unit
        finally:
            pveSshClient.close()
        return unit
            
            
    except Exception as e:
        print(f"Excepted error: {e}")
        return None, unit
def security_update_step_4(unit):
    load_dotenv(env_path)
    scryptSshUsername = os.getenv("scryptuserssh")
    scryptSshPass = os.getenv("scryptpass")
    scryptSshPassQ = shlex.quote(scryptSshPass or "")
    company = os.getenv("company")
    ip = None
    errors = ""
    errors2 = ""
    drivers_loaded = True

    commands = [
        f"echo {scryptSshPassQ} | sudo -S lspci -nn | grep -i VGA",
        f"echo {scryptSshPassQ} | sudo -S lsmod | grep i915",
    ]
    cmd2 = f"echo {scryptSshPassQ} | sudo -S dmesg | grep -i i915 | tail -20"
    cmdscript = "\n".join(commands)
    scryptSshClient = paramiko.SSHClient()
    scryptSshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    vga_counter = 0
    i915_counter = 0

    row = _net_row_for_unit(unit)
    if row is None or len(row) <= 12 or not str(row[12]).strip():
        print(f"No Scrypted IP for {unit} in net sheet")
        return False
    ip = row[12]
    try:
        scryptSshClient.connect(hostname=ip, username=scryptSshUsername, password=scryptSshPass, timeout=30)
        stdin, stdout, stderr = scryptSshClient.exec_command(f"bash << 'EOF'\n{cmdscript}\nEOF", timeout=30)
        errors = stderr.read().decode("utf-8")
        output = stdout.read().decode("utf-8")

        if errors:
            print(f"errors: {errors}")
        output = output.splitlines()
        for line in output:
            if "VGA compatible controller" in line:
                vga_counter += 1
            if "i915" in line:
                i915_counter += 1
        print("DUCK-DB Restarted..")
        stdin2, stdout2, stderr2 = scryptSshClient.exec_command(f"{cmd2}", timeout=30)
        errors2 = stderr2.read().decode("utf-8")
        output2 = stdout2.read().decode("utf-8")

        if errors2:
            print(f"errors: {errors2}")

        output2 = output2.splitlines()
        for line in output2:
            print(line)
        print(f"VGA controllers: {vga_counter}")
        print(f"i915 entries: {i915_counter}")

        if vga_counter != 2 or i915_counter != 7:
            print("!!!!Some drivers did not load!!!!")
            drivers_loaded = False
        return drivers_loaded
    except Exception as e:
        print(f"Exception error: {e}")
        return False
    finally:
        scryptSshClient.close()
def refresh_platform_services(unit):
    load_dotenv(env_path)
    scryptSshUsername = os.getenv("scryptuserssh")
    scryptSshPass = os.getenv("scryptpass")
    scryptSshPassQ = shlex.quote(scryptSshPass or "")
    company = os.getenv("company")
    ip = None
    errors = ""

    # Kept in sync with PLATFORM_SERVICES / PLATFORM_SERVICES_UNPREFIXED in
    # diagnostics.py — indexer, rtsp and docker were all missing until
    # 2026-09-12 (verified live: every real box runs exactly these 16).
    # docker.service goes first and unprefixed (no {company}- for it) — it
    # hosts the engine the rest depend on, so it needs to be back before
    # they are; systemctl restart blocks until systemd reports it started,
    # so the next line in this script doesn't run until docker actually is.
    commands = [
        f"echo {scryptSshPassQ} | sudo -S systemctl restart docker.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-database.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-watchdog.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-web.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-metadata.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-images.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-indexer.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-capture.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-rtsp.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-smtp.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-alarms.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-events.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-onvif.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-monitor.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-snmp.service",
        f"echo {scryptSshPassQ} | sudo -S systemctl restart {company}-cache.service"
    ]

    row = _net_row_for_unit(unit)
    if row is None or len(row) <= 12 or not str(row[12]).strip():
        print(f"No Scrypted IP for {unit} in net sheet")
        return False
    ip = row[12]
    try:
        with _ssh_client(ip, scryptSshUsername, scryptSshPass) as client:
            output, errors, _exit_status = _ssh_exec(client, _bash_script(commands), timeout=60)
    except Exception as e:
        print(f"exception: {e}")
        return False
    if errors:
        print(f"errors: {errors}")
    for line in output.splitlines():
        print(line)
    return True
def _security_fix_ip_pair(unit):
    """PVE + Scrypted IPs for the security update fix flow, via the modern netsheet helpers."""
    row = ensure_unit_net_info(unit, needed_indexes=(11, 12))
    if not row:
        return None, None, f"Unit {unit} not found in net sheet"
    pve_ip = _host_only(row[11] if len(row) > 11 else "")
    scrypted_ip = _host_only(row[12] if len(row) > 12 else "")
    if not pve_ip:
        return None, None, f"No PVE IP for {unit}"
    if not scrypted_ip:
        return None, None, f"No Scrypted IP for {unit}"
    return pve_ip, scrypted_ip, None
def security_update_web_step1(unit):
    """
    Security update fix, step 1: on PVE, stop VM 101 and remove the GPU
    passthrough (hostpci0) config, saving its value for later reassignment.
    Web-safe counterpart of security_update_fix_part_1 (no input()).
    """
    unit = str(unit or "").strip()
    if not unit:
        return False, "Missing unit", None
    pve_ip, _scrypted_ip, err = _security_fix_ip_pair(unit)
    if err:
        return False, err, None
    username, password, cred_error = _pve_ssh_credentials()
    if cred_error:
        return False, cred_error, None

    commands = [
        "set -e",
        "qm stop 101",
        "qm config 101 | grep hostpci",
        "qm set 101 --delete hostpci0",
        "qm set 101 --vga std",
    ]
    log_lines = []
    version = None
    try:
        with _ssh_client(pve_ip, username, password) as client:
            output, errors, _exit_status = _ssh_exec(client, _bash_script(commands))
    except Exception as exc:
        return False, f"Step 1 failed: {exc}", None
    output = output.strip().splitlines()
    errors = errors.strip()
    if errors:
        log_lines.append(f"stderr: {errors}")
    for line in output:
        log_lines.append(line)
        if "hostpci" in line and "delete" not in line:
            version = line.split(":", 1)[1].strip()
    if version is None:
        return False, f"Could not find hostpci configuration for {unit}", None
    log_lines.append(f"Saved hostpci0 version: {version}")
    return True, "\n".join(log_lines), version
def security_update_web_step2(unit):
    """
    Security update fix, step 2: on Scrypted, purge the vulnerable kernel
    package, hold the previous one, update grub, and reboot.
    Web-safe counterpart of security_update_fix_step_2 (no input()).
    """
    unit = str(unit or "").strip()
    if not unit:
        return False, "Missing unit"
    _pve_ip, scrypted_ip, err = _security_fix_ip_pair(unit)
    if err:
        return False, err
    username, password = _scrypted_ssh_credentials()
    if not username or not password:
        return False, "Set scryptuserssh and scryptpass in .env"
    passwordQ = shlex.quote(password)

    unattended_fix_cmd = f"""
    if ! grep -q '"linux-image";' /etc/apt/apt.conf.d/50unattended-upgrades; then
        echo {passwordQ} | sudo -S sed -i 's|^Unattended-Upgrade::Package-Blacklist {{|Unattended-Upgrade::Package-Blacklist {{\\n\\t"linux-image";\\n\\t"linux-headers";\\n\\t"linux-generic";\\n\\t"linux-modules";\\n\\t"linux-tools";|' /etc/apt/apt.conf.d/50unattended-upgrades
    fi
    """
    # The vulnerable build number isn't fixed fleet-wide — caught live,
    # 2026-09-29 (RD3338): this used to hardcode "6.8.0-139-generic", but
    # RD3338 had already drifted to 6.8.0-142-generic (unattended-upgrades
    # presumably got past the blacklist before this same step re-applies
    # it below), so purging 139 was a silent no-op — nothing installed by
    # that exact name — leaving whatever actually-installed kernel(s) the
    # unit had untouched. Now purges every installed 6.8.0-*-generic
    # image/headers package EXCEPT the one being held below (138, the
    # known-good GPU-passthrough build — see this module's own docstring),
    # covering the currently-booted kernel and any other stale ones that
    # piled up, not just whichever single version happened to be current
    # when this line was written.
    purge_kernels_cmd = (
        "PURGE_PKGS=$(dpkg-query -W -f='${Package}\\n' "
        "'linux-image-6.8.0-*-generic' 'linux-headers-6.8.0-*-generic' 2>/dev/null "
        "| grep -v -- '-138-generic' || true); "
        f"if [ -n \"$PURGE_PKGS\" ]; then echo {passwordQ} | sudo -S apt purge -y $PURGE_PKGS; "
        "else echo 'No non-6.8.0-138-generic kernel packages installed to purge'; fi"
    )
    commands = [
        "set -e",
        purge_kernels_cmd,
        f"echo {passwordQ} | sudo -S apt install -f -y",
        f"echo {passwordQ} | sudo -S apt-mark hold linux-image-6.8.0-138-generic linux-headers-6.8.0-138-generic",
        f"echo {passwordQ} | sudo -S sed -i 's|^GRUB_DEFAULT=.*|GRUB_DEFAULT=0|' /etc/default/grub",
        f"echo {passwordQ} | sudo -S update-grub",
        "ls /boot/vmlinuz-* /boot/initrd.img-*",
        f"echo {passwordQ} | sudo -S dpkg -l | grep -E '^i[^i]' || true",
        f"echo {passwordQ} | sudo -S apt-mark showhold",
        unattended_fix_cmd,
        f"echo {passwordQ} | sudo -S grep -A8 'Package-Blacklist' /etc/apt/apt.conf.d/50unattended-upgrades || true",
        f"echo {passwordQ} | sudo -S unattended-upgrade --dry-run --debug 2>&1 | grep -i 'blacklist\\|linux-' || true",
    ]
    try:
        with _ssh_client(scrypted_ip, username, password) as client:
            output, errors, exit_status = _ssh_exec(client, _bash_script(commands), timeout=120)
            log_lines = output.splitlines()
            if errors:
                # apt/update-grub write normal progress messages to stderr; only a
                # non-zero exit status (the script has `set -e`) means a command
                # actually failed.
                log_lines.append(f"stderr (informational unless the script failed): {errors}")
            if exit_status != 0:
                return False, "Step 2 error (command failed, exit status %d):\n%s" % (
                    exit_status, "\n".join(log_lines)
                )
            _ssh_exec(client, f"echo {passwordQ} | sudo -S reboot", timeout=30)
            log_lines.append(f"Rebooting {unit}...")
            return True, "\n".join(log_lines)
    except Exception as exc:
        return False, f"Step 2 failed: {exc}"
def security_update_web_shutdown(unit):
    """
    Security update fix, checkpoint: confirm the running kernel on Scrypted
    (after it comes back up on the held kernel from step 2), then shut it
    down so PVE can safely reassign the GPU. The web UI waits for you to
    confirm the unit is fully powered off before calling the finish step.
    """
    unit = str(unit or "").strip()
    if not unit:
        return False, "Missing unit"
    _pve_ip, scrypted_ip, err = _security_fix_ip_pair(unit)
    if err:
        return False, err
    username, password = _scrypted_ssh_credentials()
    if not username or not password:
        return False, "Set scryptuserssh and scryptpass in .env"
    passwordQ = shlex.quote(password)

    try:
        with _ssh_client(scrypted_ip, username, password) as client:
            output, errors, _exit_status = _ssh_exec(client, f"echo {passwordQ} | sudo -S uname -r")
            log_lines = []
            if errors.strip():
                log_lines.append(f"stderr: {errors.strip()}")
            log_lines.append(f"Running kernel: {output.strip()}")
            log_lines.append("Shutting down...")
            _ssh_exec(client, f"echo {passwordQ} | sudo -S shutdown -h now")
            return True, "\n".join(log_lines)
    except Exception as exc:
        return False, f"Shutdown step failed: {exc}"
def security_update_web_finish(unit, version):
    """
    Security update fix, finish: on PVE, reassign hostpci0 to the version
    saved in step 1 and start VM 101 back up. Only call this once the unit
    is confirmed fully shut down.
    """
    unit = str(unit or "").strip()
    version = str(version or "").strip()
    if not unit:
        return False, "Missing unit"
    if not version:
        return False, "Missing saved hostpci version from step 1"
    pve_ip, _scrypted_ip, err = _security_fix_ip_pair(unit)
    if err:
        return False, err
    username, password, cred_error = _pve_ssh_credentials()
    if cred_error:
        return False, cred_error

    commands = [
        "set -e",
        f"qm set 101 --hostpci0 {version}",
        "qm start 101",
    ]
    try:
        with _ssh_client(pve_ip, username, password) as client:
            output_text, errors, exit_status = _ssh_exec(client, _bash_script(commands))
    except Exception as exc:
        return False, f"Finish step failed: {exc}"
    output = output_text.splitlines()
    errors = errors.strip()
    if errors:
        output.append(f"stderr (informational unless the script failed): {errors}")
    if exit_status != 0:
        return False, "Finish step error (command failed, exit status %d):\n%s" % (
            exit_status, "\n".join(output)
        )
    message = "\n".join(output) if output else f"Set hostpci0 to {version} and started VM 101"
    return True, message
_VGA_CONTROLLERS_EXPECTED = 2
_I915_ENTRIES_EXPECTED = 7
def security_update_web_verify(unit):
    """
    Security update fix, verify: confirm the VGA/i915 passthrough drivers
    loaded after VM 101 is back up. Web-safe counterpart of
    security_update_step4 (returns a message instead of printing).

    Returns (ok, message, drivers_loaded, counts). counts is
    {"vga_counter", "vga_expected", "i915_counter", "i915_expected"} — the
    web wizard's Verify step visually flags each grepped count against its
    expected total (2 VGA controllers, 7 i915 entries) rather than making
    someone read the raw log to notice one came up short.
    """
    empty_counts = {
        "vga_counter": 0, "vga_expected": _VGA_CONTROLLERS_EXPECTED,
        "i915_counter": 0, "i915_expected": _I915_ENTRIES_EXPECTED,
    }
    unit = str(unit or "").strip()
    if not unit:
        return False, "Missing unit", False, empty_counts
    _pve_ip, scrypted_ip, err = _security_fix_ip_pair(unit)
    if err:
        return False, err, False, empty_counts
    username, password = _scrypted_ssh_credentials()
    if not username or not password:
        return False, "Set scryptuserssh and scryptpass in .env", False, empty_counts

    passwordQ = shlex.quote(password)
    commands = [
        f"echo {passwordQ} | sudo -S lspci -nn | grep -i VGA",
        f"echo {passwordQ} | sudo -S lsmod | grep i915",
    ]
    cmd2 = f"echo {passwordQ} | sudo -S dmesg | grep -i i915 | tail -20"
    vga_counter = 0
    i915_counter = 0
    log_lines = []
    try:
        with _ssh_client(scrypted_ip, username, password) as client:
            primary_output, primary_errors, _es1 = _ssh_exec(client, _bash_script(commands))
            if primary_errors:
                log_lines.append(f"stderr: {primary_errors}")
            for line in primary_output.splitlines():
                if "VGA compatible controller" in line:
                    vga_counter += 1
                if "i915" in line:
                    i915_counter += 1
            secondary_output, secondary_errors, _es2 = _ssh_exec(client, cmd2)
    except Exception as exc:
        return False, f"Verify step failed: {exc}", False, empty_counts
    if secondary_errors:
        log_lines.append(f"stderr: {secondary_errors}")
    log_lines.extend(secondary_output.splitlines())
    log_lines.append(f"VGA controllers: {vga_counter}")
    log_lines.append(f"i915 entries: {i915_counter}")
    drivers_loaded = vga_counter == _VGA_CONTROLLERS_EXPECTED and i915_counter == _I915_ENTRIES_EXPECTED
    if not drivers_loaded:
        log_lines.append("Some drivers did not load")
    counts = {
        "vga_counter": vga_counter, "vga_expected": _VGA_CONTROLLERS_EXPECTED,
        "i915_counter": i915_counter, "i915_expected": _I915_ENTRIES_EXPECTED,
    }
    return True, "\n".join(log_lines), drivers_loaded, counts
def restart_platform_services(unit):
    """Web-safe wrapper: restart all Scrypted platform services for unit, return (ok, message)."""
    unit = str(unit or "").strip()
    if not unit:
        return False, "Missing unit"
    ok = refresh_platform_services(unit)
    if ok:
        return True, f"Restarted all platform services on {unit}"
    return False, f"Failed to restart services on {unit}"
