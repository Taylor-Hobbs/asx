"""Generate golden-label stub files for ingested Appendix 3Y filings.

    uv run python scripts/make_director_trade_stubs.py

One JSON stub per 3Y filing in golden/director_trades/, pre-filled from BQ,
labels empty, status "unlabeled". NEVER overwrites existing files.

Queries the announcements table for rows whose headline matches the 3Y pattern —
the same filter used during ingestion.
"""

import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import load_settings
from asx_engine.schemas.director_trades import DirectorTradeGoldenLabel, GoldenDirectorTradesLabels

LABELS_DIR = Path("golden/director_trades")
SYDNEY = ZoneInfo("Australia/Sydney")

_3Y_HEADLINE = re.compile(
    r"appendix\s*3y|change in director|director.s interest|directors interest",
    re.IGNORECASE,
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    load_dotenv()
    settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    query = f"""
    SELECT ticker, announcement_id, announced_at, headline, content_hash
    FROM `{dataset}.announcements`
    ORDER BY ticker, announced_at
    """  # noqa: S608 - own table

    created = existing = skipped = 0
    for row in bq.query_and_wait(query):
        if not _3Y_HEADLINE.search(row["headline"]):
            skipped += 1
            continue
        sydney_date = row["announced_at"].astimezone(SYDNEY).date()
        path = LABELS_DIR / f"{row['ticker']}_{sydney_date}_{row['announcement_id']}.json"
        if path.exists():
            existing += 1
            continue
        stub = DirectorTradeGoldenLabel(
            ticker=row["ticker"],
            announcement_id=row["announcement_id"],
            announced_at=row["announced_at"],
            headline=row["headline"],
            content_hash=row["content_hash"],
            labels=GoldenDirectorTradesLabels(trades=[]),
        )
        path.write_text(stub.model_dump_json(indent=2) + "\n", encoding="utf-8")
        created += 1
        print(f"created  {path.name}")

    print(
        f"\n{created} stubs created, {existing} already existed (untouched), "
        f"{skipped} non-3Y skipped"
    )


if __name__ == "__main__":
    main()
