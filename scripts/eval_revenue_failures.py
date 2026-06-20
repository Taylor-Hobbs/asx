"""Query revenue/NPAT field results from the Haiku eval run."""
from dotenv import load_dotenv
load_dotenv()
from google.cloud import bigquery
from asx_engine.config import load_settings

HAIKU_RUN = "c1a1bb62-af47-447f-9462-be9cad407149"

s = load_settings()
bq = bigquery.Client(project=s.gcp_project)

query = (
    "SELECT field_name, subfield, golden_value, extracted_value, value_match, ticker "
    "FROM `asx-scanner-499110.asx_engine.eval_field_results` "
    f"WHERE eval_run_id = '{HAIKU_RUN}' "
    "AND field_name IN ('revenue', 'npat') "
    "ORDER BY ticker, field_name, subfield"
)

rows = list(bq.query_and_wait(query))
print(f"{'':2s} {'ticker':4s} {'field':20s}  {'golden':>18s}  {'extracted':>18s}")
print("-" * 70)
for r in rows:
    match = "OK" if r["value_match"] else "XX"
    print(f"{match} {r['ticker']:4s} {r['field_name']}.{r['subfield']:7s}  {str(r['golden_value']):>18s}  {str(r['extracted_value']):>18s}")
