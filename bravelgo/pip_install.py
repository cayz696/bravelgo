"""Install Python packages on bare Ubuntu (BravelGo runs as root via sudo)."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys


def _pip_available() -> bool:
    return subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True,
    ).returncode == 0


def _ensure_pip(log=None) -> bool:
    if _pip_available():
        return True
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        if log:
            log("Installing python3-pip (missing on fresh Ubuntu)…")
        subprocess.run(
            ["apt-get", "install", "-y", "python3-pip"],
            capture_output=True,
            check=False,
        )
        return _pip_available()
    if log:
        log("ERROR: sudo apt install python3-pip")
    return False


def ensure_import(module: str, pip_name: str | None = None, log=None) -> bool:
    """Import *module*; install *pip_name* (defaults to module) via pip if missing."""
    pkg = pip_name or module
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        pass

    if log:
        log(f"Installing {pkg}…")
    if not _ensure_pip(log):
        return False

    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg, "--break-system-packages", "-q"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        if log:
            hint = (r.stderr or r.stdout or "").strip().splitlines()
            log(f"ERROR: {sys.executable} -m pip install {pkg} --break-system-packages")
            if hint:
                log(hint[-1][:120])
        return False

    try:
        importlib.import_module(module)
        return True
    except ImportError:
        if log:
            log(f"ERROR: {pkg} install failed — restart BravelGo after: sudo apt install python3-pip")
        return False
