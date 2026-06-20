"""One-off migration: patch stored extraction_records payloads for the June 13 schema rename.

The 2026-06-13 schema change renamed revenue_aud/npat_aud -> revenue/npat and added
reporting_currency to EarningsResult. The 26 records already in BQ were extracted on
June 12 and still use the old field names. This script reads them, patches the JSON,
and overwrites the table.

    uv run python scripts/migrate_extraction_schema.py --dry-run   # preview only
    uv run python scripts/migrate_extraction_schema.py             # apply
"""

import argparse
import json

from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import load_settings


def migrate_payload(payload_str: str) -> tuple[str, bool]:
    """Rename old fields and add reporting_currency. Returns (new_payload, changed)."""
    data = json.loads(payload_str)
    changed = False

    if "revenue_aud" in data:
        data["revenue"] = data.pop("revenue_aud")
        changed = True

    if "npat_aud" in data:
        data["npat"] = data.pop("npat_aud")
        changed = True

    if "reporting_currency" not in data:
        data["reporting_currency"] = {
            "value": "AUD",
            "confidence": 1.0,
            "source_quote": None,
            "page": None,
        }
        changed = True

    return json.dumps(data), changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print changes, write nothing")
    args = parser.parse_args()

    load_dotenv()
    settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    table_id = f"{settings.gcp_project}.{settings.bq_dataset}.extraction_records"

    rows = list(bq.query_and_wait(f"SELECT * FROM `{table_id}`"))  # noqa: S608
    print(f"read {len(rows)} rows")

    migrated = []
    changed_count = 0
    for row in rows:
        new_payload, changed = migrate_payload(row["payload"])
        if changed:
            changed_count += 1
        record = dict(row)
        record["payload"] = new_payload
        # BQ returns Timestamp objects; convert to ISO string for load job
        record["extracted_at"] = record["extracted_at"].isoformat()
        migrated.append(record)

    print(f"{changed_count}/{len(rows)} payloads need migration")

    if args.dry_run:
        print("dry-run: no writes")
        return

    schema = bq.get_table(table_id).schema
    bq.load_table_from_json(
        migrated,
        table_id,
        job_config=bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    ).result()
    print("done — table overwritten with migrated payloads")


if __name__ == "__main__":
    main()
