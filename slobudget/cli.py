"""Command-line interface: ``slo-tracker``.

Wires ingest -> slo/burn math -> report. Fully offline; defaults point at the
bundled sample data so ``slo-tracker report`` works out of the box from the
repo root.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console

from slobudget import __version__, burn, slo as slo_math
from slobudget.ingest import load_series, load_slo
from slobudget.report import render_markdown, render_rich

DEFAULT_DATA = "data/requests_sample.csv"
DEFAULT_SLO = "slo.example.yaml"


@click.group()
@click.version_option(__version__, prog_name="slo-tracker")
def main() -> None:
    """Compute SLO compliance and error-budget burn from request counts."""


@main.command()
@click.option(
    "--data",
    "data_path",
    default=DEFAULT_DATA,
    show_default=True,
    help="CSV of interval,good,total counts.",
)
@click.option(
    "--slo",
    "slo_path",
    default=DEFAULT_SLO,
    show_default=True,
    help="YAML SLO definition (target + window).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["rich", "markdown"]),
    default="rich",
    show_default=True,
    help="Output format.",
)
def report(data_path: str, slo_path: str, fmt: str) -> None:
    """Render a full SLO / error-budget / burn-rate report."""
    try:
        series = load_series(data_path)
        slo_def, windows = load_slo(slo_path)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    status = slo_math.evaluate(slo_def, series)
    results = burn.evaluate_all(slo_def, series, windows)

    if fmt == "markdown":
        click.echo(render_markdown(slo_def, status, results))
    else:
        render_rich(slo_def, status, results, Console())

    # Non-zero exit when a page-severity alert is firing -> CI / cron friendly.
    if any(r.firing and r.window.severity == "page" for r in results):
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
