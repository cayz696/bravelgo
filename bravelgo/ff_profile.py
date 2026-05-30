"""Firefox profile management — prefs only on BravelGo profile."""
from __future__ import annotations

import os
import re
import subprocess

BRIDGE_PORT = 8118


def run(cmd: str) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def create_profile(user_home: str, real_user: str, fp: dict, log, profile_name: str | None = None) -> str:
    if not profile_name:
        from bravelgo.registry import ff_profile_name
        profile_name = ff_profile_name(fp)
    ff_dir = f"{user_home}/.mozilla/firefox"
    profile_dir = f"{ff_dir}/{profile_name}"
    ini_path = f"{ff_dir}/profiles.ini"

    os.makedirs(profile_dir, exist_ok=True)
    run(f"chown -R {real_user}:{real_user} '{ff_dir}'")

    if not os.path.exists(ini_path):
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(
                "[General]\nStartWithLastProfile=1\nVersion=2\n\n"
                "[Profile0]\nName=default\nIsRelative=1\nPath=default-release\nDefault=0\n"
            )

    with open(ini_path, encoding="utf-8") as f:
        ini_content = f.read()

    if f"Name={profile_name}" not in ini_content:
        ini_content = re.sub(r"^Default=1\s*$", "Default=0", ini_content, flags=re.MULTILINE)
        idx = len(re.findall(r"^\[Profile\d+\]", ini_content, re.MULTILINE))
        ini_content += (
            f"\n[Profile{idx}]\n"
            f"Name={profile_name}\n"
            f"IsRelative=0\n"
            f"Path={profile_dir}\n"
            f"Default=1\n"
        )
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(ini_content)
    else:
        ini_content = re.sub(r"^Default=1\s*$", "Default=0", ini_content, flags=re.MULTILINE)
        block = re.search(
            rf"\[Profile\d+\]\nName={re.escape(profile_name)}\n.*?(?=\n\[|\Z)",
            ini_content,
            re.DOTALL,
        )
        if block:
            chunk = block.group(0)
            chunk = re.sub(r"^Default=.*$", "Default=1", chunk, flags=re.MULTILINE)
            ini_content = ini_content.replace(block.group(0), chunk)
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write(ini_content)

    run(f"chown {real_user}:{real_user} '{ini_path}'")
    log(f"Firefox profile: {profile_name}")
    return profile_dir


def write_user_js(profile_dir: str, fp: dict, real_user: str, proxy_enabled: bool, log) -> None:
    if not profile_dir or not os.path.isdir(profile_dir):
        log("No BravelGo profile — skip user.js")
        return

    lines = [
        "// BravelGo user.js",
        f'user_pref("intl.accept_languages", "{fp["lang_full"]}");',
        f'user_pref("intl.locale.requested", "{fp["ff_locale"]}");',
        'user_pref("media.peerconnection.enabled", false);',
        'user_pref("media.peerconnection.ice.default_address_only", true);',
        'user_pref("media.peerconnection.ice.no_host", true);',
        'user_pref("dom.battery.enabled", false);',
        'user_pref("toolkit.telemetry.enabled", false);',
        'user_pref("datareporting.healthreport.uploadEnabled", false);',
        'user_pref("privacy.timezone.js.enabled", true);',
    ]

    if proxy_enabled:
        lines.extend([
            'user_pref("network.proxy.type", 1);',
            f'user_pref("network.proxy.http", "127.0.0.1");',
            f'user_pref("network.proxy.http_port", {BRIDGE_PORT});',
            f'user_pref("network.proxy.ssl", "127.0.0.1");',
            f'user_pref("network.proxy.ssl_port", {BRIDGE_PORT});',
            'user_pref("network.proxy.share_proxy_settings", true);',
            'user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1");',
        ])
    else:
        lines.append('user_pref("network.proxy.type", 0);')

    path = os.path.join(profile_dir, "user.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    run(f"chown {real_user}:{real_user} '{path}'")
    log(f"user.js → {os.path.basename(profile_dir)}")


def launch_profile(real_user: str, profile_dir: str, log) -> None:
    if not profile_dir or not os.path.isdir(profile_dir):
        subprocess.Popen(
            ["sudo", "-u", real_user, "env", "DISPLAY=:0", "firefox"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log("Firefox (default profile)")
        return
    subprocess.Popen(
        [
            "sudo", "-u", real_user, "env", "DISPLAY=:0",
            "firefox", "--no-remote", "--profile", profile_dir,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log(f"Firefox → {os.path.basename(profile_dir)}")
