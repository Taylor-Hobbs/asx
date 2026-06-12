"""Generate golden-label stub files for every stored announcement.

    uv run python scripts/make_golden_stubs.py

One JSON stub per document in golden/labels/, reference keys pre-filled from
BigQuery, every label value null, status "unlabeled". NEVER overwrites an
existing file — hand labels are the most expensive artifact in this project
and no script gets to destroy them. Filenames use the Sydney-local
announcement date (what the ASX website displays), so others can find the
filing from public sources.
"""

import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from google.cloud import bigquery

from asx_engine.config import load_settings
from asx_engine.schemas import GoldenEarningsLabels, GoldenLabel, GoldenMetric

LABELS_DIR = Path("golden/labels")
SYDNEY = ZoneInfo("Australia/Sydney")


def empty_labels() -> GoldenEarningsLabels:
    metric = GoldenMetric(current=None, prior=None)
    return GoldenEarningsLabels(
        period=None,
        revenue_aud=metric,
        npat_aud=metric,
        eps_cents=metric,
        dividend_cents=metric,
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    query = f"""
    SELECT ticker, announcement_id, announced_at, headline, content_hash
    FROM `{dataset}.announcements` ORDER BY ticker, announced_at
    """  # noqa: S608 - own table
    created = existing = 0
    for row in bq.query_and_wait(query):
        sydney_date = row["announced_at"].astimezone(SYDNEY).date()
        path = LABELS_DIR / f"{row['ticker']}_{sydney_date}_{row['announcement_id']}.json"
        if path.exists():
            existing += 1
            continue
        stub = GoldenLabel(
            ticker=row["ticker"],
            announcement_id=row["announcement_id"],
            announced_at=row["announced_at"],
            headline=row["headline"],
            content_hash=row["content_hash"],
            labels=empty_labels(),
        )
        path.write_text(stub.model_dump_json(indent=2) + "\n", encoding="utf-8")
        created += 1
        print(f"created  {path.name}")

    print(f"\n{created} stubs created, {existing} already existed (untouched)")


if __name__ == "__main__":
    main()
