"""Bulk backfill: the whole universe, months of history, one resumable crawl.

    # Dry-run first: listings only, no PDFs, prints what a real run would fetch
    uv run python -m asx_engine.ingestion.backfill --filter 3y --dry-run

    # Phase 1 (decided 2026-07-06): 24 months of director trades only
    uv run python -m asx_engine.ingestion.backfill --filter 3y

    # Phase 2: everything non-excluded (taxonomy: collect broad, extract narrow)
    uv run python -m asx_engine.ingestion.backfill --filter broad

This is the bulk sibling of ingestion.manual — same client, same store, same
BQ-keyed idempotency — with the properties a multi-hour crawl needs and the
hand-curation tool deliberately lacks:

- **No per-ticker cap.** The universe file and the date cutoff are the bounds.
- **Error isolation.** One ticker's parse drift must not kill hour five of a
  crawl: failures are logged, counted, reported at the end, and the ticker is
  simply retried on the next run (idempotency makes reruns free).
- **Resumable by construction.** Pending work is decided against BigQuery
  BEFORE any PDF request, so a crash resumes where it stopped; re-running
  after adding tickers to the universe file only fetches the difference.

Universe file: data/universe/*.csv (ticker,company,sector). Current file is
the Wikipedia S&P/ASX 200 table (as of 2026-04-05) — no free machine-readable
ASX 300 source exists; the +100 small ordinaries top-up happens when EODHD
(Q2) provides constituents, as a plain rerun with a fuller file. Known and
accepted: today's constituents ≠ historical constituents (survivorship);
EODHD's historical membership fixes the *event-study universe* in Q2 — this
crawl is collection, not the point-in-time record.
"""

import argparse
import csv
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import structlog
from dotenv import load_dotenv

from asx_engine.config import load_settings
from asx_engine.ingestion.asx_client import AsxClient, HtmlAnnouncement
from asx_engine.ingestion.director_trades_ingest import is_3y_candidate
from asx_engine.ingestion.manual import AnnouncementSource
from asx_engine.ingestion.store import AnnouncementStore, build_announcement
from asx_engine.schemas import Announcement, utc_now

log = structlog.get_logger()

DEFAULT_UNIVERSE = Path("data/universe/asx200_2026-04-05_wikipedia.csv")

# Admin noise per the CLAUDE.md taxonomy exclude list. Everything NOT matching
# is collected under --filter broad ("collect broad, extract narrow").
_ADMIN_NOISE = re.compile(
    r"change of (registered office|address|registry|share registry)"
    r"|constitution"
    r"|notice of (annual general meeting|meeting|agm)"
    r"|proxy form"
    r"|results of (annual general )?meeting"
    r"|cleansing (notice|statement)"
    r"|section 708A?"
    r"|corporate governance statement"
    r"|change of (company )?secretary",
    re.IGNORECASE,
)


def is_broad_candidate(listed: HtmlAnnouncement) -> bool:
    return not _ADMIN_NOISE.search(listed.headline)


# P0 (priority crawl, decided 2026-07-09): the two categories that unblock
# existing findings. Results filings give exact earnings dates (the
# reporting-season confound verdict + PR-001's season split); appointment/
# cessation notices state director roles (the exec-seller hypothesis).
_RESULTS_HEADLINE = re.compile(
    r"appendix\s*4[cde]|half[\s-]*year|full[\s-]*year|annual\s+report"
    r"|preliminary final|results (announcement|presentation|release)"
    r"|\bFY\d{2}.{0,12}results|results for announcement",
    re.IGNORECASE,
)
_APPOINTMENT_HEADLINE = re.compile(
    r"appendix\s*3[xz]|appointment of|resignation of (a )?director"
    r"|(initial|final) director.s interest|ceases (as|to be) (a )?director"
    r"|(managing director|ceo|chief executive|chairman|director) "
    r"(appointment|succession|transition|retirement)",
    re.IGNORECASE,
)
_RESULTS_FALSE_POSITIVES = re.compile(
    r"results of (annual general )?meeting|resignation of auditor", re.IGNORECASE
)


def is_p0_candidate(listed: HtmlAnnouncement) -> bool:
    if _RESULTS_FALSE_POSITIVES.search(listed.headline):
        return False
    # Results must carry the price-sensitive flag (real results filings do;
    # presentations reposts often don't matter). Appointments usually are NOT
    # flagged, so they pass on headline alone.
    if listed.price_sensitive and _RESULTS_HEADLINE.search(listed.headline):
        return True
    return bool(_APPOINTMENT_HEADLINE.search(listed.headline))


# Guidance vertical (decided 2026-07-17): trading updates, guidance changes and
# profit warnings — the expectations layer ES-1 showed the market actually
# trades. Deliberately headline-only (no PS gate): guidance WITHDRAWALS and
# quiet downgrades are sometimes unflagged, and flag-vs-content divergence is
# itself a finding.
_GUIDANCE_HEADLINE = re.compile(
    r"guidance|trading update|market update|profit warning|earnings update"
    r"|trading performance|outlook (update|statement)"
    r"|(upgrade|downgrade)s? (to )?(fy|hy|earnings|profit|guidance)"
    r"|business update|operational update",
    re.IGNORECASE,
)


def is_guidance_candidate(listed: HtmlAnnouncement) -> bool:
    return bool(_GUIDANCE_HEADLINE.search(listed.headline))


FILTERS = {
    "3y": is_3y_candidate,
    "broad": is_broad_candidate,
    "p0": is_p0_candidate,
    "guidance": is_guidance_candidate,
}

# Rows buffered before one BigQuery load job. Sized for the quota (1,500 load
# jobs/table/day — the 2026-07-06 run tripped it doing one job per row): a
# full broad crawl at 250 rows/flush is ~400 jobs, comfortably under. The
# tradeoff is crash exposure — at most one bufferful of rows re-fetched from
# ASX on the next run (~12 minutes of crawl), which idempotency absorbs.
FLUSH_EVERY = 250


class BulkStore(Protocol):
    """Storage a bulk crawl needs: PDFs immediately, rows batched."""

    def existing_announcement_ids(self) -> set[str]: ...
    def save_pdf(self, announcement: Announcement, pdf_bytes: bytes) -> None: ...
    def append_rows(self, announcements: list[Announcement]) -> None: ...


@dataclass
class BackfillSummary:
    ingested: int = 0
    would_ingest: int = 0  # dry-run counterpart of ingested
    skipped_existing: int = 0
    filtered_out: int = 0
    before_cutoff: int = 0
    failed_tickers: dict[str, str] = field(default_factory=dict)


def load_universe(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        tickers = [row["ticker"].strip().upper() for row in csv.DictReader(f)]
    if not tickers:
        raise ValueError(f"universe file {path} contains no tickers")
    return tickers


def years_covering(cutoff: datetime, now: datetime) -> list[int]:
    """Calendar years the listing endpoint must be asked for, oldest first."""
    return list(range(cutoff.year, now.year + 1))


def run(
    source: AnnouncementSource,
    store: BulkStore,
    tickers: list[str],
    *,
    months: int,
    candidate_fn: Callable[[HtmlAnnouncement], bool],
    dry_run: bool,
    now: datetime | None = None,
    flush_every: int = FLUSH_EVERY,
) -> BackfillSummary:
    summary = BackfillSummary()
    now = now or utc_now()
    # ~30.44 days/month: a cutoff, not an accounting boundary — nothing
    # downstream depends on it landing on a month edge.
    cutoff = now - timedelta(days=months * 30.44)
    years = years_covering(cutoff, now)
    existing = store.existing_announcement_ids()
    log.info(
        "backfill.start",
        tickers=len(tickers),
        months=months,
        cutoff=cutoff.date().isoformat(),
        years=years,
        existing_records=len(existing),
        dry_run=dry_run,
    )

    # PDFs upload as they arrive; metadata rows buffer here and flush as ONE
    # load job per flush_every rows (see FLUSH_EVERY for the quota arithmetic).
    row_buffer: list[Announcement] = []

    def flush() -> None:
        if row_buffer:
            store.append_rows(row_buffer)
            log.info("backfill.rows_flushed", rows=len(row_buffer))
            row_buffer.clear()

    for position, ticker in enumerate(tickers, 1):
        try:
            kept: list[HtmlAnnouncement] = []
            fetched = 0
            for year in years:
                listings = source.get_announcements_html(ticker, year=year)
                fetched += len(listings)
                for listed in listings:
                    if listed.announced_at.astimezone(UTC) < cutoff:
                        summary.before_cutoff += 1
                        continue
                    if not candidate_fn(listed):
                        summary.filtered_out += 1
                        continue
                    kept.append(listed)

            new = [a for a in kept if a.ids_id not in existing]
            summary.skipped_existing += len(kept) - len(new)
            log.info(
                "backfill.ticker",
                ticker=ticker,
                position=f"{position}/{len(tickers)}",
                fetched=fetched,
                kept=len(kept),
                new=len(new),
            )
            if dry_run:
                summary.would_ingest += len(new)
                continue

            for listed in new:
                if listed.ids_id in existing:
                    # Same idsId listed under two years within this run — the
                    # `new` list was computed before fetching began.
                    continue
                pdf_url, pdf_bytes = source.fetch_pdf(listed.ids_id)
                announcement = build_announcement(
                    listed,
                    ticker=ticker,
                    pdf_url=pdf_url,
                    pdf_bytes=pdf_bytes,
                    ingested_at=utc_now(),
                )
                store.save_pdf(announcement, pdf_bytes)
                row_buffer.append(announcement)
                if len(row_buffer) >= flush_every:
                    flush()
                # Guard against the same PDF listed under two tickers/years
                # within one run — BQ state only covers previous runs.
                existing.add(listed.ids_id)
                summary.ingested += 1
                log.info(
                    "backfill.stored",
                    ticker=ticker,
                    ids_id=listed.ids_id,
                    headline=listed.headline,
                    announced_at=listed.announced_at.isoformat(),
                )
        except Exception as exc:  # noqa: BLE001 — isolation is the point
            # One ticker must not kill hour five of a crawl. The failure is
            # loud in the log and the summary; the rerun retries it for free.
            summary.failed_tickers[ticker] = f"{type(exc).__name__}: {exc}"
            log.error("backfill.ticker_failed", ticker=ticker, error=str(exc))

    flush()
    log.info(
        "backfill.done",
        ingested=summary.ingested,
        would_ingest=summary.would_ingest,
        skipped_existing=summary.skipped_existing,
        filtered_out=summary.filtered_out,
        before_cutoff=summary.before_cutoff,
        failed=len(summary.failed_tickers),
    )
    for ticker, error in summary.failed_tickers.items():
        log.warning("backfill.failed_ticker", ticker=ticker, error=error)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers-file", type=Path, default=DEFAULT_UNIVERSE, help="universe CSV (ticker column)"
    )
    parser.add_argument("--months", type=int, default=24, help="history window in months")
    parser.add_argument(
        "--filter",
        choices=sorted(FILTERS),
        required=True,
        help="3y: Appendix 3Y only; broad: everything non-excluded",
    )
    parser.add_argument("--dry-run", action="store_true", help="listings only, fetch no PDFs")
    parser.add_argument(
        "--limit-tickers", type=int, default=None, help="crawl only the first N tickers (testing)"
    )
    args = parser.parse_args()

    load_dotenv()
    settings = load_settings()
    tickers = load_universe(args.tickers_file)
    if args.limit_tickers is not None:
        tickers = tickers[: args.limit_tickers]
    store = AnnouncementStore(settings)
    with AsxClient(
        user_agent=settings.user_agent,
        request_interval_seconds=settings.request_interval_seconds,
    ) as client:
        run(
            client,
            store,
            tickers,
            months=args.months,
            candidate_fn=FILTERS[args.filter],
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
