import paradox as sig
import backtest


def test_confidence_equals_peak_for_sole_viewer():
    for t in [0, 10, 100, 1000]:
        peak = sig.peak_confidence(t)
        assert abs(sig.confidence_for(1, t) - peak) < 1e-9
        assert abs(sig.confidence_for(0, t) - peak) < 1e-9


def test_confidence_decays_monotonically_with_viewers():
    t = 123.0
    prev = sig.confidence_for(1, t)
    for viewers in range(2, 50):
        cur = sig.confidence_for(viewers, t)
        assert cur < prev, f"confidence should strictly decrease at viewers={viewers}"
        assert cur > 50.0, "confidence should never fall to or below the coin-flip baseline"
        prev = cur


def test_confidence_approaches_fifty_in_the_limit():
    t = 55.0
    c = sig.confidence_for(100_000, t)
    assert abs(c - 50.0) < 0.01


def test_peak_confidence_bounded():
    for t in range(0, 2000, 17):
        p = sig.peak_confidence(t)
        assert 45 <= p <= 100


def test_call_generator_target_direction_consistent():
    gen = sig.CallGenerator(reroll_every_s=0, seed=1)
    prices = {"BTC": {"usd": 60000.0}, "ETH": {"usd": 3000.0}, "SOL": {"usd": 140.0}}
    gen.maybe_reroll(0.0, prices)
    if gen.direction == "LONG":
        assert gen.target > gen.entry
    else:
        assert gen.target < gen.entry


def test_backtest_curve_and_sharpe():
    curve = backtest.generate_equity_curve(n=60, seed=1)
    assert len(curve) == 60
    assert curve[0] > 0
    # Constructed with positive drift and tiny smoothed volatility, so the
    # curve should trend up and produce an absurdly high Sharpe - that's
    # the whole point.
    assert curve[-1] > curve[0]
    sharpe = backtest.sharpe_ratio(curve)
    assert sharpe > 5
