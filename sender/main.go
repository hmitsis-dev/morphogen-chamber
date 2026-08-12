// Command sender is the "backend" half of the pulse pipeline. It never
// exposes any API. Instead it continuously crafts raw ICMP echo requests
// (ordinary-looking pings) whose payload secretly carries a pulse.Pulse
// frame, and fires them at the receiver. To anything watching the wire it
// looks like one host pinging another; the payload is where the signal
// actually lives.
package main

import (
	"log"
	"math"
	"math/rand"
	"net"
	"os"
	"strconv"
	"time"

	"golang.org/x/net/icmp"
	"golang.org/x/net/ipv4"

	"pale-moon/pulse"
)

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	peerAddr := envOr("PEER_ADDR", "receiver")
	intervalMs, err := strconv.Atoi(envOr("SEND_INTERVAL_MS", "80"))
	if err != nil || intervalMs <= 0 {
		intervalMs = 80
	}

	dst, err := net.ResolveIPAddr("ip4", peerAddr)
	if err != nil {
		log.Fatalf("resolve peer %q: %v", peerAddr, err)
	}

	conn, err := icmp.ListenPacket("ip4:icmp", "0.0.0.0")
	if err != nil {
		log.Fatalf("listen icmp (needs CAP_NET_RAW): %v", err)
	}
	defer conn.Close()

	log.Printf("sender: streaming pulses to %s every %dms", dst, intervalMs)

	pid := os.Getpid() & 0xffff
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))
	start := time.Now()

	var seq uint32
	ticker := time.NewTicker(time.Duration(intervalMs) * time.Millisecond)
	defer ticker.Stop()

	for range ticker.C {
		t := time.Since(start).Seconds()

		p := pulse.Pulse{
			Seq:         seq,
			TimestampMs: time.Now().UnixMilli(),
			Hue:         float32(0.5 + 0.5*math.Sin(t*0.07)),
			Energy:      float32(0.5 + 0.4*math.Sin(t*0.31) + 0.1*rng.Float64()),
			Speed:       float32(0.4 + 0.3*math.Sin(t*0.13+1.7)),
			Burst:       0,
		}
		// Rare, short-lived bursts so the visual has punctuation, not just drift.
		if rng.Float64() < 0.01 {
			p.Burst = float32(0.6 + 0.4*rng.Float64())
		}

		msg := icmp.Message{
			Type: ipv4.ICMPTypeEcho,
			Code: 0,
			Body: &icmp.Echo{
				ID:   pid,
				Seq:  int(seq),
				Data: pulse.Encode(p),
			},
		}

		wb, err := msg.Marshal(nil)
		if err != nil {
			log.Printf("marshal: %v", err)
			continue
		}
		if _, err := conn.WriteTo(wb, dst); err != nil {
			log.Printf("write to %s: %v", dst, err)
		}

		seq++
	}
}
