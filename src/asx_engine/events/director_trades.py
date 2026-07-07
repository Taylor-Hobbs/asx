"""Materialize the director-trades event store: one row per trade, point in time.

    uv run python -m asx_engine.events.director_trades

The first Q2 artifact. Every downstream event study reads THIS table, never
extraction_records directly, because this is where the point-in-time and
data-hygiene decisions live — made once, in one place:

- **The anchor is `announced_at`** — the ASX release timestamp captured at
  ingestion (Sydney local converted to UTC). NOT trade_date: the market can
  only react when the notice is released, and a director has five business
  days to lodge, so trade_date precedes the tradeable moment by up to a week.
  Using trade_date in a study would be lookahead. Both are kept; the study
  aligns on announced_at, and (announced_at - trade_date) is itself a feature
  (disclosure lag).
- **Dedupe by content_hash, latest extraction wins.** The 2026-07-08
  collection left up to ~250 duplicated extraction_records rows (a load job
  that committed server-side while the client saw a 429). ROW_NUMBER over
  extracted_at makes the store immune to that class of accident.
- **Whole-table rebuild, not append.** CREATE OR REPLACE from the sources on
  every run: the store is a *derived* artifact, so idempotency comes from
  regeneration, not bookkeeping. Re-run after any re-extraction.
- Set-based SQL, not a Python loop: BigQuery unnests 3,200 JSON payloads into
  4,700 rows in one statement. Row-at-a-time is the habit to unlearn here.
"""

import sys

import structlog
from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import Settings, load_settings

log = structlog.get_logger()

EVENTS_TABLE = "events_director_trades"
PROMPT_VERSION = "director_trades_v3"
MODEL = "claude-haiku-4-5"


def build_events_sql(dataset: str) -> str:
    """The one statement that defines the event store."""
    return f"""
    CREATE OR REPLACE TABLE `{dataset}.{EVENTS_TABLE}` AS
    WITH latest_extraction AS (
      SELECT content_hash, payload,
             ROW_NUMBER() OVER (
               PARTITION BY content_hash ORDER BY extracted_at DESC
             ) AS rn
      FROM `{dataset}.extraction_records`
      WHERE prompt_version = '{PROMPT_VERSION}' AND model = '{MODEL}'
    ),
    trades AS (
      SELECT
        e.content_hash,
        idx AS trade_index,
        JSON_EXTRACT_SCALAR(t, '$.director_name.value')      AS director_name,
        JSON_EXTRACT_SCALAR(t, '$.director_role.value')      AS director_role,
        JSON_EXTRACT_SCALAR(t, '$.trade_type.value')         AS trade_type,
        JSON_EXTRACT_SCALAR(t, '$.nature.value')             AS nature,
        JSON_EXTRACT_SCALAR(t, '$.security_class.value') AS security_class,
        SAFE_CAST(JSON_EXTRACT_SCALAR(t, '$.quantity.value') AS NUMERIC)
          AS quantity,
        SAFE_CAST(JSON_EXTRACT_SCALAR(t, '$.price_per_security.value') AS NUMERIC)
          AS price_per_security,
        SAFE_CAST(JSON_EXTRACT_SCALAR(t, '$.total_consideration.value') AS NUMERIC)
          AS total_consideration,
        SAFE_CAST(JSON_EXTRACT_SCALAR(t, '$.trade_date.value') AS DATE)
          AS trade_date,
        SAFE_CAST(JSON_EXTRACT_SCALAR(t, '$.holdings_before.value') AS NUMERIC)
          AS holdings_before,
        SAFE_CAST(JSON_EXTRACT_SCALAR(t, '$.holdings_after.value') AS NUMERIC)
          AS holdings_after
      FROM latest_extraction e,
           UNNEST(JSON_EXTRACT_ARRAY(e.payload, '$.trades')) AS t WITH OFFSET AS idx
      WHERE e.rn = 1
    )
    SELECT
      -- One stable id per trade: the document hash plus its position within it.
      CONCAT(t.content_hash, '#', CAST(t.trade_index AS STRING)) AS event_id,
      a.ticker,
      a.announcement_id,
      -- THE point-in-time anchor: when the market could first react.
      a.announced_at,
      a.headline,
      a.price_sensitive,
      t.* EXCEPT (content_hash, trade_index),
      t.content_hash,
      -- Disclosure lag in days — a feature, and a data-quality tripwire
      -- (negative values would mean a mis-extracted trade_date).
      DATE_DIFF(DATE(a.announced_at, 'Australia/Sydney'), t.trade_date, DAY)
        AS disclosure_lag_days
    FROM trades t
    JOIN `{dataset}.announcements` a USING (content_hash)
    """  # noqa: S608 - own dataset


def run(settings: Settings) -> None:
    bq = bigquery.Client(project=settings.gcp_project)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    bq.query_and_wait(build_events_sql(dataset))

    stats = next(
        iter(
            bq.query_and_wait(
                f"""
        SELECT COUNT(*) AS events,
               COUNT(DISTINCT content_hash) AS documents,
               COUNT(DISTINCT ticker) AS tickers,
               MIN(DATE(announced_at)) AS earliest,
               MAX(DATE(announced_at)) AS latest,
               COUNTIF(disclosure_lag_days < 0) AS negative_lags,
               COUNTIF(trade_date IS NULL) AS null_trade_dates
        FROM `{dataset}.{EVENTS_TABLE}`
        """  # noqa: S608 - own table
            )
        )
    )
    log.info(
        "events.built",
        table=EVENTS_TABLE,
        events=stats["events"],
        documents=stats["documents"],
        tickers=stats["tickers"],
        earliest=str(stats["earliest"]),
        latest=str(stats["latest"]),
        negative_lags=stats["negative_lags"],
        null_trade_dates=stats["null_trade_dates"],
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    load_dotenv()
    run(load_settings())


if __name__ == "__main__":
    main()
