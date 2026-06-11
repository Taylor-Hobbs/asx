"""Pretty-print stored extractions next to their announcement metadata.

    uv run python scripts/eyeball_extractions.py

The manual review step between "extraction ran" and "extraction trusted":
every payload field with its value, confidence, verbatim quote and page,
grouped per filing. Proto-eval tooling — the harness (step 9) automates the
comparison this script asks a human to do.
"""

from google.cloud import bigquery

from asx_engine.config import load_settings
from asx_engine.schemas import EarningsResult, SourcedField

METRICS = ("revenue_aud", "npat_aud", "eps_cents", "dividend_cents")


def show(name: str, f: SourcedField) -> None:  # type: ignore[type-arg]
    quote = f" | {f.source_quote!r} (p{f.page})" if f.source_quote else ""
    print(f"  {name:22} {str(f.value):>14}  conf={f.confidence:.2f}{quote}")


def main() -> None:
    settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    query = f"""
    SELECT a.ticker, a.headline, a.announced_at, e.payload, e.content_hash
    FROM `{dataset}.extraction_records` e
    JOIN `{dataset}.announcements` a USING (content_hash)
    ORDER BY a.ticker, a.announced_at
    """  # noqa: S608 - own tables
    for row in bq.query_and_wait(query):
        payload = EarningsResult.model_validate_json(row["payload"])
        print(f"\n=== {row['ticker']} | {row['headline']} | {row['announced_at']:%Y-%m-%d}")
        print(f"    hash {row['content_hash'][:12]}...")
        show("period", payload.period)
        for metric_name in METRICS:
            metric = getattr(payload, metric_name)
            show(f"{metric_name}.current", metric.current)
            show(f"{metric_name}.prior", metric.prior)


if __name__ == "__main__":
    main()
