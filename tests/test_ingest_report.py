"""Ingest validation and report rendering on the bundled sample data."""

from pathlib import Path

import pytest

from slobudget import burn, slo as slo_math
from slobudget.ingest import load_series, load_slo
from slobudget.report import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = REPO_ROOT / "data" / "requests_sample.csv"
SAMPLE_SLO = REPO_ROOT / "slo.example.yaml"


def test_load_sample_series():
    series = load_series(SAMPLE_CSV)
    assert len(series.frame) == 864
    assert series.interval_seconds == 300  # 5-minute intervals
    assert series.total == 864_000
    assert series.good < series.total


def test_load_sample_slo():
    slo, windows = load_slo(SAMPLE_SLO)
    assert slo.target == pytest.approx(0.999)
    assert slo.window == "30d"
    assert windows is not None and len(windows) == 4


def test_missing_column_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("interval,good\n2026-07-01T00:00:00Z,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required column"):
        load_series(bad)


def test_good_gt_total_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "interval,good,total\n2026-07-01T00:00:00Z,20,10\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="good > total"):
        load_series(bad)


def test_end_to_end_markdown_report_reflects_alert():
    series = load_series(SAMPLE_CSV)
    slo, windows = load_slo(SAMPLE_SLO)
    status = slo_math.evaluate(slo, series)
    results = burn.evaluate_all(slo, series, windows)

    md = render_markdown(slo, status, results)
    assert "# SLO report: checkout-api-availability" in md
    assert "FIRING" in md  # the sample tail trips fast-critical
    assert status.is_met  # ... yet overall budget is still intact
