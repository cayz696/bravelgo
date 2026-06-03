"""Install Playwright for publish automation."""
from __future__ import annotations

import subprocess


def ensure_publish_deps(real_user: str, log) -> bool:
    if not _user_import(real_user, "playwright"):
        log("Installing playwright (pip)…")
        proc = subprocess.run(
            ["sudo", "-u", real_user, "python3", "-m", "pip", "install", "--user", "playwright>=1.40.0"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            log(f"pip playwright failed: {proc.stderr[:200]}")
            return False
    log("Playwright: install firefox browser (first run may download)…")
    proc = subprocess.run(
        ["sudo", "-u", real_user, "python3", "-m", "playwright", "install", "firefox"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        log(f"playwright install firefox: {proc.stderr[:200]}")
        return False
    log("Publish deps OK")
    return True


def _user_import(real_user: str, module: str) -> bool:
    proc = subprocess.run(
        ["sudo", "-u", real_user, "python3", "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0
