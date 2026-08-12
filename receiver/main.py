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
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pulse"))
import pulse  # noqa: E402

from aiohttp import web, WSMsgType  # noqa: E402

START_TIME = time.monotonic()

clients: set[web.WebSocketResponse] = set()
clients_lock = threading.Lock()

total_packets_seen = 0
total_packets_lock = threading.Lock()

# Per-source-IP cooldown plus a small global cap, so the one endpoint that
# triggers outbound raw sockets from user input can't be turned into a
# packet-flooding amplifier.
NUDGE_COOLDOWN_S = 0.25
NUDGE_GLOBAL_MAX_PER_SEC = 15
_last_nudge_by_ip: dict[str, float] = {}
_nudge_lock = threading.Lock()
_recent_nudge_times: list[float] = []


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
    global total_packets_seen
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

        parsed = pulse.parse_ip_and_icmp(packet)
        if parsed is None:
            continue
        icmp_type, _code, _pkt_id, _pkt_seq, payload = parsed
        if icmp_type != 8:  # echo request only
            continue

        with total_packets_lock:
            total_packets_seen += 1

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


async def nudge_handler(request: web.Request) -> web.Response:
    """A visitor clicked the page. Ping the sender for real, asking it to
    inflate its next burst - the one place this whole project accepts
    outside input, so it's rate-limited per source and globally."""
    peer_ip = request.app.get("peer_ip")
    if not peer_ip:
        return web.json_response({"ok": False, "error": "no peer configured"}, status=503)

    remote = request.remote or "unknown"
    now = time.monotonic()

    with _nudge_lock:
        if now - _last_nudge_by_ip.get(remote, 0.0) < NUDGE_COOLDOWN_S:
            return web.json_response({"ok": False, "error": "too soon"}, status=429)

        cutoff = now - 1.0
        while _recent_nudge_times and _recent_nudge_times[0] < cutoff:
            _recent_nudge_times.pop(0)
        if len(_recent_nudge_times) >= NUDGE_GLOBAL_MAX_PER_SEC:
            return web.json_response({"ok": False, "error": "busy"}, status=429)

        _last_nudge_by_ip[remote] = now
        _recent_nudge_times.append(now)

    sock: socket.socket = request.app["nudge_sock"]
    icmp_id = request.app["nudge_icmp_id"]
    seq = int(time.monotonic() * 1000) & 0xFFFF

    packet = pulse.build_echo_request(icmp_id, seq, pulse.encode_nudge(0.85))
    try:
        sock.sendto(packet, (peer_ip, 0))
    except OSError as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=500)

    return web.json_response({"ok": True})


async def meta_broadcaster() -> None:
    """Every couple seconds, tell connected pages how many others are
    watching and what the machine is doing - separate from the pulse
    stream since it's about the audience/host, not the wire trick."""
    while True:
        await asyncio.sleep(2)

        with clients_lock:
            viewers = len(clients)
        with total_packets_lock:
            packets_total = total_packets_seen
        try:
            load1 = os.getloadavg()[0]
        except (OSError, AttributeError):
            load1 = None

        await broadcast({
            "kind": "meta",
            "viewers": viewers,
            "packetsTotal": packets_total,
            "uptimeS": int(time.monotonic() - START_TIME),
            "load1": load1,
            "ts": int(time.time() * 1000),
        })


async def on_startup(app: web.Application) -> None:
    loop = asyncio.get_event_loop()

    peer_ip = None
    peer_addr = os.environ.get("PEER_ADDR")
    if peer_addr:
        peer_ip = socket.gethostbyname(peer_addr)
        print(f"receiver: only accepting pulses from {peer_addr} ({peer_ip})", flush=True)
    app["peer_ip"] = peer_ip

    app["nudge_sock"] = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    app["nudge_icmp_id"] = os.getpid() & 0xFFFF

    t = threading.Thread(target=icmp_listener, args=(loop, peer_ip), daemon=True)
    t.start()

    app["meta_task"] = asyncio.create_task(meta_broadcaster())


def main() -> None:
    static_dir = os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "static"))
    port = int(os.environ.get("PORT", "8080"))

    app = web.Application()
    app.router.add_get("/ws", ws_handler)
    app.router.add_post("/nudge", nudge_handler)
    app.router.add_static("/", path=static_dir, show_index=True)
    app.on_startup.append(on_startup)

    print(f"receiver: listening on :{port}, serving {static_dir}", flush=True)
    web.run_app(app, host="0.0.0.0", port=port, print=None)


if __name__ == "__main__":
    main()
