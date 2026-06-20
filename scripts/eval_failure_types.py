"""Categorise v3 failures: wrong value vs missed value vs hallucinated value."""
from dotenv import load_dotenv
load_dotenv()
from google.cloud import bigquery
from asx_engine.config import load_settings

V3_RUN = "f42cc860-e460-418b-af0e-a8268fb56c2a"  # Haiku v3 + corrected ANZ labels

s = load_settings()
bq = bigquery.Client(project=s.gcp_project)

rows = list(bq.query_and_wait(
    "SELECT ticker, field_name, subfield, golden_value, extracted_value, reporting_currency "
    f"FROM `{s.gcp_project}.{s.bq_dataset}.eval_field_results` "
    f"WHERE eval_run_id = '{V3_RUN}' AND value_match = FALSE "
    "ORDER BY ticker, field_name, subfield"
))

wrong_value   = []  # both non-null, different numbers — FAKE DATA
model_null    = []  # golden has value, model said null — MISSING DATA
hallucinated  = []  # golden null, model extracted something — FAKE DATA

for r in rows:
    g = r["golden_value"]
    e = r["extracted_value"]
    if g is not None and e is not None:
        wrong_value.append(r)
    elif g is not None and e is None:
        model_null.append(r)
    elif g is None and e is not None:
        hallucinated.append(r)

total_fields = 22 * 8  # 22 docs × 8 fields
total_failures = len(rows)

print(f"Total fields scored: {total_fields}")
print(f"Total failures:      {total_failures} ({total_failures/total_fields:.1%})")
print()

print(f"MISSING DATA  (model null, golden has value): {len(model_null):>3}  ({len(model_null)/total_fields:.1%})  — gaps, not lies")
print(f"WRONG VALUE   (both non-null, disagree):      {len(wrong_value):>3}  ({len(wrong_value)/total_fields:.1%})  — *** FAKE DATA ***")
print(f"HALLUCINATED  (golden null, model non-null):  {len(hallucinated):>3}  ({len(hallucinated)/total_fields:.1%})  — *** FAKE DATA ***")
print()

if wrong_value:
    print("--- WRONG VALUES ---")
    for r in wrong_value:
        print(f"  {r['ticker']:4s} {r['field_name']}.{r['subfield']:7s}  [{r['reporting_currency']}]  golden={r['golden_value']:>15s}  extracted={r['extracted_value']:>15s}")
    print()

if hallucinated:
    print("--- HALLUCINATED (golden=null, model extracted) ---")
    for r in hallucinated:
        print(f"  {r['ticker']:4s} {r['field_name']}.{r['subfield']:7s}  [{r['reporting_currency']}]  extracted={r['extracted_value']}")
    print()

if model_null:
    print("--- MISSING (model=null, golden has value) ---")
    for r in model_null:
        print(f"  {r['ticker']:4s} {r['field_name']}.{r['subfield']:7s}  [{r['reporting_currency']}]  golden={r['golden_value']}")
