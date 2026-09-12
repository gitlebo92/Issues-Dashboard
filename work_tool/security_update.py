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
        pveSshClient.connect(hostname=ip, username=pveSshUsername, password=pveSshPass)
        stdin, stdout, stderr = pveSshClient.exec_command(f"bash << 'EOF'\n{pvescript}\nEOF")
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
    ip = None
    errors = ""
    unattended_fix_cmd = f"""
    if ! grep -q '"linux-image";' /etc/apt/apt.conf.d/50unattended-upgrades; then
        echo '{scryptSshPass}' | sudo -S sed -i 's|^Unattended-Upgrade::Package-Blacklist {{|Unattended-Upgrade::Package-Blacklist {{\\n\\t"linux-image";\\n\\t"linux-headers";\\n\\t"linux-generic";\\n\\t"linux-modules";\\n\\t"linux-tools";|' /etc/apt/apt.conf.d/50unattended-upgrades
    fi
    """
    commands = [
            "set -e",
            f"echo '{scryptSshPass}' | sudo -S apt purge -y linux-image-6.8.0-139-generic linux-headers-6.8.0-139-generic",
            f"echo '{scryptSshPass}' | sudo -S apt install -f -y",
            f"echo '{scryptSshPass}' | sudo -S apt-mark hold linux-image-6.8.0-138-generic linux-headers-6.8.0-138-generic",
            f"echo '{scryptSshPass}' | sudo -S sed -i 's|^GRUB_DEFAULT=.*|GRUB_DEFAULT=0|' /etc/default/grub",
            f"echo '{scryptSshPass}' | sudo -S update-grub",
            "ls /boot/vmlinuz-* /boot/initrd.img-*",
            f"echo '{scryptSshPass}' | sudo -S dpkg -l | grep -E '^i[^i]' || true",
            f"echo '{scryptSshPass}' | sudo -S apt-mark showhold",
            unattended_fix_cmd,
            f"echo '{scryptSshPass}' | sudo -S grep -A8 'Package-Blacklist' /etc/apt/apt.conf.d/50unattended-upgrades || true",
            f"echo '{scryptSshPass}' | sudo -S unattended-upgrade --dry-run --debug 2>&1 | grep -i 'blacklist\\|linux-' || true"
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
        scryptedSshClient.connect(hostname=ip, username=scryptSshUsername, password=scryptSshPass)
        stdin, stdout, stderr = scryptedSshClient.exec_command(f"bash << 'EOF'\n{scryptedscript}\nEOF")
        output = stdout.read().decode("utf-8")
        errors = stderr.read().decode("utf-8")

        if errors:
            print(f"errors: {errors}")
            

        output = output.splitlines()
        for line in output:
            print(line)

        print(f"Rebooting {unit}...")

        scryptedSshClient.exec_command(
            f"echo '{scryptSshPass}' | sudo -S reboot")
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
    pveSshUsername = os.getenv("pvesshuser")
    pveSshPass = os.getenv("pvepass")
    scrypt_ip = None
    pve_ip = None
    errors = ""
    errors2 = ""
    commands = [
        "set -e",
        f"echo '{scryptSshPass}' | sudo -S uname -r "
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

        scryptSshClient.connect(hostname=scrypt_ip, username=scryptSshUsername, password=scryptSshPass)
        stdin, stdout, stderr = scryptSshClient.exec_command(f"bash << 'EOF'\n{cmdscript}\nEOF")
        output = stdout.read().decode("utf-8")
        errors = stderr.read().decode("utf-8")

        output = output.splitlines()
        if errors:
            print(f"errors: {errors}")
            

        for line in output:
            print(line)
        print("Shutting down...")
        
        scryptSshClient.exec_command(f"echo '{scryptSshPass}' | sudo -S shutdown -h now")
        scryptSshClient.close()

        input("Once unit has fully shut down press enter to continue: ")
        try:
            print(f"Set hostpci version to: {version}")
            pveSshClient.connect(hostname=pve_ip, username=pveSshUsername, password=pveSshPass)
            stdin2, stdout2, stderr2 = pveSshClient.exec_command(f"bash << 'EOF'\n{cmdscript2}\nEOF")
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
    company = os.getenv("company")
    ip = None
    errors = ""
    errors2 = ""
    drivers_loaded = True

    commands = [
        f"echo {scryptSshPass} | sudo -S lspci -nn | grep -i VGA",
        f"echo {scryptSshPass} | sudo -S lsmod | grep i915",
    ]
    cmd2 = f"echo {scryptSshPass} | sudo -S dmesg | grep -i i915 | tail -20"
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
        scryptSshClient.connect(hostname=ip, username=scryptSshUsername, password=scryptSshPass)
        stdin, stdout, stderr = scryptSshClient.exec_command(f"bash << 'EOF'\n{cmdscript}\nEOF")
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
        stdin2, stdout2, stderr2 = scryptSshClient.exec_command(f"{cmd2}")
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
    company = os.getenv("company")
    ip = None
    errors = ""

    commands = [
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-database.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-watchdog.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-web.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-metadata.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-images.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-capture.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-smtp.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-alarms.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-events.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-onvif.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-monitor.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-snmp.service",
        f"echo {scryptSshPass} | sudo -S systemctl restart {company}-cache.service"
    ]

    cmdscript = "\n".join(commands)
    row = _net_row_for_unit(unit)
    if row is None or len(row) <= 12 or not str(row[12]).strip():
        print(f"No Scrypted IP for {unit} in net sheet")
        return False
    ip = row[12]
    scryptSshClient = paramiko.SSHClient()
    scryptSshClient.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        scryptSshClient.connect(hostname=ip, username=scryptSshUsername, password=scryptSshPass)
        stdin, stdout, stderr = scryptSshClient.exec_command(f"bash << 'EOF'\n{cmdscript}\nEOF")
        errors = stderr.read().decode("utf-8")
        output = stdout.read().decode("utf-8")
        output = output.splitlines()

        if errors:
            print(f"errors: {errors}")
        for line in output:
            print(line)
        return True
    except Exception as e:
        print(f"exception: {e}")
        return False

    finally:
        scryptSshClient.close()
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
    script = "\n".join(commands)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log_lines = []
    version = None
    try:
        client.connect(
            hostname=pve_ip, username=username, password=password,
            timeout=30, allow_agent=False, look_for_keys=False,
        )
        stdin, stdout, stderr = client.exec_command(f"bash << 'EOF'\n{script}\nEOF")
        output = stdout.read().decode("utf-8").strip().splitlines()
        errors = stderr.read().decode("utf-8").strip()
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
    except Exception as exc:
        return False, f"Step 1 failed: {exc}", None
    finally:
        client.close()
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

    unattended_fix_cmd = f"""
    if ! grep -q '"linux-image";' /etc/apt/apt.conf.d/50unattended-upgrades; then
        echo '{password}' | sudo -S sed -i 's|^Unattended-Upgrade::Package-Blacklist {{|Unattended-Upgrade::Package-Blacklist {{\\n\\t"linux-image";\\n\\t"linux-headers";\\n\\t"linux-generic";\\n\\t"linux-modules";\\n\\t"linux-tools";|' /etc/apt/apt.conf.d/50unattended-upgrades
    fi
    """
    commands = [
        "set -e",
        f"echo '{password}' | sudo -S apt purge -y linux-image-6.8.0-139-generic linux-headers-6.8.0-139-generic",
        f"echo '{password}' | sudo -S apt install -f -y",
        f"echo '{password}' | sudo -S apt-mark hold linux-image-6.8.0-138-generic linux-headers-6.8.0-138-generic",
        f"echo '{password}' | sudo -S sed -i 's|^GRUB_DEFAULT=.*|GRUB_DEFAULT=0|' /etc/default/grub",
        f"echo '{password}' | sudo -S update-grub",
        "ls /boot/vmlinuz-* /boot/initrd.img-*",
        f"echo '{password}' | sudo -S dpkg -l | grep -E '^i[^i]' || true",
        f"echo '{password}' | sudo -S apt-mark showhold",
        unattended_fix_cmd,
        f"echo '{password}' | sudo -S grep -A8 'Package-Blacklist' /etc/apt/apt.conf.d/50unattended-upgrades || true",
        f"echo '{password}' | sudo -S unattended-upgrade --dry-run --debug 2>&1 | grep -i 'blacklist\\|linux-' || true",
    ]
    script = "\n".join(commands)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=scrypted_ip, username=username, password=password,
            timeout=30, allow_agent=False, look_for_keys=False,
        )
        stdin, stdout, stderr = client.exec_command(f"bash << 'EOF'\n{script}\nEOF")
        output = stdout.read().decode("utf-8")
        errors = stderr.read().decode("utf-8")
        exit_status = stdout.channel.recv_exit_status()
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
        client.exec_command(f"echo '{password}' | sudo -S reboot")
        log_lines.append(f"Rebooting {unit}...")
        return True, "\n".join(log_lines)
    except Exception as exc:
        return False, f"Step 2 failed: {exc}"
    finally:
        client.close()
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

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=scrypted_ip, username=username, password=password,
            timeout=30, allow_agent=False, look_for_keys=False,
        )
        stdin, stdout, stderr = client.exec_command(f"echo '{password}' | sudo -S uname -r")
        output = stdout.read().decode("utf-8").strip()
        errors = stderr.read().decode("utf-8").strip()
        log_lines = []
        if errors:
            log_lines.append(f"stderr: {errors}")
        log_lines.append(f"Running kernel: {output}")
        log_lines.append("Shutting down...")
        client.exec_command(f"echo '{password}' | sudo -S shutdown -h now")
        return True, "\n".join(log_lines)
    except Exception as exc:
        return False, f"Shutdown step failed: {exc}"
    finally:
        client.close()
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
    script = "\n".join(commands)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=pve_ip, username=username, password=password,
            timeout=30, allow_agent=False, look_for_keys=False,
        )
        stdin, stdout, stderr = client.exec_command(f"bash << 'EOF'\n{script}\nEOF")
        output = stdout.read().decode("utf-8").splitlines()
        errors = stderr.read().decode("utf-8").strip()
        exit_status = stdout.channel.recv_exit_status()
        if errors:
            output.append(f"stderr (informational unless the script failed): {errors}")
        if exit_status != 0:
            return False, "Finish step error (command failed, exit status %d):\n%s" % (
                exit_status, "\n".join(output)
            )
        message = "\n".join(output) if output else f"Set hostpci0 to {version} and started VM 101"
        return True, message
    except Exception as exc:
        return False, f"Finish step failed: {exc}"
    finally:
        client.close()
def security_update_web_verify(unit):
    """
    Security update fix, verify: confirm the VGA/i915 passthrough drivers
    loaded after VM 101 is back up. Web-safe counterpart of
    security_update_step4 (returns a message instead of printing).
    """
    unit = str(unit or "").strip()
    if not unit:
        return False, "Missing unit", False
    _pve_ip, scrypted_ip, err = _security_fix_ip_pair(unit)
    if err:
        return False, err, False
    username, password = _scrypted_ssh_credentials()
    if not username or not password:
        return False, "Set scryptuserssh and scryptpass in .env", False

    commands = [
        f"echo '{password}' | sudo -S lspci -nn | grep -i VGA",
        f"echo '{password}' | sudo -S lsmod | grep i915",
    ]
    cmd2 = f"echo '{password}' | sudo -S dmesg | grep -i i915 | tail -20"
    script = "\n".join(commands)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    vga_counter = 0
    i915_counter = 0
    log_lines = []
    try:
        client.connect(
            hostname=scrypted_ip, username=username, password=password,
            timeout=30, allow_agent=False, look_for_keys=False,
        )
        stdin, stdout, stderr = client.exec_command(f"bash << 'EOF'\n{script}\nEOF")
        primary_output = stdout.read().decode("utf-8")
        primary_errors = stderr.read().decode("utf-8")
        if primary_errors:
            log_lines.append(f"stderr: {primary_errors}")
        for line in primary_output.splitlines():
            if "VGA compatible controller" in line:
                vga_counter += 1
            if "i915" in line:
                i915_counter += 1
        stdin2, stdout2, stderr2 = client.exec_command(cmd2)
        secondary_output = stdout2.read().decode("utf-8")
        secondary_errors = stderr2.read().decode("utf-8")
        if secondary_errors:
            log_lines.append(f"stderr: {secondary_errors}")
        log_lines.extend(secondary_output.splitlines())
        log_lines.append(f"VGA controllers: {vga_counter}")
        log_lines.append(f"i915 entries: {i915_counter}")
        drivers_loaded = vga_counter == 2 and i915_counter == 7
        if not drivers_loaded:
            log_lines.append("Some drivers did not load")
        return True, "\n".join(log_lines), drivers_loaded
    except Exception as exc:
        return False, f"Verify step failed: {exc}", False
    finally:
        client.close()
def restart_platform_services(unit):
    """Web-safe wrapper: restart all Scrypted platform services for unit, return (ok, message)."""
    unit = str(unit or "").strip()
    if not unit:
        return False, "Missing unit"
    ok = refresh_platform_services(unit)
    if ok:
        return True, f"Restarted all platform services on {unit}"
    return False, f"Failed to restart services on {unit}"
