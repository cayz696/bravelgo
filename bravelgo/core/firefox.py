from __future__ import annotations

import configparser
import os
import secrets
import subprocess
from pathlib import Path

from bravelgo.core.gost import GOST_LOCAL_PORT


def create_profile(real_user: str, profile_name: str, accept_langs: str, log) -> Path:
    user_home = Path(f"/home/{real_user}")
    profiles_root = user_home / ".config" / "bravelgo" / "firefox-profiles"
    profiles_root.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in profile_name)
    profile_dir = profiles_root / f"{safe_name}-{secrets.token_hex(2)}"
    profile_dir.mkdir(parents=True, exist_ok=True)

    ini_path = user_home / ".mozilla" / "firefox" / "profiles.ini"
    ini_path.parent.mkdir(parents=True, exist_ok=True)

    profile_id = secrets.token_hex(4)
    config = configparser.RawConfigParser()
    if ini_path.exists():
        config.read(ini_path, encoding="utf-8")

    if not config.has_section("General"):
        config.add_section("General")
    config.set("General", "StartWithLastProfile", "1")

    section = f"Profile{profile_id}"
    config.add_section(section)
    config.set(section, "Name", profile_name)
    config.set(section, "IsRelative", "0")
    config.set(section, "Path", str(profile_dir))
    config.set(section, "Default", "1")

    with ini_path.open("w", encoding="utf-8") as fh:
        config.write(fh)

    user_js = profile_dir / "user.js"
    user_js.write_text(_firefox_prefs(accept_langs), encoding="utf-8")

    uid = _uid(real_user)
    gid = _gid(real_user)
    for path in (profiles_root, profile_dir, ini_path.parent, ini_path, user_js):
        os.chown(path, uid, gid)
        if path.is_dir():
            for root, dirs, files in os.walk(path):
                for name in dirs + files:
                    os.chown(os.path.join(root, name), uid, gid)

    log(f"Firefox профіль: {profile_dir}")
    return profile_dir


def _firefox_prefs(accept_langs: str) -> str:
    lines = [
        'user_pref("network.proxy.type", 1);',
        f'user_pref("network.proxy.socks", "127.0.0.1");',
        f'user_pref("network.proxy.socks_port", {GOST_LOCAL_PORT});',
        'user_pref("network.proxy.socks_version", 5);',
        'user_pref("network.proxy.socks_remote_dns", true);',
        'user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1");',
        'user_pref("media.peerconnection.enabled", false);',
        'user_pref("media.peerconnection.ice.no_host", true);',
        'user_pref("media.peerconnection.ice.default_address_only", true);',
        'user_pref("privacy.resistFingerprinting", true);',
        'user_pref("privacy.trackingprotection.enabled", true);',
        f'user_pref("intl.accept_languages", "{accept_langs}");',
        'user_pref("dom.webdriver.enabled", false);',
        'user_pref("useAutomationExtension", false);',
        'user_pref("browser.shell.checkDefaultBrowser", false);',
        'user_pref("datareporting.healthreport.uploadEnabled", false);',
        'user_pref("toolkit.telemetry.enabled", false);',
    ]
    return "\n".join(lines) + "\n"


def launch_firefox(real_user: str, url: str, profile_dir: Path) -> None:
    env = os.environ.copy()
    env["DISPLAY"] = env.get("DISPLAY", ":0")
    subprocess.Popen(
        ["sudo", "-u", real_user, "firefox", "-no-remote", "-profile", str(profile_dir), url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def _uid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_uid


def _gid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_gid
