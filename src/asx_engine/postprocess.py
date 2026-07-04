"""Post-processing filters applied to EarningsResult after extraction.

These are deterministic rules that correct systematic model errors without
re-extracting. They are applied at analysis time, not stored in BQ — the
raw extraction records remain the ground truth of what the model said.

Current filters:
- Bank/insurer revenue null: financial companies don't report IFRS 15 revenue.
  When the model extracts a revenue figure for these tickers, it has picked up
  net interest income or total income instead. Null it out.
"""

from decimal import Decimal

from asx_engine.schemas.extraction import EarningsResult, ReportedMetric, SourcedField

# ASX 300 tickers where IFRS 15 revenue is not reported. When a model extracts
# revenue for these, it's always the wrong line item.
BANK_AND_INSURER_TICKERS: frozenset[str] = frozenset(
    {
        # Big 4 banks
        "ANZ",
        "CBA",
        "NAB",
        "WBC",
        # Investment banks / diversified
        "MQG",
        # Regional banks
        "BEN",
        "BOQ",
        # Insurers
        "QBE",
        "IAG",
        "SUN",
        # Diversified financials
        "AMP",
        "MFG",
        "PPT",
        "CPU",
        "IFL",
        "HUB",
        "NWL",
        "PDL",
    }
)

_NULL_SOURCED: SourcedField[Decimal] = SourcedField[Decimal](
    value=None, confidence=1.0, source_quote=None, page=None
)
_NULL_REVENUE = ReportedMetric(current=_NULL_SOURCED, prior=_NULL_SOURCED)


def apply_bank_revenue_filter(result: EarningsResult, ticker: str) -> EarningsResult:
    """Null out revenue for bank/insurer tickers regardless of what the model extracted."""
    if ticker not in BANK_AND_INSURER_TICKERS:
        return result
    return result.model_copy(update={"revenue": _NULL_REVENUE})
