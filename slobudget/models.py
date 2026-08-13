"""Core data models for SLOs, request series, budgets and burn-rate results.

These are intentionally thin, immutable value objects. All the math lives in
:mod:`slobudget.slo` and :mod:`slobudget.burn`; keeping the models dumb makes
the numeric code easy to unit-test in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


def parse_duration(text: str) -> int:
    """Parse a compact duration string (e.g. ``"5m"``, ``"1h"``, ``"3d"``) to seconds.

    Supported units: ``s`` (seconds), ``m`` (minutes), ``h`` (hours), ``d`` (days).
    Raises ``ValueError`` on anything else so bad config fails loudly.
    """
    text = str(text).strip().lower()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if not text or text[-1] not in units:
        raise ValueError(f"Unrecognised duration: {text!r} (use e.g. 5m, 1h, 3d)")
    try:
        value = float(text[:-1])
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unrecognised duration: {text!r}") from exc
    if value <= 0:
        raise ValueError(f"Duration must be positive: {text!r}")
    return int(value * units[text[-1]])


@dataclass(frozen=True)
class SLO:
    """A Service Level Objective definition.

    Attributes:
        name:   Human-readable objective name.
        target: Objective as a fraction in ``(0, 1)`` -- e.g. ``0.999`` for 99.9%.
        window: Rolling compliance window as a duration string (e.g. ``"30d"``).
        description: Optional free text describing what is measured.
    """

    name: str
    target: float
    window: str = "30d"
    description: str = ""

    def __post_init__(self) -> None:
        if not 0.0 < self.target < 1.0:
            raise ValueError(
                f"SLO target must be a fraction in (0, 1), got {self.target!r}"
            )

    @property
    def target_pct(self) -> float:
        """Target expressed as a percentage (e.g. ``99.9``)."""
        return self.target * 100.0

    @property
    def error_budget_fraction(self) -> float:
        """Fraction of requests allowed to fail, i.e. ``1 - target``."""
        return 1.0 - self.target

    @property
    def window_seconds(self) -> int:
        return parse_duration(self.window)


@dataclass(frozen=True)
class IntervalSeries:
    """A tidy time-series of good/total request counts per interval.

    Wraps a pandas frame with columns ``interval`` (datetime), ``good`` and
    ``total`` (ints). The frame is assumed sorted ascending by ``interval``.
    """

    frame: pd.DataFrame

    @property
    def good(self) -> int:
        return int(self.frame["good"].sum())

    @property
    def total(self) -> int:
        return int(self.frame["total"].sum())

    @property
    def bad(self) -> int:
        return self.total - self.good

    @property
    def interval_seconds(self) -> int:
        """Detected sampling period, from the median gap between intervals."""
        if len(self.frame) < 2:
            return 0
        deltas = self.frame["interval"].diff().dropna()
        return int(deltas.dt.total_seconds().median())


@dataclass(frozen=True)
class BudgetStatus:
    """The outcome of evaluating an :class:`SLO` over an :class:`IntervalSeries`."""

    target: float
    total_requests: int
    good_requests: int
    bad_requests: int
    sli: float
    error_budget: float
    budget_consumed: float
    budget_remaining: float
    consumed_fraction: float
    remaining_fraction: float

    @property
    def is_met(self) -> bool:
        """True when the achieved SLI is at or above the target."""
        return self.sli >= self.target

    @property
    def is_exhausted(self) -> bool:
        """True once consumed failures meet or exceed the allowed budget.

        Requires actual traffic: a zero-traffic window has no failures and a
        fully-intact budget, so it is *not* exhausted even though its absolute
        ``budget_remaining`` is ``0`` (there were ``0`` allowed failures).
        """
        return self.total_requests > 0 and self.budget_remaining <= 0


@dataclass(frozen=True)
class BurnWindow:
    """A single multi-window burn-rate alert rule (Google SRE workbook style).

    A rule fires only when *both* the long and short windows exceed ``threshold``,
    which suppresses flapping once an incident is over.
    """

    name: str
    long_window: str
    short_window: str
    threshold: float
    severity: str = "page"

    @property
    def long_seconds(self) -> int:
        return parse_duration(self.long_window)

    @property
    def short_seconds(self) -> int:
        return parse_duration(self.short_window)


@dataclass(frozen=True)
class BurnResult:
    """Evaluation of a :class:`BurnWindow` against the tail of a series."""

    window: BurnWindow
    long_burn_rate: float
    short_burn_rate: float
    long_intervals: int
    short_intervals: int
    firing: bool = field(default=False)

    @property
    def budget_consumed_pct_per_hour(self) -> float:
        """Share of the total error budget burned per hour at the long-window rate."""
        return self.long_burn_rate * 100.0 / 720.0  # 720h in a 30d budget window
