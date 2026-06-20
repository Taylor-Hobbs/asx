"""Find the correct content_hash for NAB 03089679 in extraction_records."""
from google.cloud import bigquery
from asx_engine.config import load_settings

s = load_settings()
bq = bigquery.Client(project=s.gcp_project)

# Get all hashes from v3 run
rows = list(bq.query_and_wait(
    f"SELECT DISTINCT content_hash FROM `{s.gcp_project}.{s.bq_dataset}.extraction_records` "
    "WHERE prompt_version = 'earnings_v3'"
))
all_hashes = [r["content_hash"] for r in rows]

bad = "a9048236fdc54c7bc3fca8f03445ba34e2ffee25c3d87b996116caef9c3e8d6a"
print(f"Bad hash:  {bad}  (len={len(bad)})")
print()

# Look for hashes that differ by exactly 1 character
candidates = []
for h in all_hashes:
    diffs = sum(a != b for a, b in zip(bad, h))
    if diffs <= 2:
        candidates.append((diffs, h))

candidates.sort()
print("Close matches in extraction_records:")
for diffs, h in candidates:
    print(f"  diff={diffs}  {h}")

# Also try prefix match
print()
print("Hashes starting with 'a904':")
for h in all_hashes:
    if h.startswith("a904"):
        print(f"  {h}")
