"""Burn-rate math and multi-window alert firing behaviour."""

import pytest

from slobudget.models import SLO, BurnWindow
from slobudget.burn import (
    DEFAULT_WINDOWS,
    burn_rate,
    error_rate,
    evaluate_all,
    evaluate_window,
    worst_firing,
)


def test_burn_rate_definition():
    # 0.1% budget (99.9% target): a 1.44% error rate is exactly 14.4x burn.
    assert burn_rate(good=9856, total=10000, target=0.999) == pytest.approx(14.4)
    # A burn rate of 1 means error rate == budget rate.
    assert burn_rate(good=999, total=1000, target=0.999) == pytest.approx(1.0)


def test_error_rate_edges():
    assert error_rate(0, 0) == 0.0
    assert error_rate(50, 100) == pytest.approx(0.5)


def test_fast_alert_fires_on_incident(incident_series):
    slo = SLO(name="t", target=0.999, window="30d")
    fast = BurnWindow("fast-critical", "1h", "5m", 14.4, "page")
    result = evaluate_window(slo, incident_series, fast)

    # Last hour is a flat 2.5% error rate => 25x burn on both windows.
    assert result.long_burn_rate == pytest.approx(25.0)
    assert result.short_burn_rate == pytest.approx(25.0)
    assert result.firing is True


def test_fast_alert_quiet_on_healthy(healthy_series):
    slo = SLO(name="t", target=0.999, window="30d")
    results = evaluate_all(slo, healthy_series, DEFAULT_WINDOWS)

    assert all(not r.firing for r in results)
    assert worst_firing(results) is None


def test_incident_pages_but_does_not_falsely_trip_slow_windows(incident_series):
    slo = SLO(name="t", target=0.999, window="30d")
    results = evaluate_all(slo, incident_series, DEFAULT_WINDOWS)
    firing = {r.window.name for r in results if r.firing}

    # The 1-hour burst pages fast-critical; the multi-hour/day windows need the
    # long window to also breach, which a single hour of errors does not.
    assert "fast-critical" in firing
    assert "slow-low" not in firing

    worst = worst_firing(results)
    assert worst is not None
    assert worst.window.severity == "page"


def test_zero_budget_target_is_infinite_burn():
    # Defensive: a 100% target has no budget, so any error is infinite burn.
    assert burn_rate(good=99, total=100, target=1.0) == float("inf")
    assert burn_rate(good=100, total=100, target=1.0) == 0.0
