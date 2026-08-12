"""The actual joke, expressed as math.

The Grossman-Stiglitz paradox: if markets were perfectly efficient, no one
could profit from gathering information, so no one would bother gathering
it, so markets couldn't stay efficient. Private information has value
precisely because it's private. Once everyone can see it, the edge is gone.

So: this terminal publishes a live "alpha signal" whose confidence starts
high when you're the only one looking, and decays toward 50% (a coin flip)
as more people load the page. Not a metaphor - literally computed from the
live viewer count.
"""

from __future__ import annotations

import math
import random
import time

# How aggressively confidence collapses per additional viewer. Higher =
# faster decay. Tuned so 2-3 viewers already feels the erosion, and it's
# clearly a coin flip (>=~50.5%) by a dozen or so.
DECAY_K = 0.4


def peak_confidence(t: float) -> float:
    """The confidence a *sole* observer would see: a slow, multi-frequency
    drift so it feels alive rather than static, bounded to roughly 52-94%."""
    return 73 + 16 * math.sin(t * 0.021) + 6 * math.sin(t * 0.083 + 1.3)


def confidence_for(viewers: int, t: float) -> float:
    """Confidence collapses toward 50% (random-walk baseline) as viewers
    grow. The first viewer pays no penalty - information is only "public"
    once someone else is also looking."""
    peak = peak_confidence(t)
    others = max(0, viewers - 1)
    decay = 1.0 / (1.0 + DECAY_K * others)
    return 50.0 + (peak - 50.0) * decay


ADJECTIVES = [
    "asymmetric", "convex", "idiosyncratic", "non-linear", "regime-dependent",
    "mean-reverting", "structurally mispriced", "de-correlated",
    "path-dependent", "reflexive",
]
NOUNS = [
    "alpha", "gamma exposure", "order flow imbalance", "microstructure noise",
    "tail risk", "carry", "a liquidity pocket", "beta decay",
    "vol surface skew", "basis risk",
]
MACRO = [
    "quantitative tightening", "a risk-on rotation", "yield curve dynamics",
    "a cross-asset correlation breakdown", "flight to quality",
    "a momentum unwind", "central bank forward guidance",
    "a positioning washout",
]
STATUS_HIGH = [
    "conviction elevated", "thesis intact", "high signal-to-noise",
    "edge confirmed (allegedly)",
]
STATUS_MID = [
    "thesis under review", "moderate conviction",
    "signal-to-noise deteriorating", "proceeding with caution",
]
STATUS_LOW = [
    "edge compressing toward zero", "signal indistinguishable from noise",
    "thesis effectively random at this point",
    "confidence approaching coin-flip territory",
]


def status_for(confidence: float, rng: random.Random) -> str:
    if confidence > 75:
        return rng.choice(STATUS_HIGH)
    if confidence > 58:
        return rng.choice(STATUS_MID)
    return rng.choice(STATUS_LOW)


def commentary(symbol: str, confidence: float, rng: random.Random) -> str:
    adj = rng.choice(ADJECTIVES)
    noun = rng.choice(NOUNS)
    macro = rng.choice(MACRO)
    status = status_for(confidence, rng)
    return f"{symbol} exhibiting {adj} {noun} amid {macro} — {status}."


class CallGenerator:
    """The fake trade idea currently being "published". Rerolls itself on
    a slow interval so it feels like a running desk, not a static banner."""

    def __init__(self, reroll_every_s: float = 75.0, seed: int | None = None) -> None:
        self.reroll_every_s = reroll_every_s
        self._rng = random.Random(seed)
        self._last_roll = -math.inf
        self.asset = "BTC"
        self.direction = "LONG"
        self.entry = 0.0
        self.target = 0.0

    def maybe_reroll(self, now_monotonic: float, prices: dict[str, dict]) -> None:
        if now_monotonic - self._last_roll < self.reroll_every_s:
            return
        self._last_roll = now_monotonic
        self.asset = self._rng.choice(list(prices.keys()))
        self.direction = self._rng.choice(["LONG", "SHORT"])
        entry = prices[self.asset]["usd"]
        move = self._rng.uniform(0.02, 0.09)
        sign = 1 if self.direction == "LONG" else -1
        self.entry = entry
        self.target = entry * (1 + sign * move)

    def commentary(self, confidence: float) -> str:
        return commentary(self.asset, confidence, self._rng)
