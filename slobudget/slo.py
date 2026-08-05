"""SLI and error-budget math.

Definitions (request-based / count-based SLI):

    SLI              = good / total
    error budget     = (1 - target) * total          # failures we are *allowed*
    budget consumed  = bad                            # failures we actually had
    budget remaining = error budget - bad
    consumed fraction= bad / error budget

These are the count-based formulas from the Google SRE workbook, chapter
"Implementing SLOs". All functions are pure so they are trivial to test.
"""

from __future__ import annotations

from slobudget.models import SLO, BudgetStatus, IntervalSeries


def compute_sli(good: int, total: int) -> float:
    """Achieved SLI as a fraction. Returns ``1.0`` for an empty series."""
    if total <= 0:
        return 1.0
    return good / total


def compute_budget(slo: SLO, good: int, total: int) -> BudgetStatus:
    """Evaluate an :class:`SLO` against aggregate good/total counts.

    The error budget is the *number of failures allowed* over the observed
    traffic: ``(1 - target) * total``. Consuming more than that means the SLO
    is missed and ``budget_remaining`` goes negative.
    """
    good = int(good)
    total = int(total)
    if total < 0 or good < 0 or good > total:
        raise ValueError(
            f"Invalid counts: good={good}, total={total} (need 0 <= good <= total)"
        )

    bad = total - good
    sli = compute_sli(good, total)
    error_budget = slo.error_budget_fraction * total
    budget_remaining = error_budget - bad

    # Guard against a zero-traffic window producing a divide-by-zero.
    consumed_fraction = bad / error_budget if error_budget > 0 else 0.0
    remaining_fraction = 1.0 - consumed_fraction

    return BudgetStatus(
        target=slo.target,
        total_requests=total,
        good_requests=good,
        bad_requests=bad,
        sli=sli,
        error_budget=error_budget,
        budget_consumed=float(bad),
        budget_remaining=budget_remaining,
        consumed_fraction=consumed_fraction,
        remaining_fraction=remaining_fraction,
    )


def evaluate(slo: SLO, series: IntervalSeries) -> BudgetStatus:
    """Convenience wrapper: evaluate an SLO over a whole :class:`IntervalSeries`."""
    return compute_budget(slo, series.good, series.total)
