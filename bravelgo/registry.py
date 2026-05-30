"""Cross-VM identity registry — avoids reusing hostname/MAC/machine-id."""
from __future__ import annotations

import json
import os
import random
import time

from bravelgo.countries import generate_fingerprint

REGISTRY_NAME = ".bravelgo-registry.json"


def registry_path(user_home: str, mount_pt: str) -> str:
    """Prefer MacFolder (shared on Mac) so all VM clones share one ledger."""
    if os.path.isdir(mount_pt) and os.access(mount_pt, os.W_OK):
        return os.path.join(mount_pt, REGISTRY_NAME)
    return os.path.join(user_home, REGISTRY_NAME)


def load_registry(path: str) -> dict:
    try:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("vms"), list):
                return data
    except Exception:
        pass
    return {"vms": []}


def save_registry(path: str, data: dict, real_user: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if real_user and os.geteuid() == 0:
        import subprocess
        subprocess.run(
            ["chown", f"{real_user}:{real_user}", path],
            check=False,
            capture_output=True,
        )


def used_sets(path: str) -> tuple[set[str], set[str], set[str], set[str]]:
    data = load_registry(path)
    hosts, mids, macs, profiles = set(), set(), set(), set()
    for row in data.get("vms", []):
        if h := row.get("hostname"):
            hosts.add(h.upper())
        if m := row.get("machine_id"):
            mids.add(m.lower())
        if m := row.get("mac"):
            macs.add(m.lower())
        if p := row.get("ff_profile"):
            profiles.add(p.lower())
    return hosts, mids, macs, profiles


def unique_fingerprint(
    country_code: str,
    timezone_override: str | None,
    path: str,
    log=None,
) -> dict:
    used_hosts, _, _, _ = used_sets(path)
    for attempt in range(64):
        fp = generate_fingerprint(country_code, timezone_override)
        if fp["hostname"].upper() not in used_hosts:
            return fp
    if log:
        log("⚠ Could not find unused hostname in registry — using last generated")
    return fp


def unique_mac(path: str) -> str:
    _, _, used_macs, _ = used_sets(path)
    for _ in range(64):
        b = [random.randint(0, 255) for _ in range(6)]
        b[0] = (b[0] & 0xFC) | 0x02
        mac = ":".join(f"{x:02x}" for x in b)
        if mac.lower() not in used_macs:
            return mac
    b = [random.randint(0, 255) for _ in range(6)]
    b[0] = (b[0] & 0xFC) | 0x02
    return ":".join(f"{x:02x}" for x in b)


def ff_profile_name(fp: dict) -> str:
    """Firefox profile label — looks like a normal Ubuntu install."""
    tag = fp["hostname"].split("-", 1)[-1].lower()
    return f"ubuntu-{tag}"


def register_vm(
    path: str,
    *,
    hostname: str,
    machine_id: str,
    mac: str,
    ff_profile: str,
    country: str,
    timezone: str,
    real_user: str,
    log=None,
) -> None:
    data = load_registry(path)
    record = {
        "hostname": hostname,
        "machine_id": machine_id,
        "mac": mac,
        "ff_profile": ff_profile,
        "country": country,
        "timezone": timezone,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    data["vms"].append(record)
    save_registry(path, data, real_user)
    if log:
        where = "MacFolder" if "MacFolder" in path else "local"
        log(f"Registry ({where}): {len(data['vms'])} VM(s) — saved {hostname}")


def registry_summary(path: str) -> str:
    if not os.path.isfile(path):
        return "Registry: empty (no file yet)"
    n = len(load_registry(path).get("vms", []))
    where = "MacFolder" if "MacFolder" in path else os.path.basename(path)
    return f"Registry: {n} VM(s) @ {where}"
