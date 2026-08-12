// Command receiver is the public-facing half of the pulse pipeline. It
// serves the static frontend, sniffs raw ICMP traffic for echo requests
// carrying a pulse.Pulse payload, and rebroadcasts decoded frames (plus a
// raw hex packet log) to any connected browser over WebSocket.
package main

import (
	"encoding/hex"
	"encoding/json"
	"log"
	"net"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"golang.org/x/net/icmp"
	"golang.org/x/net/ipv4"

	"pale-moon/pulse"
)

const packetLogCapacity = 64

// event is the single wire shape sent to every connected browser.
type event struct {
	Kind string `json:"kind"` // "pulse" or "packet"

	// pulse fields
	Seq    uint32  `json:"seq,omitempty"`
	Hue    float32 `json:"hue,omitempty"`
	Energy float32 `json:"energy,omitempty"`
	Speed  float32 `json:"speed,omitempty"`
	Burst  float32 `json:"burst,omitempty"`

	// packet fields
	Src string `json:"src,omitempty"`
	Hex string `json:"hex,omitempty"`

	TimestampMs int64 `json:"ts"`
}

type hub struct {
	mu      sync.Mutex
	clients map[*websocket.Conn]chan []byte
}

func newHub() *hub {
	return &hub{clients: make(map[*websocket.Conn]chan []byte)}
}

func (h *hub) add(c *websocket.Conn) chan []byte {
	ch := make(chan []byte, 32)
	h.mu.Lock()
	h.clients[c] = ch
	h.mu.Unlock()
	return ch
}

func (h *hub) remove(c *websocket.Conn) {
	h.mu.Lock()
	if ch, ok := h.clients[c]; ok {
		close(ch)
		delete(h.clients, c)
	}
	h.mu.Unlock()
}

func (h *hub) broadcast(payload []byte) {
	h.mu.Lock()
	defer h.mu.Unlock()
	for c, ch := range h.clients {
		select {
		case ch <- payload:
		default:
			// Slow client: drop the frame rather than block the pipeline.
			_ = c
		}
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	listenAddr := envOr("LISTEN_ADDR", ":8080")
	staticDir := envOr("STATIC_DIR", "./static")

	// Optional allowlist: if set, only pulses arriving from this resolved
	// peer are rendered. Leave unset to accept correctly-formed pulses
	// from anyone who finds the trick (magic bytes still required).
	var peerIP net.IP
	if peerAddr := os.Getenv("PEER_ADDR"); peerAddr != "" {
		addr, err := net.ResolveIPAddr("ip4", peerAddr)
		if err != nil {
			log.Fatalf("resolve PEER_ADDR %q: %v", peerAddr, err)
		}
		peerIP = addr.IP
		log.Printf("receiver: only accepting pulses from %s (%s)", peerAddr, peerIP)
	}

	h := newHub()

	go listenICMP(h, peerIP)

	mux := http.NewServeMux()
	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		serveWS(h, w, r)
	})
	mux.Handle("/", http.FileServer(http.Dir(staticDir)))

	log.Printf("receiver: listening on %s, serving %s", listenAddr, staticDir)
	if err := http.ListenAndServe(listenAddr, mux); err != nil {
		log.Fatal(err)
	}
}

func listenICMP(h *hub, peerIP net.IP) {
	conn, err := icmp.ListenPacket("ip4:icmp", "0.0.0.0")
	if err != nil {
		log.Fatalf("listen icmp (needs CAP_NET_RAW): %v", err)
	}
	defer conn.Close()

	buf := make([]byte, 1500)
	for {
		n, peer, err := conn.ReadFrom(buf)
		if err != nil {
			log.Printf("icmp read: %v", err)
			continue
		}

		if peerIP != nil {
			if udp, ok := peer.(*net.IPAddr); !ok || !udp.IP.Equal(peerIP) {
				continue
			}
		}

		msg, err := icmp.ParseMessage(1 /* ICMPv4 protocol number */, buf[:n])
		if err != nil || msg.Type != ipv4.ICMPTypeEcho {
			continue
		}
		echo, ok := msg.Body.(*icmp.Echo)
		if !ok {
			continue
		}

		now := time.Now().UnixMilli()

		// Every echo request that lands here gets a place in the raw
		// packet log, matched or not - that's the "how the hell" proof.
		h.broadcast(mustJSON(event{
			Kind:        "packet",
			Src:         peer.String(),
			Hex:         hex.EncodeToString(echo.Data),
			TimestampMs: now,
		}))

		p, err := pulse.Decode(echo.Data)
		if err != nil {
			continue
		}
		h.broadcast(mustJSON(event{
			Kind:        "pulse",
			Seq:         p.Seq,
			Hue:         p.Hue,
			Energy:      p.Energy,
			Speed:       p.Speed,
			Burst:       p.Burst,
			TimestampMs: now,
		}))
	}
}

func mustJSON(e event) []byte {
	b, err := json.Marshal(e)
	if err != nil {
		log.Printf("marshal event: %v", err)
		return nil
	}
	return b
}

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

func serveWS(h *hub, w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("ws upgrade: %v", err)
		return
	}
	defer conn.Close()

	ch := h.add(conn)
	defer h.remove(conn)

	// Discard anything the client sends; this is a one-way broadcast feed.
	go func() {
		for {
			if _, _, err := conn.NextReader(); err != nil {
				conn.Close()
				return
			}
		}
	}()

	for payload := range ch {
		if payload == nil {
			continue
		}
		conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
		if err := conn.WriteMessage(websocket.TextMessage, payload); err != nil {
			return
		}
	}
}
