"""Role extraction over appointment/cessation notices (Batches API).

    uv run python -m asx_engine.extraction.roles_job --confirm
    uv run python -m asx_engine.extraction.roles_job --resume BATCH_ID

Corpus: parsed-good announcements whose headline matches the P0 appointment
pattern. Purpose: primary-document verification of the LLM-knowledge role
enrichment (2026-07-10) behind the exec-seller verdict. Same submit/poll/
collect/--resume shape and the same batched+backoff BQ writes as the other
extraction jobs; records land in extraction_records under
prompt_version=director_roles_v1.
"""

import argparse
import sys
import time
from pathlib import Path

import anthropic
import google.cloud.storage as storage
import structlog
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv
from google.cloud import bigquery
from pydantic import TypeAdapter, ValidationError

from asx_engine.config import load_settings
from asx_engine.extraction.earnings import EXTRACTION_MODEL, MAX_OUTPUT_TOKENS, supports_thinking
from asx_engine.extraction.job import EXTRACTIONS_TABLE, load_rows_with_backoff
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument, ParseQuality
from asx_engine.schemas import ExtractionRecord, utc_now
from asx_engine.schemas.roles import RolesResult

log = structlog.get_logger()

PROMPT_PATH = Path("prompts/director_roles_v1.md")
_APPOINTMENT_SQL = (
    r"(?i)appendix\s*3[xz]|appointment of|resignation of (a )?director"
    r"|(initial|final) director.s interest|ceases (as|to be) (a )?director"
    r"|(managing director|ceo|chief executive|chairman|director) "
    r"(appointment|succession|transition|retirement)"
)
FLUSH_EVERY = 250


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--resume", metavar="BATCH_ID", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    load_dotenv()
    settings = load_settings()
    prompt_version, system_prompt = PROMPT_PATH.stem, PROMPT_PATH.read_text(encoding="utf-8")
    bq = bigquery.Client(project=settings.gcp_project)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    extractions_id = f"{dataset}.{EXTRACTIONS_TABLE}"
    schema_bq = bq.get_table(extractions_id).schema
    bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)

    pending_q = f"""
    SELECT DISTINCT p.content_hash FROM `{dataset}.parsed_documents` p
    JOIN `{dataset}.announcements` a USING (content_hash)
    WHERE p.parser_version=@pv AND p.quality=@q
      AND REGEXP_CONTAINS(a.headline, @pattern)
      AND p.content_hash NOT IN (
        SELECT content_hash FROM `{extractions_id}`
        WHERE model=@model AND prompt_version=@promptv)
    """  # noqa: S608
    cfg = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("pv", "STRING", PARSER_VERSION),
            bigquery.ScalarQueryParameter("q", "STRING", ParseQuality.GOOD.value),
            bigquery.ScalarQueryParameter("pattern", "STRING", _APPOINTMENT_SQL),
            bigquery.ScalarQueryParameter("model", "STRING", EXTRACTION_MODEL),
            bigquery.ScalarQueryParameter("promptv", "STRING", prompt_version),
        ]
    )
    pending = sorted(r["content_hash"] for r in bq.query_and_wait(pending_q, job_config=cfg))
    if args.limit:
        pending = pending[: args.limit]
    done: set[str] = set()

    client = anthropic.Anthropic()
    if args.resume:
        batch = client.messages.batches.retrieve(args.resume)
        # Anything flushed before a crash must not be re-written.
        done = {
            r["content_hash"]
            for r in bq.query_and_wait(
                f"SELECT content_hash FROM `{extractions_id}` "  # noqa: S608
                f"WHERE model='{EXTRACTION_MODEL}' AND prompt_version='{prompt_version}'"
            )
        }
        log.info("roles.batch.resumed", batch_id=batch.id, status=batch.processing_status)
    else:
        est = len(pending) * (3 * 450 * 0.5 + 300 * 2.5) / 1e6
        if not args.confirm:
            print(f"would extract roles from {len(pending)} documents (~${est:.0f}). --confirm to run.")
            return
        if not pending:
            print("nothing pending")
            return
        schema = anthropic.transform_schema(TypeAdapter(RolesResult).json_schema())

        def load_text(h: str) -> str:
            blob = bucket.blob(f"parsed/{PARSER_VERSION}/{h}.json")
            return ParsedDocument.model_validate_json(bytes(blob.download_as_bytes())).text()

        requests = []
        for h in pending:
            params: MessageCreateParamsNonStreaming = {
                "model": EXTRACTION_MODEL,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "system": system_prompt,
                "messages": [{"role": "user", "content": load_text(h)}],
                "output_config": {"format": {"type": "json_schema", "schema": schema}},
            }
            if supports_thinking(EXTRACTION_MODEL):
                params["thinking"] = {"type": "adaptive"}
            requests.append(Request(custom_id=h, params=params))
        batch = client.messages.batches.create(requests=requests)
        log.info("roles.batch.submitted", batch_id=batch.id, requests=len(requests),
                 resume_hint=f"--resume {batch.id}")

    while batch.processing_status != "ended":
        time.sleep(30)
        batch = client.messages.batches.retrieve(batch.id)
        log.info("roles.batch.status", status=batch.processing_status,
                 succeeded=batch.request_counts.succeeded, errored=batch.request_counts.errored)

    buffer: list[dict[str, object]] = []
    stored = failed = 0

    def flush() -> None:
        nonlocal buffer
        if buffer:
            load_rows_with_backoff(bq, buffer, extractions_id, list(schema_bq))
            log.info("roles.records_flushed", records=len(buffer))
            buffer = []

    for result in client.messages.batches.results(batch.id):
        h = result.custom_id
        if h in done:
            continue
        if result.result.type != "succeeded":
            failed += 1
            continue
        message = result.result.message
        text = next((b.text for b in message.content if b.type == "text"), None)
        if message.stop_reason != "end_turn" or text is None:
            failed += 1
            continue
        try:
            payload = RolesResult.model_validate_json(text)
        except ValidationError:
            failed += 1
            continue
        record = ExtractionRecord[RolesResult](
            content_hash=h, model=EXTRACTION_MODEL, prompt_version=prompt_version,
            extracted_at=utc_now(), payload=payload,
        )
        row = record.model_dump(mode="json", exclude={"payload"})
        row["payload"] = record.payload.model_dump_json()
        buffer.append(row)
        if len(buffer) >= FLUSH_EVERY:
            flush()
        stored += 1
        log.info("roles.stored", content_hash=h, events=len(payload.events))
    flush()
    log.info("roles.done", stored=stored, failed=failed)


if __name__ == "__main__":
    main()
