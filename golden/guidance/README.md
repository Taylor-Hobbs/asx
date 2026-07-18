# Guidance golden labels — conventions (locked 2026-07-17, before labeling)

Format: one JSON per document in `labels/`, keyed by content_hash, with
`labels.statements` — a list matching `GuidanceResult`. An EMPTY list is a
valid, common label: many "business updates" guide nothing.

Rules (decided before reading any document, per the role-label lesson —
label only what the document states):

1. **Statement = (metric, period) the company guides.** Revenue and EBITDA
   guided in one document = two statements. FY26 and FY27 = two statements.
2. **direction** relative to the company's prior guidance AS STATED IN THIS
   DOCUMENT. If the document does not characterize the change ("provides
   guidance of $X" with no reference to prior), label `initiated` only if it
   says first/maiden/initial; otherwise use the direction its own words
   support. Never import memory of what the company guided before — if this
   document doesn't say, the honest label is what it says.
3. **metric / basis / period**: the company's words, verbatim. No
   normalization ("underlying EBITDA" stays "underlying EBITDA"; basis null
   when unstated). Periods as written ("FY26", "year ending 30 June 2026" —
   whichever the document uses).
4. **Ranges** in absolute AUD ("$120–130m" → 120000000/130000000); point
   estimates duplicate; percent-only or non-AUD guidance → null/null;
   withdrawn → null/null. Never derive.
5. **Not guidance**: reported/actual results for completed periods; broker
   or media views quoted; aspirational statements with no metric+period
   ("well positioned for growth"); production/cost guidance IS guidance
   (miners guide koz and AISC — metric as stated, ranges null unless AUD).
6. Documents labeled from parsed text only. Auditor (Taylor) spot-checks
   ≥20% of labels against the PDFs before the set is trusted.

Conventions added during labeling (2026-07-18, before any extraction ran;
each triggered by a real document):

7. **Per-unit guidance → null ranges.** `range_*_aud` is labeled only for
   company-level absolute AUD amounts ($20–30M → 20000000/30000000).
   Per-security cents, $/oz AISC, koz production, percentages, non-AUD:
   ranges null; the quote carries the numbers. (SGP, RMS, TLX.)
8. **Cost-metric polarity**: an adverse revision is a `downgrade` in the
   metric's own terms — AISC guidance RAISED = downgrade (RMS Mar-26);
   expenditure guidance LOWERED = upgrade (SEK).
9. **Steering within an unchanged range = `affirmed`** ("around the lower
   end of the guidance range" — RSG, RWC Americas). The range is the
   guidance; pointing at an end of it is commentary.
10. **Completed periods are not guidance**, even pre-report ("FY26 within
    guided ranges", announced after year end — RRL, RYM). Matches the
    prompt's future-period rule.
11. **JORC production targets / feasibility-study parameters are not
    guidance** (S32 decks: Taylor ~290kt ZnEq etc.). Study disclosures,
    not market guidance.
12. **Segments**: component rows of a group guidance table are NOT
    separate statements (RRL Duketon/Tropicana); segment guidance
    individually revised or characterized in prose IS (RWC Americas/APAC/
    EMEA; RSG per-mine where no group aggregate exists).
13. **"Tracking ahead of guidance; update to come" is not a statement**
    (RYM Q2); "remains on track to deliver guidance of X" IS `affirmed`
    (RYM Q1 FY27).

Dataset version: guidance_golden_v1. Accuracy gate for any bulk run: ≥80%
overall (frozen in GS-1 before extraction).
