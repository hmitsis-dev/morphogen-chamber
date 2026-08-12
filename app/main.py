"""Singata Capital: a satirical hedge-fund terminal.

Publishes a live "alpha signal" whose confidence is computed straight from
the Grossman-Stiglitz paradox (see paradox.py) - it decays toward a coin
flip as more people watch the page, because public information can't be
an edge. Everything else (the ticker, the commentary, the suspiciously
smooth backtest) is dressed-up satire around that one real idea.

Not investment advice. Not a real fund. See the footer.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time

import backtest
import prices as prices_mod
import paradox as sig

from aiohttp import ClientSession, web, WSMsgType

clients: set[web.WebSocketResponse] = set()

TICK_INTERVAL_S = 2.0
PRICE_REFRESH_S = 45.0
CALL_REROLL_S = 75.0


async def broadcast(payload: dict) -> None:
    if not clients:
        return
    data = json.dumps(payload)
    dead = []
    for ws in list(clients):
        try:
            await ws.send_str(data)
        except (ConnectionResetError, RuntimeError):
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


async def price_loop(app: web.Application) -> None:
    book: prices_mod.PriceBook = app["price_book"]
    async with ClientSession() as session:
        while True:
            try:
                await book.refresh(session)
            except Exception as exc:  # noqa: BLE001 - keep serving stale prices on any failure
                print(f"price refresh failed (serving last known values): {exc}", file=sys.stderr, flush=True)
            await asyncio.sleep(PRICE_REFRESH_S)


async def tick_loop(app: web.Application) -> None:
    book: prices_mod.PriceBook = app["price_book"]
    call_gen: sig.CallGenerator = app["call_gen"]
    start = time.monotonic()

    while True:
        await asyncio.sleep(TICK_INTERVAL_S)

        now = time.monotonic()
        t = now - start
        viewers = len(clients)
        confidence = sig.confidence_for(viewers, t)

        snapshot = book.snapshot()
        call_gen.maybe_reroll(now, snapshot)

        await broadcast({
            "kind": "tick",
            "confidence": round(confidence, 2),
            "viewers": viewers,
            "prices": snapshot,
            "call": {
                "asset": call_gen.asset,
                "direction": call_gen.direction,
                "entry": round(call_gen.entry, 2),
                "target": round(call_gen.target, 2),
            },
            "commentary": call_gen.commentary(confidence),
            "ts": int(time.time() * 1000),
        })


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    clients.add(ws)
    try:
        curve = request.app["equity_curve"]
        sharpe = request.app["sharpe"]
        await ws.send_str(json.dumps({"kind": "backtest", "curve": curve, "sharpe": round(sharpe, 1)}))

        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
            # One-way broadcast feed; anything the client sends is ignored.
    finally:
        clients.discard(ws)
    return ws


async def on_startup(app: web.Application) -> None:
    mock = os.environ.get("MOCK_PRICES") == "1"
    app["price_book"] = prices_mod.PriceBook(mock=mock)
    app["call_gen"] = sig.CallGenerator(reroll_every_s=CALL_REROLL_S, seed=random.randint(0, 1 << 30))

    curve = backtest.generate_equity_curve()
    app["equity_curve"] = curve
    app["sharpe"] = backtest.sharpe_ratio(curve)

    # Best-effort initial fetch so the first page load isn't stuck on
    # fallback numbers; if it fails or the network is unavailable, the
    # page still renders with the seeded fallback and the price loop
    # keeps retrying in the background.
    try:
        async with ClientSession() as session:
            await asyncio.wait_for(app["price_book"].refresh(session), timeout=8)
    except Exception as exc:  # noqa: BLE001
        print(f"initial price fetch failed, serving fallback values: {exc}", file=sys.stderr, flush=True)

    app["price_task"] = asyncio.create_task(price_loop(app))
    app["tick_task"] = asyncio.create_task(tick_loop(app))


def main() -> None:
    static_dir = os.environ.get("STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "static"))
    port = int(os.environ.get("PORT", "8080"))

    app = web.Application()
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/", path=static_dir, show_index=True)
    app.on_startup.append(on_startup)

    print(f"pale moon capital: listening on :{port}, serving {static_dir}", flush=True)
    web.run_app(app, host="0.0.0.0", port=port, print=None)


if __name__ == "__main__":
    main()
