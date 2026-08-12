"""The public-facing half of the pulse pipeline.

Serves the static frontend, sniffs raw ICMP traffic for echo requests
carrying a pulse.Pulse payload, and rebroadcasts decoded frames (plus a
raw hex packet log) to any connected browser over WebSocket.

Only third-party dependency is aiohttp (HTTP + WebSocket server). Raw
ICMP capture is plain stdlib sockets, read in a background thread since
recvfrom() blocks.
"""

import asyncio
import binascii
import json
import os
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pulse"))
import pulse  # noqa: E402

from aiohttp import web, WSMsgType  # noqa: E402

clients: set[web.WebSocketResponse] = set()
clients_lock = threading.Lock()


def parse_ip_and_icmp(packet: bytes):
    """Raw ICMP sockets on Linux hand back the IP header too; strip it."""
    if len(packet) < 20:
        return None
    ihl = (packet[0] & 0x0F) * 4
    icmp_part = packet[ihl:]
    if len(icmp_part) < 8:
        return None
    icmp_type, code, _chksum, pkt_id, pkt_seq = struct.unpack_from("!BBHHH", icmp_part, 0)
    payload = icmp_part[8:]
    return icmp_type, code, pkt_id, pkt_seq, payload


async def broadcast(event: dict) -> None:
    data = json.dumps(event)
    dead = []
    for ws in list(clients):
        try:
            await ws.send_str(data)
        except ConnectionResetError:
            dead.append(ws)
    if dead:
        with clients_lock:
            for ws in dead:
                clients.discard(ws)


def icmp_listener(loop: asyncio.AbstractEventLoop, peer_ip: str | None) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    while True:
        try:
            packet, addr = sock.recvfrom(65535)
        except OSError as exc:
            print(f"icmp read error: {exc}", file=sys.stderr, flush=True)
            continue

        src_ip = addr[0]
        if peer_ip is not None and src_ip != peer_ip:
            continue

        parsed = parse_ip_and_icmp(packet)
        if parsed is None:
            continue
        icmp_type, _code, _pkt_id, _pkt_seq, payload = parsed
        if icmp_type != 8:  # echo request only
            continue

        now_ms = int(time.time() * 1000)

        # Every matching echo request gets a place in the raw packet log,
        # decodable or not - that's the "how the hell" proof on the page.
        packet_event = {
            "kind": "packet",
            "src": src_ip,
            "hex": binascii.hexlify(payload[:32]).decode(),
            "ts": now_ms,
        }
        asyncio.run_coroutine_threadsafe(broadcast(packet_event), loop)

        try:
            p = pulse.decode(payload)
        except pulse.DecodeError:
            continue

        pulse_event = {
            "kind": "pulse",
            "seq": p.seq,
            "hue": p.hue,
            "energy": p.energy,
            "speed": p.speed,
            "burst": p.burst,
            "ts": now_ms,
        }
        asyncio.run_coroutine_threadsafe(broadcast(pulse_event), loop)


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    with clients_lock:
        clients.add(ws)
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
            # One-way broadcast feed; anything the client sends is ignored.
    finally:
        with clients_lock:
            clients.discard(ws)
    return ws


async def on_startup(app: web.Application) -> None:
    loop = asyncio.get_event_loop()

    peer_ip = None
    peer_addr = os.environ.get("PEER_ADDR")
    if peer_addr:
        peer_ip = socket.gethostbyname(peer_addr)
        print(f"receiver: only accepting pulses from {peer_addr} ({peer_ip})", flush=True)

    t = threading.Thread(target=icmp_listener, args=(loop, peer_ip), daemon=True)
    t.start()


def main() -> None:
    static_dir = os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "static"))
    port = int(os.environ.get("PORT", "8080"))

    app = web.Application()
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/", path=static_dir, show_index=True)
    app.on_startup.append(on_startup)

    print(f"receiver: listening on :{port}, serving {static_dir}", flush=True)
    web.run_app(app, host="0.0.0.0", port=port, print=None)


if __name__ == "__main__":
    main()
