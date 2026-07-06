"""Persistence for ingested announcements: PDF bytes -> GCS, metadata -> BigQuery.

Layout (see infra/README.md):
- PDFs are hash-addressed: raw/{content_hash}.pdf. "Never re-fetch" becomes a
  key lookup, and an amended filing (different bytes, different hash) can
  never overwrite the original.
- Metadata rows are appended via BigQuery *load jobs*, not streaming inserts:
  load jobs are free and atomic, while streaming costs per-MB and parks rows
  in a buffer that blocks deletes for ~90 minutes. At our volumes a load job
  per batch is the right default.

Write order is PDF-then-row on purpose: if the BQ append fails midway, the
next run sees the announcement_id missing from BQ and retries; re-uploading
identical bytes to the same hash-addressed blob is harmless. The reverse
order could leave a metadata row pointing at a PDF we never stored.
"""

import hashlib
from datetime import datetime

import google.cloud.storage as storage
from google.cloud import bigquery

from asx_engine.config import Settings
from asx_engine.ingestion.asx_client import HtmlAnnouncement
from asx_engine.schemas import Announcement

ANNOUNCEMENTS_TABLE = "announcements"


def build_announcement(
    listed: HtmlAnnouncement,
    *,
    ticker: str,
    pdf_url: str,
    pdf_bytes: bytes,
    ingested_at: datetime,
) -> Announcement:
    """Convert a listed announcement + its PDF into our canonical record.

    The content hash is computed here, from the exact bytes we will store —
    the one place where "identity = bytes" is established. document_type is
    None: the HTML listing (the source of truth) has no type taxonomy.
    """
    return Announcement(
        content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
        announcement_id=listed.ids_id,
        ticker=ticker,
        headline=listed.headline,
        document_type=None,
        price_sensitive=listed.price_sensitive,
        document_url=pdf_url,
        announced_at=listed.announced_at,
        ingested_at=ingested_at,
    )


class AnnouncementStore:
    """GCS + BigQuery writer for announcement records."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._storage = storage.Client(project=settings.gcp_project)
        self._bucket = self._storage.bucket(settings.gcs_raw_bucket)
        self._bq = bigquery.Client(project=settings.gcp_project)
        self._table_id = f"{settings.gcp_project}.{settings.bq_dataset}.{ANNOUNCEMENTS_TABLE}"
        # Pin the load-job schema to the live table's schema instead of letting
        # BigQuery autodetect from one JSON row (autodetect guesses; we don't).
        self._table_schema = self._bq.get_table(self._table_id).schema

    def existing_announcement_ids(self) -> set[str]:
        """All announcement_ids already in BigQuery — the idempotency check.

        Queried once per run so "never re-fetch a stored PDF" is enforced
        BEFORE any network request to ASX, not after.
        """
        query = f"SELECT announcement_id FROM `{self._table_id}`"  # noqa: S608 - own table
        return {row["announcement_id"] for row in self._bq.query_and_wait(query)}

    def save(self, announcement: Announcement, pdf_bytes: bytes) -> None:
        """Store the PDF (if absent) then append the metadata row.

        One load job per call — right for hand-curated ingestion (dozens of
        documents), WRONG for bulk: BigQuery allows 1,500 load jobs per table
        per day, and the 2026-07-06 backfill run proved it the hard way (90
        tickers failed after the quota tripped at ~1,500 rows). Bulk callers
        must use save_pdf() + append_rows() and batch their appends.
        """
        self.save_pdf(announcement, pdf_bytes)
        self.append_rows([announcement])

    def save_pdf(self, announcement: Announcement, pdf_bytes: bytes) -> None:
        """Store the PDF bytes in GCS (if absent). No BigQuery write."""
        blob = self._bucket.blob(f"raw/{announcement.content_hash}.pdf")
        if not blob.exists():
            blob.upload_from_string(pdf_bytes, content_type="application/pdf")

    def append_rows(self, announcements: list[Announcement]) -> None:
        """Append many metadata rows in ONE load job.

        The batching exists to respect the 1,500 load-jobs/table/day quota: a
        full backfill crawl is a handful of jobs instead of thousands. Callers
        keep the PDF-then-row write order by uploading each PDF as it arrives
        (save_pdf) and flushing rows afterwards — a crash between the two
        leaves a hash-addressed blob without a row, which the next run's
        BQ-based idempotency check simply re-fetches and re-writes (harmless).
        """
        if not announcements:
            return
        # mode="json" serializes datetimes to ISO-8601 strings, which BQ's
        # JSON loader parses into TIMESTAMP.
        rows = [a.model_dump(mode="json") for a in announcements]
        job_config = bigquery.LoadJobConfig(
            schema=self._table_schema,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        self._bq.load_table_from_json(rows, self._table_id, job_config=job_config).result()
