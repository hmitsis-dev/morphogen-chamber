// Package pulse defines the wire format smuggled inside ICMP echo payloads.
//
// A Pulse is a tiny snapshot of generative parameters (hue, energy, speed,
// burst) that the sender crafts and hides in the data section of ordinary
// ICMP echo requests. The receiver never runs a normal API - it sniffs raw
// ICMP traffic and decodes whichever packets happen to carry this format.
package pulse

import (
	"encoding/binary"
	"errors"
	"math"
)

// Magic marks a payload as ours so the receiver can ignore stray pings.
var Magic = [2]byte{0xF0, 0x9F}

// Size is the fixed length of an encoded Pulse in bytes.
const Size = 2 + 4 + 8 + 4*4

// Pulse is one frame of generative signal riding inside an ICMP packet.
type Pulse struct {
	Seq         uint32
	TimestampMs int64
	Hue         float32 // 0..1
	Energy      float32 // 0..1
	Speed       float32 // 0..1
	Burst       float32 // 0..1, spikes briefly on notable events
}

// ErrTooShort is returned when a payload is smaller than Size.
var ErrTooShort = errors.New("pulse: payload too short")

// ErrBadMagic is returned when a payload doesn't start with Magic.
var ErrBadMagic = errors.New("pulse: bad magic")

// Encode serializes p into a Size-byte buffer.
func Encode(p Pulse) []byte {
	buf := make([]byte, Size)
	buf[0], buf[1] = Magic[0], Magic[1]
	binary.BigEndian.PutUint32(buf[2:6], p.Seq)
	binary.BigEndian.PutUint64(buf[6:14], uint64(p.TimestampMs))
	binary.BigEndian.PutUint32(buf[14:18], math.Float32bits(p.Hue))
	binary.BigEndian.PutUint32(buf[18:22], math.Float32bits(p.Energy))
	binary.BigEndian.PutUint32(buf[22:26], math.Float32bits(p.Speed))
	binary.BigEndian.PutUint32(buf[26:30], math.Float32bits(p.Burst))
	return buf
}

// Decode parses a Pulse out of an ICMP echo payload. Extra trailing bytes
// (padding some OSes add to pings) are ignored.
func Decode(b []byte) (Pulse, error) {
	if len(b) < Size {
		return Pulse{}, ErrTooShort
	}
	if b[0] != Magic[0] || b[1] != Magic[1] {
		return Pulse{}, ErrBadMagic
	}
	return Pulse{
		Seq:         binary.BigEndian.Uint32(b[2:6]),
		TimestampMs: int64(binary.BigEndian.Uint64(b[6:14])),
		Hue:         math.Float32frombits(binary.BigEndian.Uint32(b[14:18])),
		Energy:      math.Float32frombits(binary.BigEndian.Uint32(b[18:22])),
		Speed:       math.Float32frombits(binary.BigEndian.Uint32(b[22:26])),
		Burst:       math.Float32frombits(binary.BigEndian.Uint32(b[26:30])),
	}, nil
}
