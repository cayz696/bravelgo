from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

LISTEN_PORT = 1080
GOST_PATHS = (
    "/usr/local/bin/gost",
    "/opt/bravelgo/gost",
)

# gost | python-http | python-socks
_proxy_mode = "none"
_upstream_scheme = ""


def proxy_mode() -> str:
    if _upstream_scheme and _proxy_mode == "gost":
        return f"gost/{_upstream_scheme}"
    return _proxy_mode


def upstream_scheme() -> str:
    return _upstream_scheme


def _log(log, msg: str) -> None:
    if log:
        log(msg)


def port_open(port: int = LISTEN_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def stop_all(log) -> None:
    global _proxy_mode, _upstream_scheme
    subprocess.run(["pkill", "-f", "gost.*127.0.0.1:1080"], check=False)
    subprocess.run(["pkill", "-f", "local_proxy.py"], check=False)
    subprocess.run(["pkill", "-f", "local_socks_chain.py"], check=False)
    subprocess.run(["systemctl", "stop", "privoxy"], check=False)
    _proxy_mode = "none"
    _upstream_scheme = ""
    _log(log, "Проксі-сервіси зупинено.")


def _kill_listener_only() -> None:
    subprocess.run(["pkill", "-f", "gost.*127.0.0.1:1080"], check=False)
    subprocess.run(["pkill", "-f", "local_proxy.py"], check=False)
    subprocess.run(["pkill", "-f", "local_socks_chain.py"], check=False)
    time.sleep(0.3)


def _find_gost() -> str | None:
    for path in GOST_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return shutil.which("gost")


def install_gost(log, user_home: str) -> str | None:
    existing = _find_gost()
    if existing:
        _log(log, f"gost: {existing}")
        return existing

    _log(log, "Завантажую gost (HTTP + SOCKS5 upstream)...")
    arch = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()
    gost_arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(arch)
    if not gost_arch:
        _log(log, f"Архітектура {arch} — без gost, лише Python fallback")
        return None

    version = "3.2.6"
    url = f"https://github.com/go-gost/gost/releases/download/v{version}/gost_{version}_linux_{gost_arch}.tar.gz"
    tmp = Path("/tmp/bravelgo_gost")
    tmp.mkdir(exist_ok=True)
    tar_path = tmp / "gost.tar.gz"

    downloaded = False
    for tool_cmd in (
        ["curl", "-fsSL", url, "-o", str(tar_path)],
        ["wget", "-q", url, "-O", str(tar_path)],
    ):
        if not shutil.which(tool_cmd[0]):
            continue
        result = subprocess.run(tool_cmd, capture_output=True, text=True)
        if result.returncode == 0 and tar_path.exists() and tar_path.stat().st_size > 1000:
            downloaded = True
            break
        _log(log, f"{tool_cmd[0]}: {result.stderr.strip() or result.stdout.strip()[:200]}")

    if not downloaded:
        _log(log, "gost не завантажено — буде Python fallback")
        return None

    subprocess.run(["tar", "-xzf", str(tar_path), "-C", str(tmp)], check=True)
    binary = tmp / "gost"
    if not binary.exists():
        return None

    for target in (Path("/opt/bravelgo/gost"), Path(user_home) / ".local" / "bin" / "gost"):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary, target)
            target.chmod(0o755)
            _log(log, f"gost → {target}")
            return str(target)
        except OSError as exc:
            _log(log, f"{target}: {exc}")
    return None


def build_upstream(scheme: str, ip: str, port: str, user: str, pwd: str) -> str:
    creds = f"{quote(user, safe='')}:{quote(pwd, safe='')}"
    if scheme == "http":
        return f"http://{creds}@{ip}:{port}"
    if scheme == "socks5":
        return f"socks5://{creds}@{ip}:{port}"
    if scheme == "socks5h":
        return f"socks5h://{creds}@{ip}:{port}"
    raise ValueError(scheme)


def schemes_for_type(proxy_type: str) -> list[str]:
    proxy_type = (proxy_type or "auto").lower()
    if proxy_type == "http":
        return ["http"]
    if proxy_type == "socks5":
        return ["socks5", "socks5h"]
    # auto — residential часто HTTP, SOCKS5 другий
    return ["http", "socks5", "socks5h"]


def _start_gost(gost: str, upstream: str, log_path: Path, log) -> subprocess.Popen | None:
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"\n--- gost -F={upstream.split('@')[-1]} ---\n")
        proc = subprocess.Popen(
            [gost, f"-L=socks5://127.0.0.1:{LISTEN_PORT}", f"-F={upstream}"],
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    for _ in range(20):
        if port_open():
            return proc
        if proc.poll() is not None:
            tail = log_path.read_text(encoding="utf-8")[-600:]
            _log(log, f"gost exit:\n{tail}")
            return None
        time.sleep(0.4)
    proc.kill()
    return None


def _start_python(script_name: str, upstream_file: Path, log_path: Path, log, label: str) -> bool:
    script = Path(__file__).resolve().parent / script_name
    if not script.exists():
        _log(log, f"Немає {script}")
        return False

    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"\n--- {script_name} ---\n")
        proc = subprocess.Popen(
            [sys_executable(), str(script), str(upstream_file)],
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    for _ in range(16):
        if port_open():
            _log(log, f"{label} pid={proc.pid} → 127.0.0.1:{LISTEN_PORT}")
            return True
        if proc.poll() is not None:
            tail = log_path.read_text(encoding="utf-8")[-600:]
            _log(log, f"{script_name} exit:\n{tail}")
            return False
        time.sleep(0.4)
    proc.kill()
    return False


def sys_executable() -> str:
    import sys

    return sys.executable


def _curl_test(log) -> tuple[bool, str]:
    if _proxy_mode == "python-http":
        cmd = ["curl", "-sS", "--max-time", "25", "-x", f"http://127.0.0.1:{LISTEN_PORT}",
               "https://api.ipify.org?format=json"]
    else:
        cmd = ["curl", "-sS", "--max-time", "25", "--socks5-hostname",
               f"127.0.0.1:{LISTEN_PORT}", "https://api.ipify.org?format=json"]

    if not shutil.which("curl"):
        return _urllib_test(log)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            ip = json.loads(result.stdout).get("ip", "?")
            return True, ip
        except json.JSONDecodeError:
            pass
    _log(log, f"curl test: {result.stderr.strip() or result.stdout[:120]}")
    return False, ""


def _urllib_test(log) -> tuple[bool, str]:
    try:
        import urllib.request

        if _proxy_mode == "python-http":
            handler = urllib.request.ProxyHandler({
                "http": f"http://127.0.0.1:{LISTEN_PORT}",
                "https": f"http://127.0.0.1:{LISTEN_PORT}",
            })
        else:
            handler = urllib.request.ProxyHandler({
                "http": f"socks5h://127.0.0.1:{LISTEN_PORT}",
                "https": f"socks5h://127.0.0.1:{LISTEN_PORT}",
            })
        with urllib.request.build_opener(handler).open(
            "https://api.ipify.org?format=json", timeout=25
        ) as resp:
            ip = json.loads(resp.read().decode()).get("ip", "?")
            return True, ip
    except Exception as exc:
        _log(log, f"urllib test: {exc}")
        return False, ""


def verify_proxy(log) -> tuple[bool, str]:
    if not port_open():
        _log(log, f"Порт {LISTEN_PORT} закритий")
        return False, ""
    ok, ip = _curl_test(log)
    if ok:
        _log(log, f"✅ OK → {ip} [{proxy_mode()}]")
    return ok, ip


def start_proxy(
    ip: str,
    port: str,
    user: str,
    pwd: str,
    user_home: str,
    real_user: str,
    log,
    proxy_type: str = "auto",
) -> bool:
    global _proxy_mode, _upstream_scheme

    stop_all(log)
    time.sleep(0.3)

    config_dir = Path(user_home) / ".config" / "bravelgo"
    config_dir.mkdir(parents=True, exist_ok=True)
    log_path = config_dir / "proxy.log"
    log_path.write_text("", encoding="utf-8")
    _chown_tree(config_dir, real_user)

    upstream_file = config_dir / "upstream.json"
    upstream_file.write_text(
        json.dumps({"host": ip, "port": int(port), "user": user, "password": pwd}),
        encoding="utf-8",
    )
    _chown_tree(config_dir, real_user)

    schemes = schemes_for_type(proxy_type)
    gost = install_gost(log, user_home)

    _log(log, f"Тип: {proxy_type} | пробую: {', '.join(schemes)}")

    if gost:
        for scheme in schemes:
            _kill_listener_only()
            upstream = build_upstream(scheme, ip, port, user, pwd)
            _log(log, f"Тест gost → {scheme}://{ip}:{port}")
            proc = _start_gost(gost, upstream, log_path, log)
            if not proc:
                continue
            ok, ext_ip = _curl_test(log)
            if ok:
                _proxy_mode = "gost"
                _upstream_scheme = scheme
                _log(log, f"✅ gost/{scheme} працює → IP {ext_ip}")
                _chown_tree(config_dir, real_user)
                return True
            _log(log, f"✗ gost/{scheme} — upstream не відповідає")
            proc.kill()

    # Python fallback
    fallbacks: list[tuple[str, str, str]] = []
    if proxy_type in ("auto", "http"):
        fallbacks.append(("local_proxy.py", "python-http", "HTTP residential"))
    if proxy_type in ("auto", "socks5"):
        fallbacks.append(("local_socks_chain.py", "python-socks", "SOCKS5"))

    for script, mode, label in fallbacks:
        if scheme_blocked(script, schemes, proxy_type):
            continue
        _kill_listener_only()
        _log(log, f"Python fallback: {label}")
        if _start_python(script, upstream_file, log_path, log, label):
            ok, ext_ip = _curl_test(log)
            if ok:
                _proxy_mode = mode
                _upstream_scheme = "http" if mode == "python-http" else "socks5"
                _log(log, f"✅ {label} → IP {ext_ip}")
                _chown_tree(config_dir, real_user)
                return True
            _log(log, f"✗ {label} — upstream не відповідає")

    tail = log_path.read_text(encoding="utf-8")[-1200:] if log_path.exists() else ""
    _log(log, f"❌ Жоден протокол не підійшов.\n{tail}")
    _proxy_mode = "none"
    return False


def scheme_blocked(script: str, schemes: list[str], proxy_type: str) -> bool:
    if script == "local_proxy.py":
        return proxy_type == "socks5" and "http" not in schemes
    if script == "local_socks_chain.py":
        return proxy_type == "http"
    return False


def _chown_tree(path: Path, real_user: str) -> None:
    import pwd

    try:
        uid = pwd.getpwnam(real_user).pw_uid
        gid = pwd.getpwnam(real_user).pw_gid
        for root, dirs, files in os.walk(path):
            os.chown(root, uid, gid)
            for name in dirs + files:
                os.chown(os.path.join(root, name), uid, gid)
    except Exception:
        pass


def firefox_proxy_prefs(disable: bool = False) -> str:
    if disable:
        return 'user_pref("network.proxy.type", 0);\n'

    if _proxy_mode == "python-http":
        return f"""user_pref("network.proxy.type", 1);
user_pref("network.proxy.http", "127.0.0.1");
user_pref("network.proxy.http_port", {LISTEN_PORT});
user_pref("network.proxy.ssl", "127.0.0.1");
user_pref("network.proxy.ssl_port", {LISTEN_PORT});
user_pref("network.proxy.share_proxy_settings", true);
user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1");
user_pref("media.peerconnection.enabled", false);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.default_address_only", true);
"""

    return f"""user_pref("network.proxy.type", 1);
user_pref("network.proxy.socks", "127.0.0.1");
user_pref("network.proxy.socks_port", {LISTEN_PORT});
user_pref("network.proxy.socks_version", 5);
user_pref("network.proxy.socks_remote_dns", true);
user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1");
user_pref("media.peerconnection.enabled", false);
user_pref("media.peerconnection.ice.no_host", true);
user_pref("media.peerconnection.ice.default_address_only", true);
"""
