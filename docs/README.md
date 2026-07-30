# docs/ — index

Reading order for a first-time visitor:

| Document | What it is | Status |
|---|---|---|
| [findings-2026-07-director-trades.md](findings-2026-07-director-trades.md) | **Start here.** The director-trades study: 4,743 trades, a signal found and dismantled, honest null conclusion | Complete (PR-001 forward test pending, ≥ 2027-07) |
| [eval-history.md](eval-history.md) | Every extraction benchmark, per prompt version, per field — including the regressions and the Opus head-to-head | Living |
| [eval-methodology.md](eval-methodology.md) | How accuracy is scored (four-outcome model: correct / wrong / missed / hallucinated) — enough to reproduce every number | Complete |
| [preregistrations.md](preregistrations.md) | Four frozen hypotheses with success/refutation criteria stated before the test data existed | Live — verdicts due July 2027 |
| [analysis-plan-2026-07-earnings.md](analysis-plan-2026-07-earnings.md) | The earnings-corpus study family, frozen before running (three clean nulls resulted) | Complete |
| [architecture.md](architecture.md) | Pipeline design and component status | Living |
| [papers/](papers/) | Long-form write-up drafts | **Drafts** — see papers/README.md |
| [experiments/](experiments/) | Early per-experiment notes; superseded by BUILD_LOG.md as the working log | Archived |
| `index.html` | Built artifact for the public site's `/research/` page — `site/Dockerfile` copies it in; not documentation. Build notes: [`site/design-handoff.md`](../site/design-handoff.md) | Build artifact |
