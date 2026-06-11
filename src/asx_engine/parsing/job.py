"""Parse job: run the PDF parser over every stored-but-unparsed announcement.

    uv run python -m asx_engine.parsing.job

Idempotent and resumable by construction: pending work is the set difference
between announcements in BigQuery and parsed_documents rows for the CURRENT
parser version. A crash mid-run loses nothing; a re-run picks up where it
left off; bumping PARSER_VERSION naturally re-parses everything while
leaving the old version's records intact.

Storage mirrors ingestion:
- full text -> GCS parsed/{parser_version}/{content_hash}.json
- flags row -> BigQuery parsed_documents (no text — BQ is for querying
  "which documents parsed badly", not for serving text)
"""

from dataclasses import dataclass, field
from typing import Protocol

import google.cloud.storage as storage
import structlog
from google.cloud import bigquery

from asx_engine.config import Settings, load_settings
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument, parse_pdf
from asx_engine.schemas import utc_now

log = structlog.get_logger()

PARSED_TABLE = "parsed_documents"


class ParseBackend(Protocol):
    """Storage capabilities run() needs; faked structurally in tests."""

    def announcement_hashes(self) -> set[str]: ...
    def parsed_hashes(self, parser_version: str) -> set[str]: ...
    def load_pdf(self, content_hash: str) -> bytes: ...
    def save(self, document: ParsedDocument) -> None: ...


@dataclass
class ParseSummary:
    parsed: list[ParsedDocument] = field(default_factory=list)
    already_parsed: int = 0


def run(backend: ParseBackend, *, parser_version: str = PARSER_VERSION) -> ParseSummary:
    summary = ParseSummary()
    announced = backend.announcement_hashes()
    done = backend.parsed_hashes(parser_version)
    pending = sorted(announced - done)
    summary.already_parsed = len(announced & done)
    log.info(
        "parse.start",
        parser_version=parser_version,
        announcements=len(announced),
        already_parsed=summary.already_parsed,
        pending=len(pending),
    )

    for content_hash in pending:
        document = parse_pdf(
            backend.load_pdf(content_hash), content_hash=content_hash, parsed_at=utc_now()
        )
        backend.save(document)
        summary.parsed.append(document)
        log.info(
            "parse.stored",
            content_hash=content_hash,
            pages=document.page_count,
            empty_pages=document.empty_page_count,
            chars=document.total_chars,
            quality=document.quality.value,
        )

    quality_counts: dict[str, int] = {}
    for document in summary.parsed:
        quality_counts[document.quality.value] = quality_counts.get(document.quality.value, 0) + 1
    log.info("parse.done", parsed=len(summary.parsed), **quality_counts)
    return summary


class GcpParseBackend:
    """The real backend: PDFs and parsed text in GCS, flags in BigQuery."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)
        self._bq = bigquery.Client(project=settings.gcp_project)
        self._announcements_id = f"{settings.gcp_project}.{settings.bq_dataset}.announcements"
        self._parsed_id = f"{settings.gcp_project}.{settings.bq_dataset}.{PARSED_TABLE}"
        self._parsed_schema = self._bq.get_table(self._parsed_id).schema

    def announcement_hashes(self) -> set[str]:
        query = f"SELECT content_hash FROM `{self._announcements_id}`"  # noqa: S608 - own table
        return {row["content_hash"] for row in self._bq.query_and_wait(query)}

    def parsed_hashes(self, parser_version: str) -> set[str]:
        query = (
            f"SELECT content_hash FROM `{self._parsed_id}` "  # noqa: S608 - own table
            "WHERE parser_version = @parser_version"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("parser_version", "STRING", parser_version)
            ]
        )
        return {
            row["content_hash"] for row in self._bq.query_and_wait(query, job_config=job_config)
        }

    def load_pdf(self, content_hash: str) -> bytes:
        data = self._bucket.blob(f"raw/{content_hash}.pdf").download_as_bytes()
        return bytes(data)

    def save(self, document: ParsedDocument) -> None:
        # Text first, row second — same crash-safety reasoning as ingestion:
        # a missing BQ row just means re-parse; a row without text would lie.
        blob = self._bucket.blob(f"parsed/{document.parser_version}/{document.content_hash}.json")
        blob.upload_from_string(document.model_dump_json(), content_type="application/json")
        row = document.model_dump(mode="json", exclude={"pages"})
        job_config = bigquery.LoadJobConfig(
            schema=self._parsed_schema,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        self._bq.load_table_from_json([row], self._parsed_id, job_config=job_config).result()


def main() -> None:
    settings = load_settings()
    run(GcpParseBackend(settings))


if __name__ == "__main__":
    main()
