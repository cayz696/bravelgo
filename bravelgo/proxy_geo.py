"""Proxy geo lookup + bridge management."""
from __future__ import annotations

import json
import os
import subprocess
import time

BRIDGE_BIN = "/usr/local/bin/bravelgo_bridge.py"
BRIDGE_SVC = "/etc/systemd/system/bravelgo-bridge.service"
BRIDGE_PORT = 8118


def run(cmd: str) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def ensure_pysocks() -> None:
    try:
        import socks  # noqa: F401
        return
    except ImportError:
        run("pip3 install PySocks --break-system-packages -q")
        import socks  # noqa: F401


def _parse_http_json(raw: bytes) -> dict:
    body = raw.split(b"\r\n\r\n", 1)[-1].decode(errors="replace")
    return json.loads(body)


def geo_via_socks5(ip: str, port: str, user: str, pwd: str) -> tuple[str, str]:
    ensure_pysocks()
    import socks

    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, ip, int(port), True, user, pwd)
    s.settimeout(15)
    s.connect(("ip-api.com", 80))
    req = (
        "GET /json?fields=countryCode,timezone,query HTTP/1.0\r\n"
        "Host: ip-api.com\r\n"
        "Connection: close\r\n\r\n"
    )
    s.send(req.encode())
    chunks = []
    while True:
        part = s.recv(4096)
        if not part:
            break
        chunks.append(part)
    s.close()
    data = _parse_http_json(b"".join(chunks))
    return data.get("countryCode", "?"), data.get("timezone", "?")


def geo_via_http(ip: str, port: str, user: str, pwd: str) -> tuple[str, str]:
    import urllib.request

    proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = urllib.request.build_opener(handler)
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    with opener.open(
        "http://ip-api.com/json?fields=countryCode,timezone,query", timeout=12
    ) as resp:
        data = json.loads(resp.read().decode())
    return data.get("countryCode", "?"), data.get("timezone", "?")


def geo_via_local_bridge() -> tuple[str, str]:
    import urllib.request

    handler = urllib.request.ProxyHandler(
        {"http": f"http://127.0.0.1:{BRIDGE_PORT}", "https": f"http://127.0.0.1:{BRIDGE_PORT}"}
    )
    opener = urllib.request.build_opener(handler)
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    with opener.open(
        "http://ip-api.com/json?fields=countryCode,timezone,query", timeout=10
    ) as resp:
        data = json.loads(resp.read().decode())
    return data.get("countryCode", "?"), data.get("timezone", "?")


def get_proxy_country(
    ip: str, port: str, user: str, pwd: str, is_socks: bool, log=None
) -> tuple[str, str]:
    try:
        if is_socks:
            cc, tz = geo_via_socks5(ip, port, user, pwd)
        else:
            cc, tz = geo_via_http(ip, port, user, pwd)
        if log:
            log(f"Geo: {cc} / {tz}")
        return cc, tz
    except Exception as exc:
        if log:
            log(f"Geo lookup failed: {exc}")
        return "?", "?"


def write_bridge(ip: str, port: str, user: str, pwd: str, is_socks: bool, log=None) -> None:
    if is_socks:
        script = f'''#!/usr/bin/env python3
import asyncio, logging
try:
    import socks
except ImportError:
    import subprocess
    subprocess.run(["pip3","install","PySocks","--break-system-packages","-q"], check=False)
    import socks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler("/var/log/bravelgo_bridge.log"), logging.StreamHandler()])
log = logging.getLogger("bridge")
HOST="{ip}"; PORT={port}; USER="{user}"; PASS="{pwd}"; LPORT={BRIDGE_PORT}

async def relay(r, w):
    try:
        while chunk := await r.read(32768):
            w.write(chunk); await w.drain()
    except Exception:
        pass
    finally:
        try: w.close()
        except Exception: pass

def socks_connect(host, port):
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, HOST, PORT, True, USER, PASS)
    s.settimeout(15)
    s.connect((host, port))
    return s

async def handle(reader, writer):
    try:
        data = await asyncio.wait_for(reader.read(4096), timeout=15)
        if not data:
            writer.close(); return
        first = data.split(b"\\n")[0].decode(errors="replace").strip()
        if first.upper().startswith("CONNECT"):
            target = first.split()[1]
            host, port_s = target.rsplit(":", 1)
            loop = asyncio.get_event_loop()
            sock = await loop.run_in_executor(None, lambda: socks_connect(host, int(port_s)))
            up_r, up_w = await asyncio.open_connection(sock=sock)
            writer.write(b"HTTP/1.1 200 Connection established\\r\\n\\r\\n")
            await writer.drain()
            await asyncio.gather(relay(reader, up_w), relay(up_r, writer))
        else:
            import urllib.parse
            url = data.split(b"\\r\\n", 1)[0].decode(errors="replace").split()[1]
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or "localhost"
            port_n = parsed.port or 80
            loop = asyncio.get_event_loop()
            sock = await loop.run_in_executor(None, lambda: socks_connect(host, port_n))
            up_r, up_w = await asyncio.open_connection(sock=sock)
            up_w.write(data); await up_w.drain()
            await asyncio.gather(relay(up_r, writer), relay(reader, up_w))
    except Exception as e:
        log.error(f"err: {{e}}")
        try: writer.close()
        except Exception: pass

async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LPORT)
    log.info(f"SOCKS5 bridge 127.0.0.1:{{LPORT}} -> {{HOST}}:{{PORT}}")
    async with srv:
        await srv.serve_forever()

asyncio.run(main())
'''
    else:
        script = f'''#!/usr/bin/env python3
import asyncio, base64, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler("/var/log/bravelgo_bridge.log"), logging.StreamHandler()])
log = logging.getLogger("bridge")
HOST="{ip}"; PORT={port}
AUTH=base64.b64encode("{user}:{pwd}".encode()).decode()
LPORT={BRIDGE_PORT}

async def relay(r, w):
    try:
        while chunk := await r.read(32768):
            w.write(chunk); await w.drain()
    except Exception:
        pass
    finally:
        try: w.close()
        except Exception: pass

async def handle(reader, writer):
    try:
        data = await asyncio.wait_for(reader.read(4096), timeout=15)
        if not data:
            writer.close(); return
        first = data.split(b"\\n")[0].decode(errors="replace").strip()
        if first.upper().startswith("CONNECT"):
            target = first.split()[1]
            up_r, up_w = await asyncio.wait_for(asyncio.open_connection(HOST, PORT), timeout=10)
            req = (f"CONNECT {{target}} HTTP/1.1\\r\\nHost: {{target}}\\r\\n"
                   f"Proxy-Authorization: Basic {{AUTH}}\\r\\n\\r\\n").encode()
            up_w.write(req); await up_w.drain()
            resp = await asyncio.wait_for(up_r.read(4096), timeout=10)
            if b"200" not in resp:
                writer.close(); return
            writer.write(b"HTTP/1.1 200 Connection established\\r\\n\\r\\n")
            await writer.drain()
            await asyncio.gather(relay(reader, up_w), relay(up_r, writer))
        else:
            up_r, up_w = await asyncio.wait_for(asyncio.open_connection(HOST, PORT), timeout=10)
            if b"Proxy-Authorization" not in data:
                ins = f"Proxy-Authorization: Basic {{AUTH}}\\r\\n".encode()
                data = data.replace(b"\\r\\n", b"\\r\\n" + ins, 1)
            up_w.write(data); await up_w.drain()
            await asyncio.gather(relay(up_r, writer), relay(reader, up_w))
    except Exception as e:
        log.error(f"err: {{e}}")
        try: writer.close()
        except Exception: pass

async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LPORT)
    log.info(f"HTTP bridge 127.0.0.1:{{LPORT}} -> {{HOST}}:{{PORT}}")
    async with srv:
        await srv.serve_forever()

asyncio.run(main())
'''
    with open(BRIDGE_BIN, "w", encoding="utf-8") as f:
        f.write(script)
    run(f"chmod +x {BRIDGE_BIN}")
    svc = f"""[Unit]
Description=BravelGo Proxy Bridge
After=network.target
[Service]
Type=simple
ExecStart=/usr/bin/python3 {BRIDGE_BIN}
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
"""
    with open(BRIDGE_SVC, "w", encoding="utf-8") as f:
        f.write(svc)
    run("systemctl daemon-reload")
    run("systemctl enable bravelgo-bridge")
    if log:
        log("Bridge installed")


def start_bridge(log=None) -> bool:
    run("systemctl restart bravelgo-bridge")
    time.sleep(1)
    _, out = run("systemctl is-active bravelgo-bridge")
    ok = "active" in out
    if log:
        log(f"Bridge: {out}")
    return ok


def stop_bridge(log=None) -> None:
    run("systemctl stop bravelgo-bridge 2>/dev/null")
    run("systemctl disable bravelgo-bridge 2>/dev/null")
    if log:
        log("Bridge stopped")


def test_proxy(ip: str, port: str, user: str, pwd: str, is_socks: bool) -> str:
    if is_socks:
        ensure_pysocks()
        import socks

        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, ip, int(port), True, user, pwd)
        s.settimeout(12)
        s.connect(("api.ipify.org", 80))
        s.send(b"GET /?format=text HTTP/1.0\r\nHost: api.ipify.org\r\n\r\n")
        data = s.recv(4096).decode()
        s.close()
        lines = [l.strip() for l in data.split("\n") if l.strip() and not l.startswith("HTTP")]
        return lines[-1] if lines else "?"
    import urllib.request

    proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
    h = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = urllib.request.build_opener(h)
    with opener.open("https://api.ipify.org?format=text", timeout=12) as resp:
        return resp.read().decode().strip()
