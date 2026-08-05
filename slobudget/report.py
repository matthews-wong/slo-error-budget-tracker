"""Rendering: a rich terminal report and an equivalent Markdown report.

Both consume the same computed :class:`BudgetStatus` and list of
:class:`BurnResult`, so the two renderers never drift in their numbers.
"""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from slobudget.models import SLO, BudgetStatus, BurnResult


def _fmt_pct(fraction: float, digits: int = 4) -> str:
    return f"{fraction * 100:.{digits}f}%"


def _budget_headline(slo: SLO, status: BudgetStatus) -> str:
    verb = "MET" if status.is_met else "MISSED"
    return (
        f"SLO '{slo.name}' target {_fmt_pct(slo.target)} over {slo.window} -> {verb}"
    )


def render_rich(
    slo: SLO, status: BudgetStatus, results: List[BurnResult], console: Console
) -> None:
    """Print the full report to a rich ``Console``."""
    met_style = "bold green" if status.is_met else "bold red"
    console.print(
        Panel(
            Text(_budget_headline(slo, status), style=met_style),
            title="SLO / Error Budget",
            expand=False,
        )
    )

    budget = Table(title="Error Budget", show_header=True, header_style="bold cyan")
    budget.add_column("Metric")
    budget.add_column("Value", justify="right")
    budget.add_row("Achieved SLI", _fmt_pct(status.sli))
    budget.add_row("Target", _fmt_pct(status.target))
    budget.add_row("Total requests", f"{status.total_requests:,}")
    budget.add_row("Good / Bad", f"{status.good_requests:,} / {status.bad_requests:,}")
    budget.add_row("Error budget (allowed failures)", f"{status.error_budget:,.0f}")
    budget.add_row("Budget consumed", f"{status.budget_consumed:,.0f}")
    budget.add_row("Budget remaining", f"{status.budget_remaining:,.0f}")
    remaining_style = "green" if status.remaining_fraction > 0 else "red"
    budget.add_row(
        "Budget remaining %",
        Text(_fmt_pct(status.remaining_fraction, 2), style=remaining_style),
    )
    console.print(budget)

    burn = Table(
        title="Burn-Rate Alerts (multi-window)",
        show_header=True,
        header_style="bold cyan",
    )
    burn.add_column("Rule")
    burn.add_column("Severity")
    burn.add_column("Long", justify="right")
    burn.add_column("Short", justify="right")
    burn.add_column("Threshold", justify="right")
    burn.add_column("State", justify="center")
    for r in results:
        state = Text("FIRING", style="bold red") if r.firing else Text("ok", style="green")
        burn.add_row(
            r.window.name,
            r.window.severity,
            f"{r.long_burn_rate:.2f}x ({r.window.long_window})",
            f"{r.short_burn_rate:.2f}x ({r.window.short_window})",
            f"{r.window.threshold:g}x",
            state,
        )
    console.print(burn)

    firing = [r for r in results if r.firing]
    if firing:
        worst = max(firing, key=lambda r: r.long_burn_rate)
        console.print(
            Panel(
                Text(
                    f"ALERT: '{worst.window.name}' firing "
                    f"({worst.window.severity}) at {worst.long_burn_rate:.1f}x burn",
                    style="bold white on red",
                ),
                expand=False,
            )
        )
    else:
        console.print(
            Panel(Text("No burn-rate alerts firing.", style="bold green"), expand=False)
        )


def render_markdown(
    slo: SLO, status: BudgetStatus, results: List[BurnResult]
) -> str:
    """Return a Markdown report string (used by ``--format markdown`` and docs)."""
    lines: List[str] = []
    lines.append(f"# SLO report: {slo.name}")
    lines.append("")
    lines.append(f"- **Verdict:** {'MET' if status.is_met else 'MISSED'}")
    lines.append(f"- **Target:** {_fmt_pct(slo.target)} over `{slo.window}`")
    if slo.description:
        lines.append(f"- **Measures:** {slo.description}")
    lines.append("")
    lines.append("## Error budget")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Achieved SLI | {_fmt_pct(status.sli)} |")
    lines.append(f"| Target | {_fmt_pct(status.target)} |")
    lines.append(f"| Total requests | {status.total_requests:,} |")
    lines.append(f"| Good / Bad | {status.good_requests:,} / {status.bad_requests:,} |")
    lines.append(f"| Error budget (allowed failures) | {status.error_budget:,.0f} |")
    lines.append(f"| Budget consumed | {status.budget_consumed:,.0f} |")
    lines.append(f"| Budget remaining | {status.budget_remaining:,.0f} |")
    lines.append(f"| Budget remaining % | {_fmt_pct(status.remaining_fraction, 2)} |")
    lines.append("")
    lines.append("## Burn-rate alerts (multi-window)")
    lines.append("")
    lines.append("| Rule | Severity | Long window | Short window | Threshold | State |")
    lines.append("| --- | --- | ---: | ---: | ---: | :---: |")
    for r in results:
        state = "**FIRING**" if r.firing else "ok"
        lines.append(
            f"| {r.window.name} | {r.window.severity} "
            f"| {r.long_burn_rate:.2f}x ({r.window.long_window}) "
            f"| {r.short_burn_rate:.2f}x ({r.window.short_window}) "
            f"| {r.window.threshold:g}x | {state} |"
        )
    lines.append("")
    firing = [r for r in results if r.firing]
    if firing:
        worst = max(firing, key=lambda r: r.long_burn_rate)
        lines.append(
            f"> **ALERT:** `{worst.window.name}` firing ({worst.window.severity}) "
            f"at {worst.long_burn_rate:.1f}x burn."
        )
    else:
        lines.append("> No burn-rate alerts firing.")
    lines.append("")
    return "\n".join(lines)
