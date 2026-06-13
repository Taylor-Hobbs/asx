# Golden Dataset

Hand-labeled ground truth for the eval harness. Q1 target: 100+ filings.

## Redistribution rule (enforced)

Raw filing PDFs are **never** committed here — they live only in the private
Cloud Storage bucket. Each label file references its filing by
**ticker + Sydney-local date + ASX announcement ID**, so anyone can
reconstruct the dataset from public sources without this repo republishing
documents.

## Workflow

```
uv run python scripts/make_golden_stubs.py    # one stub per stored document (never overwrites)
# ... open the PDF on the ASX website, fill in labels/, flip status ...
uv run python scripts/validate_goldens.py     # schema check + progress count, run as you go
```

## Format

One JSON file per **document** at
`golden/labels/<TICKER>_<YYYY-MM-DD>_<announcement-id>.json`, validated by
`asx_engine.schemas.GoldenLabel`. A filled-in example:

```json
{
  "ticker": "WES",
  "announcement_id": "03091234",
  "announced_at": "2026-02-18T08:15:00Z",
  "headline": "2026 Half-year results",
  "content_hash": "113d56276a8b…(pre-filled by the stub generator)",
  "announcement_type": "earnings",
  "status": "labeled",
  "exclusion_reason": null,
  "labels": {
    "period": "Half-year ended 31 December 2025",
    "reporting_currency": "AUD",
    "revenue": { "current": "24212000000", "prior": "23490000000" },
    "npat":    { "current": "1603000000",  "prior": "1467000000" },
    "eps_cents":   { "current": "141.4",       "prior": "129.4" },
    "dividend_cents": { "current": "102",      "prior": "95" }
  },
  "labeled_by": "Taylor Hobbs",
  "labeled_at": "2026-06-14",
  "dataset_version": "golden_v1",
  "notes": "Statutory NPAT taken from p1 headline table."
}
```

- Write monetary values as **strings** (`"24212000000"`) — exact decimals,
  no float surprises. Units match the schema: absolute value in `reporting_currency`, cents per share in `reporting_currency`.
- `reporting_currency` is an ISO 4217 code (`"AUD"`, `"USD"`, etc.) — set
  to whatever currency the company reports in. AUD reporters get `"AUD"`,
  USD reporters (BHP, RIO, CSL) get `"USD"`. Revenue/NPAT values are in that
  currency; EPS and dividend are in **cents of that currency**.
- `null` for a value means *"this document does not state this figure in the
  required form"*. It is a deliberate assertion, not a skipped field.
- Status lifecycle: stubs arrive `"unlabeled"` → set `"labeled"` (requires
  `labeled_by` + `labeled_at`) or `"excluded"` (requires
  `exclusion_reason`, e.g. the RIO Q4 production report).
- Use `notes` for anything a future you will want: which table the number
  came from, judgment calls, ambiguities.

## Labeling conventions — label what THE DOCUMENT states, under these rules

These mirror `prompts/earnings_v1.md`; if labels and prompt use different
conventions, accuracy numbers measure the disagreement, not the model.

1. **Statutory beats underlying** when a document reports both.
2. **Group beats segment** — consolidated totals only.
3. **Native currency only, never convert** — label in the company's reporting
   currency (`reporting_currency`). If a doc shows USD revenue and an AUD
   translation, label the USD figure. Never convert or derive FX.
4. **Dividend** = total declared per share for the period as the document
   states it.
5. **Null beats deriving** — never compute a figure the document doesn't
   print (no EPS from NPAT ÷ shares, no revenue from summing income lines).
6. Labels are **per document**: when a media release and the 4D disagree
   (CBA: 5,367 vs 5,412), each file records its own document's number, with
   a note.

### Open rulings — decide on first encounter, record here, then apply everywhere

- **EPS basis:** continuing operations vs including discontinued (CBA
  reports both). Ruling: **including discontinued** — this is the headline
  number in most media releases; apply consistently across all tickers.
- **Bank "revenue":** total net operating income, or `null` for financials
  with no conventional revenue line. Ruling: **`null` for all banks**
  (CBA, NAB, ANZ, WBC) — "total net operating income" requires judgment
  on line selection; null is the honest answer per rule 5 (null beats
  deriving).
