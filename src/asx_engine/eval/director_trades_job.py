"""Director-trades eval runner: score stored 3Y extractions against the golden set.

    uv run python -m asx_engine.eval.director_trades_job
    uv run python -m asx_engine.eval.director_trades_job --model claude-haiku-4-5

The earnings eval job's shape, pointed at the other vertical: goldens come from
golden/director_trades/, predictions from the same extraction_records table
(prompt_version distinguishes the verticals — director_trades_v1 rows never
collide with earnings_v* rows), and the EvalRun lands in the same eval_runs
table, so the whole benchmark history lives in one place keyed by
(model, prompt_version).

The report has one line the earnings table doesn't: ``trade_detection``. A 3Y
is a list, so before fields can be compared the predicted trades are aligned to
golden trades (see director_trades_harness); a golden trade the model never
reported is a MISSED detection, an invented trade is a HALLUCINATED one. Field
lines then count only aligned pairs — their denominator is matched trades, not
golden trades, and the detection line is what keeps that honest.
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
from asx_engine.eval.director_trades_harness import aggregate, score_document
from asx_engine.eval.job import EVAL_RUNS_TABLE, _pct
from asx_engine.extraction.director_trades import load_prompt
from asx_engine.extraction.earnings import EXTRACTION_MODEL
from asx_engine.schemas import GOLDEN_DATASET_VERSION, LabelStatus, utc_now
from asx_engine.schemas.director_trades import DirectorTradeGoldenLabel, DirectorTradesResult
from asx_engine.schemas.eval import EvalRun, FieldOutcome

log = structlog.get_logger()

LABELS_DIR = Path("golden/director_trades")


class EvalBackend(Protocol):
    """Storage capabilities run() needs; faked structurally in tests."""

    def labeled_goldens(self, dataset_version: str) -> list[DirectorTradeGoldenLabel]: ...
    def extractions(self, model: str, prompt_version: str) -> dict[str, DirectorTradesResult]: ...
    def save(self, run: EvalRun) -> None: ...


@dataclass
class EvalReport:
    """The persisted aggregate plus the per-document detail it drops."""

    run: EvalRun
    scored: list[tuple[DirectorTradeGoldenLabel, list[tuple[str, FieldOutcome]]]]
    skipped: list[DirectorTradeGoldenLabel]


def run(
    backend: EvalBackend,
    *,
    model: str,
    prompt_version: str,
    dataset_version: str = GOLDEN_DATASET_VERSION,
    evaluated_at: datetime | None = None,
) -> EvalReport:
    goldens = backend.labeled_goldens(dataset_version)
    predictions = backend.extractions(model, prompt_version)

    scored: list[tuple[DirectorTradeGoldenLabel, list[tuple[str, FieldOutcome]]]] = []
    skipped: list[DirectorTradeGoldenLabel] = []
    for golden in goldens:
        prediction = predictions.get(golden.content_hash)
        if prediction is None:
            skipped.append(golden)
            continue
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

    if eval_run.n_documents:
        backend.save(eval_run)
    else:
        log.warning("eval.nothing_to_score", hint="extract the labeled 3Y filings first")

    return EvalReport(run=eval_run, scored=scored, skipped=skipped)


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

    def labeled_goldens(self, dataset_version: str) -> list[DirectorTradeGoldenLabel]:
        goldens = []
        for path in sorted(self._labels_dir.glob("*.json")):
            label = DirectorTradeGoldenLabel.model_validate_json(
                path.read_text(encoding="utf-8-sig")
            )
            if label.status is LabelStatus.LABELED and label.dataset_version == dataset_version:
                goldens.append(label)
        return goldens

    def extractions(self, model: str, prompt_version: str) -> dict[str, DirectorTradesResult]:
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
        out: dict[str, DirectorTradesResult] = {}
        for row in self._bq.query_and_wait(query, job_config=job_config):
            try:
                out[row["content_hash"]] = DirectorTradesResult.model_validate_json(row["payload"])
            except ValidationError as exc:
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
    )
    print_report(report)


if __name__ == "__main__":
    main()
