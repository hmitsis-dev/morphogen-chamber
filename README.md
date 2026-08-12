# pale-moon

A public page that shows a living, ever-changing abstract visual with no
explanation and no purpose — that is secretly being painted, live, by
ordinary-looking network pings flowing between two servers, forever, for
no reason other than that it's possible.

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

- **`pulse/pulse.py`** — the shared wire format (30-byte binary frame,
  magic bytes + sequence + timestamp + 4 float32 channels), imported
  unchanged by both services.
- **`sender/`** — stdlib-only Python. Crafts raw ICMP echo requests by
  hand (including the checksum) and fires them at the receiver on an
  interval.
- **`receiver/`** — a small [aiohttp](https://docs.aiohttp.org) app. A
  background thread owns a raw ICMP socket, sniffs every echo request
  that arrives, decodes any that carry the pulse magic bytes, and
  broadcasts them (plus a raw hex packet log) to connected browsers over
  `/ws`. Also serves the static frontend in `receiver/static/`.
- **`receiver/static/`** — plain HTML/canvas. No build step, no
  framework. Renders a synthwave-ish generative scene (drifting glow
  particles over a receding grid horizon) driven entirely by the
  WebSocket stream. A small `?` button in the corner reveals what's
  actually happening, plus a live hex dump of incoming packets.

Both services need the `NET_RAW` capability to open raw sockets — see
`docker-compose.yml`.

## Local development

```sh
docker compose build
docker compose up
```

Open `http://localhost:8080`. Both services run in one Compose project
and talk to each other over the internal Docker network.

You can also run either service directly on the host (useful for
quick iteration, since raw ICMP sockets need root or `CAP_NET_RAW`):

```sh
sudo PEER_ADDR=127.0.0.1 PORT=8091 python3 receiver/main.py
sudo PEER_ADDR=127.0.0.1 python3 sender/main.py
```

## Deploying across two real servers

This is designed for exactly two small boxes (built against 2 vCPU /
12 GB RAM Oracle Cloud instances, but any two reachable Linux hosts
work).

1. **Clone this repo on both servers.**

2. **Server B (public-facing) — runs `receiver`:**

   ```sh
   cd pale-moon
   SENDER_ADDR=<Server A's IP> docker compose up -d --build receiver
   ```

   Open inbound TCP/8080 (or put a reverse proxy like Caddy/nginx in
   front for TLS on 443 — recommended for the public URL) and inbound
   ICMP echo from Server A's IP, in both the Oracle Cloud security
   list/NSG **and** the host firewall (`firewalld`/`ufw`/`iptables`) —
   Oracle images typically block ICMP by default in both places.

3. **Server A (backend) — runs `sender`:**

   ```sh
   cd pale-moon
   RECEIVER_ADDR=<Server B's IP> docker compose up -d --build sender
   ```

   Needs outbound ICMP allowed to Server B — check the security
   list/NSG and host firewall here too.

4. **Verify:** `docker compose logs -f` on either box should show the
   services running; the receiver logs which peer it's accepting
   pulses from. Visit Server B's public URL — the visual should be
   alive within a couple of seconds.

By default the receiver only renders pulses whose source IP matches
`PEER_ADDR` (Server A). Leave that unset if you'd rather accept
correctly-formed pulses from anyone who reverse engineers the format —
not recommended for the always-on public deployment, but a fun option
for a private demo.
