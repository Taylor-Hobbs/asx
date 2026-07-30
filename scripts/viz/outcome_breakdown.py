"""Four-outcome breakdown for one prompt version — not just right/wrong.

    uv run python scripts/viz/outcome_breakdown.py --version v7
    uv run python scripts/viz/outcome_breakdown.py --version v3 --vertical director_trades
    uv run python scripts/viz/outcome_breakdown.py --version v7 --sort hallucinated

Every count comes from the stored eval_runs row for the requested version.
The point of the view: a MISSING value (the document stated it, the model
returned null) and a HALLUCINATED value (the document did not state it, the
model invented one) are different failures with different fixes, and the
harness scores them separately. Hallucinations are red whenever above zero;
missing is amber; weakest fields sort to the top.
"""

import argparse
import sys
from pathlib import Path

from rich.table import Table
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent))
from eval_data import EvalRun, FieldScore, load_eval_runs  # noqa: E402
from style import TABLE_BOX, make_console  # noqa: E402


def pick_run(runs: list[EvalRun], version: int, model: str | None) -> EvalRun | None:
    candidates = [r for r in runs if r.version_number == version]
    if model is not None:
        candidates = [r for r in candidates if r.model == model]
    if not candidates:
        return None
    # Same version can exist for more than one model — take the latest run.
    return max(candidates, key=lambda r: r.evaluated_at)


def accuracy_cell(score: FieldScore) -> Text:
    if score.accuracy is None:
        return Text("", style="muted")
    style = "gain_dim" if score.accuracy > 0.90 else ""
    return Text(f"{score.accuracy * 100:.1f}%", style=style)


def build_table(run: EvalRun, sort: str) -> Table:
    table = Table(
        title=f"{run.prompt_version} — per-field outcomes ({run.model})",
        caption=(
            f"golden dataset {run.dataset_version} · {run.n_documents} documents · "
            "missing = value stated but not extracted · "
            "hallucinated = value invented where the document stated none"
        ),
        box=TABLE_BOX,
        header_style="accent",
        title_style="accent",
        caption_style="muted",
    )
    table.add_column("field", justify="left")
    table.add_column("accuracy", justify="right")
    table.add_column("correct", justify="right")
    table.add_column("incorrect", justify="right")
    table.add_column("missing", justify="right")
    table.add_column("hallucinated", justify="right")

    if sort == "hallucinated":
        ordered = sorted(run.field_scores, key=lambda s: (-s.hallucinated, s.accuracy or 0.0))
    else:
        ordered = sorted(run.field_scores, key=lambda s: (s.accuracy is None, s.accuracy or 0.0))

    for score in ordered:
        table.add_row(
            Text(score.field),
            accuracy_cell(score),
            Text(str(score.correct)),
            Text(str(score.wrong)),
            Text(str(score.missed), style="warning" if score.missed > 0 else ""),
            Text(str(score.hallucinated), style="regression" if score.hallucinated > 0 else ""),
        )
    return table


def summary_lines(run: EvalRun) -> list[Text]:
    totals = Text("  totals: ", style="muted")
    totals.append(f"{sum(s.correct for s in run.field_scores)} correct · ")
    totals.append(f"{sum(s.wrong for s in run.field_scores)} incorrect · ")
    missed = sum(s.missed for s in run.field_scores)
    totals.append(f"{missed} missing", style="warning" if missed else None)
    totals.append(" · ")
    halluc = sum(s.hallucinated for s in run.field_scores)
    totals.append(f"{halluc} hallucinated", style="regression" if halluc else None)
    totals.append(
        f"  across {len(run.field_scores)} fields × {run.n_documents} documents", style="muted"
    )

    worst = Text("  most hallucination-prone field: ", style="muted")
    peak = max((s.hallucinated for s in run.field_scores), default=0)
    if peak == 0:
        worst.append("none — zero hallucinations in this run", style="gain")
    else:
        leaders = [s.field for s in run.field_scores if s.hallucinated == peak]
        worst.append(", ".join(leaders), style="regression")
        worst.append(f"  ({peak} each)" if len(leaders) > 1 else f"  ({peak})", style="muted")
    return [totals, worst]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="prompt version, e.g. v7")
    parser.add_argument(
        "--vertical",
        default="earnings",
        choices=["earnings", "director_trades"],
        help="which vertical's prompt family to load",
    )
    parser.add_argument("--model", default=None, help="model to score (default: latest run)")
    parser.add_argument(
        "--sort",
        default="accuracy",
        choices=["accuracy", "hallucinated"],
        help="accuracy: weakest fields first · hallucinated: most invented values first",
    )
    args = parser.parse_args()

    console = make_console()
    runs = load_eval_runs(args.vertical)
    run = pick_run(runs, int(args.version.lstrip("v")), args.model)
    if run is None:
        available = ", ".join(sorted({f"{r.version_label} ({r.model})" for r in runs}))
        console.print(
            f"no stored eval run for {args.vertical} {args.version} — available: {available}",
            style="regression",
        )
        raise SystemExit(1)

    console.print()
    console.print(build_table(run, args.sort))
    for line in summary_lines(run):
        console.print(line)
    console.print()


if __name__ == "__main__":
    main()
