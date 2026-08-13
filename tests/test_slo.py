"""Budget math on known inputs -- every number here is hand-verifiable."""

import math

import pytest

from slobudget.models import SLO
from slobudget.slo import compute_budget, compute_sli


def test_sli_basic():
    assert compute_sli(999, 1000) == pytest.approx(0.999)
    assert compute_sli(0, 0) == 1.0  # empty window is vacuously perfect


def test_budget_partially_consumed():
    # 99% target over 10_000 requests => budget = 0.01 * 10000 = 100 allowed fails.
    slo = SLO(name="t", target=0.99, window="30d")
    status = compute_budget(slo, good=9_960, total=10_000)

    assert status.bad_requests == 40
    assert status.error_budget == pytest.approx(100.0)
    assert status.budget_consumed == pytest.approx(40.0)
    assert status.budget_remaining == pytest.approx(60.0)
    assert status.consumed_fraction == pytest.approx(0.40)
    assert status.remaining_fraction == pytest.approx(0.60)
    assert status.is_met is True  # SLI 99.6% >= 99% target


def test_budget_exhausted_when_slo_missed():
    # 99.9% over 100_000 => budget = 100 fails; 250 fails overspends the budget.
    slo = SLO(name="t", target=0.999, window="30d")
    status = compute_budget(slo, good=99_750, total=100_000)

    assert status.error_budget == pytest.approx(100.0)
    assert status.budget_remaining == pytest.approx(-150.0)
    assert status.is_met is False
    assert status.is_exhausted is True
    assert status.consumed_fraction == pytest.approx(2.5)


def test_sample_style_numbers(incident_series):
    # Mirrors the bundled sample: 300k total, budget intact despite a tail burst.
    slo = SLO(name="t", target=0.999, window="30d")
    status = compute_budget(slo, incident_series.good, incident_series.total)
    assert status.is_met is True
    assert 0 < status.remaining_fraction < 1
    assert math.isclose(
        status.error_budget, 0.001 * status.total_requests, rel_tol=1e-9
    )


def test_zero_traffic_window_is_not_exhausted():
    # A window with no traffic has no failures and a fully-intact budget.
    # The status must be internally consistent: 100% remaining => NOT exhausted.
    slo = SLO(name="t", target=0.999, window="30d")
    status = compute_budget(slo, good=0, total=0)

    assert status.total_requests == 0
    assert status.bad_requests == 0
    assert status.error_budget == pytest.approx(0.0)
    assert status.consumed_fraction == pytest.approx(0.0)
    assert status.remaining_fraction == pytest.approx(1.0)
    assert status.is_met is True
    # Regression: zero traffic previously reported the budget as exhausted
    # (budget_remaining == 0 <= 0) while also reporting 100% remaining.
    assert status.is_exhausted is False


def test_budget_exactly_exhausted_boundary():
    # bad == error budget: the budget is spent to the last allowed failure.
    # target 0.5 keeps every value exact in floating point, so the boundary is
    # crisp: budget = 0.5 * 100 = 50 allowed fails, and exactly 50 fail.
    slo = SLO(name="t", target=0.5, window="30d")
    status = compute_budget(slo, good=50, total=100)

    assert status.bad_requests == 50
    assert status.error_budget == pytest.approx(50.0)
    assert status.budget_remaining == pytest.approx(0.0)
    assert status.consumed_fraction == pytest.approx(1.0)
    assert status.remaining_fraction == pytest.approx(0.0)
    assert status.sli == pytest.approx(slo.target)
    assert status.is_met is True  # sli >= target (boundary is inclusive)
    assert status.is_exhausted is True  # zero budget left == exhausted


def test_invalid_counts_raise():
    slo = SLO(name="t", target=0.99)
    with pytest.raises(ValueError):
        compute_budget(slo, good=10, total=5)


def test_invalid_target_rejected():
    with pytest.raises(ValueError):
        SLO(name="bad", target=1.5)
    with pytest.raises(ValueError):
        SLO(name="bad", target=0.0)
