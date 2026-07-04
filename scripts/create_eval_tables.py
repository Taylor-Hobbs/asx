"""Create the eval BQ tables from their schema files.

    uv run python scripts/create_eval_tables.py

Safe to re-run: skips tables that already exist.
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from google.api_core.exceptions import Conflict
from google.cloud import bigquery

from asx_engine.config import load_settings

TABLES = {
    "eval_runs": Path("infra/bq/eval_runs.schema.json"),
    "eval_field_results": Path("infra/bq/eval_field_results.schema.json"),
}


def _field(f: dict) -> bigquery.SchemaField:
    """Build a SchemaField, recursing into nested RECORD fields."""
    return bigquery.SchemaField(
        name=f["name"],
        field_type=f["type"],
        mode=f.get("mode", "NULLABLE"),
        description=f.get("description", ""),
        fields=[_field(sub) for sub in f.get("fields", [])],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="drop and recreate existing tables")
    parser.add_argument("--table", metavar="NAME", help="only act on this table (default: all)")
    args = parser.parse_args()

    load_dotenv()
    settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)

    tables = {args.table: TABLES[args.table]} if args.table else TABLES
    for table_name, schema_path in tables.items():
        table_id = f"{settings.gcp_project}.{settings.bq_dataset}.{table_name}"
        schema_json = json.loads(schema_path.read_text())
        schema = [_field(f) for f in schema_json]
        table = bigquery.Table(table_id, schema=schema)
        try:
            bq.create_table(table)
            print(f"created  {table_id}")
        except Conflict:
            if args.recreate:
                bq.delete_table(table_id)
                bq.create_table(table)
                print(f"recreated {table_id}")
            else:
                print(f"exists   {table_id}")


if __name__ == "__main__":
    main()
