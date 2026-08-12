"""The "backend" half of the pulse pipeline.

Exposes no API at all. Instead it continuously crafts raw ICMP echo
requests (ordinary-looking pings) whose payload secretly carries an
encoded pulse.Pulse frame, and fires them at the receiver. To anything
watching the wire it looks like one host pinging another; the payload is
where the signal actually lives.

A second background thread listens on the same kind of raw socket for
"nudge" packets coming back from the receiver - the other half of the
click-to-interact path: a visitor clicks the page, the receiver crafts a
nudge and pings it here, and the next few pulses we send out carry an
inflated burst value in response. Still no ordinary API anywhere.

Stdlib only - no third-party dependencies needed to speak raw ICMP.
"""

import math
import os
import random
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pulse"))
import pulse  # noqa: E402

_nudge_lock = threading.Lock()
_pending_nudge = {"intensity": 0.0, "expires": 0.0}


def nudge_listener(peer_ip: str) -> None:
    """Background thread: watch for nudge pings from the receiver."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    while True:
        try:
            packet, addr = sock.recvfrom(65535)
        except OSError as exc:
            print(f"nudge listener error: {exc}", file=sys.stderr, flush=True)
            continue

        if addr[0] != peer_ip:
            continue

        parsed = pulse.parse_ip_and_icmp(packet)
        if parsed is None:
            continue
        icmp_type, _code, _pkt_id, _pkt_seq, payload = parsed
        if icmp_type != 8:  # echo request only
            continue

        try:
            intensity = pulse.decode_nudge(payload)
        except pulse.DecodeError:
            continue

        with _nudge_lock:
            _pending_nudge["intensity"] = max(0.0, min(1.0, intensity))
            _pending_nudge["expires"] = time.monotonic() + 1.2


def take_pending_burst() -> float:
    """Consume a pending nudge, if any and not expired. Returns 0 otherwise."""
    with _nudge_lock:
        if _pending_nudge["expires"] > time.monotonic():
            value = _pending_nudge["intensity"]
            _pending_nudge["expires"] = 0.0  # one-shot: fire once, then quiet
            return value
    return 0.0


def main() -> None:
    peer_addr = os.environ.get("PEER_ADDR", "receiver")
    interval_ms = int(os.environ.get("SEND_INTERVAL_MS", "80"))
    peer_ip = socket.gethostbyname(peer_addr)

    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    icmp_id = os.getpid() & 0xFFFF
    rng = random.Random()
    start = time.monotonic()
    seq = 0

    print(f"sender: streaming pulses to {peer_addr} ({peer_ip}) every {interval_ms}ms", flush=True)

    t = threading.Thread(target=nudge_listener, args=(peer_ip,), daemon=True)
    t.start()

    while True:
        t_now = time.monotonic() - start

        hue = 0.5 + 0.5 * math.sin(t_now * 0.07)
        energy = 0.5 + 0.4 * math.sin(t_now * 0.31) + 0.1 * rng.random()
        speed = 0.4 + 0.3 * math.sin(t_now * 0.13 + 1.7)

        # Rare, short-lived bursts so the visual has punctuation on its
        # own, plus an on-demand one whenever a visitor's click reaches us.
        burst = 0.0
        if rng.random() < 0.01:
            burst = 0.6 + 0.4 * rng.random()
        nudged = take_pending_burst()
        if nudged > burst:
            burst = nudged

        p = pulse.Pulse(
            seq=seq,
            timestamp_ms=int(time.time() * 1000),
            hue=hue,
            energy=energy,
            speed=speed,
            burst=burst,
        )

        packet = pulse.build_echo_request(icmp_id, seq & 0xFFFF, pulse.encode(p))
        try:
            sock.sendto(packet, (peer_ip, 0))
        except OSError as exc:
            print(f"send error: {exc}", file=sys.stderr, flush=True)

        seq += 1
        time.sleep(interval_ms / 1000)


if __name__ == "__main__":
    main()
