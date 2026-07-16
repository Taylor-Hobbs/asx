# Paper 03 — The Microscope: What 5,000 Extractions Reveal About LLM Evaluation

**Status:** DRAFT v1 (2026-07-16) · **Corpus:** 5,364 ASX filings parsed;
3,232 director-trade + 1,466 earnings + 890 role extractions; 305,636 indexed
headlines · **Total LLM spend: < $45** · **Author:** Taylor Hobbs

## Abstract

A quant research pipeline is an unusually honest laboratory for LLM
evaluation: every extraction feeds a downstream statistic, so errors have
consequences and ground truth accumulates for free. Running one for two
months produced six transferable findings. (1) Golden labels are themselves
a failure mode — our worst-scoring field turned out to be mislabeled by the
humans, not misread by the model. (2) LLM world-knowledge enrichment fails
predictably (72% accuracy vs primary documents) and $1 of document
extraction catches every failure mode. (3) Documents describing the same
event disagree 28% of the time once independently extracted, and
**cross-document disagreement is a 7.7× error detector** whose corrections
are usually recoverable from the siblings (87%). (4) Model confidence is
usable — but as a binary flag, not a probability: above 0.95 it is
calibrated; the 0.90–0.95 bin is 21% accurate. (5) LLM attribution shares
are not event rates: a blinded-autopsy "finding" died in ten minutes against
a hard incidence join. (6) On self-authored corporate filings, sentiment is
structurally uninformative — companies falling 55% announce good news the
entire way down, and the model believes them.

## 1. The setup: evals with consequences

Prompts are versioned artifacts; every run logs (model, prompt version,
dataset version); no bulk extraction ships until it beats the incumbent on a
hand-labeled golden set. That discipline produced a clean improvement
record — earnings 67.8% (v1) → 87.8% (v7); director trades 75.0% → 93.1%
(v3) — including two versions (v4, v5) that regressed and were binned, which
is the system working. The largest single gain (+26pp on one field) came
from pinning an output *format* the labels assumed silently. Scoring
taxonomy matters: correct/wrong/missed/hallucinated are different failures
with different fixes, and list-valued documents need alignment-aware scoring
(a missed trade and an invented trade are detection errors, not field errors).

## 2. Finding 1 — your golden labels can be the bug

The eval scored director_role at 15.6%, with 27 "misses." Investigation: 30
of 36 golden role labels named roles that appear **nowhere in the
documents** — labeled from headlines and human memory, not text. The model
was being punished for correctly extracting only what the document states.
Corrected goldens: same extractions re-scored 75.0% → 81.7%. *When a model
fails a field catastrophically, audit the labels before the prompt.*

## 3. Finding 2 — world-knowledge enrichment fails predictably

Asking a frontier model "what role does this person hold at this company?"
scored **72% (18/25 verifiable)** against primary appointment filings, with
*systematic* — not random — failure modes: famous-elsewhere executives
labeled executive at companies where they are non-executives; post-cutoff
CEOs missed; time-varying roles collapsed to one era. Extracting the same
facts from 893 appointment notices cost ~$1 and caught every mode. *Model
memory is a lossy, dated database; primary documents are cheap.*

## 4. Finding 3 — cross-document disagreement, the free error detector

Most results events arrive as several documents (statutory report, media
release, presentation). Extracting each independently creates an audit that
needs no labels: 447 events with ≥2 documents showed only **45% exact
agreement, 27% within 1% (rounding), 28% outright disagreement** — worst on
EPS (~48%: basic-vs-diluted, cents-vs-dollars, statutory-vs-underlying).
Anchored to golden labels, disagreement is a **7.7× error detector**
(corroborated fields: 6.1% error; contested: 47.1%) and **87% of detected
errors have the correct value sitting in a sibling document** — consensus
voting repairs almost everything it flags, for zero marginal spend.

## 5. Finding 4 — confidence is a flag, not a probability

Golden-anchored reliability (ECE 0.072, but structured):

| stated confidence | actual accuracy |
|---|---|
| ≥ 0.98 | 97.5% |
| 0.95–0.98 | 95.0% |
| 0.90–0.95 | **21.4%** |
| 0.80–0.90 | 62.5% |

Above 0.95 the model knows what it knows; below, a "90% confident" answer is
wrong four times in five. Crucially, confidence does **not** see convention
errors: on cross-document deviant values it reads 0.951 vs 0.962 on
consensus values — wrong-by-convention feels identical to right from the
inside. Production rule that falls out: **confidence < 0.95 OR contested
across documents → review queue; confident-and-corroborated → trust.**

## 6. Finding 5 — attribution shares are not event rates

A blinded-autopsy design (605 event windows, director-interest headlines
stripped, fixed taxonomy, matched controls) suggested post-insider-sale
declines over-indexed on capital raises (18% vs 6% attribution share,
p=0.015). A ten-minute incidence join refuted it: raises follow sales at
exactly the ticker-matched base rate (3.9% vs 4.6% expected). The share was
a *composition* effect — sale windows mechanically contain fewer results
events, so surviving causes claim larger shares. **No LLM attribution
fingerprint means anything until it survives a hard count.**

## 7. Finding 6 — sentiment on self-authored filings is structurally dead

In blinded autopsies, 85% of the *worst*-outcome windows and 90% of the best
were classified "positive operational news" — companies losing half their
value announce good news all the way down, and a naive reader (human or LLM)
inherits the spin. A promotional-language lexicon over 305k headlines
confirmed: adjective density predicts nothing (and mostly measures
*performance vocabulary* — the most "promotional" issuers are large firms
factually announcing record profits). The informative tonal object is the
**trajectory**: healthy raisers ramp news volume +30% and tone (t = +2.60)
in the 90 days before a placement — disclosure management, visible in
metadata. *Level of tone: noise. Timing of tone: information.*

## 8. Economics

Everything above ran on batched Haiku for **under $45 total** (~$12
director trades, ~$19 earnings, ~$1 roles, ~$5 replication band, <$2 of
autopsies/classifications), with the golden-set baseline the only frontier-
model spend. The binding constraint was never tokens; it was label quality
and evaluation design.

## Caveats

Golden sets are small (23–28 documents); one exchange, one document culture;
one model family for bulk extraction (a cost-accuracy frontier across tiers
remains unrun); several findings have n in the dozens and are offered as
demonstrated techniques with small-n numbers, not universal constants.
