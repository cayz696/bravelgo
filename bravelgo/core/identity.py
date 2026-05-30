from __future__ import annotations

import os
import secrets
import subprocess
from pathlib import Path


LOCALE_MAP = {
    "UA": ("Europe/Kyiv", "uk_UA.UTF-8", "uk-UA,uk"),
    "FR": ("Europe/Paris", "fr_FR.UTF-8", "fr-FR,fr"),
    "USA": ("America/New_York", "en_US.UTF-8", "en-US,en"),
    "PL": ("Europe/Warsaw", "pl_PL.UTF-8", "pl-PL,pl"),
    "NO": ("Europe/Oslo", "nb_NO.UTF-8", "nb-NO,nb,no"),
    "BR": ("America/Sao_Paulo", "pt_BR.UTF-8", "pt-BR,pt"),
    "EST": ("Europe/Tallinn", "et_EE.UTF-8", "et-EE,et"),
    "NZL": ("Pacific/Auckland", "en_NZ.UTF-8", "en-NZ,en"),
}


def reset_identity(real_user: str, country: str, profile_name: str, log) -> dict:
    user_home = Path(f"/home/{real_user}")
    suffix = secrets.token_hex(3)
    new_host = f"{profile_name.lower().replace(' ', '-')}-{suffix}"

    log(f"Новий hostname: {new_host}")
    subprocess.run(["hostnamectl", "set-hostname", new_host], check=False)

    hosts = Path("/etc/hosts")
    lines = hosts.read_text(encoding="utf-8").splitlines()
    filtered = [ln for ln in lines if "127.0.1.1" not in ln]
    filtered.append(f"127.0.1.1\t{new_host}")
    hosts.write_text("\n".join(filtered) + "\n", encoding="utf-8")

    log("Регенерація machine-id...")
    for mid in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        if mid.exists():
            mid.unlink()
    subprocess.run(["systemd-machine-id-setup"], check=True)
    subprocess.run(["ln", "-sf", "/etc/machine-id", "/var/lib/dbus/machine-id"], check=False)

    tz, locale, accept_langs = LOCALE_MAP.get(country, ("UTC", "en_US.UTF-8", "en-US,en"))
    subprocess.run(["timedatectl", "set-timezone", tz], check=False)
    subprocess.run(["localectl", "set-locale", f"LANG={locale}"], check=False)
    log(f"Timezone: {tz}, locale: {locale}")

    log("Вимкнення IPv6 (запобігання leak)...")
    sysctl_cmds = [
        "net.ipv6.conf.all.disable_ipv6=1",
        "net.ipv6.conf.default.disable_ipv6=1",
    ]
    for key in sysctl_cmds:
        subprocess.run(["sysctl", "-w", key], check=False)

    log("Очищення браузерних слідів...")
    subprocess.run(["pkill", "-9", "firefox"], check=False)
    subprocess.run(["pkill", "-9", "firefox-esr"], check=False)
    for rel in (".mozilla/firefox", ".cache/mozilla", ".config/bravelgo/firefox-profiles"):
        target = user_home / rel
        if target.exists():
            subprocess.run(["rm", "-rf", str(target)], check=True)

    identity = {
        "hostname": new_host,
        "timezone": tz,
        "locale": locale,
        "accept_languages": accept_langs,
        "profile_name": profile_name,
    }
    state_dir = user_home / ".config" / "bravelgo"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "identity.json"
    import json

    state_file.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    uid = _uid(real_user)
    gid = _gid(real_user)
    os.chown(state_dir, uid, gid)
    os.chown(state_file, uid, gid)

    log("Identity reset завершено.")
    return identity


def _uid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_uid


def _gid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_gid
