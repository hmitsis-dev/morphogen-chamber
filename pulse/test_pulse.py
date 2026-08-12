import pulse


def test_round_trip():
    p = pulse.Pulse(seq=42, timestamp_ms=1723459200000, hue=0.73, energy=0.4, speed=0.91, burst=0.0)
    got = pulse.decode(pulse.encode(p))
    assert got.seq == p.seq
    assert got.timestamp_ms == p.timestamp_ms
    assert round(got.hue, 5) == round(p.hue, 5)
    assert round(got.energy, 5) == round(p.energy, 5)
    assert round(got.speed, 5) == round(p.speed, 5)
    assert round(got.burst, 5) == round(p.burst, 5)


def test_too_short():
    try:
        pulse.decode(b"")
        assert False, "expected DecodeError"
    except pulse.DecodeError:
        pass


def test_bad_magic():
    bad = bytearray(pulse.encode(pulse.Pulse(0, 0, 0, 0, 0, 0)))
    bad[0] = 0x00
    try:
        pulse.decode(bytes(bad))
        assert False, "expected DecodeError"
    except pulse.DecodeError:
        pass


def test_nudge_round_trip():
    got = pulse.decode_nudge(pulse.encode_nudge(0.85))
    assert round(got, 5) == 0.85


def test_nudge_bad_magic():
    bad = bytearray(pulse.encode_nudge(0.5))
    bad[0] = 0x00
    try:
        pulse.decode_nudge(bytes(bad))
        assert False, "expected DecodeError"
    except pulse.DecodeError:
        pass


def test_nudge_does_not_decode_as_pulse():
    # Different magic bytes and different size - must never cross-decode.
    try:
        pulse.decode(pulse.encode_nudge(0.5))
        assert False, "expected DecodeError"
    except pulse.DecodeError:
        pass


def test_pulse_does_not_decode_as_nudge():
    p = pulse.Pulse(seq=1, timestamp_ms=0, hue=0, energy=0, speed=0, burst=0)
    try:
        pulse.decode_nudge(pulse.encode(p))
        assert False, "expected DecodeError"
    except pulse.DecodeError:
        pass


def test_build_echo_request_shape():
    pkt = pulse.build_echo_request(1234, 1, pulse.encode_nudge(0.5))
    assert len(pkt) == 8 + pulse.NUDGE_SIZE
    # type=8 (echo request), code=0
    assert pkt[0] == 8
    assert pkt[1] == 0
