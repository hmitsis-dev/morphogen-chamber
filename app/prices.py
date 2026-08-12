"""Live market data, with a mock mode for offline development.

Uses CoinGecko's free, keyless simple-price endpoint. Crypto rather than
equities on purpose - no free equities API avoids an API key, and "to the
moon" is exactly the right register of joke for a fund named Pale Moon.
"""

from __future__ import annotations

import random
import time

ASSETS = [
    {"id": "bitcoin", "symbol": "BTC"},
    {"id": "ethereum", "symbol": "ETH"},
    {"id": "solana", "symbol": "SOL"},
]

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

# Used only when no real price has ever been fetched yet (server just
# started, first fetch hasn't landed) so the page has something to show
# immediately instead of a blank screen.
_FALLBACK_SEED = {"bitcoin": 60000.0, "ethereum": 3000.0, "solana": 140.0}


class PriceBook:
    """Holds the latest known price for each asset plus 24h change."""

    def __init__(self, mock: bool = False) -> None:
        self.mock = mock
        self.prices: dict[str, dict] = {
            a["id"]: {"usd": _FALLBACK_SEED[a["id"]], "usd_24h_change": 0.0, "stale": True}
            for a in ASSETS
        }
        self._rng = random.Random(7)
        self._t0 = time.monotonic()

    def snapshot(self) -> dict[str, dict]:
        return {a["symbol"]: self.prices[a["id"]] for a in ASSETS}

    async def refresh(self, session) -> None:
        if self.mock:
            self._refresh_mock()
            return
        ids = ",".join(a["id"] for a in ASSETS)
        params = {"ids": ids, "vs_currencies": "usd", "include_24hr_change": "true"}
        async with session.get(COINGECKO_URL, params=params, timeout=10) as resp:
            resp.raise_for_status()
            data = await resp.json()
        for asset_id, values in data.items():
            if asset_id in self.prices:
                self.prices[asset_id] = {
                    "usd": float(values["usd"]),
                    "usd_24h_change": float(values.get("usd_24h_change", 0.0)),
                    "stale": False,
                }

    def _refresh_mock(self) -> None:
        """Deterministic-ish wandering prices, for local dev without network."""
        t = time.monotonic() - self._t0
        for a in ASSETS:
            base = _FALLBACK_SEED[a["id"]]
            drift = 1 + 0.08 * (0.5 - abs((t * 0.01 + hash(a["id"]) % 10) % 2 - 1))
            noise = 1 + self._rng.uniform(-0.004, 0.004)
            price = base * drift * noise
            change = 100 * (drift * noise - 1)
            self.prices[a["id"]] = {"usd": round(price, 2), "usd_24h_change": round(change, 2), "stale": False}
