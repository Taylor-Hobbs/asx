"""Per-field regression view: what a blended accuracy number would have hidden.

    uv run python scripts/viz/regression_report.py --from v3 --to v6
    uv run python scripts/viz/regression_report.py --from v3 --to v6 --fields period

Rows are prompt versions, columns are overall + per-field accuracy, all loaded
from persisted eval_runs rows (per-field tallies included) — nothing hardcoded.
A field column missing from a stored run is simply not rendered. Cells that
fell more than 10pp from the previous version are red; the overall column dims
whenever it moved less than 2pp, so "headline flat, field collapsed" is visible
at a glance. If the full table would exceed the console width, the
least-changed field columns are dropped first (named in the caption).
"""

import argparse
import sys
from pathlib import Path

from rich.table import Table
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent))
from eval_data import EvalRun, load_eval_runs  # noqa: E402
from style import CONSOLE_WIDTH, TABLE_BOX, make_console  # noqa: E402

OVERALL_FLAT_PP = 2.0
FIELD_COLLAPSE_PP = 10.0

# Column-header abbreviations for the known long field names; anything not
# listed falls back to a generic shortening so new fields still render.
ABBREV = {
    "reporting_currency": "curr",
    "revenue.current": "rev.c",
    "revenue.prior": "rev.p",
    "npat.current": "npat.c",
    "npat.prior": "npat.p",
    "eps_cents.current": "eps.c",
    "eps_cents.prior": "eps.p",
    "dividend_cents.current": "div.c",
    "dividend_cents.prior": "div.p",
}


def abbrev(field: str) -> str:
    if field in ABBREV:
        return ABBREV[field]
    return field if len(field) <= 7 else field[:6] + "…"


def parse_version(text: str) -> int:
    return int(text.lstrip("v"))


def pick_series(runs: list[EvalRun], lo: int, hi: int) -> list[EvalRun]:
    """One model's runs across the range — the model with the most versions wins."""
    in_range = [r for r in runs if lo <= r.version_number <= hi]
    by_model: dict[str, list[EvalRun]] = {}
    for run in in_range:
        by_model.setdefault(run.model, []).append(run)
    if not by_model:
        return []
    model = max(by_model, key=lambda m: len(by_model[m]))
    return sorted(by_model[model], key=lambda r: r.version_number)


def field_accuracy(run: EvalRun, field: str) -> float | None:
    for score in run.field_scores:
        if score.field == field:
            return score.accuracy
    return None


def max_move(series: list[EvalRun], field: str) -> float:
    """Largest absolute version-to-version move for a field — the drop ranking."""
    moves = []
    for prev, cur in zip(series, series[1:], strict=False):
        a, b = field_accuracy(prev, field), field_accuracy(cur, field)
        if a is not None and b is not None:
            moves.append(abs(b - a))
    return max(moves, default=0.0)


def build_table(series: list[EvalRun], fields: list[str], dropped: list[str]) -> Table:
    caption = (
        f"{series[0].model} · golden dataset {series[0].dataset_version}"
        " · per-field tallies from persisted eval_runs records"
    )
    if dropped:
        caption += f" · dropped (least changed): {', '.join(abbrev(f) for f in dropped)}"
    table = Table(
        title="Earnings extraction — per-field accuracy by prompt version",
        caption=caption,
        box=TABLE_BOX,
        header_style="accent",
        title_style="accent",
        caption_style="muted",
    )
    table.add_column("ver", justify="left")
    table.add_column("overall", justify="right")
    for field in fields:
        table.add_column(abbrev(field), justify="right")

    for i, run in enumerate(series):
        prev = series[i - 1] if i > 0 else None
        cells: list[Text] = [Text(run.version_label)]

        overall = run.overall_accuracy
        overall_style = ""
        if prev is not None and overall is not None and prev.overall_accuracy is not None:
            if abs(overall - prev.overall_accuracy) * 100 < OVERALL_FLAT_PP:
                overall_style = "flat"
        cells.append(Text("" if overall is None else f"{overall * 100:.1f}%", style=overall_style))

        for field in fields:
            acc = field_accuracy(run, field)
            if acc is None:
                cells.append(Text("", style="muted"))
                continue
            style = ""
            if prev is not None:
                prior = field_accuracy(prev, field)
                if prior is not None and (acc - prior) * 100 < -FIELD_COLLAPSE_PP:
                    style = "regression"
            cells.append(Text(f"{acc * 100:.1f}%", style=style))
        table.add_row(*cells)
    return table


def findings(series: list[EvalRun], fields: list[str]) -> list[Text]:
    """Versions where overall stayed flat while at least one field moved >10pp."""
    lines: list[Text] = []
    for prev, cur in zip(series, series[1:], strict=False):
        if prev.overall_accuracy is None or cur.overall_accuracy is None:
            continue
        overall_move = (cur.overall_accuracy - prev.overall_accuracy) * 100
        if abs(overall_move) >= OVERALL_FLAT_PP:
            continue
        for field in fields:
            a, b = field_accuracy(prev, field), field_accuracy(cur, field)
            if a is None or b is None:
                continue
            move = (b - a) * 100
            if abs(move) <= FIELD_COLLAPSE_PP:
                continue
            verb = "fell" if move < 0 else "rose"
            line = Text("  ")
            line.append(f"{cur.version_label}: ", style="champion")
            line.append(
                f"overall flat ({prev.overall_accuracy * 100:.1f}% → "
                f"{cur.overall_accuracy * 100:.1f}%, {overall_move:+.1f}pp) while "
            )
            line.append(f"{field} {verb} ", style="champion")
            line.append(
                f"{a * 100:.1f}% → {b * 100:.1f}% ({move:+.1f}pp)",
                style="regression" if move < 0 else "gain",
            )
            lines.append(line)
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_v", required=True, help="first version, e.g. v3")
    parser.add_argument("--to", dest="to_v", required=True, help="last version, e.g. v6")
    parser.add_argument(
        "--fields", default=None, help="comma-separated field subset (full names or substrings)"
    )
    args = parser.parse_args()

    console = make_console()
    lo, hi = parse_version(args.from_v), parse_version(args.to_v)
    series = pick_series(load_eval_runs("earnings"), lo, hi)
    if not series:
        console.print(f"no eval_runs rows for earnings v{lo}..v{hi}", style="regression")
        raise SystemExit(1)

    # Canonical column order comes from the last run's stored field_scores.
    all_fields = [s.field for s in series[-1].field_scores]
    if args.fields:
        wanted = [w.strip().lower() for w in args.fields.split(",")]
        all_fields = [f for f in all_fields if any(w in f.lower() for w in wanted)]

    # Fit 100 columns by dropping the least-changed fields, never by wrapping
    # or squeezing. measure() clamps to the console width, so measure against
    # an effectively unbounded width to learn the table's natural size.
    unbounded = console.options.update_width(10_000)
    fields = list(all_fields)
    dropped: list[str] = []
    while fields:
        table = build_table(series, fields, dropped)
        if table.__rich_measure__(console, unbounded).maximum <= CONSOLE_WIDTH:
            break
        quietest = min(fields, key=lambda f: max_move(series, f))
        fields.remove(quietest)
        dropped.append(quietest)

    console.print()
    console.print(table)
    console.print()
    found = findings(series, all_fields)
    header = Text("FINDINGS", style="accent")
    header.append(" — flat overall, collapsed field (computed from eval_runs)", style="muted")
    console.print(header)
    if found:
        for line in found:
            console.print(line)
    else:
        console.print("  none in this range", style="muted")
    console.print()


if __name__ == "__main__":
    main()
