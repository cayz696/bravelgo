#!/usr/bin/env python3
"""
Локальний SOCKS5 (без auth) → upstream SOCKS5 з логіном/паролем.
Запуск: python3 local_socks_chain.py /path/to/upstream.json
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import sys
from pathlib import Path

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 1080

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("socks-chain")


def load_cfg(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def socks5_connect_upstream(host: str, port: int, user: str, pwd: str, target: str, tport: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=25)

    writer.write(b"\x05\x01\x02")
    await writer.drain()
    resp = await asyncio.wait_for(reader.readexactly(2), timeout=15)
    if resp[0] != 5 or resp[1] != 2:
        raise ConnectionError(f"upstream auth method: {resp.hex()}")

    u, p = user.encode(), pwd.encode()
    auth = b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p
    writer.write(auth)
    await writer.drain()
    auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=15)
    if auth_resp[1] != 0:
        raise ConnectionError("upstream auth rejected")

    th, tp = target.encode(), tport
    req = b"\x05\x01\x00\x03" + bytes([len(th)]) + th + struct.pack("!H", tp)
    writer.write(req)
    await writer.drain()
    hdr = await asyncio.wait_for(reader.readexactly(4), timeout=15)
    if hdr[1] != 0:
        raise ConnectionError(f"upstream connect code {hdr[1]}")
    atyp = hdr[3]
    if atyp == 1:
        await reader.readexactly(4 + 2)
    elif atyp == 3:
        ln = (await reader.readexactly(1))[0]
        await reader.readexactly(ln + 2)
    elif atyp == 4:
        await reader.readexactly(16 + 2)
    return reader, writer


async def relay(a: asyncio.StreamReader, b: asyncio.StreamWriter) -> None:
    try:
        while chunk := await a.read(65536):
            b.write(chunk)
            await b.drain()
    except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        try:
            b.close()
            await b.wait_closed()
        except Exception:
            pass


async def handle_client(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter, cfg: dict) -> None:
    try:
        header = await asyncio.wait_for(client_r.readexactly(2), timeout=20)
        if header[0] != 5:
            return
        methods = await client_r.readexactly(header[1])
        if 0 not in methods:
            client_w.write(b"\x05\xff")
            await client_w.drain()
            return
        client_w.write(b"\x05\x00")
        await client_w.drain()

        req = await asyncio.wait_for(client_r.readexactly(4), timeout=20)
        if req[0] != 5 or req[1] != 1:
            return
        atyp = req[3]
        if atyp == 1:
            addr = await client_r.readexactly(4)
            target = ".".join(str(b) for b in addr)
        elif atyp == 3:
            ln = (await client_r.readexactly(1))[0]
            target = (await client_r.readexactly(ln)).decode()
        elif atyp == 4:
            raw = await client_r.readexactly(16)
            target = ":".join(f"{raw[i:i+2].hex()}" for i in range(0, 16, 2))
        else:
            return
        tport = struct.unpack("!H", await client_r.readexactly(2))[0]

        up_r, up_w = await socks5_connect_upstream(
            cfg["host"], int(cfg["port"]), cfg["user"], cfg["password"], target, tport
        )
        client_w.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await client_w.drain()
        await asyncio.gather(relay(client_r, up_w), relay(up_r, client_w))
    except Exception as exc:
        log.error("client: %s", exc)
    finally:
        try:
            client_w.close()
            await client_w.wait_closed()
        except Exception:
            pass


async def main() -> None:
    cfg = load_cfg(sys.argv[1])
    log.info("SOCKS5 %s:%s → %s:%s", LISTEN_HOST, LISTEN_PORT, cfg["host"], cfg["port"])
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, cfg), LISTEN_HOST, LISTEN_PORT
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
