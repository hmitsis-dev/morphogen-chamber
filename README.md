# singata-capital

A fake hedge-fund terminal. There is no fund. It publishes a live "alpha
signal" whose confidence starts high when you're the only visitor, and
mathematically decays toward 50% — a coin flip — as more people load the
page, live, in front of you.

That's not a random gimmick — it's a straight illustration of the
**Grossman–Stiglitz paradox**: if markets were perfectly efficient, no one
could profit from gathering information, so no one would bother gathering
it, so markets couldn't stay efficient. Private information has value
*because* it's private; the moment it's public, the edge is gone. This
terminal computes that decay directly from the live viewer count, every
two seconds, and dresses it up in full Bloomberg-terminal seriousness:
real crypto prices, a scrolling ticker, dense jargon-generated commentary,
and a backtest that's suspiciously, tellingly smooth.

Not investment advice. Not a real company. See the in-page disclosure
(and the `?` panel) for the rest of the bit.

## How it works

- **`app/prices.py`** — live prices for BTC/ETH/SOL from CoinGecko's free,
  keyless endpoint, refreshed every 45s. Falls back to seeded values and
  keeps retrying if a fetch fails, rather than breaking the page. A
  `MOCK_PRICES=1` mode generates wandering fake prices instead, for local
  dev without a network call.
- **`app/paradox.py`** — the actual joke, as math. `confidence_for(viewers,
  t)` starts at a slowly-drifting "peak" value (52-94%, what a sole
  observer would see) and decays toward 50% as `viewers` grows, via
  `1 / (1 + K * (viewers - 1))`. The first viewer pays no penalty —
  information is only "public" once someone else is also looking. Also
  generates the fake trade call (asset/direction/target) and the
  jargon-template commentary, tied loosely to the current confidence band
  so the copy at least sounds like it's reacting to something real.
  (Named `paradox.py`, not `signal.py`, so it doesn't shadow Python's
  stdlib `signal` module — aiohttp needs the real one.)
- **`app/backtest.py`** — a fake equity curve: a seeded random walk with
  slight positive drift, smoothed twice with a moving average. The Sharpe
  ratio shown is real arithmetic computed on that series — genuinely
  absurd (order of 20-30) precisely because the smoothing engineered away
  the volatility a real strategy would have. The math isn't lying; the
  input is.
- **`app/main.py`** — aiohttp app: serves the static frontend, ticks every
  2s recomputing confidence from the live WebSocket client count and
  broadcasting the current call + commentary + prices, sends the backtest
  curve once on connect.
- **`static/`** — plain HTML/canvas, no build step. Amber-on-black
  terminal aesthetic, a scrolling price ticker, the confidence gauge, a
  hand-drawn backtest line chart, and a `?` panel that explains the
  Grossman-Stiglitz mechanic plainly for anyone who wants the joke
  spelled out.

## Running it

Single machine, one service:

```sh
docker compose build
docker compose up
```

Open `http://localhost:8080`. Set `MOCK_PRICES=1` before `docker compose
up` to run without hitting the network (useful for offline dev, or if
you're testing in an environment that blocks outbound API calls).

Without Docker:

```sh
cd app
pip install -r requirements.txt
MOCK_PRICES=1 python3 main.py
```

For a public deployment, run the same commands on your VM, open inbound
TCP/8080 (or put a reverse proxy such as Caddy/nginx in front for TLS on
443), and you're done — no second machine needed.
