"""Daily price loader: yfinance -> BigQuery, with an honest coverage report.

    uv run python -m asx_engine.prices.loader

PROTOTYPE-GRADE BY DECREE (CLAUDE.md): yfinance is sanctioned for hypothesis
generation; EODHD (adjusted, delisting-aware) gates anything PUBLISHED. The
known dirt this loader carries, on purpose:

- survivorship — today's universe file, no delisted tickers;
- yfinance adjustment quality is unaudited (splits usually right, complex
  corporate actions not guaranteed);
- gaps and zero-volume days are stored as-is, flagged in the coverage report,
  never imputed.

Design:

- **Universe = the universe file + the market index** (^AXJO, S&P/ASX 200) —
  the market-model benchmark rides in the same table with ticker "XJO".
- **Window = earliest event minus one year** — event studies need an
  estimation window BEFORE the first event; one year covers a 120-trading-day
  estimation with margin.
- **Whole-table rebuild** like the event store: prices are a derived cache of
  an external source, so idempotency comes from regeneration. One load job.
- **The coverage report is the point.** yfinance fails quietly (renamed
  tickers return nothing, thin listings return fragments). Every ticker lands
  in exactly one bucket — ok / short_history / empty — and the study joins
  only what's clean, knowingly.
"""

import sys
from dataclasses import dataclass
from datetime import date
from typing import cast

import pandas as pd
import structlog
import yfinance as yf
from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import Settings, load_settings
from asx_engine.ingestion.backfill import DEFAULT_UNIVERSE, load_universe
from asx_engine.schemas import utc_now

log = structlog.get_logger()

PRICES_TABLE = "daily_prices"
INDEX_TICKER = "XJO"  # stored name for ^AXJO, the S&P/ASX 200
START_DATE = date(2023, 7, 1)  # earliest event 2024-07-07 minus a year
SOURCE = "yfinance"

# A ticker whose history covers less than this fraction of the index's
# trading days is "short_history" — usable for events inside its coverage,
# excluded from anything needing the full estimation window.
MIN_COVERAGE = 0.90


def to_yahoo(ticker: str) -> str:
    """ASX code -> Yahoo symbol. Yahoo's ASX index symbols carry an A: ^AXJO."""
    return f"^A{ticker}" if ticker == INDEX_TICKER else f"{ticker}.AX"


@dataclass
class Coverage:
    ok: list[str]
    short_history: dict[str, int]  # ticker -> rows found
    empty: list[str]


def classify_coverage(
    rows_per_ticker: dict[str, int], index_days: int, tickers: list[str]
) -> Coverage:
    """Bucket every requested ticker by how much history came back."""
    coverage = Coverage(ok=[], short_history={}, empty=[])
    threshold = int(index_days * MIN_COVERAGE)
    for ticker in tickers:
        rows = rows_per_ticker.get(ticker, 0)
        if rows == 0:
            coverage.empty.append(ticker)
        elif rows < threshold:
            coverage.short_history[ticker] = rows
        else:
            coverage.ok.append(ticker)
    return coverage


def frame_to_rows(prices: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """yfinance's wide multi-index frame -> long (ticker, date, ...) rows.

    yfinance returns columns keyed (ticker, field) with auto_adjust=False.
    Long format is what BigQuery and every downstream join wants; rows where
    Close is NaN (non-trading days padded in by the shared calendar) drop out.
    """
    frames = []
    for ticker in tickers:
        yahoo = to_yahoo(ticker)
        if yahoo not in prices.columns.get_level_values(0):
            continue
        per_ticker = cast(pd.DataFrame, prices[yahoo])
        sub = per_ticker[["Close", "Adj Close", "Volume"]].dropna(subset=["Close"])
        if sub.empty:
            continue
        frame = sub.reset_index()
        frame.columns = pd.Index(["date", "close", "adj_close", "volume"])
        frame.insert(0, "ticker", ticker)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["ticker", "date", "close", "adj_close", "volume"])
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out


def run(settings: Settings, *, end: date | None = None) -> Coverage:
    tickers = [*load_universe(DEFAULT_UNIVERSE), INDEX_TICKER]
    end = end or utc_now().date()
    log.info("prices.start", tickers=len(tickers), start=str(START_DATE), end=str(end))

    prices = yf.download(
        [to_yahoo(t) for t in tickers],
        start=str(START_DATE),
        end=str(end),
        auto_adjust=False,  # keep BOTH close and adj_close; returns use adj
        actions=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    rows = frame_to_rows(prices, tickers)

    rows_per_ticker = cast(dict[str, int], rows.groupby("ticker").size().to_dict())
    index_days = rows_per_ticker.get(INDEX_TICKER, 0)
    if index_days == 0:
        raise RuntimeError("index (^AXJO) returned no data — nothing to benchmark against")
    coverage = classify_coverage(rows_per_ticker, index_days, tickers)

    rows["source"] = SOURCE
    rows["loaded_at"] = utc_now().isoformat()
    # json.dumps can't serialize datetime.date; BQ's DATE column parses the
    # ISO string form. String conversion happens HERE, at the load boundary —
    # everything upstream keeps real date objects.
    rows["date"] = rows["date"].astype(str)
    bq = bigquery.Client(project=settings.gcp_project)
    table_id = f"{settings.gcp_project}.{settings.bq_dataset}.{PRICES_TABLE}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("close", "FLOAT64"),
            bigquery.SchemaField("adj_close", "FLOAT64"),
            bigquery.SchemaField("volume", "FLOAT64"),
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("loaded_at", "TIMESTAMP"),
        ],
    )
    records = cast(list[dict[str, object]], rows.to_dict(orient="records"))
    bq.load_table_from_json(records, table_id, job_config=job_config).result()

    log.info(
        "prices.loaded",
        rows=len(rows),
        index_trading_days=index_days,
        ok=len(coverage.ok),
        short_history=len(coverage.short_history),
        empty=len(coverage.empty),
    )
    if coverage.empty:
        log.warning("prices.empty_tickers", tickers=sorted(coverage.empty))
    if coverage.short_history:
        log.warning("prices.short_history", tickers=coverage.short_history)
    return coverage


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    load_dotenv()
    run(load_settings())


if __name__ == "__main__":
    main()
