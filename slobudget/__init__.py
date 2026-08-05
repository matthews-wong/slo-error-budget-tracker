"""slobudget - compute SLO compliance and error-budget burn from request counts.

Public entry points:
    - :mod:`slobudget.slo`     -- SLI and error-budget math
    - :mod:`slobudget.burn`    -- multi-window burn-rate alerting
    - :mod:`slobudget.ingest`  -- load good/total counts from CSV
    - :mod:`slobudget.report`  -- rich + Markdown reporting
"""

from slobudget.models import (
    SLO,
    BudgetStatus,
    BurnResult,
    BurnWindow,
    IntervalSeries,
)

__all__ = [
    "SLO",
    "BudgetStatus",
    "BurnResult",
    "BurnWindow",
    "IntervalSeries",
    "__version__",
]

__version__ = "0.1.0"
