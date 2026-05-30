#!/usr/bin/env python3
"""
BravelGo Local HTTP Proxy — fallback без gost.
Слухає 127.0.0.1:1080, тунелює через upstream HTTP proxy з auth.
Запуск: python3 local_proxy.py /path/to/upstream.json
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
from pathlib import Path

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 1080

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("bravelgo-proxy")


def load_upstream(path: str) -> tuple[str, int, str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["host"], int(data["port"]), data["user"], data["password"]


def auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Proxy-Authorization: Basic {token}\r\n"


async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle_connect(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target: str,
    upstream_host: str,
    upstream_port: int,
    extra_headers: str,
) -> None:
    up_reader, up_writer = await asyncio.wait_for(
        asyncio.open_connection(upstream_host, upstream_port),
        timeout=20,
    )
    req = (
        f"CONNECT {target} HTTP/1.1\r\n"
        f"Host: {target}\r\n"
        f"{extra_headers}"
        f"\r\n"
    ).encode()
    up_writer.write(req)
    await up_writer.drain()

    resp = await asyncio.wait_for(up_reader.read(4096), timeout=20)
    if b" 200" not in resp.split(b"\r\n", 1)[0]:
        log.warning("Upstream CONNECT fail %s: %s", target, resp[:120])
        client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await client_writer.drain()
        up_writer.close()
        return

    client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await client_writer.drain()
    await asyncio.gather(
        relay(client_reader, up_writer),
        relay(up_reader, client_writer),
    )


async def handle_http(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    first_line: bytes,
    header_lines: list[bytes],
    upstream_host: str,
    upstream_port: int,
    extra_headers: str,
) -> None:
    up_reader, up_writer = await asyncio.wait_for(
        asyncio.open_connection(upstream_host, upstream_port),
        timeout=20,
    )
    headers = b"".join(header_lines)
    if b"Proxy-Authorization" not in headers:
        headers += extra_headers.encode()
    payload = first_line + headers + b"\r\n"
    up_writer.write(payload)
    await up_writer.drain()
    await asyncio.gather(
        relay(client_reader, up_writer),
        relay(up_reader, client_writer),
    )


async def handle_client(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_host: str,
    upstream_port: int,
    extra_headers: str,
) -> None:
    try:
        first_line = await asyncio.wait_for(client_reader.readline(), timeout=30)
        if not first_line:
            return

        header_lines: list[bytes] = []
        while True:
            line = await client_reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            header_lines.append(line)

        method = first_line.decode(errors="replace").split(" ", 1)[0].upper()

        if method == "CONNECT":
            target = first_line.decode(errors="replace").split(" ")[1].strip()
            await handle_connect(
                client_reader, client_writer, target,
                upstream_host, upstream_port, extra_headers,
            )
        else:
            await handle_http(
                client_reader, client_writer, first_line, header_lines,
                upstream_host, upstream_port, extra_headers,
            )
    except Exception as exc:
        log.error("Client error: %s", exc)
    finally:
        try:
            client_writer.close()
            await client_writer.wait_closed()
        except Exception:
            pass


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: local_proxy.py upstream.json", file=sys.stderr)
        sys.exit(1)

    host, port, user, pwd = load_upstream(sys.argv[1])
    extra = auth_header(user, pwd)
    log.info("Listening %s:%s → %s:%s", LISTEN_HOST, LISTEN_PORT, host, port)

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, host, port, extra),
        LISTEN_HOST,
        LISTEN_PORT,
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
