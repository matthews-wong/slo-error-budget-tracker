"""Load good/total request counts per interval from CSV, and SLOs from YAML.

Expected CSV columns (header required):

    interval,good,total

``interval`` is any pandas-parseable timestamp. ``good`` and ``total`` are
non-negative integers with ``good <= total``. Rows are sorted ascending by
interval so the burn-rate "tail" windows are well defined.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from slobudget.models import SLO, BurnWindow, IntervalSeries

REQUIRED_COLUMNS = ("interval", "good", "total")


def load_series(path: str | Path) -> IntervalSeries:
    """Read a request-count CSV into a validated :class:`IntervalSeries`."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Request CSV not found: {path}")

    frame = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"CSV {path} missing required column(s): {', '.join(missing)}"
        )

    frame = frame[list(REQUIRED_COLUMNS)].copy()
    frame["interval"] = pd.to_datetime(frame["interval"], utc=True)
    frame["good"] = frame["good"].astype(int)
    frame["total"] = frame["total"].astype(int)

    if (frame["good"] < 0).any() or (frame["total"] < 0).any():
        raise ValueError(f"CSV {path} has negative counts")
    if (frame["good"] > frame["total"]).any():
        raise ValueError(f"CSV {path} has rows where good > total")

    frame = frame.sort_values("interval").reset_index(drop=True)
    return IntervalSeries(frame=frame)


def load_slo(path: str | Path) -> tuple[SLO, list[BurnWindow] | None]:
    """Load an SLO definition (and optional burn windows) from YAML.

    Returns ``(slo, windows)`` where ``windows`` is ``None`` when the file
    does not override the default burn-rate ladder.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"SLO YAML not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    slo = SLO(
        name=data.get("name", "unnamed-slo"),
        target=float(data["target"]),
        window=str(data.get("window", "30d")),
        description=data.get("description", ""),
    )

    windows = None
    if data.get("burn_windows"):
        windows = [
            BurnWindow(
                name=w["name"],
                long_window=str(w["long"]),
                short_window=str(w["short"]),
                threshold=float(w["threshold"]),
                severity=w.get("severity", "page"),
            )
            for w in data["burn_windows"]
        ]

    return slo, windows
