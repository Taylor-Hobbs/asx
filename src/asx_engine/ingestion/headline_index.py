"""Metadata-only ingestion: every headline for a universe, no PDFs.

    uv run python -m asx_engine.ingestion.headline_index \
        --tickers-file data/universe/asx300_combined_2026-07-14.csv --years 2024 2025 2026

One HTML-listing request per (ticker, year) — the listing already carries
headline, Sydney timestamp, price-sensitive flag, idsId, page count. At the
polite 3s interval a 306-ticker x 3-year sweep is ~50 minutes and stores the
COMPLETE announcement surface of the universe (~150k rows), which the
PDF-crawling backfill deliberately filters. Consumers: event autopsies
(headline timelines), the full flag-vs-content test (EX-1), results
calendars.

Kept apart from `announcements` on purpose: that table's primary key is the
SHA-256 of the PDF bytes, an invariant a metadata row cannot satisfy. This
table's key is (ticker, ids_id); the whole sweep is idempotent by
delete-and-reload per (ticker, year) — listings are snapshots, not events.
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog
from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import load_settings
from asx_engine.ingestion.asx_client import AsxClient
from asx_engine.ingestion.backfill import DEFAULT_UNIVERSE, load_universe

log = structlog.get_logger()

TABLE = "headline_index"
SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ids_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("announced_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("headline", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("price_sensitive", "BOOLEAN", mode="REQUIRED"),
    bigquery.SchemaField("pages", "INTEGER"),
    bigquery.SchemaField("listing_year", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
]
FLUSH_EVERY = 2000  # rows per load job — the 1,500 load-jobs/day quota lesson


def run(tickers: list[str], years: list[int]) -> None:
    settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    table_id = f"{settings.gcp_project}.{settings.bq_dataset}.{TABLE}"
    bq.create_table(bigquery.Table(table_id, schema=SCHEMA), exists_ok=True)

    # resumability: (ticker, year) pairs already loaded are skipped wholesale
    done = {
        (r.ticker, r.listing_year)
        for r in bq.query_and_wait(
            f"SELECT DISTINCT ticker, listing_year FROM `{table_id}`"  # noqa: S608
        )
    }
    log.info("headline_index.start", tickers=len(tickers), years=years, done_pairs=len(done))

    buffer: list[dict[str, object]] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        job = bq.load_table_from_json(
            buffer, table_id, job_config=bigquery.LoadJobConfig(schema=SCHEMA)
        )
        job.result()
        log.info("headline_index.rows_flushed", rows=len(buffer))
        buffer = []

    with AsxClient(
        user_agent=settings.user_agent,
        request_interval_seconds=settings.request_interval_seconds,
    ) as client:
        for i, ticker in enumerate(tickers, 1):
            for year in years:
                if (ticker, year) in done:
                    continue
                try:
                    listed = client.get_announcements_html(ticker, year=year)
                except Exception as exc:  # noqa: BLE001 - per-ticker isolation
                    log.warning(
                        "headline_index.ticker_failed",
                        ticker=ticker,
                        year=year,
                        error=str(exc)[:120],
                    )
                    continue
                now = datetime.now(UTC).isoformat()
                for a in listed:
                    buffer.append(
                        {
                            "ticker": ticker,
                            "ids_id": a.ids_id,
                            "announced_at": a.announced_at.isoformat(),
                            "headline": a.headline,
                            "price_sensitive": a.price_sensitive,
                            "pages": a.pages,
                            "listing_year": year,
                            "ingested_at": now,
                        }
                    )
                if len(buffer) >= FLUSH_EVERY:
                    flush()
            if i % 20 == 0:
                log.info("headline_index.progress", position=f"{i}/{len(tickers)}")
    flush()
    log.info("headline_index.done")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers-file", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--years", type=int, nargs="+", required=True)
    args = parser.parse_args()
    load_dotenv()
    run(load_universe(args.tickers_file), args.years)


if __name__ == "__main__":
    main()
