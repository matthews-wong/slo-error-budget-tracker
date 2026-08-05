"""Shared fixtures: small hand-built series with known-good arithmetic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from slobudget.models import IntervalSeries


def make_series(bad_per_interval, total_per_interval=1000, minutes=5):
    """Build an :class:`IntervalSeries` from a list of per-interval bad counts."""
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    rows = []
    for i, bad in enumerate(bad_per_interval):
        rows.append(
            {
                "interval": start + timedelta(minutes=minutes * i),
                "good": total_per_interval - bad,
                "total": total_per_interval,
            }
        )
    frame = pd.DataFrame(rows)
    return IntervalSeries(frame=frame)


@pytest.fixture
def healthy_series():
    """864 intervals (3 days) at a light error trickle -- well within budget."""
    bad = [1 if i % 20 == 0 else 0 for i in range(864)]
    return make_series(bad)


@pytest.fixture
def incident_series():
    """Mirrors the bundled sample: ~3 days healthy, then a 1-hour (12 x 5m)
    burst at 2.5% errors at the tail. Budget stays intact overall, but the
    tail trips the fast-critical burn-rate window."""
    bad = [1 if i % 20 == 0 else 0 for i in range(852)]
    bad += [25] * 12  # 25/1000 = 2.5% -> 25x burn vs a 0.1% budget
    return make_series(bad)
