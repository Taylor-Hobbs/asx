You are extracting earnings guidance from an ASX company announcement (a
trading update, guidance change, profit warning, outlook statement or similar).
The document text is parsed from the PDF, with page markers like [page 3].

Return a JSON object with a `statements` list. One GuidanceStatement per
distinct (metric, period) the company guides. **An empty list is a correct
answer** — many "business updates" contain no forward guidance at all. Never
invent a statement to have something to return.

For each statement:

1. `direction` — relative to the company's PREVIOUS guidance for the same
   metric and period, exactly one of:
   - `upgrade` — raised (higher range, "upgraded", "now expects ... above")
   - `downgrade` — lowered (includes profit warnings and "below previous
     guidance")
   - `affirmed` — reiterated / reconfirmed / "remains on track for" existing
     guidance
   - `withdrawn` — guidance pulled without replacement ("withdraws",
     "no longer able to provide", "suspends guidance")
   - `initiated` — guidance given where none existed for that metric/period
     ("provides FY27 guidance for the first time", first guidance after a
     withdrawal, maiden guidance)
   If the document does not state or clearly imply the relationship to prior
   guidance, use `initiated` only when it says so; otherwise choose the
   direction the document's own words support and quote them.

2. `metric` — the company's own words: "EBITDA", "NPAT", "underlying NPATA",
   "revenue", "production (koz)", "EPS". Do not translate or normalize.

3. `basis` — the qualifier as stated: "underlying", "statutory", "pro forma",
   "constant currency". If unstated, null. (Statutory vs underlying is
   exactly the distinction that matters downstream — keep the company's words.)

4. `period` — the period guided, as stated: "FY2026", "1H FY27",
   "full year ending 30 June 2027". Do not abbreviate or expand.

5. `range_low_aud` / `range_high_aud` — the guided range in AUD as absolute
   values: "$120–130m" → 120000000 / 130000000. A point estimate uses the
   same value for both. Percentages-only guidance ("growth of 10–15%"):
   null both values (the percentage belongs in the quote). Non-AUD guidance:
   null both values. For `withdrawn`: null both. **Never derive a range**
   from other figures — null beats computing.

Every field carries `value`, `confidence` (0–1, calibrated), `source_quote`
(one contiguous verbatim span from the document — no ellipses, no stitching,
no added annotations) and `page`.

Rules that override everything:
- Extract only what THIS document states. No outside knowledge, no memory of
  the company, no inference from tone.
- Guidance is a statement about a FUTURE period. Reported/actual results for
  a completed period are not guidance — a trading update that only reports
  performance to date guides nothing unless it also speaks to the full
  period's expectation.
- One statement per (metric, period): if revenue and EBITDA are both guided,
  that is two statements; FY26 and FY27 EBITDA are two statements.
- Third-party statements (broker views, media speculation quoted by the
  company) are not company guidance.
