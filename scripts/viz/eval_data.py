"""Shared BigQuery loader for the viz scripts.

eval_runs is the only place the harness persists results (there are no local
result files), so every viz script loads through here. Where the same
(model, prompt_version, dataset_version) was evaluated more than once — the
director-trades golden correction did this — the latest evaluated_at wins.
"""

import warnings
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import load_settings


@dataclass(frozen=True)
class FieldScore:
    field: str
    correct: int
    wrong: int
    missed: int
    hallucinated: int
    total: int
    accuracy: float | None


@dataclass(frozen=True)
class EvalRun:
    model: str
    prompt_version: str
    dataset_version: str
    evaluated_at: datetime
    n_documents: int
    overall_accuracy: float | None
    field_scores: tuple[FieldScore, ...]

    @property
    def version_number(self) -> int:
        return int(self.prompt_version.rsplit("_v", 1)[1])

    @property
    def version_label(self) -> str:
        return f"v{self.version_number}"


def load_eval_runs(prompt_family: str) -> list[EvalRun]:
    """Every eval run whose prompt_version matches `family_v%`, deduped to latest."""
    # The ADC user-credential advisory would sit above the table in a screenshot.
    warnings.filterwarnings("ignore", category=UserWarning, module="google.auth._default")
    load_dotenv()
    settings = load_settings()
    client = bigquery.Client(project=settings.gcp_project)
    table_id = f"{settings.gcp_project}.{settings.bq_dataset}.eval_runs"
    query = (
        "SELECT model, prompt_version, dataset_version, evaluated_at,"  # noqa: S608 - own table
        f" n_documents, overall_accuracy, field_scores FROM `{table_id}`"
        " WHERE prompt_version LIKE @family"
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("family", "STRING", f"{prompt_family}_v%")]
    )
    latest: dict[tuple[str, str, str], EvalRun] = {}
    for record in client.query_and_wait(query, job_config=job_config):
        run = EvalRun(
            model=record["model"],
            prompt_version=record["prompt_version"],
            dataset_version=record["dataset_version"],
            evaluated_at=record["evaluated_at"],
            n_documents=record["n_documents"],
            overall_accuracy=record["overall_accuracy"],
            field_scores=tuple(
                FieldScore(
                    field=f["field"],
                    correct=f["correct"],
                    wrong=f["wrong"],
                    missed=f["missed"],
                    hallucinated=f["hallucinated"],
                    total=f["total"],
                    accuracy=f["accuracy"],
                )
                for f in record["field_scores"]
            ),
        )
        key = (run.model, run.prompt_version, run.dataset_version)
        if key not in latest or run.evaluated_at > latest[key].evaluated_at:
            latest[key] = run
    return sorted(latest.values(), key=lambda r: (r.version_number, r.model))
