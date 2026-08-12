# pale-moon

A public page that shows a living, ever-changing abstract visual with no
explanation and no purpose — that is secretly being painted, live, by
ordinary-looking network pings flowing between two services, forever,
for no reason other than that it's possible. Runs fine as two
containers on one machine, or split across two separate ones if you
want the ping to actually cross the internet.

## How it works

```
 Server A ("sender")                       Server B ("receiver")
 ┌─────────────────────┐   ICMP echo       ┌──────────────────────────┐
 │ generates a stream   │   requests, a    │ raw-sniffs ICMP traffic  │
 │ of "pulse" values     │──few per second─▶│ for ones carrying the    │
 │ (hue/energy/speed/    │   payload hides  │ pulse magic bytes,       │
 │ burst) and hides each  │   the data       │ decodes them, and        │
 │ one inside a normal    │                  │ rebroadcasts over        │
 │ ping's payload         │                  │ WebSocket to the page    │
 └─────────────────────┘                    └──────────────────────────┘
                                                        │
                                                        ▼
                                              browser canvas renders a
                                              generative visual driven
                                              by the live pulse stream
```

To anything watching the wire, Server A is just pinging Server B. The
signal actually lives in the ICMP payload — this is the same trick as
projects like [pingfs](https://github.com/yarrick/pingfs), used here to
drive generative art instead of a filesystem.

Clicking or tapping the page runs the same trick in reverse: the
receiver crafts its own "nudge" ICMP packet (a different, distinct
payload format) and pings the sender with it, asking for an inflated
burst. There's no ordinary HTTP API between the two services anywhere
in either direction — every real signal, in or out, travels disguised
as a ping.

- **`pulse/pulse.py`** — the shared wire formats: a 30-byte `Pulse`
  frame (magic bytes + sequence + timestamp + 4 float32 channels) and a
  6-byte `nudge` frame (distinct magic + one float32), plus the raw
  ICMPv4 echo-request builder/parser both services use. Single source
  of truth, imported unchanged by both.
- **`sender/`** — stdlib-only Python. Crafts raw ICMP echo requests by
  hand (including the checksum) and fires them at the receiver on an
  interval. A second background thread listens for nudge packets coming
  back from the receiver and inflates the next burst in response.
- **`receiver/`** — a small [aiohttp](https://docs.aiohttp.org) app. A
  background thread owns a raw ICMP socket, sniffs every echo request
  that arrives, decodes any that carry the pulse magic bytes, and
  broadcasts them (plus a raw hex packet log) to connected browsers over
  `/ws`. A periodic task also broadcasts a `meta` event with the live
  viewer count and host load average. `POST /nudge` (rate-limited per
  visitor and overall) is the one real piece of outside input — it
  crafts and sends the nudge packet to the sender. Also serves the
  static frontend in `receiver/static/`.
- **`receiver/static/`** — plain HTML/canvas. No build step, no
  framework. Renders a synthwave-ish generative scene (drifting glow
  particles over a receding grid horizon) driven entirely by the
  WebSocket stream, and reacts to clicks with a paired local/real ring
  effect (see below). A small `?` button in the corner reveals what's
  actually happening: the wire format, a live packets/sec + viewer count
  + host load readout, and a hex dump of incoming packets.

Both services need the `NET_RAW` capability to open raw sockets — see
`docker-compose.yml`.

## Quick start (single machine)

Everything runs happily on one box — one Docker network, both
containers, no extra configuration:

```sh
docker compose build
docker compose up
```

Open `http://localhost:8080`. The `sender` and `receiver` containers
find each other over Docker's internal DNS (`sender` and `receiver`
are the default hostnames baked into `docker-compose.yml`) and start
pinging each other immediately.

For a public deployment on a single VM, just run the same commands
there, open inbound TCP/8080 (or put a reverse proxy such as
Caddy/nginx in front for TLS on 443 — recommended for a public URL),
and you're done. No second machine required.

You can also run either service directly on the host without Docker
(useful for quick iteration, since raw ICMP sockets need root or
`CAP_NET_RAW`):

```sh
sudo PEER_ADDR=127.0.0.1 PORT=8091 python3 receiver/main.py
sudo PEER_ADDR=127.0.0.1 python3 sender/main.py
```

## Optional: splitting across two machines

The whole point of the trick still works with one box, but it's a bit
more fun for real if the "ping" is actually crossing the open internet
between two separate servers instead of staying inside one Docker
network. If you have two reachable Linux hosts, you can split the
two services between them:

1. **Clone this repo on both servers.**

2. **Server B (public-facing) — runs `receiver`:**

   ```sh
   cd pale-moon
   SENDER_ADDR=<Server A's IP> docker compose up -d --build receiver
   ```

   Open inbound TCP/8080 (or put a reverse proxy like Caddy/nginx in
   front for TLS on 443) and inbound ICMP echo from Server A's IP, in
   both your cloud provider's firewall/security-group settings **and**
   the host firewall (`firewalld`/`ufw`/`iptables`) — most cloud
   provider images block ICMP by default in both places.

3. **Server A (backend) — runs `sender`:**

   ```sh
   cd pale-moon
   RECEIVER_ADDR=<Server B's IP> docker compose up -d --build sender
   ```

   Needs outbound ICMP allowed to Server B — check the firewall/
   security-group settings and host firewall here too.

4. **Verify:** `docker compose logs -f` on either box should show the
   services running; the receiver logs which peer it's accepting
   pulses from. Visit Server B's public URL — the visual should be
   alive within a couple of seconds.

By default the receiver only renders pulses whose source IP matches
`PEER_ADDR` (Server A). Leave that unset if you'd rather accept
correctly-formed pulses from anyone who reverse engineers the format —
not recommended for an always-on public deployment, but a fun option
for a private demo.
