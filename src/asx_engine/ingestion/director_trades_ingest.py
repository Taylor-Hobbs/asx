"""Manual ingestion: Appendix 3Y director interest notices for the golden set.

Usage (from the repo root):

    # Dry-run first — see candidates before downloading anything:
    uv run python -m asx_engine.ingestion.director_trades_ingest BHP CBA WES --dry-run

    # Ingest (3 per ticker by default):
    uv run python -m asx_engine.ingestion.director_trades_ingest BHP CBA WES

    # Exclude false positives found in the dry-run:
    uv run python -m asx_engine.ingestion.director_trades_ingest BHP --exclude 03099693

Same pattern as ingestion.manual: dry-run first, hand-pick, then ingest.
Appendix 3Y filings are stored in the same GCS bucket and BQ table as earnings.
"""

import argparse
import re

import structlog
from dotenv import load_dotenv

from asx_engine.config import load_settings
from asx_engine.ingestion.asx_client import AsxClient, HtmlAnnouncement
from asx_engine.ingestion.manual import run
from asx_engine.ingestion.store import AnnouncementStore

log = structlog.get_logger()

_3Y_HEADLINE = re.compile(
    r"appendix\s*3y|change in director|director.s interest|directors interest",
    re.IGNORECASE,
)


def is_3y_candidate(listed: HtmlAnnouncement) -> bool:
    return bool(_3Y_HEADLINE.search(listed.headline))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually ingest Appendix 3Y director notices.")
    parser.add_argument("tickers", nargs="+", help="ASX tickers, e.g. BHP CBA WES")
    parser.add_argument("--year", type=int, default=2026, help="listing year (calendar)")
    parser.add_argument("--limit", type=int, default=3, help="max filings per ticker")
    parser.add_argument("--dry-run", action="store_true", help="list candidates, ingest nothing")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        metavar="IDS_ID",
        help="idsIds to skip (hand-pick after dry-run)",
    )
    args = parser.parse_args()

    load_dotenv()
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
            candidate_fn=is_3y_candidate,
        )


if __name__ == "__main__":
    main()
