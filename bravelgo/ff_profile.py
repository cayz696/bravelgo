"""Firefox profile management — prefs only on BravelGo profile."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

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
        'user_pref("dom.webdriver.enabled", false);',
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


def resolve_firefox_binary(log=None, install_if_missing: bool = False) -> str | None:
    """Real Firefox binary for Selenium (not /usr/bin/firefox shell wrapper)."""
    import glob
    import os
    import shutil
    import subprocess

    for path in _firefox_candidates():
        resolved = _resolve_firefox_path(path)
        if resolved and _verify_firefox_binary(resolved, log):
            if log:
                if os.path.realpath(path) != os.path.realpath(resolved):
                    log(f"Firefox: {path} → {resolved}")
                else:
                    log(f"System Firefox: {resolved}")
            return resolved

    if install_if_missing and hasattr(os, "geteuid") and os.geteuid() == 0:
        if log:
            log("Firefox not found — installing via apt…")
        subprocess.run(["apt-get", "update", "-qq"], check=False)
        subprocess.run(
            ["apt-get", "install", "-y", "firefox", "firefox-geckodriver"],
            check=False,
        )
        for path in _firefox_candidates():
            resolved = _resolve_firefox_path(path)
            if resolved and _verify_firefox_binary(resolved, log):
                if log:
                    log(f"Firefox installed: {resolved}")
                return resolved

    if log:
        if shutil.which("firefox") and "/snap/" in (shutil.which("firefox") or ""):
            log("ERROR: snap Firefox — run: sudo snap remove firefox && sudo apt install firefox")
        else:
            log("ERROR: sudo apt install firefox firefox-geckodriver")
    return None


def _firefox_candidates() -> list[str]:
    import glob
    import shutil

    out: list[str] = []
    for pattern in (
        "/usr/lib/firefox/firefox",
        "/usr/lib/firefox-esr/firefox",
        "/usr/lib/firefox/firefox-bin",
        "/usr/lib64/firefox/firefox",
        "/opt/firefox/firefox",
        "/opt/firefox-esr/firefox",
        "/snap/firefox/current/usr/lib/firefox/firefox",
    ):
        out.append(pattern)
    for match in sorted(glob.glob("/usr/lib/firefox*/firefox")):
        out.append(match)
    which = shutil.which("firefox")
    if which:
        out.append(which)
    out.extend(("/usr/bin/firefox", "/usr/bin/firefox-esr"))
    seen: set[str] = set()
    ordered: list[str] = []
    for item in out:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _verify_firefox_binary(path: str, log=None) -> bool:
    import subprocess

    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        text = f"{proc.stdout} {proc.stderr}".lower()
        ok = proc.returncode == 0 and "mozilla firefox" in text
        if not ok and log:
            log(f"Skip invalid binary {path}: {(proc.stdout or proc.stderr).strip()[:80]}")
        return ok
    except Exception as exc:
        if log:
            log(f"Skip {path}: {exc}")
        return False


def _is_elf_executable(path: Path) -> bool:
    try:
        if not path.is_file() or not os.access(path, os.X_OK):
            return False
        with path.open("rb") as fh:
            return fh.read(4) == b"\x7fELF"
    except OSError:
        return False


def _resolve_firefox_path(raw: str) -> str | None:
    import os
    import re

    p = Path(raw)
    if not p.exists():
        return None

    if _is_elf_executable(p):
        return str(p.resolve())

    real = Path(os.path.realpath(raw))
    if real != p and _is_elf_executable(real):
        return str(real)

    if not p.is_file():
        return None

    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    moz_dist = ""
    moz_app = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("MOZ_DIST="):
            moz_dist = line.split("=", 1)[1].strip().strip("'\"")
        elif line.startswith("MOZ_APP="):
            moz_app = line.split("=", 1)[1].strip().strip("'\"")

    for candidate in (moz_app, f"{moz_dist}/firefox" if moz_dist else ""):
        if not candidate:
            continue
        expanded = candidate.replace("$MOZ_DIST", moz_dist).replace('"', "").replace("'", "")
        cp = Path(expanded)
        if _is_elf_executable(cp):
            return str(cp.resolve())

    for match in re.finditer(r"([/\w.-]+/firefox(?:-bin)?)", text):
        cp = Path(match.group(1))
        if cp.is_file() and (_is_elf_executable(cp) or _verify_firefox_binary(str(cp))):
            return str(cp.resolve())

    return None


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
