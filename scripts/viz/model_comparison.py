"""Earnings accuracy per prompt version and model, straight from eval_runs.

    uv run python scripts/viz/model_comparison.py

Loads every persisted earnings EvalRun from BigQuery — the only place the
harness writes results; there are no local result files — and renders the
prompt-version progression per model as a rich table. Nothing is hardcoded:
a (version, model) row appears only if a stored run exists for it, so a
missing benchmark shows up as a missing row, not an invented number.

Where the same (model, prompt_version, dataset_version) was evaluated more
than once (the director-trades golden correction did this), the latest
evaluated_at wins — the same rule the eval history applies.
"""

import sys
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery
from rich.table import Table
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent))
from style import TABLE_BOX, make_console  # noqa: E402

from asx_engine.config import load_settings  # noqa: E402

PROMPT_FAMILY = "earnings_v%"


@dataclass(frozen=True)
class EvalRow:
    model: str
    prompt_version: str
    dataset_version: str
    evaluated_at: datetime
    n_documents: int
    overall_accuracy: float | None

    @property
    def version_number(self) -> int:
        return int(self.prompt_version.rsplit("_v", 1)[1])

    @property
    def version_label(self) -> str:
        return f"v{self.version_number}"


def load_rows() -> list[EvalRow]:
    """Every earnings eval run, deduped to the latest per (model, prompt, dataset)."""
    # ADC user-credential advisory would sit above the table in the screenshot.
    warnings.filterwarnings("ignore", category=UserWarning, module="google.auth._default")
    settings = load_settings()
    client = bigquery.Client(project=settings.gcp_project)
    table_id = f"{settings.gcp_project}.{settings.bq_dataset}.eval_runs"
    query = (
        "SELECT model, prompt_version, dataset_version, evaluated_at,"  # noqa: S608 - own table
        f" n_documents, overall_accuracy FROM `{table_id}`"
        " WHERE prompt_version LIKE @family"
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("family", "STRING", PROMPT_FAMILY)]
    )
    latest: dict[tuple[str, str, str], EvalRow] = {}
    for record in client.query_and_wait(query, job_config=job_config):
        row = EvalRow(
            model=record["model"],
            prompt_version=record["prompt_version"],
            dataset_version=record["dataset_version"],
            evaluated_at=record["evaluated_at"],
            n_documents=record["n_documents"],
            overall_accuracy=record["overall_accuracy"],
        )
        key = (row.model, row.prompt_version, row.dataset_version)
        if key not in latest or row.evaluated_at > latest[key].evaluated_at:
            latest[key] = row
    return sorted(latest.values(), key=lambda r: (r.version_number, r.model))


def delta_text(delta: float | None) -> Text:
    """Delta vs the previous version of the same model's series, coloured by sign."""
    if delta is None:
        return Text("—", style="muted")
    if delta > 0:
        return Text(f"+{delta * 100:.1f}pp", style="gain")
    if delta < 0:
        return Text(f"{delta * 100:.1f}pp", style="regression")
    return Text("+0.0pp", style="flat")


def find_champion(rows: list[EvalRow]) -> EvalRow:
    scored = [r for r in rows if r.overall_accuracy is not None]
    return max(scored, key=lambda r: (r.overall_accuracy or 0.0, r.version_number))


def build_table(rows: list[EvalRow]) -> Table:
    champion = find_champion(rows)
    caption = (
        f"golden dataset {champion.dataset_version} · {champion.n_documents} labeled documents"
        " · every row is a persisted eval_runs record"
    )
    table = Table(
        title="Earnings extraction — accuracy by prompt version",
        caption=caption,
        box=TABLE_BOX,
        header_style="accent",
        title_style="accent",
        caption_style="muted",
    )
    table.add_column("version", justify="left")
    table.add_column("model", justify="left")
    table.add_column("overall accuracy", justify="right")
    table.add_column("Δ vs prev version", justify="right")

    previous_by_model: dict[str, tuple[int, float | None]] = {}
    for row in rows:
        accuracy = row.overall_accuracy
        prior = previous_by_model.get(row.model)
        # A delta only means "vs prev version" when the previous version is
        # actually version−1 — opus jumps v1→v7, and +26pp styled as a
        # one-step delta would misread in a screenshot.
        delta = None
        if accuracy is not None and prior is not None:
            prior_version, prior_accuracy = prior
            if prior_accuracy is not None and prior_version == row.version_number - 1:
                delta = accuracy - prior_accuracy
        previous_by_model[row.model] = (row.version_number, accuracy)

        is_champion = row is champion
        acc_cell = Text("" if accuracy is None else f"{accuracy * 100:.1f}%")
        table.add_row(
            Text(row.version_label + (" ★" if is_champion else "")),
            Text(row.model),
            acc_cell,
            delta_text(delta),
            style="champion" if is_champion else None,
        )
    return table


def summary_line(rows: list[EvalRow]) -> Text:
    """The iteration story: v1 → best of the most-iterated model's series."""
    scored = [r for r in rows if r.overall_accuracy is not None]
    by_model: dict[str, list[EvalRow]] = {}
    for row in scored:
        by_model.setdefault(row.model, []).append(row)
    series = by_model[max(by_model, key=lambda m: len(by_model[m]))]
    first = min(series, key=lambda r: r.version_number)
    best = max(series, key=lambda r: (r.overall_accuracy or 0.0, r.version_number))
    assert first.overall_accuracy is not None and best.overall_accuracy is not None
    movement = (best.overall_accuracy - first.overall_accuracy) * 100
    text = Text()
    text.append(f"{first.version_label} → {best.version_label} ({best.model}): ", style="muted")
    text.append(f"{first.overall_accuracy * 100:.1f}% → {best.overall_accuracy * 100:.1f}%")
    text.append(f"  ({movement:+.1f}pp)", style="gain" if movement > 0 else "regression")
    text.append(f"  across {len(rows)} stored eval runs", style="muted")
    return text


def main() -> None:
    load_dotenv()
    console = make_console()
    rows = load_rows()
    if not rows:
        console.print("no earnings rows in eval_runs — run the eval job first", style="regression")
        raise SystemExit(1)
    console.print()
    console.print(build_table(rows))
    console.print(summary_line(rows))
    console.print()


if __name__ == "__main__":
    main()
