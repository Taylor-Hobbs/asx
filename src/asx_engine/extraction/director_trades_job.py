"""Director-trades extraction job: golden set (sync) or full corpus (batch).

    # Golden set — 28 labeled filings, sync, pocket change:
    uv run python -m asx_engine.extraction.director_trades_job

    # Full corpus — every parsed 3Y in BigQuery, Batches API (50% off).
    # Deliberately gated: prints the document count and refuses without --confirm.
    uv run python -m asx_engine.extraction.director_trades_job --scope corpus --batch --confirm

    # Collect an already-submitted batch after a crash (no resubmission):
    uv run python -m asx_engine.extraction.director_trades_job --scope corpus --batch --resume ID

Two scopes over the same machinery:

- **golden** — the content hashes of LABELED golden files. Cheap, sync, exists
  to produce the benchmark number. Excluded filings are never extracted.
- **corpus** — every announcement whose headline matches the 3Y pattern AND
  whose parse is good quality. This is the backfill path: thousands of
  documents, so it runs through the Message Batches API with the same
  submit/poll/collect/resume shape as the earnings job. The --confirm gate is
  CLAUDE.md's "extraction costs real money" rule made mechanical.

Idempotent like every extraction job: pending = scope hashes minus
extraction_records rows for (model, prompt_version); a crash after batch
submission is recovered with --resume (results are retained 29 days).
"""

import argparse
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import anthropic
import google.cloud.storage as storage
import structlog
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv
from google.cloud import bigquery
from pydantic import TypeAdapter, ValidationError

from asx_engine.config import Settings, load_settings
from asx_engine.extraction.director_trades import extract_director_trades, load_prompt
from asx_engine.extraction.earnings import EXTRACTION_MODEL, MAX_OUTPUT_TOKENS, supports_thinking
from asx_engine.extraction.job import EXTRACTIONS_TABLE
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument, ParseQuality
from asx_engine.schemas import ExtractionRecord, LabelStatus, utc_now
from asx_engine.schemas.director_trades import DirectorTradeGoldenLabel, DirectorTradesResult

log = structlog.get_logger()

LABELS_DIR = Path("golden/director_trades")

# The BQ-side twin of director_trades_ingest._3Y_HEADLINE (RE2 syntax, (?i)
# instead of re.IGNORECASE). Both crawl-time and extraction-time selection ask
# "is this a 3Y?" of the same headline, so the patterns must agree.
_3Y_HEADLINE_SQL = r"(?i)appendix\s*3y|change in director|director.s interest|directors interest"

# str in, validated payload out — tests inject a deterministic callable.
Extractor = Callable[[str], DirectorTradesResult]


class ExtractionBackend(Protocol):
    """Storage capabilities the runners need; faked structurally in tests."""

    def golden_hashes(self) -> set[str]: ...
    def corpus_hashes(self) -> set[str]: ...
    def extracted_hashes(self, model: str, prompt_version: str) -> set[str]: ...
    def load_text(self, content_hash: str) -> str: ...
    def save(self, record: ExtractionRecord[DirectorTradesResult]) -> None: ...


@dataclass
class ExtractionSummary:
    extracted: list[ExtractionRecord[DirectorTradesResult]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    already_extracted: int = 0
    pending_after_limit: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def _pending(
    backend: ExtractionBackend,
    *,
    scope: str,
    model: str,
    prompt_version: str,
    limit: int | None,
    summary: ExtractionSummary,
) -> tuple[list[str], set[str]]:
    """The shared idempotency arithmetic: (pending hashes, already-done hashes)."""
    wanted = backend.golden_hashes() if scope == "golden" else backend.corpus_hashes()
    done = backend.extracted_hashes(model, prompt_version)
    pending = sorted(wanted - done)
    summary.already_extracted = len(wanted & done)
    if limit is not None:
        summary.pending_after_limit = max(0, len(pending) - limit)
        pending = pending[:limit]
    return pending, done


def _record(
    content_hash: str, model: str, prompt_version: str, payload: DirectorTradesResult
) -> ExtractionRecord[DirectorTradesResult]:
    return ExtractionRecord[DirectorTradesResult](
        content_hash=content_hash,
        model=model,
        prompt_version=prompt_version,
        extracted_at=utc_now(),
        payload=payload,
    )


def run(
    backend: ExtractionBackend,
    extractor: Extractor,
    *,
    model: str,
    prompt_version: str,
    scope: str = "golden",
    limit: int | None = None,
) -> ExtractionSummary:
    """Sync extraction: one blocking API call per document."""
    summary = ExtractionSummary()
    pending, _ = _pending(
        backend,
        scope=scope,
        model=model,
        prompt_version=prompt_version,
        limit=limit,
        summary=summary,
    )
    log.info(
        "extract.3y.start",
        scope=scope,
        model=model,
        prompt_version=prompt_version,
        already_extracted=summary.already_extracted,
        pending=len(pending),
        deferred_by_limit=summary.pending_after_limit,
    )

    for content_hash in pending:
        payload = extractor(backend.load_text(content_hash))
        record = _record(content_hash, model, prompt_version, payload)
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


def run_batch(
    backend: ExtractionBackend,
    client: anthropic.Anthropic,
    *,
    model: str,
    prompt_version: str,
    system_prompt: str,
    scope: str = "corpus",
    limit: int | None = None,
    resume_batch_id: str | None = None,
    poll_seconds: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> ExtractionSummary:
    """Extract every pending document through the Message Batches API.

    Same shape as the earnings run_batch: submit once, poll until ended,
    validate every payload back through the full Pydantic model on collection.
    A document that fails (API error, refusal, invalid payload) is logged,
    counted, never saved — it stays pending for a future run. A crash between
    submit and collect is recovered with --resume, never by resubmitting.
    """
    summary = ExtractionSummary()
    pending, done = _pending(
        backend,
        scope=scope,
        model=model,
        prompt_version=prompt_version,
        limit=limit,
        summary=summary,
    )

    if resume_batch_id is not None:
        batch = client.messages.batches.retrieve(resume_batch_id)
        log.info("extract.3y.batch.resumed", batch_id=batch.id, status=batch.processing_status)
    else:
        if not pending:
            log.info(
                "extract.3y.batch.nothing_pending", already_extracted=summary.already_extracted
            )
            return summary
        schema = anthropic.transform_schema(TypeAdapter(DirectorTradesResult).json_schema())
        requests = []
        for content_hash in pending:
            params: MessageCreateParamsNonStreaming = {
                "model": model,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "system": system_prompt,
                "messages": [{"role": "user", "content": backend.load_text(content_hash)}],
                "output_config": {"format": {"type": "json_schema", "schema": schema}},
            }
            if supports_thinking(model):
                params["thinking"] = {"type": "adaptive"}
            requests.append(Request(custom_id=content_hash, params=params))
        batch = client.messages.batches.create(requests=requests)
        log.info(
            "extract.3y.batch.submitted",
            batch_id=batch.id,
            requests=len(requests),
            resume_hint=f"--resume {batch.id}",
        )

    while batch.processing_status != "ended":
        sleep(poll_seconds)
        batch = client.messages.batches.retrieve(batch.id)
        log.info(
            "extract.3y.batch.status",
            batch_id=batch.id,
            status=batch.processing_status,
            processing=batch.request_counts.processing,
            succeeded=batch.request_counts.succeeded,
            errored=batch.request_counts.errored,
        )

    for result in client.messages.batches.results(batch.id):
        content_hash = result.custom_id
        if content_hash in done:
            continue  # resume after a partial save: already recorded
        if result.result.type != "succeeded":
            summary.failed.append(content_hash)
            log.warning(
                "extract.3y.batch.failed", content_hash=content_hash, result=result.result.type
            )
            continue
        message = result.result.message
        summary.input_tokens += message.usage.input_tokens
        summary.output_tokens += message.usage.output_tokens
        text = next((b.text for b in message.content if b.type == "text"), None)
        if message.stop_reason != "end_turn" or text is None:
            summary.failed.append(content_hash)
            log.warning(
                "extract.3y.batch.failed",
                content_hash=content_hash,
                stop_reason=message.stop_reason,
            )
            continue
        try:
            payload = DirectorTradesResult.model_validate_json(text)
        except ValidationError as exc:
            summary.failed.append(content_hash)
            log.warning("extract.3y.batch.invalid", content_hash=content_hash, error=str(exc))
            continue
        record = _record(content_hash, model, prompt_version, payload)
        backend.save(record)
        summary.extracted.append(record)
        log.info(
            "extract.3y.stored",
            content_hash=content_hash,
            trades=len(payload.trades),
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    log.info(
        "extract.3y.batch.done",
        extracted=len(summary.extracted),
        failed=len(summary.failed),
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
    )
    return summary


class GcpExtractionBackend:
    """The real backend: goldens from the repo, text from GCS, records in BigQuery."""

    def __init__(self, settings: Settings, labels_dir: Path = LABELS_DIR) -> None:
        self._labels_dir = labels_dir
        self._bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)
        self._bq = bigquery.Client(project=settings.gcp_project)
        dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
        self._announcements_id = f"{dataset}.announcements"
        self._parsed_id = f"{dataset}.parsed_documents"
        self._extractions_id = f"{dataset}.{EXTRACTIONS_TABLE}"
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

    def corpus_hashes(self) -> set[str]:
        # 3Y-headline announcements that parsed cleanly. The join is the
        # correctness guard: extraction over a partial parse would measure the
        # parser, not the prompt.
        query = (
            "SELECT DISTINCT a.content_hash "
            f"FROM `{self._announcements_id}` a "  # noqa: S608 - own tables
            f"JOIN `{self._parsed_id}` p USING (content_hash) "
            "WHERE REGEXP_CONTAINS(a.headline, @pattern) "
            "AND p.parser_version = @parser_version AND p.quality = @quality"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("pattern", "STRING", _3Y_HEADLINE_SQL),
                bigquery.ScalarQueryParameter("parser_version", "STRING", PARSER_VERSION),
                bigquery.ScalarQueryParameter("quality", "STRING", ParseQuality.GOOD.value),
            ]
        )
        return {
            row["content_hash"] for row in self._bq.query_and_wait(query, job_config=job_config)
        }

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
    parser.add_argument(
        "--scope",
        choices=["golden", "corpus"],
        default="golden",
        help="golden: labeled filings only (benchmark); corpus: every parsed 3Y (backfill)",
    )
    parser.add_argument("--limit", type=int, default=None, help="extract at most N documents")
    parser.add_argument(
        "--batch", action="store_true", help="use the Message Batches API (50%% cheaper)"
    )
    parser.add_argument(
        "--resume",
        metavar="BATCH_ID",
        default=None,
        help="collect an already-submitted batch instead of submitting a new one",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="required for corpus runs — extraction costs real API credits",
    )
    args = parser.parse_args()

    load_dotenv()
    settings = load_settings()
    prompt_version, system_prompt = load_prompt()
    client = anthropic.Anthropic()
    backend = GcpExtractionBackend(settings)

    if args.scope == "corpus" and not (args.confirm or args.resume):
        # The cost gate: show the bill before anything is submitted.
        summary = ExtractionSummary()
        pending, _ = _pending(
            backend,
            scope="corpus",
            model=EXTRACTION_MODEL,
            prompt_version=prompt_version,
            limit=args.limit,
            summary=summary,
        )
        print(
            f"corpus run would extract {len(pending)} documents "
            f"({summary.already_extracted} already done). "
            f"Rough cost at Haiku batch rates: ~${len(pending) * 0.003:.0f}. "
            f"Re-run with --confirm to proceed."
        )
        return

    if args.batch or args.resume:
        run_batch(
            backend,
            client,
            model=EXTRACTION_MODEL,
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            scope=args.scope,
            limit=args.limit,
            resume_batch_id=args.resume,
        )
        return

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
        scope=args.scope,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
