"""Audit-trail check: is every source_quote really in the parsed text?

    uv run python scripts/verify_quotes.py

Matching is whitespace-normalized (any run of whitespace == one space):
table rows linearize across line breaks, so a model quoting "label: value
row" joins two lines with a space. That is a faithful quote of the document,
not a hallucination — byte-exact matching would punish the parser's line
breaks, and the first live run proved exactly that (5 of 27 quotes spanned a
line break; zero were fabricated). Page attribution is checked separately
and reported as WRONG PAGE rather than MISSING.
"""

import re

import google.cloud.storage as storage
from google.cloud import bigquery

from asx_engine.config import load_settings
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument
from asx_engine.schemas import EarningsResult, SourcedField

METRICS = ("revenue_aud", "npat_aud", "eps_cents", "dividend_cents")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def sourced_fields(payload: EarningsResult) -> list[tuple[str, SourcedField]]:  # type: ignore[type-arg]
    fields: list[tuple[str, SourcedField]] = [("period", payload.period)]  # type: ignore[type-arg]
    for name in METRICS:
        metric = getattr(payload, name)
        fields.append((f"{name}.current", metric.current))
        fields.append((f"{name}.prior", metric.prior))
    return fields


def main() -> None:
    settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"

    rows = bq.query_and_wait(
        f"SELECT content_hash, payload FROM `{dataset}.extraction_records`"  # noqa: S608 - own table
    )
    checked = failures = 0
    for row in rows:
        payload = EarningsResult.model_validate_json(row["payload"])
        blob = bucket.blob(f"parsed/{PARSER_VERSION}/{row['content_hash']}.json")
        doc = ParsedDocument.model_validate_json(bytes(blob.download_as_bytes()))
        pages = [norm(p) for p in doc.pages]
        for name, f in sourced_fields(payload):
            if f.source_quote is None:
                continue
            checked += 1
            quote = norm(f.source_quote)
            if not any(quote in p for p in pages):
                failures += 1
                print(f"MISSING    {row['content_hash'][:12]} {name}: {f.source_quote!r}")
            elif f.page is None or quote not in pages[f.page - 1]:
                failures += 1
                print(f"WRONG PAGE {row['content_hash'][:12]} {name}: said p{f.page}")
    print(f"\n{checked} quotes checked, {failures} failures")


if __name__ == "__main__":
    main()
