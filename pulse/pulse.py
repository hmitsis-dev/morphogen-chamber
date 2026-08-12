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

# A second, distinct payload shape for the interactive path: a visitor
# clicking the page asks the receiver to ask the sender for an extra
# burst. Different magic so it can never be mistaken for a Pulse frame.
NUDGE_MAGIC = (0xF1, 0x9F)
_NUDGE_FORMAT = ">BBf"  # magic (2 bytes) + intensity (float32)
NUDGE_SIZE = struct.calcsize(_NUDGE_FORMAT)  # 6 bytes


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


def encode_nudge(intensity: float) -> bytes:
    return struct.pack(_NUDGE_FORMAT, NUDGE_MAGIC[0], NUDGE_MAGIC[1], intensity)


def decode_nudge(data: bytes) -> float:
    if len(data) < NUDGE_SIZE:
        raise DecodeError(f"nudge payload too short: {len(data)} < {NUDGE_SIZE}")

    m0, m1, intensity = struct.unpack_from(_NUDGE_FORMAT, data, 0)
    if (m0, m1) != NUDGE_MAGIC:
        raise DecodeError("bad nudge magic")

    return intensity


def parse_ip_and_icmp(packet: bytes):
    """Raw ICMP sockets on Linux hand back the IP header too; strip it.

    Returns (icmp_type, code, pkt_id, pkt_seq, payload) or None if the
    packet is too short to be a real ICMP message.
    """
    if len(packet) < 20:
        return None
    ihl = (packet[0] & 0x0F) * 4
    icmp_part = packet[ihl:]
    if len(icmp_part) < 8:
        return None
    icmp_type, code, _chksum, pkt_id, pkt_seq = struct.unpack_from("!BBHHH", icmp_part, 0)
    payload = icmp_part[8:]
    return icmp_type, code, pkt_id, pkt_seq, payload


def build_echo_request(icmp_id: int, seq: int, payload: bytes) -> bytes:
    """Craft a raw ICMPv4 echo request (type 8) with a valid checksum."""
    header = struct.pack("!BBHHH", 8, 0, 0, icmp_id, seq)
    chksum = _checksum(header + payload)
    header = struct.pack("!BBHHH", 8, 0, chksum, icmp_id, seq)
    return header + payload


def _checksum(data: bytes) -> int:
    """Standard 16-bit one's complement checksum used by ICMP/IP."""
    if len(data) % 2:
        data += b"\x00"
    total = sum((data[i] << 8) + data[i + 1] for i in range(0, len(data), 2))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return ~total & 0xFFFF
