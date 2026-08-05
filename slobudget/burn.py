"""Multi-window, multi-burn-rate alerting.

Burn rate is how fast the error budget is being consumed relative to a
"steady" rate that would exhaust it exactly at the end of the SLO window:

    burn_rate = observed_error_rate / (1 - target)

A burn rate of 1 exhausts the budget exactly over the window; 14.4 exhausts it
in 1/14.4 of the window. Following the Google SRE workbook ("Alerting on SLOs"),
a rule fires only when BOTH a long and a short window exceed the threshold --
the long window gives significance, the short window makes the alert reset
quickly once the incident ends.

Default rules (target-agnostic, from the workbook's 99.9% / 30-day example):

    long   short  factor  budget over window   severity
    1h     5m     14.4    2%   in 1 hour        page
    6h     30m    6       5%   in 6 hours       page
    1d     2h     3       10%  in 1 day         ticket
    3d     6h     1       ~100% over 3 days     ticket
"""

from __future__ import annotations

from typing import List

from slobudget.models import SLO, BurnResult, BurnWindow, IntervalSeries

# The canonical four-rule ladder from the SRE workbook.
DEFAULT_WINDOWS: List[BurnWindow] = [
    BurnWindow("fast-critical", "1h", "5m", 14.4, "page"),
    BurnWindow("fast-high", "6h", "30m", 6.0, "page"),
    BurnWindow("slow-medium", "1d", "2h", 3.0, "ticket"),
    BurnWindow("slow-low", "3d", "6h", 1.0, "ticket"),
]


def error_rate(good: int, total: int) -> float:
    """Observed failure fraction; ``0.0`` for an empty window."""
    if total <= 0:
        return 0.0
    return (total - good) / total


def burn_rate(good: int, total: int, target: float) -> float:
    """Budget burn rate = observed error rate / allowed error rate.

    ``target`` is a fraction in ``(0, 1)``. A perfect target of 1.0 has no
    budget, so any error is an infinite burn -- we clamp to a large sentinel.
    """
    budget_fraction = 1.0 - target
    er = error_rate(good, total)
    if budget_fraction <= 0:
        return float("inf") if er > 0 else 0.0
    return er / budget_fraction


def _tail_burn(series: IntervalSeries, window_seconds: int, target: float):
    """Burn rate over the most-recent ``window_seconds`` of the series.

    Returns ``(burn_rate, n_intervals_used)``. Windows longer than the
    available data fall back to all available intervals.
    """
    interval = series.interval_seconds or window_seconds
    n = max(1, round(window_seconds / interval))
    n = min(n, len(series.frame))
    tail = series.frame.tail(n)
    good = int(tail["good"].sum())
    total = int(tail["total"].sum())
    return burn_rate(good, total, target), n


def evaluate_window(
    slo: SLO, series: IntervalSeries, window: BurnWindow
) -> BurnResult:
    """Evaluate one multi-window rule against the tail of ``series``."""
    long_rate, long_n = _tail_burn(series, window.long_seconds, slo.target)
    short_rate, short_n = _tail_burn(series, window.short_seconds, slo.target)
    firing = long_rate >= window.threshold and short_rate >= window.threshold
    return BurnResult(
        window=window,
        long_burn_rate=long_rate,
        short_burn_rate=short_rate,
        long_intervals=long_n,
        short_intervals=short_n,
        firing=firing,
    )


def evaluate_all(
    slo: SLO, series: IntervalSeries, windows: List[BurnWindow] | None = None
) -> List[BurnResult]:
    """Evaluate every rule (defaults to :data:`DEFAULT_WINDOWS`)."""
    windows = windows if windows is not None else DEFAULT_WINDOWS
    return [evaluate_window(slo, series, w) for w in windows]


def worst_firing(results: List[BurnResult]) -> BurnResult | None:
    """Return the firing rule with the highest burn rate, or ``None`` if quiet."""
    firing = [r for r in results if r.firing]
    if not firing:
        return None
    return max(firing, key=lambda r: r.long_burn_rate)
