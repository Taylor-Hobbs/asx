"""Check what the model extracted for the three CSL docs in the last eval run."""
from google.cloud import bigquery
from asx_engine.config import load_settings

V3_RUN = "f42cc860-e460-418b-af0e-a8268fb56c2a"

CSL_HASHES = [
    ("03058873", "fae5b57f14b33d166fc565095a1e23ec9f3394e885afa13b917762758d281e59"),
    ("03058874", "76707846d52cbd919a64ccf6fa7677a28341b754b58164a5e912e4db625637dd"),
    ("03058876", "c66b7defd763266ca0908e797c36d9a2d7b71445b592f3b14b43443a0d212a87"),
]

s = load_settings()
bq = bigquery.Client(project=s.gcp_project)

for ann_id, h in CSL_HASHES:
    rows = list(bq.query_and_wait(
        f"""
        SELECT field_name, subfield, golden_value, extracted_value, value_match, source_quote
        FROM `{s.gcp_project}.{s.bq_dataset}.eval_field_results`
        WHERE eval_run_id = '{V3_RUN}'
          AND content_hash = '{h}'
        ORDER BY field_name, subfield
        """
    ))
    print(f"=== {ann_id} ({h[:12]}) ===")
    for r in rows:
        match_flag = "OK" if r["value_match"] else "FAIL"
        print(f"  [{match_flag}] {r['field_name']}.{r['subfield']:<8} golden={str(r['golden_value'] or 'null'):>15}  extracted={str(r['extracted_value'] or 'null'):>15}")
        if not r["value_match"] and r["source_quote"]:
            print(f"         quote: {r['source_quote'][:100]}")
    print()
