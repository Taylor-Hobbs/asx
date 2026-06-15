# Infrastructure

GCP resources for the pipeline. Everything here was created with the commands
below (2026-06-11) so the environment is reproducible from scratch — no
console clicking required beyond project + billing creation.

**Project:** `asx-scanner-499110` · **Region:** `australia-southeast2` (Melbourne)

## Setup commands

```sh
# APIs
gcloud services enable storage.googleapis.com bigquery.googleapis.com \
  --project asx-scanner-499110

# Raw PDF bucket — PRIVATE, per the redistribution rule in CLAUDE.md.
# --public-access-prevention makes public ACLs impossible, not just absent;
# --uniform-bucket-level-access disables per-object ACLs entirely.
gcloud storage buckets create gs://asx-scanner-499110-raw-pdfs \
  --project asx-scanner-499110 \
  --location australia-southeast2 \
  --uniform-bucket-level-access \
  --public-access-prevention

# BigQuery dataset + announcements table (schema is versioned in this repo)
bq mk --dataset --location=australia-southeast2 \
  --description "ASX Announcement Intelligence Engine: metadata, extractions, eval runs" \
  asx-scanner-499110:asx_engine

bq mk --table \
  --description "Immutable announcement metadata, content-hash keyed" \
  asx-scanner-499110:asx_engine.announcements \
  infra/bq/announcements.schema.json

# Remaining tables follow the same pattern, schema from this repo:
bq mk --table asx-scanner-499110:asx_engine.parsed_documents   infra/bq/parsed_documents.schema.json
bq mk --table asx-scanner-499110:asx_engine.extraction_records infra/bq/extraction_records.schema.json

# Eval runs — one row per (model, prompt_version, dataset_version) scoring,
# field_scores as a repeated record so a field can be tracked across versions.
bq mk --table \
  --description "Per-field eval results vs the golden set; reproducible accuracy history" \
  asx-scanner-499110:asx_engine.eval_runs \
  infra/bq/eval_runs.schema.json
```

## Layout conventions

- **GCS:** raw PDFs at `gs://asx-scanner-499110-raw-pdfs/raw/{content_hash}.pdf` —
  hash-addressed storage makes "never re-fetch" a lookup, and an amended filing
  (different bytes) can never overwrite the original.
- **BigQuery:** table schemas live in `infra/bq/*.schema.json` and are applied via
  `bq mk`/`bq update` — schema changes are code-reviewed like everything else.
- **Local config:** `.env` (gitignored) carries `ASX_GCP_PROJECT`,
  `ASX_GCS_RAW_BUCKET`, `ASX_BQ_DATASET`. Auth is Application Default Credentials
  (`gcloud auth application-default login`) — no key files, nothing to leak.
