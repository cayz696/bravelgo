"""Resolve Firefox profile directory on the VM (BravelGo / Mozilla)."""
from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Callable


def resolve_profile_dir(
    user_home: str,
    cfg: dict,
    log: Callable[[str], None] | None = None,
) -> str | None:
    """
    Priority:
    1. cfg['ff_profile'] if directory exists
    2. profiles.ini entry with Default=1
    3. Newest bravelgo-* profile with user.js
    4. Any profile with BravelGo user.js marker
    """
    saved = (cfg.get("ff_profile") or "").strip()
    if saved and os.path.isdir(saved):
        if log:
            log(f"Firefox profile (config): {saved}")
        return saved

    ff_root = Path(user_home) / ".mozilla" / "firefox"
    ini_path = ff_root / "profiles.ini"
    if ini_path.is_file():
        found = _from_profiles_ini(ini_path, ff_root, log)
        if found:
            return found

    bravel = _newest_bravelgo_profile(ff_root)
    if bravel:
        if log:
            log(f"Firefox profile (BravelGo): {bravel}")
        return bravel

    if log:
        log("ERROR: no Firefox profile — run Full uniquify or log in via Launch Firefox")
    return None


def _from_profiles_ini(ini_path: Path, ff_root: Path, log) -> str | None:
    cp = configparser.RawConfigParser()
    try:
        cp.read(ini_path, encoding="utf-8")
    except Exception:
        return None

    default_name: str | None = None
    profiles: list[tuple[str, str, int]] = []

    for section in cp.sections():
        if not section.startswith("Profile"):
            continue
        name = cp.get(section, "Name", fallback="")
        path = cp.get(section, "Path", fallback="")
        is_rel = cp.get(section, "IsRelative", fallback="1") == "1"
        is_def = cp.get(section, "Default", fallback="0") == "1"
        if not path:
            continue
        full = str(ff_root / path) if is_rel else path
        if not os.path.isdir(full):
            continue
        profiles.append((name, full, 1 if is_def else 0))
        if is_def:
            default_name = full

    if default_name:
        if log:
            log(f"Firefox profile (profiles.ini default): {default_name}")
        return default_name

    for name, full, _ in profiles:
        if (Path(full) / "user.js").is_file() and "bravelgo" in name.lower():
            if log:
                log(f"Firefox profile (named): {full}")
            return full

    if profiles:
        full = profiles[0][1]
        if log:
            log(f"Firefox profile (first in ini): {full}")
        return full
    return None


def _newest_bravelgo_profile(ff_root: Path) -> str | None:
    candidates: list[Path] = []
    if not ff_root.is_dir():
        return None
    for child in ff_root.iterdir():
        if not child.is_dir():
            continue
        if child.name in (".", "..", "Crash Reports", "Pending Pings"):
            continue
        uj = child / "user.js"
        if uj.is_file():
            try:
                head = uj.read_text(encoding="utf-8", errors="ignore")[:200]
                if "BravelGo" in head or child.name.startswith("bravelgo"):
                    candidates.append(child)
            except OSError:
                continue
    if not candidates:
        return None
    best = max(candidates, key=lambda p: p.stat().st_mtime)
    return str(best)
