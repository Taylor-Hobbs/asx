# Build Log

Short entry per session: what was built, what broke, what the evals showed.
Feeds the weekly public build-log posts. Newest entries first.

---

## 2026-06-11 — Repo setup + scaffold

**Built:**
- Repo created and published to github.com/Taylor-Hobbs/asx (CLAUDE.md v2, README, .gitignore).
- Python scaffold: uv-managed `pyproject.toml` (src/ layout, hatchling), `asx_engine` package
  with `ingestion` / `parsing` / `extraction` / `schemas` subpackages.
- `config.py` — typed settings via pydantic-settings (`ASX_`-prefixed env vars); required GCP
  fields fail loudly when missing; ingestion-etiquette defaults (3s request interval,
  identifiable User-Agent) live here.
- Tests for config (env loading, defaults, fail-loud validation).
- CI: GitHub Actions running ruff (lint + format), mypy --strict, pytest on every push/PR.
- Docs stubs: architecture.md, eval-methodology.md. Conventions READMEs in prompts/ and golden/.
- **Schemas:** `Announcement` (frozen, content-hash keyed, tz-aware UTC-normalized
  `announced_at`/`ingested_at` — naive datetimes rejected at construction).
  `SourcedField[T]` (PEP 695 generic; per-field confidence + verbatim source quote),
  `ReportedMetric` (current + prior comparative), `EarningsResult`, `GuidanceStatement`
  (direction enum, ordered-range validation, open-ended ranges allowed),
  `ExtractionRecord[PayloadT]` envelope binding payloads to (model, prompt version,
  timestamp) for eval reproducibility. Decimal for money, units in field names.
- 26 tests passing; mypy --strict clean.

**Broke:** nothing yet — machine had no Python; installed uv + managed Python 3.12.13.

**Evals:** n/a (harness not built yet).

**Decisions made:** confidence/source-span at field grain (matches per-field eval grain);
source spans as quoted text not char offsets (parser-version proof); units encoded in
field names (`revenue_aud`, `eps_cents`) with normalization at extraction time.

**Next:** GCP project setup (owner), then manual ingestion of ~20 hand-picked earnings
PDFs in the final schema shape.
