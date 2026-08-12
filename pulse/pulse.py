"""Wire format smuggled inside ICMP echo payloads.

A Pulse is a tiny snapshot of generative parameters (hue, energy, speed,
burst) that the sender crafts and hides in the data section of ordinary
ICMP echo requests. The receiver never runs a normal API - it sniffs raw
ICMP traffic and decodes whichever packets happen to carry this format.

This module is the single source of truth for the format; sender and
receiver both import it unchanged (see each Dockerfile).
"""

from dataclasses import dataclass
import struct

MAGIC = (0xF0, 0x9F)

# > = big-endian, no padding
# B B          magic (2 bytes)
# I            seq (uint32)
# q            timestamp_ms (int64)
# f f f f      hue, energy, speed, burst (float32 each)
_FORMAT = ">BBIq4f"
SIZE = struct.calcsize(_FORMAT)  # 30 bytes


class DecodeError(ValueError):
    pass


@dataclass
class Pulse:
    seq: int
    timestamp_ms: int
    hue: float
    energy: float
    speed: float
    burst: float


def encode(p: Pulse) -> bytes:
    return struct.pack(
        _FORMAT,
        MAGIC[0], MAGIC[1],
        p.seq & 0xFFFFFFFF,
        p.timestamp_ms,
        p.hue, p.energy, p.speed, p.burst,
    )


def decode(data: bytes) -> Pulse:
    if len(data) < SIZE:
        raise DecodeError(f"payload too short: {len(data)} < {SIZE}")

    m0, m1, seq, ts, hue, energy, speed, burst = struct.unpack_from(_FORMAT, data, 0)
    if (m0, m1) != MAGIC:
        raise DecodeError("bad magic")

    return Pulse(seq=seq, timestamp_ms=ts, hue=hue, energy=energy, speed=speed, burst=burst)
