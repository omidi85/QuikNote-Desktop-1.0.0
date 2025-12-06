# -*- coding: utf-8 -*-
from __future__ import annotations
import hashlib
import os
import platform
import subprocess
import sys
import uuid

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# ---------- Windows helpers ----------
def _read_machine_guid_windows() -> str | None:
    """Read HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid"""
    try:
        out = subprocess.check_output(
            ["reg", "query", r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
            stderr=subprocess.STDOUT, text=True, shell=False
        )
        for line in out.splitlines():
            if "MachineGuid" in line:
                parts = [p for p in line.split("    ") if p.strip()]
                if parts:
                    return parts[-1].strip()
    except Exception:
        return None
    return None

def _get_cpu_id_windows() -> str | None:
    try:
        out = subprocess.check_output(
            ["wmic", "cpu", "get", "ProcessorId"],
            stderr=subprocess.STDOUT, text=True, shell=False
        )
        vals = [v.strip() for v in out.splitlines() if v.strip() and v.strip().lower() != "processorid"]
        return vals[0] if vals else None
    except Exception:
        return None

def _get_disk_serial_windows() -> str | None:
    try:
        out = subprocess.check_output(
            ["wmic", "diskdrive", "get", "SerialNumber"],
            stderr=subprocess.STDOUT, text=True, shell=False
        )
        vals = [v.strip() for v in out.splitlines() if v.strip() and v.strip().lower() != "serialnumber"]
        return vals[0] if vals else None
    except Exception:
        return None

# ---------- Public API ----------
def get_hwid() -> str:
    """
    Returns a stable, anonymized HWID hash for this machine.
    Priority (Windows): MachineGuid → CPU ProcessorId → Disk Serial → MAC
    Cross‑platform fallback: MAC.
    """
    pieces = []
    if platform.system().lower() == "windows":
        mg = _read_machine_guid_windows()
        if mg:
            pieces.append(("machine_guid", mg))
        cpu = _get_cpu_id_windows()
        if cpu:
            pieces.append(("cpu_id", cpu))
        dsn = _get_disk_serial_windows()
        if dsn:
            pieces.append(("disk_sn", dsn))

    # Fallback (any OS): MAC address (uuid.getnode may return a random MAC in VMs)
    mac = f"{uuid.getnode():012x}"
    pieces.append(("mac", mac))

    base = "|".join(f"{k}:{v}" for k, v in pieces)
    salt = f"py{sys.version_info.major}.{sys.version_info.minor}-{platform.platform()}-{os.name}"
    return _sha256(base + "|" + salt)

def get_hwid_legacy() -> str:
    """
    Legacy variant used by older builds: hash of MAC only (for backward compatibility).
    """
    mac = f"{uuid.getnode():012x}"
    return _sha256("legacy|" + mac)
