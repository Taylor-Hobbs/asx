# Golden Dataset — Director Trades (Appendix 3Y)

Hand-labeled ground truth for the director trades eval harness.

## Workflow

```
# 1. Dry-run to see what's available — read headlines before downloading
uv run python -m asx_engine.ingestion.director_trades_ingest BHP CBA NAB ANZ WBC WES TLS WOW CSL RIO --dry-run

# 2. Ingest (exclude false positives found in dry-run)
uv run python -m asx_engine.ingestion.director_trades_ingest BHP CBA NAB ANZ WBC WES TLS WOW CSL RIO

# 3. Generate stubs (never overwrites)
uv run python scripts/make_director_trade_stubs.py

# 4. Open each PDF on the ASX website, fill in the trades, flip status to "labeled"
# 5. Validate as you go
uv run python scripts/validate_goldens.py
```

## Format

One JSON file per filing at `golden/director_trades/<TICKER>_<YYYY-MM-DD>_<id>.json`.

A filled example (on-market purchase):

```json
{
  "ticker": "WES",
  "announcement_id": "03091234",
  "announced_at": "2026-03-12T00:09:00Z",
  "headline": "Change in Director's Interest Notice",
  "content_hash": "abc123...",
  "announcement_type": "director_trade",
  "status": "labeled",
  "labels": {
    "trades": [
      {
        "director_name": "Rob Scott",
        "director_role": "Managing Director & CEO",
        "trade_type": "acquisition",
        "nature": "on-market purchase",
        "security_class": "ordinary shares",
        "quantity": "5000",
        "price_per_security": "71.44",
        "total_consideration": "357200",
        "trade_date": "2026-03-11",
        "holdings_before": "1241300",
        "holdings_after": "1246300"
      }
    ]
  },
  "labeled_by": "Taylor Hobbs",
  "labeled_at": "2026-06-23",
  "dataset_version": "golden_v1",
  "notes": "Single on-market purchase. Holdings confirmed from Part 2 of the form."
}
```

A filled example (nil-consideration vesting):

```json
{
  "labels": {
    "trades": [
      {
        "director_name": "David Lamont",
        "director_role": "Chief Financial Officer",
        "trade_type": "acquisition",
        "nature": "vesting of performance rights",
        "security_class": "ordinary shares",
        "quantity": "42500",
        "price_per_security": null,
        "total_consideration": null,
        "trade_date": "2026-04-15",
        "holdings_before": "285000",
        "holdings_after": "327500"
      }
    ]
  }
}
```

## Labeling conventions

### What is a "trade" to label?

Label every row in Part 2 (Change in relevant interest) of the Appendix 3Y that
represents a completed transaction. Common types:

- On-market purchase / on-market sale
- Exercise of options
- Vesting of performance rights
- Off-market transfer
- Dividend reinvestment plan (DRP) allotment

**Do NOT label** Part 1 declarations of existing holdings with no change
(e.g. "Balance as at..." rows with no corresponding change event). Initial
Director's Interest Notices that only declare pre-existing holdings (no
transaction occurred) should be **excluded** with `exclusion_reason`:
`"Initial notice — no transaction, pre-existing holdings only"`.

### One label per transaction row

If the form shows separate rows for direct and indirect interests changing on
the same day, label them as two separate trades. If a single trade involves
both ordinary shares and options, label each security class separately.

### Field conventions

- **quantity** — always a positive integer, regardless of trade direction.
  A disposal of 5,000 shares → quantity `"5000"`, trade_type `"disposal"`.
- **price_per_security** — AUD (or reporting currency) per security as stated.
  Null for nil-consideration transactions (options exercise at $0, performance
  right vestings, scrip-for-scrip with no stated price).
- **total_consideration** — total cash as stated. Null when no cash changed hands.
  Do NOT compute price × quantity — if only one is stated, only label that one.
- **trade_date** — the date the transaction occurred (ISO 8601: YYYY-MM-DD),
  NOT the lodgement date. The form states both; use the transaction date.
- **holdings_before / holdings_after** — label if stated in the form. Null if
  omitted (common for indirect interests and some older forms).
- **nature** — verbatim or close to verbatim from the form. Examples:
  `"on-market purchase"`, `"vesting of performance rights"`,
  `"exercise of unlisted options"`, `"off-market transfer"`.
- **security_class** — as stated: `"ordinary shares"`, `"unlisted options"`,
  `"performance rights"`, `"convertible notes"`.

### Open rulings — decide on first encounter, record here

- **Indirect interests:** If the form discloses both direct and indirect
  holdings changing, label each separately. Use the nature as stated
  (e.g. "on-market purchase — indirect interest held by [entity]").
- **Multiple tranches same day:** Label each tranche as its own trade.
- **Nil price:** Options exercised at nil cost and performance right vestings
  always have `price_per_security: null` and `total_consideration: null`.
- **Holdings omitted:** Many forms omit holdings_before for indirect interests.
  Null is correct — do not derive or estimate.
- **Transfers (ruled 2026-07-04, from CBA 03099309 / NAB 03066280 /
  TLS 03073126):** securities moving between a director's own holdings with no
  change in net beneficial interest — custodian swaps, direct-to-family-trust
  moves, trust-to-SMSF rebalancing — are `trade_type: "transfer"`, ONE trade
  per movement (never a disposal row plus an acquisition row). They are
  directionless on purpose: calling them acquisitions or disposals would
  fabricate buy/sell signal for the event study.
