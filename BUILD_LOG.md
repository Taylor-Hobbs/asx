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

**Broke:** nothing yet — machine had no Python; installed uv + managed Python 3.12.13.

**Evals:** n/a (harness not built yet).

**Next:** Pydantic schemas — `Announcement` metadata model (content-hash keyed), then
`EarningsResult` / `GuidanceStatement` extraction models with confidence + source spans.
