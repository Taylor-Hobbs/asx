"""Extraction job: run the earnings extractor over parsed announcements.

    uv run python -m asx_engine.extraction.job --limit 3      # sync, full price
    uv run python -m asx_engine.extraction.job --batch        # Batches API, 50% off
    uv run python -m asx_engine.extraction.job --resume ID    # collect an existing batch

Idempotent and resumable the same way the parse job is: pending work is the
set difference between good-quality parsed documents and extraction_records
rows for the CURRENT (model, prompt_version) pair. A crash loses nothing; a
re-run picks up where it left off; a new prompt version or model naturally
re-extracts everything while leaving the old records intact for evals.

Two execution modes against the same pending set:

- **Sync** (`run`): one blocking API call per document. Immediate feedback;
  right for eyeball runs of a handful.
- **Batch** (`run_batch`): submit every pending document to the Message
  Batches API in one request, poll until ended, collect results. Half the
  token price, and the natural shape for headless full-scale runs — nothing
  about extraction is latency-sensitive. One submission risk exists that
  sync mode doesn't have: a crash after submit but before collection would,
  on naive re-run, resubmit and double-spend. Hence `--resume <batch_id>`,
  which collects without resubmitting (the API retains results 29 days).

Unlike parsing there is no GCS artifact: the whole ExtractionRecord (a few KB
of JSON) fits in its BigQuery row, with the payload stored as a JSON string
the eval harness validates back through the Pydantic schema.

`--limit` exists because extraction costs real API tokens: run a handful,
eyeball the payloads against the PDFs, then widen.
"""

import argparse
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
import google.cloud.storage as storage
import structlog
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv
from google.api_core.exceptions import TooManyRequests
from google.cloud import bigquery
from pydantic import TypeAdapter, ValidationError

from asx_engine.config import Settings, load_settings
from asx_engine.extraction.earnings import (
    EXTRACTION_MODEL,
    MAX_OUTPUT_TOKENS,
    extract_earnings,
    load_prompt,
    supports_thinking,
)
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument, ParseQuality
from asx_engine.schemas import EarningsResult, ExtractionRecord, utc_now

log = structlog.get_logger()

EXTRACTIONS_TABLE = "extraction_records"

# str in, validated payload out — the job orchestrates, the extractor extracts.
# Tests inject a deterministic callable here instead of faking the Anthropic SDK.
Extractor = Callable[[str], EarningsResult]


class ExtractionBackend(Protocol):
    """Storage capabilities run() needs; faked structurally in tests."""

    def parsed_hashes(self, parser_version: str) -> set[str]: ...
    def extracted_hashes(self, model: str, prompt_version: str) -> set[str]: ...
    def load_text(self, content_hash: str) -> str: ...
    def save_records(self, records: list[ExtractionRecord[EarningsResult]]) -> None: ...


# Records buffered per BigQuery load job during batch collection — the quota
# is 1,500 load jobs/table/day and per-record jobs tripped it on three tables
# (announcements, parsed_documents, extraction_records) before every bulk
# writer got swept. Batch results are retained 29 days; --resume recovers a
# crash between flushes.
FLUSH_EVERY = 250


def load_rows_with_backoff(
    bq: bigquery.Client,
    rows: list[dict[str, object]],
    table_id: str,
    schema: list[bigquery.SchemaField],
    *,
    sleep: Callable[[float], None] = time.sleep,
    max_attempts: int = 6,
) -> None:
    """One load job, retried with exponential backoff on 429s.

    Batch collection has no API latency between flushes — 250-record buffers
    fill in seconds, and back-to-back load jobs trip BigQuery's SHORT-TERM
    table-update rate limit (~5 ops per 10s per table; distinct from the
    1,500/day quota, which backoff cannot fix and which stays fatal). A 429
    here is therefore "slow down", not "stop": wait, retry, and only give up
    after max_attempts.
    """
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    for attempt in range(max_attempts):
        try:
            bq.load_table_from_json(rows, table_id, job_config=job_config).result()
            return
        except TooManyRequests:
            if attempt == max_attempts - 1:
                raise
            delay = 10.0 * 2**attempt  # 10s, 20s, 40s, 80s, 160s
            log.warning("bq.rate_limited", table=table_id, retry_in_seconds=delay)
            sleep(delay)


@dataclass
class ExtractionSummary:
    extracted: list[ExtractionRecord[EarningsResult]] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    already_extracted: int = 0
    pending_after_limit: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def run(
    backend: ExtractionBackend,
    extractor: Extractor,
    *,
    model: str,
    prompt_version: str,
    parser_version: str = PARSER_VERSION,
    limit: int | None = None,
) -> ExtractionSummary:
    summary = ExtractionSummary()
    pending, _ = _pending(
        backend,
        model=model,
        prompt_version=prompt_version,
        parser_version=parser_version,
        limit=limit,
        summary=summary,
    )
    log.info(
        "extract.start",
        model=model,
        prompt_version=prompt_version,
        already_extracted=summary.already_extracted,
        pending=len(pending),
        deferred_by_limit=summary.pending_after_limit,
    )

    for content_hash in pending:
        payload = extractor(backend.load_text(content_hash))
        record = ExtractionRecord[EarningsResult](
            content_hash=content_hash,
            model=model,
            prompt_version=prompt_version,
            extracted_at=utc_now(),
            payload=payload,
        )
        # Sync runs are small (--limit eyeball runs) — immediate persistence
        # per record is worth the load job.
        backend.save_records([record])
        summary.extracted.append(record)
        log.info(
            "extract.stored",
            content_hash=content_hash,
            period=payload.period.value,
            reporting_currency=payload.reporting_currency.value,
            revenue=str(payload.revenue.current.value),
            npat=str(payload.npat.current.value),
        )

    log.info("extract.done", extracted=len(summary.extracted))
    return summary


def _pending(
    backend: ExtractionBackend,
    *,
    model: str,
    prompt_version: str,
    parser_version: str,
    limit: int | None,
    summary: ExtractionSummary,
) -> tuple[list[str], set[str]]:
    """The shared idempotency arithmetic: (pending hashes, already-done hashes)."""
    parsed = backend.parsed_hashes(parser_version)
    done = backend.extracted_hashes(model, prompt_version)
    pending = sorted(parsed - done)
    summary.already_extracted = len(parsed & done)
    if limit is not None:
        summary.pending_after_limit = max(0, len(pending) - limit)
        pending = pending[:limit]
    return pending, done


def run_batch(
    backend: ExtractionBackend,
    client: anthropic.Anthropic,
    *,
    model: str,
    prompt_version: str,
    system_prompt: str,
    parser_version: str = PARSER_VERSION,
    limit: int | None = None,
    resume_batch_id: str | None = None,
    poll_seconds: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> ExtractionSummary:
    """Extract every pending document through the Message Batches API.

    Same output as run() at half the token price. The structured-output
    schema is built from EarningsResult exactly as messages.parse() would
    build it (transform_schema strips constraints the API can't enforce,
    e.g. confidence bounds); collection validates each payload back through
    the full Pydantic model, so nothing the API couldn't check goes unchecked.
    A document that fails (API error, refusal, invalid payload) is logged and
    counted, never saved, and never kills the rest of the batch — it simply
    stays pending for a future run.
    """
    summary = ExtractionSummary()
    pending, done = _pending(
        backend,
        model=model,
        prompt_version=prompt_version,
        parser_version=parser_version,
        limit=limit,
        summary=summary,
    )

    if resume_batch_id is not None:
        batch = client.messages.batches.retrieve(resume_batch_id)
        log.info("extract.batch.resumed", batch_id=batch.id, status=batch.processing_status)
    else:
        if not pending:
            log.info("extract.batch.nothing_pending", already_extracted=summary.already_extracted)
            return summary
        schema = anthropic.transform_schema(TypeAdapter(EarningsResult).json_schema())
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
            "extract.batch.submitted",
            batch_id=batch.id,
            requests=len(requests),
            resume_hint=f"--resume {batch.id}",
        )

    while batch.processing_status != "ended":
        sleep(poll_seconds)
        batch = client.messages.batches.retrieve(batch.id)
        log.info(
            "extract.batch.status",
            batch_id=batch.id,
            status=batch.processing_status,
            processing=batch.request_counts.processing,
            succeeded=batch.request_counts.succeeded,
            errored=batch.request_counts.errored,
        )

    record_buffer: list[ExtractionRecord[EarningsResult]] = []

    def flush() -> None:
        if record_buffer:
            backend.save_records(record_buffer)
            log.info("extract.batch.records_flushed", records=len(record_buffer))
            record_buffer.clear()

    for result in client.messages.batches.results(batch.id):
        content_hash = result.custom_id
        if content_hash in done:
            continue  # resume after a partial save: already recorded
        if result.result.type != "succeeded":
            summary.failed.append(content_hash)
            log.warning(
                "extract.batch.failed", content_hash=content_hash, result=result.result.type
            )
            continue
        message = result.result.message
        summary.input_tokens += message.usage.input_tokens
        summary.output_tokens += message.usage.output_tokens
        text = next((b.text for b in message.content if b.type == "text"), None)
        if message.stop_reason != "end_turn" or text is None:
            summary.failed.append(content_hash)
            log.warning(
                "extract.batch.failed", content_hash=content_hash, stop_reason=message.stop_reason
            )
            continue
        try:
            payload = EarningsResult.model_validate_json(text)
        except ValidationError as exc:
            summary.failed.append(content_hash)
            log.warning("extract.batch.invalid", content_hash=content_hash, error=str(exc))
            continue
        record = ExtractionRecord[EarningsResult](
            content_hash=content_hash,
            model=model,
            prompt_version=prompt_version,
            extracted_at=utc_now(),
            payload=payload,
        )
        record_buffer.append(record)
        if len(record_buffer) >= FLUSH_EVERY:
            flush()
        summary.extracted.append(record)
        log.info(
            "extract.stored",
            content_hash=content_hash,
            period=payload.period.value,
            reporting_currency=payload.reporting_currency.value,
            revenue=str(payload.revenue.current.value),
            npat=str(payload.npat.current.value),
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    flush()
    log.info(
        "extract.batch.done",
        extracted=len(summary.extracted),
        failed=len(summary.failed),
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
    )
    return summary


class GcpExtractionBackend:
    """The real backend: parsed text from GCS, records to BigQuery."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)
        self._bq = bigquery.Client(project=settings.gcp_project)
        self._parsed_id = f"{settings.gcp_project}.{settings.bq_dataset}.parsed_documents"
        self._extractions_id = f"{settings.gcp_project}.{settings.bq_dataset}.{EXTRACTIONS_TABLE}"
        self._extractions_schema = self._bq.get_table(self._extractions_id).schema

    def parsed_hashes(self, parser_version: str) -> set[str]:
        # Only good parses: extraction over partial/empty text would produce
        # records whose failures measure the parser, not the prompt.
        query = (
            f"SELECT content_hash FROM `{self._parsed_id}` "  # noqa: S608 - own table
            "WHERE parser_version = @parser_version AND quality = @quality"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("parser_version", "STRING", parser_version),
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

    def save_records(self, records: list[ExtractionRecord[EarningsResult]]) -> None:
        """Many records, ONE load job — see FLUSH_EVERY for the quota story."""
        if not records:
            return
        rows = []
        for record in records:
            row = record.model_dump(mode="json", exclude={"payload"})
            row["payload"] = record.payload.model_dump_json()
            rows.append(row)
        load_rows_with_backoff(self._bq, rows, self._extractions_id, self._extractions_schema)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
    args = parser.parse_args()

    # ANTHROPIC_API_KEY lives in .env (gitignored). pydantic-settings reads
    # that file privately for its own fields; the anthropic client reads the
    # PROCESS environment — so the .env contents must be exported into it.
    load_dotenv()
    settings = load_settings()
    prompt_version, system_prompt = load_prompt()
    client = anthropic.Anthropic()
    backend = GcpExtractionBackend(settings)

    if args.batch or args.resume:
        run_batch(
            backend,
            client,
            model=EXTRACTION_MODEL,
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            limit=args.limit,
            resume_batch_id=args.resume,
        )
        return

    def extractor(document_text: str) -> EarningsResult:
        return extract_earnings(document_text, client=client, system_prompt=system_prompt)

    run(
        backend,
        extractor,
        model=EXTRACTION_MODEL,
        prompt_version=prompt_version,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
