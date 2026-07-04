"""Eval harness runner: score stored extractions against the golden set.

    uv run python -m asx_engine.eval.job                 # current prompt, default model
    uv run python -m asx_engine.eval.job --prompt-version earnings_v1
    uv run python -m asx_engine.eval.job --model claude-opus-4-8

Loads every `labeled` golden, joins it to the extraction for (model,
prompt_version) by content_hash, scores per field, prints a per-field table,
and appends one EvalRun row to BigQuery — so every reported accuracy number is
reproducible and comparable across prompt versions (CLAUDE.md / the eval
methodology doc). The regression gate is downstream of this: a new prompt
ships only if its EvalRun matches or beats the incumbent's.

Structured like the parse and extraction jobs: a Protocol describes the storage
the run needs, the real GcpEvalBackend implements it, and tests drive a
structural fake — the scoring logic in `harness` is what unit tests pin down,
not the BigQuery wiring.

Two coverage facts are kept honest rather than hidden:

- `n_skipped`: labeled goldens with no extraction for this (model, prompt) —
  the denominator must not silently shrink to whatever happens to be scorable.
- empty runs are not saved: with zero labeled goldens the harness still runs
  (and the table prints all-zero rows) but writes nothing to BigQuery, so the
  eval_runs history starts the day real labels exist, not before.
"""

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import structlog
from dotenv import load_dotenv
from google.cloud import bigquery
from pydantic import ValidationError

from asx_engine.config import Settings, load_settings
from asx_engine.eval.harness import SCORED_FIELDS, aggregate, score_document
from asx_engine.extraction.earnings import EXTRACTION_MODEL, load_prompt
from asx_engine.postprocess import apply_bank_revenue_filter
from asx_engine.schemas import (
    GOLDEN_DATASET_VERSION,
    EarningsResult,
    GoldenLabel,
    LabelStatus,
    utc_now,
)
from asx_engine.schemas.eval import EvalRun, FieldOutcome

log = structlog.get_logger()

EVAL_RUNS_TABLE = "eval_runs"
LABELS_DIR = Path("golden/labels")


class EvalBackend(Protocol):
    """Storage capabilities run() needs; faked structurally in tests."""

    def labeled_goldens(self, dataset_version: str) -> list[GoldenLabel]: ...
    def extractions(self, model: str, prompt_version: str) -> dict[str, EarningsResult]: ...
    def save(self, run: EvalRun) -> None: ...


@dataclass
class EvalReport:
    """The full result of a run: the persisted summary plus per-document detail.

    `run` is what lands in BigQuery (the aggregate). `scored` and `skipped` stay
    in memory for the console table and for tests — the detail a human needs to
    chase a WRONG field back to its document, which the aggregate deliberately
    drops.
    """

    run: EvalRun
    scored: list[tuple[GoldenLabel, dict[str, FieldOutcome]]]
    skipped: list[GoldenLabel]


def run(
    backend: EvalBackend,
    *,
    model: str,
    prompt_version: str,
    dataset_version: str = GOLDEN_DATASET_VERSION,
    evaluated_at: datetime | None = None,
    post_process: bool = False,
) -> EvalReport:
    goldens = backend.labeled_goldens(dataset_version)
    predictions = backend.extractions(model, prompt_version)

    scored: list[tuple[GoldenLabel, dict[str, FieldOutcome]]] = []
    skipped: list[GoldenLabel] = []
    for golden in goldens:
        prediction = predictions.get(golden.content_hash)
        if prediction is None:
            skipped.append(golden)
            continue
        if post_process:
            prediction = apply_bank_revenue_filter(prediction, golden.ticker)
        scored.append((golden, score_document(golden.labels, prediction)))

    eval_run = EvalRun(
        model=model,
        prompt_version=prompt_version,
        dataset_version=dataset_version,
        evaluated_at=evaluated_at or utc_now(),
        n_documents=len(scored),
        n_skipped=len(skipped),
        field_scores=aggregate([outcomes for _, outcomes in scored]),
    )
    log.info(
        "eval.scored",
        model=model,
        prompt_version=prompt_version,
        dataset_version=dataset_version,
        n_documents=eval_run.n_documents,
        n_skipped=eval_run.n_skipped,
        overall_accuracy=eval_run.overall_accuracy,
    )

    # Don't persist an empty run: the eval_runs history should begin when real
    # labels do, not record zero-document runs taken before the golden set exists.
    if eval_run.n_documents:
        backend.save(eval_run)
    else:
        log.warning("eval.nothing_to_score", hint="label goldens in golden/labels/ first")

    return EvalReport(run=eval_run, scored=scored, skipped=skipped)


def _pct(value: float | None) -> str:
    return "  —  " if value is None else f"{value * 100:5.1f}%"


def print_report(report: EvalReport) -> None:
    """Per-field table to stdout — the human-facing companion to the BQ row."""
    eval_run = report.run
    print(
        f"\neval {eval_run.model} / {eval_run.prompt_version} / {eval_run.dataset_version}"
        f"  —  {eval_run.n_documents} scored, {eval_run.n_skipped} skipped (no extraction)"
    )
    header = f"  {'field':22} {'acc':>6}  {'ok':>3} {'wrong':>5} {'miss':>4} {'halluc':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for score in eval_run.field_scores:
        print(
            f"  {score.field:22} {_pct(score.accuracy)}  "
            f"{score.correct:>3} {score.wrong:>5} {score.missed:>4} {score.hallucinated:>6}"
        )
    print("  " + "-" * (len(header) - 2))
    print(f"  {'OVERALL':22} {_pct(eval_run.overall_accuracy)}")
    if report.skipped:
        print("\n  skipped (labeled but not extracted for this model/prompt):")
        for golden in report.skipped:
            print(f"    {golden.ticker} {golden.announcement_id}  {golden.headline}")


class GcpEvalBackend:
    """The real backend: goldens from the repo, extractions and runs in BigQuery."""

    def __init__(self, settings: Settings, labels_dir: Path = LABELS_DIR) -> None:
        self._labels_dir = labels_dir
        self._bq = bigquery.Client(project=settings.gcp_project)
        dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
        self._extractions_id = f"{dataset}.extraction_records"
        self._eval_runs_id = f"{dataset}.{EVAL_RUNS_TABLE}"
        self._eval_runs_schema = self._bq.get_table(self._eval_runs_id).schema

    def labeled_goldens(self, dataset_version: str) -> list[GoldenLabel]:
        goldens = []
        for path in sorted(self._labels_dir.glob("*.json")):
            label = GoldenLabel.model_validate_json(path.read_text(encoding="utf-8"))
            if label.status is LabelStatus.LABELED and label.dataset_version == dataset_version:
                goldens.append(label)
        return goldens

    def extractions(self, model: str, prompt_version: str) -> dict[str, EarningsResult]:
        query = (
            f"SELECT content_hash, payload FROM `{self._extractions_id}` "  # noqa: S608 - own table
            "WHERE model = @model AND prompt_version = @prompt_version"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("model", "STRING", model),
                bigquery.ScalarQueryParameter("prompt_version", "STRING", prompt_version),
            ]
        )
        out: dict[str, EarningsResult] = {}
        for row in self._bq.query_and_wait(query, job_config=job_config):
            try:
                out[row["content_hash"]] = EarningsResult.model_validate_json(row["payload"])
            except ValidationError as exc:  # a stored payload that no longer validates
                log.warning(
                    "eval.payload_invalid", content_hash=row["content_hash"], error=str(exc)
                )
        return out

    def save(self, run: EvalRun) -> None:
        job_config = bigquery.LoadJobConfig(
            schema=self._eval_runs_schema,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        row = run.model_dump(mode="json")
        self._bq.load_table_from_json([row], self._eval_runs_id, job_config=job_config).result()


def main(argv: Iterable[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=EXTRACTION_MODEL, help="model identifier to score")
    parser.add_argument(
        "--prompt-version", default=None, help="prompt version to score (default: current prompt)"
    )
    parser.add_argument(
        "--dataset-version", default=GOLDEN_DATASET_VERSION, help="golden dataset version"
    )
    parser.add_argument(
        "--post-process",
        action="store_true",
        help="apply post-processing filters (e.g. bank revenue null) before scoring",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    load_dotenv()
    settings = load_settings()
    prompt_version = args.prompt_version or load_prompt()[0]
    backend = GcpEvalBackend(settings)
    report = run(
        backend,
        model=args.model,
        prompt_version=prompt_version,
        dataset_version=args.dataset_version,
        post_process=args.post_process,
    )
    print_report(report)


if __name__ == "__main__":
    main()


# Re-exported so callers can iterate the canonical field order without reaching
# into the harness internals (the report table and tests both rely on it).
__all__ = ["EvalBackend", "EvalReport", "EvalRun", "SCORED_FIELDS", "main", "print_report", "run"]
