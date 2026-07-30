"""Bulk extraction cost per vertical, from logged token usage.

    uv run python scripts/viz/cost_report.py
    uv run python scripts/viz/cost_report.py --compare-model claude-opus-4-8 \\
        --compare-price-in 2.50 --compare-price-out 12.50

Token counts are the recorded artifact: every extraction job logs one
`extract.stored` / `extract.3y.stored` line per document with input_tokens and
output_tokens (structlog, extract_*.log in the repo root). BigQuery does not
persist usage, so these logs are the source. Prices are NOT recorded anywhere,
so spend is necessarily tokens × stated rates — the rates are printed with the
table so the arithmetic is auditable from the screenshot. Verticals with no
logged token data (roles, guidance; capital raises never had an extraction
vertical) are omitted, not estimated.

Exact-duplicate lines (same document, same token counts) are collapsed — they
are batch-result refetches after a crash, not separate billed calls. The same
document extracted under different prompt versions has different token counts
and is kept: each of those calls was billed.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from rich.table import Table
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent))
from style import TABLE_BOX, make_console  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

# claude-haiku-4-5 Batch API rates (50% of $1.00/$5.00 per MTok list price),
# the model and API every bulk job used. Overridable so the assumption is a
# flag, not a constant buried in code.
DEFAULT_PRICE_IN = 0.50
DEFAULT_PRICE_OUT = 2.50
DEFAULT_MODEL = "claude-haiku-4-5 (Batch API)"

# structlog sorts kwargs alphabetically, so other fields (npat=, period=, …)
# can sit between input_tokens and output_tokens — hence the lazy gaps.
STORED_LINE = re.compile(
    r"\b(?P<event>extract\.(?:3y\.)?stored)\b.*?"
    r"content_hash=(?P<hash>[0-9a-f]{8,}).*?"
    r"input_tokens=(?P<inp>\d+).*?output_tokens=(?P<out>\d+)"
)

VERTICAL_BY_EVENT = {
    "extract.stored": "company results (earnings)",
    "extract.3y.stored": "director trades (3Y)",
}

# Verticals a reader might expect that have no persisted token data — named
# explicitly so their absence reads as a fact, not an oversight.
ABSENT = (
    "director roles — extraction ran but its job logged no token counts",
    "guidance — not yet extracted",
    "capital raises — never an extraction vertical (headline-index only)",
)


def read_log(path: Path) -> str:
    """Logs come from two writers: structlog direct (UTF-8) and PowerShell
    redirection (UTF-16 with BOM, e.g. extract_asx300.log). Decode either."""
    data = path.read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in data[:200]:
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def load_usage() -> tuple[dict[str, set[tuple[str, int, int]]], int, int]:
    """Per-vertical sets of (content_hash, in, out) billed calls, from the logs."""
    calls: dict[str, set[tuple[str, int, int]]] = defaultdict(set)
    files = 0
    lines = 0
    for path in sorted(REPO_ROOT.glob("extract_*.log")):
        if path.name.endswith(".err.log"):
            continue
        files += 1
        for line in read_log(path).splitlines():
            match = STORED_LINE.search(line)
            if match is None:
                continue
            lines += 1
            vertical = VERTICAL_BY_EVENT[match["event"]]
            calls[vertical].add((match["hash"], int(match["inp"]), int(match["out"])))
    return calls, files, lines


def build_table(
    calls: dict[str, set[tuple[str, int, int]]], price_in: float, price_out: float
) -> Table:
    table = Table(
        title="Bulk extraction cost by vertical",
        caption="token counts from extract_*.log job records · spend = tokens × stated rates",
        box=TABLE_BOX,
        header_style="accent",
        title_style="accent",
        caption_style="muted",
    )
    table.add_column("vertical", justify="left")
    table.add_column("documents", justify="right")
    table.add_column("input tokens", justify="right")
    table.add_column("output tokens", justify="right")
    table.add_column("total spend", justify="right")
    table.add_column("cost / document", justify="right")

    total_docs = total_in = total_out = 0
    for vertical in sorted(calls):
        rows = calls[vertical]
        docs = len({h for h, _, _ in rows})
        tokens_in = sum(i for _, i, _ in rows)
        tokens_out = sum(o for _, _, o in rows)
        spend = tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out
        table.add_row(
            vertical,
            f"{docs:,}",
            f"{tokens_in:,}",
            f"{tokens_out:,}",
            f"${spend:,.2f}",
            f"${spend / docs:,.4f}",
        )
        total_docs += docs
        total_in += tokens_in
        total_out += tokens_out

    total_spend = total_in / 1e6 * price_in + total_out / 1e6 * price_out
    table.add_section()
    table.add_row(
        Text("TOTAL", style="champion"),
        Text(f"{total_docs:,}", style="champion"),
        Text(f"{total_in:,}", style="champion"),
        Text(f"{total_out:,}", style="champion"),
        Text(f"${total_spend:,.2f}", style="champion"),
        Text(f"${total_spend / total_docs:,.4f}", style="champion"),
    )
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model label for the rate line")
    parser.add_argument("--price-in", type=float, default=DEFAULT_PRICE_IN, help="$/MTok input")
    parser.add_argument("--price-out", type=float, default=DEFAULT_PRICE_OUT, help="$/MTok output")
    parser.add_argument("--compare-model", default=None, help="model name for the projection")
    parser.add_argument("--compare-price-in", type=float, default=None, help="$/MTok input")
    parser.add_argument("--compare-price-out", type=float, default=None, help="$/MTok output")
    args = parser.parse_args()
    compare_args = (args.compare_model, args.compare_price_in, args.compare_price_out)
    if any(a is not None for a in compare_args) and None in compare_args:
        parser.error("--compare-model, --compare-price-in and --compare-price-out go together")

    console = make_console()
    calls, files, lines = load_usage()
    if not calls:
        console.print("no extract_*.log files with token records found", style="regression")
        raise SystemExit(1)

    console.print()
    console.print(build_table(calls, args.price_in, args.price_out))

    rates = Text("  rates: ", style="muted")
    rates.append(f"{args.model} — input ${args.price_in:.2f}/MTok, ", style="muted")
    rates.append(f"output ${args.price_out:.2f}/MTok", style="muted")
    billed = sum(len(rows) for rows in calls.values())
    rates.append(
        f" · source: {files} log files, {lines:,} usage lines → {billed:,} billed calls",
        style="muted",
    )
    console.print(rates)
    for note in ABSENT:
        console.print(f"  not shown: {note}", style="muted")

    if args.compare_model is not None:
        total_in = sum(i for rows in calls.values() for _, i, _ in rows)
        total_out = sum(o for rows in calls.values() for _, _, o in rows)
        actual = total_in / 1e6 * args.price_in + total_out / 1e6 * args.price_out
        projected = total_in / 1e6 * args.compare_price_in + (
            total_out / 1e6 * args.compare_price_out
        )
        console.print()
        line = Text("  ESTIMATED", style="warning")
        line.append(
            f" — the same token volume on {args.compare_model} at "
            f"${args.compare_price_in:.2f}/MTok in, ${args.compare_price_out:.2f}/MTok out "
            f"would have cost ",
        )
        line.append(f"~${projected:,.2f}", style="champion")
        line.append(f"  ({projected / actual:,.1f}× the ${actual:,.2f} computed above)")
        console.print(line)
        console.print("  this is a projection at stated prices, not a measured cost", style="muted")
    console.print()


if __name__ == "__main__":
    main()
