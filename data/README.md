# data/ — committed datasets

Small reference datasets the research is keyed to. Everything else under
`data/` (analysis scratch, review notes) is local-only and gitignored.

## universe/

Point-in-time universe snapshots — which tickers each study phase covered.
Filenames carry the snapshot date; studies cite the file they used.

| File | What it is |
|---|---|
| `asx200_2026-04-05_wikipedia.csv` | ASX 200 constituents as listed on Wikipedia, 2026-04-05 — the Q1/Q2 study universe |
| `asx300_combined_2026-07-14.csv` | Combined ASX 300 universe used for the replication band and the paper-trading signal universe (frozen in PR-002) |
| `asx300_delta_2026-07-14_directory.csv` | The 201–300 band delta (tickers added over the ASX 200 set), from the ASX directory |
| `asx_full_2026-07-16_directory.csv` | Full ASX listed-company directory snapshot backing the whole-market headline index |

Known limitation (documented in the findings): these are *current-constituent*
snapshots, not historical membership series — band-selection/survivorship
effects are discussed wherever they bite (e.g. REP-1, REP-2 in BUILD_LOG.md).

## enrichment/

| File | What it is |
|---|---|
| `director_roles_llm.json` | LLM-inferred role (executive vs non-executive) per director name+ticker |

**⚠ `director_roles_llm.json` is model output, not fact.** These roles were
inferred by an LLM from director names and company context — *not* extracted
from primary documents. When verified against 51 primary-source appointment
notices, agreement was only **72%**, with systematic failure modes
(famous-elsewhere executives mislabeled, post-knowledge-cutoff appointments
wrong, time-dependent roles collapsed to one value). It is committed for
reproducibility of the (null) exec-seller analysis, not as a reference
dataset about the named individuals. Do not reuse it as ground truth.
Verification details: BUILD_LOG.md, role-verification entry (2026-07-13).
