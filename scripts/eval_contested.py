"""Show failing fields from the latest eval run, grouped by ticker and field.

Flags cases most likely to be golden label errors:
- Model returns a non-null value that differs from golden (possible wrong label)
- Model consistently returns the same wrong value across multiple docs for same ticker
- Null/non-null flips (model says null, golden says value, or vice versa)
"""
from dotenv import load_dotenv
load_dotenv()
from google.cloud import bigquery
from asx_engine.config import load_settings
from collections import defaultdict

V2_RUN = "59599c9f-7a10-43c8-bc32-e5a8d8826d19"

s = load_settings()
bq = bigquery.Client(project=s.gcp_project)

rows = list(bq.query_and_wait(
    "SELECT ticker, field_name, subfield, golden_value, extracted_value, "
    "value_match, source_quote, content_hash "
    f"FROM `{s.gcp_project}.{s.bq_dataset}.eval_field_results` "
    f"WHERE eval_run_id = '{V2_RUN}' AND value_match = FALSE "
    "ORDER BY ticker, field_name, subfield"
))

# Group by ticker+field+subfield to spot consistent model disagreement
groups = defaultdict(list)
for r in rows:
    key = (r["ticker"], r["field_name"], r["subfield"])
    groups[key].append(r)

print(f"{'TICKER':<5} {'FIELD':<25} {'GOLDEN':>18}  {'EXTRACTED':>18}  NOTE")
print("-" * 85)

for (ticker, field, subfield), cases in sorted(groups.items()):
    extracted_vals = set(str(r["extracted_value"]) for r in cases)
    golden_vals    = set(str(r["golden_value"]) for r in cases)

    # Classify the disagreement type
    if all(r["golden_value"] is None for r in cases):
        note = "MODEL NON-NULL, GOLDEN NULL"
    elif all(r["extracted_value"] is None for r in cases):
        note = "MODEL NULL, GOLDEN NON-NULL"
    elif len(extracted_vals) == 1:
        note = f"CONSISTENT WRONG ({len(cases)} docs)"
    else:
        note = f"INCONSISTENT ({len(cases)} docs)"

    for r in cases:
        print(
            f"{ticker:<5} {field}.{subfield:<20} "
            f"{str(r['golden_value']):>18}  {str(r['extracted_value']):>18}  {note}"
        )
    print()
