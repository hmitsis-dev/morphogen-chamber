package pulse

import "testing"

func TestRoundTrip(t *testing.T) {
	in := Pulse{Seq: 42, TimestampMs: 1723459200000, Hue: 0.73, Energy: 0.4, Speed: 0.91, Burst: 0}
	got, err := Decode(Encode(in))
	if err != nil {
		t.Fatalf("decode error: %v", err)
	}
	if got != in {
		t.Fatalf("round trip mismatch: got %+v want %+v", got, in)
	}
}

func TestDecodeErrors(t *testing.T) {
	if _, err := Decode(nil); err != ErrTooShort {
		t.Fatalf("expected ErrTooShort, got %v", err)
	}
	bad := Encode(Pulse{})
	bad[0] = 0x00
	if _, err := Decode(bad); err != ErrBadMagic {
		t.Fatalf("expected ErrBadMagic, got %v", err)
	}
}
