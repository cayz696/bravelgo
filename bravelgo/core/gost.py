from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

GOST_LOCAL_PORT = 1080
GOST_BIN = "/usr/local/bin/gost"


def ensure_gost(log) -> bool:
    if shutil.which(GOST_BIN) or shutil.which("gost"):
        return True
    log("gost не знайдено — встановлюю...")
    try:
        proc = subprocess.run(
            ["bash", "-c", "curl -fsSL https://github.com/go-gost/gost/raw/master/install.sh | bash -s -- --install"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0 and (shutil.which(GOST_BIN) or shutil.which("gost")):
            log("gost встановлено.")
            return True
    except Exception as exc:
        log(f"install.sh не вдався: {exc}")

    arch = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()
    gost_arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(arch)
    if not gost_arch:
        log(f"Невідома архітектура: {arch}")
        return False

    version = "3.2.6"
    url = f"https://github.com/go-gost/gost/releases/download/v{version}/gost_{version}_linux_{gost_arch}.tar.gz"
    tmp = Path("/tmp/bravelgo_gost")
    tmp.mkdir(exist_ok=True)
    subprocess.run(["curl", "-fsSL", url, "-o", str(tmp / "gost.tar.gz")], check=True)
    subprocess.run(["tar", "-xzf", str(tmp / "gost.tar.gz"), "-C", str(tmp)], check=True)
    subprocess.run(["install", "-m", "755", str(tmp / "gost"), GOST_BIN], check=True)
    log("gost встановлено вручну.")
    return True


def gost_binary() -> str:
    if shutil.which(GOST_BIN):
        return GOST_BIN
    return shutil.which("gost") or GOST_BIN


def stop_gost(log) -> None:
    subprocess.run(["pkill", "-f", f"gost.*127.0.0.1:{GOST_LOCAL_PORT}"], check=False)
    subprocess.run(["pkill", "-f", "bravelgo_bridge.py"], check=False)
    subprocess.run(["systemctl", "stop", "privoxy"], check=False)
    log("Проксі-сервіси зупинено.")


def start_gost(real_user: str, upstream_url: str, log) -> bool:
    if not ensure_gost(log):
        return False

    stop_gost(log)
    time.sleep(0.5)

    gost = gost_binary()
    log_file = Path(f"/home/{real_user}/.config/bravelgo/gost.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [gost, f"-L=socks5://127.0.0.1:{GOST_LOCAL_PORT}", f"-F={upstream_url}"],
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    for i in range(20):
        if _port_open(GOST_LOCAL_PORT):
            log(f"gost слухає 127.0.0.1:{GOST_LOCAL_PORT} (pid {proc.pid})")
            return True
        if proc.poll() is not None:
            tail = log_file.read_text(encoding="utf-8")[-500:] if log_file.exists() else ""
            log(f"gost впав одразу. Лог: {tail}")
            return False
        time.sleep(0.5)

    log("gost не відповідає на порту 1080 за 10 сек.")
    return False


def _port_open(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def verify_proxy(log) -> tuple[bool, str]:
    """Перевірка через curl — працює без додаткових Python-пакетів."""
    if not _port_open(GOST_LOCAL_PORT):
        log(f"Порт {GOST_LOCAL_PORT} закритий — gost не запущений.")
        return False, ""

    result = subprocess.run(
        [
            "curl",
            "-sS",
            "--max-time",
            "25",
            "--socks5-hostname",
            f"127.0.0.1:{GOST_LOCAL_PORT}",
            "https://api.ipify.org?format=json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"curl через проксі не вдався: {result.stderr.strip()}")
        return False, ""

    try:
        data = json.loads(result.stdout)
        ip = data.get("ip", "?")
        log(f"Проксі OK → зовнішній IP: {ip}")
        return True, ip
    except json.JSONDecodeError:
        log(f"Невідповідь проксі: {result.stdout[:120]}")
        return False, ""
