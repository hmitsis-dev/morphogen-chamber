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
