"""Manual ingestion: hand-picked earnings announcements for the Q1 slice.

Usage (from the repo root):

    # See what WOULD be ingested, fetch nothing heavy:
    uv run python -m asx_engine.ingestion.manual BHP CBA CSL --limit 4 --dry-run

    # Actually ingest:
    uv run python -m asx_engine.ingestion.manual BHP CBA CSL --limit 4

Dry-run first is the intended workflow — the headline filter is a heuristic,
and CLAUDE.md says HAND-picked: a human curates the candidate list before any
PDF is downloaded.

Listings come from the announcements.do HTML page (full year per request) —
the source of truth for idsId; see the asx_client module docstring for why
the JSON endpoint cannot be used for this.

This module is deliberately separate from the future scheduled poller: it
takes explicit tickers and a per-ticker cap, and it never loops. The Cloud
Run job (later in Q1) will share the client and store, not this entry point.
"""

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import structlog

from asx_engine.config import load_settings
from asx_engine.ingestion.asx_client import AsxClient, HtmlAnnouncement
from asx_engine.ingestion.store import AnnouncementStore, build_announcement
from asx_engine.schemas import Announcement, utc_now

log = structlog.get_logger()

# Earnings-shaped headlines. Appendix 4D = half-year report, 4E = preliminary
# final report — the two statutory earnings filings on ASX. The rest catches
# results announcements that don't lead with the appendix number. A heuristic,
# refined by the dry-run curation step, not trusted blindly.
EARNINGS_HEADLINE = re.compile(
    r"appendix\s*4[de]|half[\s-]*year|full[\s-]*year|annual\s+report|results",
    re.IGNORECASE,
)


def is_earnings_candidate(listed: HtmlAnnouncement) -> bool:
    return listed.price_sensitive and bool(EARNINGS_HEADLINE.search(listed.headline))


class AnnouncementSource(Protocol):
    """What run() needs from a client.

    typing.Protocol is structural: AsxClient satisfies this without
    inheriting from it, and tests substitute a plain fake class. The
    dependency points at the *capability*, not the concrete class.
    """

    def get_announcements_html(self, ticker: str, *, year: int) -> list[HtmlAnnouncement]: ...
    def fetch_pdf(self, ids_id: str) -> tuple[str, bytes]: ...


class Store(Protocol):
    def existing_announcement_ids(self) -> set[str]: ...
    def save(self, announcement: Announcement, pdf_bytes: bytes) -> None: ...


@dataclass
class IngestSummary:
    ingested: list[Announcement] = field(default_factory=list)
    candidates: list[HtmlAnnouncement] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)


def run(
    source: AnnouncementSource,
    store: Store,
    tickers: list[str],
    *,
    year: int,
    per_ticker_limit: int,
    dry_run: bool,
    exclude: set[str] | None = None,
    candidate_fn: Callable[[HtmlAnnouncement], bool] | None = None,
) -> IngestSummary:
    summary = IngestSummary()
    excluded = exclude or set()
    existing = store.existing_announcement_ids()
    log.info(
        "ingest.start",
        tickers=tickers,
        year=year,
        existing_records=len(existing),
        excluded=len(excluded),
        dry_run=dry_run,
    )

    for ticker in tickers:
        announcements = source.get_announcements_html(ticker, year=year)
        # Exclusions apply BEFORE the limit so a dropped false positive
        # frees its slot for the next real candidate.
        is_candidate = candidate_fn or is_earnings_candidate
        candidates = [
            a for a in announcements if is_candidate(a) and a.ids_id not in excluded
        ][:per_ticker_limit]
        log.info(
            "ingest.candidates", ticker=ticker, fetched=len(announcements), kept=len(candidates)
        )

        for listed in candidates:
            if listed.ids_id in existing:
                # Idempotency: decided from BQ state BEFORE any PDF request,
                # so re-runs never re-fetch from ASX.
                summary.skipped_existing.append(listed.ids_id)
                log.info("ingest.skip_existing", ticker=ticker, ids_id=listed.ids_id)
                continue
            summary.candidates.append(listed)
            if dry_run:
                log.info(
                    "ingest.would_ingest",
                    ticker=ticker,
                    headline=listed.headline,
                    announced_at=listed.announced_at.isoformat(),
                    ids_id=listed.ids_id,
                    pages=listed.pages,
                    file_size=listed.file_size,
                )
                continue

            pdf_url, pdf_bytes = source.fetch_pdf(listed.ids_id)
            announcement = build_announcement(
                listed, ticker=ticker, pdf_url=pdf_url, pdf_bytes=pdf_bytes, ingested_at=utc_now()
            )
            store.save(announcement, pdf_bytes)
            summary.ingested.append(announcement)
            log.info(
                "ingest.stored",
                ticker=ticker,
                headline=listed.headline,
                content_hash=announcement.content_hash,
                pdf_url=pdf_url,
                bytes=len(pdf_bytes),
            )

    log.info(
        "ingest.done",
        ingested=len(summary.ingested),
        skipped_existing=len(summary.skipped_existing),
        dry_run=dry_run,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually ingest earnings announcements.")
    parser.add_argument("tickers", nargs="+", help="ASX tickers, e.g. BHP CBA CSL")
    parser.add_argument("--year", type=int, default=2026, help="listing year (calendar)")
    parser.add_argument("--limit", type=int, default=2, help="max filings per ticker")
    parser.add_argument("--dry-run", action="store_true", help="list candidates, ingest nothing")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        metavar="IDS_ID",
        help="idsIds to skip — the hand-picking mechanism after a dry-run",
    )
    args = parser.parse_args()

    settings = load_settings()
    store = AnnouncementStore(settings)
    with AsxClient(
        user_agent=settings.user_agent,
        request_interval_seconds=settings.request_interval_seconds,
    ) as client:
        run(
            client,
            store,
            [t.upper() for t in args.tickers],
            year=args.year,
            per_ticker_limit=args.limit,
            dry_run=args.dry_run,
            exclude=set(args.exclude),
        )


if __name__ == "__main__":
    main()
