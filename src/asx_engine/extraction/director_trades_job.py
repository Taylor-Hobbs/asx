"""Director-trades extraction job: run the 3Y extractor over the golden set.

    uv run python -m asx_engine.extraction.director_trades_job --limit 3
    uv run python -m asx_engine.extraction.director_trades_job

Scope is deliberately the golden set, not "everything that parses": the pending
set is the content hashes of LABELED golden files in golden/director_trades/
minus what's already extracted for this (model, prompt_version). Excluded
filings (initial notices, superseded amendments) are never extracted, and no
headline regex gets a second chance to misclassify. The Q2 backfill will need a
generalized announcement-type-aware job; this one exists to produce the golden
accuracy number.

Sync calls only — 28 documents of a few KB each is pocket change, and the
Batches API's submit/collect split (and its --resume machinery) buys nothing at
this scale. Idempotent the same way the earnings job is: re-runs skip what's
recorded, a new prompt version naturally re-extracts everything.

Records land in the same extraction_records table as earnings, distinguished by
prompt_version (director_trades_v* vs earnings_v*) — one benchmark history, one
join key for the eval job.
"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import anthropic
import google.cloud.storage as storage
import structlog
from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import Settings, load_settings
from asx_engine.extraction.director_trades import extract_director_trades, load_prompt
from asx_engine.extraction.earnings import EXTRACTION_MODEL
from asx_engine.extraction.job import EXTRACTIONS_TABLE
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument
from asx_engine.schemas import ExtractionRecord, LabelStatus, utc_now
from asx_engine.schemas.director_trades import DirectorTradeGoldenLabel, DirectorTradesResult

log = structlog.get_logger()

LABELS_DIR = Path("golden/director_trades")

# str in, validated payload out — tests inject a deterministic callable.
Extractor = Callable[[str], DirectorTradesResult]


class ExtractionBackend(Protocol):
    """Storage capabilities run() needs; faked structurally in tests."""

    def golden_hashes(self) -> set[str]: ...
    def extracted_hashes(self, model: str, prompt_version: str) -> set[str]: ...
    def load_text(self, content_hash: str) -> str: ...
    def save(self, record: ExtractionRecord[DirectorTradesResult]) -> None: ...


@dataclass
class ExtractionSummary:
    extracted: list[ExtractionRecord[DirectorTradesResult]] = field(default_factory=list)
    already_extracted: int = 0
    pending_after_limit: int = 0


def run(
    backend: ExtractionBackend,
    extractor: Extractor,
    *,
    model: str,
    prompt_version: str,
    limit: int | None = None,
) -> ExtractionSummary:
    summary = ExtractionSummary()
    golden = backend.golden_hashes()
    done = backend.extracted_hashes(model, prompt_version)
    pending = sorted(golden - done)
    summary.already_extracted = len(golden & done)
    if limit is not None:
        summary.pending_after_limit = max(0, len(pending) - limit)
        pending = pending[:limit]
    log.info(
        "extract.3y.start",
        model=model,
        prompt_version=prompt_version,
        already_extracted=summary.already_extracted,
        pending=len(pending),
        deferred_by_limit=summary.pending_after_limit,
    )

    for content_hash in pending:
        payload = extractor(backend.load_text(content_hash))
        record = ExtractionRecord[DirectorTradesResult](
            content_hash=content_hash,
            model=model,
            prompt_version=prompt_version,
            extracted_at=utc_now(),
            payload=payload,
        )
        backend.save(record)
        summary.extracted.append(record)
        log.info(
            "extract.3y.stored",
            content_hash=content_hash,
            trades=len(payload.trades),
            directors=sorted({t.director_name.value or "?" for t in payload.trades}),
        )

    log.info("extract.3y.done", extracted=len(summary.extracted))
    return summary


class GcpExtractionBackend:
    """The real backend: goldens from the repo, text from GCS, records to BigQuery."""

    def __init__(self, settings: Settings, labels_dir: Path = LABELS_DIR) -> None:
        self._labels_dir = labels_dir
        self._bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)
        self._bq = bigquery.Client(project=settings.gcp_project)
        self._extractions_id = f"{settings.gcp_project}.{settings.bq_dataset}.{EXTRACTIONS_TABLE}"
        self._extractions_schema = self._bq.get_table(self._extractions_id).schema

    def golden_hashes(self) -> set[str]:
        hashes = set()
        for path in sorted(self._labels_dir.glob("*.json")):
            label = DirectorTradeGoldenLabel.model_validate_json(
                path.read_text(encoding="utf-8-sig")
            )
            if label.status is LabelStatus.LABELED:
                hashes.add(label.content_hash)
        return hashes

    def extracted_hashes(self, model: str, prompt_version: str) -> set[str]:
        query = (
            f"SELECT content_hash FROM `{self._extractions_id}` "  # noqa: S608 - own table
            "WHERE model = @model AND prompt_version = @prompt_version"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("model", "STRING", model),
                bigquery.ScalarQueryParameter("prompt_version", "STRING", prompt_version),
            ]
        )
        return {
            row["content_hash"] for row in self._bq.query_and_wait(query, job_config=job_config)
        }

    def load_text(self, content_hash: str) -> str:
        blob = self._bucket.blob(f"parsed/{PARSER_VERSION}/{content_hash}.json")
        document = ParsedDocument.model_validate_json(bytes(blob.download_as_bytes()))
        return document.text()

    def save(self, record: ExtractionRecord[DirectorTradesResult]) -> None:
        row = record.model_dump(mode="json", exclude={"payload"})
        row["payload"] = record.payload.model_dump_json()
        job_config = bigquery.LoadJobConfig(
            schema=self._extractions_schema,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        self._bq.load_table_from_json([row], self._extractions_id, job_config=job_config).result()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="extract at most N documents")
    args = parser.parse_args()

    load_dotenv()
    settings = load_settings()
    prompt_version, system_prompt = load_prompt()
    client = anthropic.Anthropic()
    backend = GcpExtractionBackend(settings)

    def extractor(document_text: str) -> DirectorTradesResult:
        return extract_director_trades(
            document_text,
            client=client,
            system_prompt=system_prompt,
            model=EXTRACTION_MODEL,
        )

    run(
        backend,
        extractor,
        model=EXTRACTION_MODEL,
        prompt_version=prompt_version,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
