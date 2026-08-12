"""The "backend" half of the pulse pipeline.

Exposes no API at all. Instead it continuously crafts raw ICMP echo
requests (ordinary-looking pings) whose payload secretly carries an
encoded pulse.Pulse frame, and fires them at the receiver. To anything
watching the wire it looks like one host pinging another; the payload is
where the signal actually lives.

Stdlib only - no third-party dependencies needed to speak raw ICMP.
"""

import math
import os
import random
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pulse"))
import pulse  # noqa: E402


def checksum(data: bytes) -> int:
    """Standard 16-bit one's complement checksum used by ICMP/IP."""
    if len(data) % 2:
        data += b"\x00"
    total = sum((data[i] << 8) + data[i + 1] for i in range(0, len(data), 2))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return ~total & 0xFFFF


def build_echo_request(icmp_id: int, seq: int, payload: bytes) -> bytes:
    header = struct.pack("!BBHHH", 8, 0, 0, icmp_id, seq)  # type=8 (echo request)
    chksum = checksum(header + payload)
    header = struct.pack("!BBHHH", 8, 0, chksum, icmp_id, seq)
    return header + payload


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

    while True:
        t = time.monotonic() - start

        hue = 0.5 + 0.5 * math.sin(t * 0.07)
        energy = 0.5 + 0.4 * math.sin(t * 0.31) + 0.1 * rng.random()
        speed = 0.4 + 0.3 * math.sin(t * 0.13 + 1.7)
        burst = 0.0
        # Rare, short-lived bursts so the visual has punctuation, not just drift.
        if rng.random() < 0.01:
            burst = 0.6 + 0.4 * rng.random()

        p = pulse.Pulse(
            seq=seq,
            timestamp_ms=int(time.time() * 1000),
            hue=hue,
            energy=energy,
            speed=speed,
            burst=burst,
        )

        packet = build_echo_request(icmp_id, seq & 0xFFFF, pulse.encode(p))
        try:
            sock.sendto(packet, (peer_ip, 0))
        except OSError as exc:
            print(f"send error: {exc}", file=sys.stderr, flush=True)

        seq += 1
        time.sleep(interval_ms / 1000)


if __name__ == "__main__":
    main()
