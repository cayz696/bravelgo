"""Warmup dependencies — Firefox, geckodriver, selenium (fresh Ubuntu / ARM)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

GECKODRIVER_VERSION = "0.36.0"
GECKODRIVER_PATHS = ("/usr/local/bin/geckodriver", "/usr/bin/geckodriver")


def is_snap_path(path: str | None) -> bool:
    return bool(path and "/snap/" in path)


def _deb_firefox_ok() -> bool:
    return any(
        Path(p).is_file() for p in ("/usr/lib/firefox/firefox", "/usr/lib/firefox-esr/firefox")
    )


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _user_import_ok(real_user: str, module: str) -> bool:
    proc = _run(["sudo", "-u", real_user, "python3", "-c", f"import {module}"])
    return proc.returncode == 0


def _apt_install(packages: list[str], log) -> bool:
    if not packages:
        return True
    log(f"apt install {' '.join(packages)}…")
    _run(["apt-get", "update", "-qq"])
    proc = _run(["apt-get", "install", "-y", *packages])
    if proc.returncode != 0:
        for line in (proc.stderr or proc.stdout or "").splitlines():
            if line.strip():
                log(line.strip()[:140])
        return False
    return True


def reinstall_firefox(log) -> bool:
    """Deb Firefox — snap breaks Selenium; install Mozilla apt build if needed."""
    log("Firefox: removing snap (Selenium incompatible)…")
    _run(["snap", "remove", "firefox"], check=False)
    _run(["snap", "remove", "firefox", "--purge"], check=False)

    if not _deb_firefox_ok():
        if not _apt_install(["firefox"], log):
            log("apt firefox failed — trying Mozilla official repo…")
        if not _deb_firefox_ok():
            _install_firefox_mozilla_apt(log)

    _run(["apt-get", "install", "-y", "--reinstall", "firefox"], check=False)

    if _deb_firefox_ok():
        log(f"Firefox OK: /usr/lib/firefox/firefox")
        return True

    log("ERROR: deb Firefox missing — snap removed but install failed")
    log("Manual: sudo snap remove firefox && sudo apt install firefox")
    return False


def _install_firefox_mozilla_apt(log) -> None:
    """Official Mozilla APT repo (deb package, not snap)."""
    log("Adding packages.mozilla.org…")
    keyring = Path("/etc/apt/keyrings/packages.mozilla.org.asc")
    keyring.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(
            "https://packages.mozilla.org/apt/repo-signing-key.gpg",
            keyring,
        )
    except Exception as exc:
        log(f"Mozilla key download failed: {exc}")
        return

    src = Path("/etc/apt/sources.list.d/mozilla.list")
    src.write_text(
        "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] "
        "https://packages.mozilla.org/apt mozilla main\n",
        encoding="utf-8",
    )
    prefs = Path("/etc/apt/preferences.d/mozilla-firefox")
    if not prefs.exists():
        prefs.write_text(
            "Package: firefox*\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n",
            encoding="utf-8",
        )
    _apt_install(["firefox"], log)


def install_geckodriver(log) -> str | None:
    for path in GECKODRIVER_PATHS:
        if Path(path).is_file() and os.access(path, os.X_OK):
            log(f"Geckodriver: {path}")
            return path

    found = shutil.which("geckodriver")
    if found and not is_snap_path(found):
        log(f"Geckodriver: {found}")
        return found
    if is_snap_path(found):
        log("Skip snap geckodriver (use /usr/local/bin)…")

    for pkg in ("firefox-geckodriver", "geckodriver"):
        log(f"Trying apt package {pkg}…")
        proc = _run(["apt-get", "install", "-y", pkg])
        if proc.returncode == 0:
            for path in GECKODRIVER_PATHS:
                if Path(path).is_file():
                    log(f"Geckodriver: {path}")
                    return path
            found = shutil.which("geckodriver")
            if found and not is_snap_path(found):
                log(f"Geckodriver: {found}")
                return found

    log("Geckodriver: downloading from GitHub…")
    return _download_geckodriver(log)


def _download_geckodriver(log) -> str | None:
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "linux64",
        "amd64": "linux64",
        "aarch64": "linux-aarch64",
        "arm64": "linux-aarch64",
    }
    arch = arch_map.get(machine)
    if not arch:
        log(f"ERROR: unsupported CPU for geckodriver: {machine}")
        return None

    url = (
        f"https://github.com/mozilla/geckodriver/releases/download/v{GECKODRIVER_VERSION}/"
        f"geckodriver-v{GECKODRIVER_VERSION}-{arch}.tar.gz"
    )
    dest = Path("/usr/local/bin/geckodriver")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "geckodriver.tar.gz"
            urllib.request.urlretrieve(url, archive)
            with tarfile.open(archive) as tar:
                tar.extractall(tmp)
            binary = Path(tmp) / "geckodriver"
            if not binary.is_file():
                log("ERROR: geckodriver archive invalid")
                return None
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary, dest)
            dest.chmod(0o755)
        log(f"Geckodriver installed: {dest}")
        return str(dest)
    except Exception as exc:
        log(f"ERROR: geckodriver download failed: {exc}")
        return None


def install_selenium(real_user: str, log) -> bool:
    if _user_import_ok(real_user, "selenium"):
        log("Selenium OK (user python)")
        return True

    log("Installing selenium for desktop user…")
    for pkg in ("python3-selenium",):
        if _run(["apt-cache", "show", pkg]).returncode == 0:
            if _apt_install([pkg], log) and _user_import_ok(real_user, "selenium"):
                log("Selenium OK (apt)")
                return True

    pip_cmds = [
        ["sudo", "-u", real_user, "python3", "-m", "pip", "install", "--user", "selenium", "-q"],
        ["sudo", "-u", real_user, "python3", "-m", "pip", "install", "selenium", "--break-system-packages", "-q"],
        ["/usr/bin/python3", "-m", "pip", "install", "selenium", "--break-system-packages", "-q"],
    ]
    for cmd in pip_cmds:
        if shutil.which(cmd[0]) or cmd[0].startswith("/"):
            proc = _run(cmd)
            if proc.returncode == 0 and _user_import_ok(real_user, "selenium"):
                log("Selenium OK (pip)")
                return True

    if os.geteuid() == 0 and not _run(["dpkg", "-l", "python3-pip"]).stdout.strip():
        _apt_install(["python3-pip"], log)

    proc = _run(["sudo", "-u", real_user, "python3", "-m", "pip", "install", "--user", "selenium"])
    if proc.returncode == 0 and _user_import_ok(real_user, "selenium"):
        log("Selenium OK")
        return True

    tail = (proc.stderr or proc.stdout or "").strip().splitlines()
    log("ERROR: selenium install failed")
    for line in tail[-3:]:
        log(line[:140])
    log(f"Manual: sudo -u {real_user} pip3 install --user selenium")
    return False


def install_pysocks(real_user: str, log) -> bool:
    if _user_import_ok(real_user, "socks"):
        return True
    _run(["sudo", "-u", real_user, "python3", "-m", "pip", "install", "--user", "PySocks", "-q"])
    if _user_import_ok(real_user, "socks"):
        return True
    _apt_install(["python3-pysocks"], log)
    return _user_import_ok(real_user, "socks")


def ensure_warmup_deps(log, real_user: str) -> bool:
    """Full stack for Selenium warmup — run from sudo bravelgo.py."""
    if os.geteuid() != 0:
        return True

    from bravelgo.ff_profile import resolve_firefox_binary

    ff = resolve_firefox_binary(log)
    if is_snap_path(ff) or not _deb_firefox_ok():
        log("Snap Firefox detected — installing deb package…")
        if not reinstall_firefox(log):
            return False
    elif ff:
        log(f"Firefox present: {ff}")

    gecko = install_geckodriver(log)
    if is_snap_path(gecko):
        log("Replacing snap geckodriver…")
        gecko = _download_geckodriver(log)
    if not gecko:
        return False
    if not install_selenium(real_user, log):
        return False
    install_pysocks(real_user, log)

    ff = resolve_firefox_binary(log)
    if is_snap_path(ff) or not _deb_firefox_ok():
        log("ERROR: still on snap Firefox — click Reinstall Firefox")
        return False
    gecko = gecko or shutil.which("geckodriver") or ""
    if is_snap_path(gecko):
        gecko = "/usr/local/bin/geckodriver"
    if not ff:
        log("ERROR: Firefox missing after install")
        return False
    if not gecko or not Path(gecko).is_file():
        log("ERROR: geckodriver missing after install")
        return False
    log(f"Warmup ready · Firefox={ff} · geckodriver={gecko}")
    return True
