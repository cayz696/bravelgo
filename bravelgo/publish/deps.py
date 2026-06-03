"""Publish browser deps — Selenium + geckodriver (same as Warmup)."""
from __future__ import annotations

import os
import subprocess
from typing import Callable


def ensure_publish_deps(*, log: Callable[[str], None], real_user: str) -> bool:
    user = _validate_user(real_user)
    if not user:
        log("ERROR: invalid desktop user for publish deps")
        return False

    if not _user_import(user, "selenium"):
        log("Installing selenium (pip)…")
        proc = _run_as_user(
            user,
            ["python3", "-m", "pip", "install", "--user", "selenium>=4.15.0"],
        )
        if proc.returncode != 0:
            log(f"pip selenium failed: {(proc.stderr or '')[:200]}")
            return False

    if os.geteuid() == 0:
        from bravelgo.deps import ensure_warmup_deps

        if not ensure_warmup_deps(log, user):
            return False
    elif not _geckodriver_present():
        log("geckodriver missing — run BravelGo as sudo and Reinstall Firefox (Warmup)")
        return False

    log("Publish deps OK (Selenium + Firefox)")
    return True


def _validate_user(real_user: str) -> str | None:
    if not isinstance(real_user, str):
        return None
    user = real_user.strip()
    return user if user else None


def _run_as_user(real_user: str, argv: list[str]) -> subprocess.CompletedProcess:
    """Run command as desktop user without nested sudo password prompt."""
    if os.geteuid() == 0:
        for runner in (
            ["runuser", "-u", real_user, "--"] + argv,
            ["sudo", "-n", "-u", real_user] + argv,
        ):
            try:
                proc = subprocess.run(runner, capture_output=True, text=True)
                if proc.returncode == 0 or runner[0] == "sudo":
                    return proc
            except FileNotFoundError:
                continue
        return subprocess.run(["sudo", "-n", "-u", real_user] + argv, capture_output=True, text=True)
    return subprocess.run(argv, capture_output=True, text=True)


def _geckodriver_present() -> bool:
    for candidate in ("/usr/local/bin/geckodriver", "/usr/bin/geckodriver"):
        if os.path.isfile(candidate):
            return True
    proc = subprocess.run(["which", "geckodriver"], capture_output=True, text=True)
    return proc.returncode == 0 and "/snap/" not in (proc.stdout or "")


def _user_import(real_user: str, module: str) -> bool:
    user = _validate_user(real_user)
    if not user:
        return False
    proc = _run_as_user(user, ["python3", "-c", f"import {module}"])
    return proc.returncode == 0
