from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path

from bravelgo.core.gost import GOST_LOCAL_PORT


def find_firefox_profiles(user_home: str) -> list[Path]:
    patterns = [
        f"{user_home}/.mozilla/firefox/*.default*",
        f"{user_home}/.mozilla/firefox/*.default-release*",
        f"{user_home}/snap/firefox/common/.mozilla/firefox/*.default*",
        f"{user_home}/snap/firefox/common/.mozilla/firefox/*.default-release*",
    ]
    dirs: list[Path] = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            p = Path(path)
            if p.is_dir():
                dirs.append(p)
    return dirs


def ensure_firefox_profile(real_user: str, user_home: str, log) -> list[Path]:
    profiles = find_firefox_profiles(user_home)
    if profiles:
        return profiles

    log("Firefox профіль не знайдено — ініціалізація...")
    subprocess.run(
        [
            "sudo",
            "-u",
            real_user,
            "env",
            "DISPLAY=:0",
            "firefox",
            "--headless",
            "--screenshot",
            "/tmp/ff_init.png",
            "https://example.com",
        ],
        capture_output=True,
        timeout=30,
    )
    subprocess.run(["killall", "-9", "firefox", "firefox-esr"], check=False)
    import time

    time.sleep(3)
    profiles = find_firefox_profiles(user_home)
    if not profiles:
        log("⚠️ Профіль Firefox досі не створено — запусти Firefox вручну один раз.")
    return profiles


def apply_socks_proxy(user_home: str, real_user: str, log, disable: bool = False) -> None:
    profiles = ensure_firefox_profile(real_user, user_home, log)
    if not profiles:
        return

    prefs_block = _proxy_user_js(disable)
    for profile_dir in profiles:
        user_js = profile_dir / "user.js"
        user_js.write_text(prefs_block, encoding="utf-8")
        os.chown(user_js, _uid(real_user), _gid(real_user))
        log(f"user.js → {profile_dir.name}")

        # Також чистимо старі HTTP-proxy prefs (8118 privoxy) з prefs.js
        prefs_js = profile_dir / "prefs.js"
        if prefs_js.exists():
            text = prefs_js.read_text(encoding="utf-8")
            lines = [
                ln
                for ln in text.splitlines()
                if "network.proxy" not in ln and "media.peerconnection" not in ln
            ]
            prefs_js.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.chown(prefs_js, _uid(real_user), _gid(real_user))


def _proxy_user_js(disable: bool) -> str:
    if disable:
        return 'user_pref("network.proxy.type", 0);\n'

    return f"""user_pref("network.proxy.type", 1);
user_pref("network.proxy.socks", "127.0.0.1");
user_pref("network.proxy.socks_port", {GOST_LOCAL_PORT});
user_pref("network.proxy.socks_version", 5);
user_pref("network.proxy.socks_remote_dns", true);
user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1");
user_pref("network.proxy.share_proxy_settings", true);
user_pref("media.peerconnection.enabled", false);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.default_address_only", true);
"""


def _uid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_uid


def _gid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_gid
