"""Demo: fetch a live 3Y from ASX, parse it, extract director trades, print results.

    uv run python scripts/demo_director_trades.py
    uv run python scripts/demo_director_trades.py --ticker WES --year 2026
"""

import argparse
import hashlib
import sys
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

from asx_engine.config import load_settings
from asx_engine.extraction.director_trades import extract_director_trades, load_prompt
from asx_engine.ingestion.asx_client import AsxClient
from asx_engine.parsing.pdf import parse_pdf

_3Y_KEYWORDS = ("appendix 3y", "change in director", "director's interest", "directors interest")


def is_3y(headline: str) -> bool:
    h = headline.lower()
    return any(kw in h for kw in _3Y_KEYWORDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="BHP", help="ASX ticker (default: BHP)")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="calendar year")
    parser.add_argument("--limit", type=int, default=1, help="number of 3Y filings to extract")
    args = parser.parse_args()

    load_dotenv()
    settings = load_settings()
    prompt_version, system_prompt = load_prompt()
    client = anthropic.Anthropic()

    print(f"\nFetching {args.ticker} announcements for {args.year}...")
    with AsxClient(user_agent=settings.user_agent, request_interval_seconds=settings.request_interval_seconds) as asx:
        all_announcements = asx.get_announcements_html(args.ticker, year=args.year)
        filings_3y = [a for a in all_announcements if is_3y(a.headline)]

        if not filings_3y:
            print(f"No 3Y filings found for {args.ticker} in {args.year}.")
            sys.exit(0)

        print(f"Found {len(filings_3y)} Appendix 3Y filing(s). Processing first {args.limit}...\n")

        for filing in filings_3y[: args.limit]:
            print(f"  {filing.announced_at.strftime('%Y-%m-%d %H:%M')}  {filing.headline}")
            print(f"  idsId={filing.ids_id}")

            _, pdf_bytes = asx.fetch_pdf(filing.ids_id)
            content_hash = hashlib.sha256(pdf_bytes).hexdigest()
            parsed = parse_pdf(
                pdf_bytes,
                content_hash=content_hash,
                parsed_at=datetime.now(tz=timezone.utc),
            )
            print(f"  Parsed: {parsed.page_count} pages, {parsed.total_chars:,} chars, quality={parsed.quality}")

            print(f"  Extracting with {prompt_version}...")
            result = extract_director_trades(
                parsed.text(),
                client=client,
                system_prompt=system_prompt,
                model="claude-opus-4-8",
            )

            print(f"\n  {'Director':<28} {'Role':<30} {'Type':<12} {'Nature':<30} {'Qty':>12} {'Price':>8} {'Date':<12}")
            print("  " + "-" * 120)
            for trade in result.trades:
                print(
                    f"  {trade.director_name.value:<28} "
                    f"{(trade.director_role.value or ''):<30} "
                    f"{trade.trade_type.value:<12} "
                    f"{(trade.nature.value or ''):<30} "
                    f"{trade.quantity.value:>12,.0f} "
                    f"{str(trade.price_per_security.value or '—'):>8} "
                    f"{str(trade.trade_date.value):<12}"
                )
            print()


if __name__ == "__main__":
    main()
