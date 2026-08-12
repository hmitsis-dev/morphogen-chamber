"""A suspiciously smooth fake equity curve.

Generated once at startup from a seeded random walk, then smoothed twice
with a moving average - which is exactly the kind of thing that turns an
ordinary backtest into a Sharpe ratio nobody should trust. The Sharpe
computed below is real arithmetic; the input series is the lie.
"""

from __future__ import annotations

import random
import statistics


def _moving_average(values: list[float], window: int) -> list[float]:
    out = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        out.append(sum(values[lo : i + 1]) / (i - lo + 1))
    return out


def generate_equity_curve(n: int = 120, seed: int = 42) -> list[float]:
    rng = random.Random(seed)
    vals = [100.0]
    for _ in range(n - 1):
        vals.append(vals[-1] * (1 + rng.uniform(-0.004, 0.011)))
    return _moving_average(_moving_average(vals, 5), 5)


def sharpe_ratio(curve: list[float], periods_per_year: int = 252) -> float:
    returns = [(curve[i] / curve[i - 1]) - 1 for i in range(1, len(curve))]
    mean = statistics.fmean(returns)
    stdev = statistics.pstdev(returns)
    if stdev == 0:
        return float("inf")
    return (mean / stdev) * (periods_per_year ** 0.5)
