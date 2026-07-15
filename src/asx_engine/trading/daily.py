"""PR-002 daily paper-trading job.

    uv run python -m asx_engine.trading.daily                  # dry run (default)
    uv run python -m asx_engine.trading.daily --execute        # place paper orders
    ... --skip-crawl --skip-extract                            # skip pipeline freshen

Order of operations each ASX evening: freshen the 3Y crawl (1-month window,
idempotent) -> parse -> extract pending 3Y docs -> rebuild the event store ->
apply the FROZEN PR-002 gates -> enter/exit on the IBKR paper account (or log
the would-be orders in dry mode) -> snapshot equity. Every decision, including
skips, lands in `paper_ledger` — the skip log is a deliverable of the forward
test, not telemetry.

Dry mode writes DRY_* ledger rows so a dry book has continuity; switching to
--execute starts a fresh live-paper book (position keys are mode-scoped).
"""

import argparse
import subprocess
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import structlog
from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import Settings, load_settings
from asx_engine.events.director_trades import EVENTS_TABLE
from asx_engine.events.director_trades import run as rebuild_events
from asx_engine.trading.signals import (
    HOLD_TRADING_DAYS,
    NOTIONAL_AUD,
    OpenPosition,
    SaleFiling,
    exits_due,
    select_entries,
)

log = structlog.get_logger()

LEDGER_TABLE = "paper_ledger"
EQUITY_TABLE = "paper_equity"
UNIVERSE = Path("data/universe/asx300_combined_2026-07-14.csv")

RESULTS_RE = (
    r"(?i)appendix\s*4[cde]|half[\s-]*year|full[\s-]*year|annual\s+report"
    r"|preliminary final|results (announcement|presentation|release)"
    r"|results for announcement"
)

LEDGER_SCHEMA = [
    bigquery.SchemaField("ts", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("mode", "STRING", mode="REQUIRED"),  # dry | paper
    bigquery.SchemaField("action", "STRING", mode="REQUIRED"),  # ENTER/EXIT/SKIP_*
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("director", "STRING"),
    bigquery.SchemaField("filed_date", "DATE"),
    bigquery.SchemaField("entry_date", "DATE"),
    bigquery.SchemaField("qty", "INTEGER"),
    bigquery.SchemaField("price", "FLOAT"),
    bigquery.SchemaField("size_aud", "FLOAT"),
    bigquery.SchemaField("note", "STRING"),
]
EQUITY_SCHEMA = [
    bigquery.SchemaField("ts", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("mode", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("net_liquidation", "FLOAT"),
    bigquery.SchemaField("cash", "FLOAT"),
    bigquery.SchemaField("gross_position_value", "FLOAT"),
    bigquery.SchemaField("open_positions", "INTEGER"),
]


def ensure_tables(bq: bigquery.Client, dataset: str) -> None:
    for name, schema in ((LEDGER_TABLE, LEDGER_SCHEMA), (EQUITY_TABLE, EQUITY_SCHEMA)):
        bq.create_table(bigquery.Table(f"{dataset}.{name}", schema=schema), exists_ok=True)


def freshen_pipeline(*, skip_crawl: bool, skip_extract: bool) -> None:
    """Shell out to the existing idempotent jobs — their CLIs are the contract."""
    steps: list[list[str]] = []
    if not skip_crawl:
        steps.append(
            [
                sys.executable,
                "-m",
                "asx_engine.ingestion.backfill",
                "--filter",
                "3y",
                "--months",
                "1",
                "--tickers-file",
                str(UNIVERSE),
            ]
        )
    steps.append([sys.executable, "-m", "asx_engine.parsing.job"])
    if not skip_extract:
        steps.append(
            [
                sys.executable,
                "-m",
                "asx_engine.extraction.director_trades_job",
                "--scope",
                "corpus",
                "--batch",
                "--confirm",
            ]
        )
    for cmd in steps:
        log.info("daily.step", cmd=" ".join(cmd[2:]))
        subprocess.run(cmd, check=True)  # noqa: S603 - our own module CLIs


def load_state(
    bq: bigquery.Client, dataset: str, mode: str, today: date
) -> tuple[
    list[SaleFiling],
    dict[str, list[date]],
    list[date],
    list[OpenPosition],
    dict[tuple[str, str], date],
]:
    filings = [
        SaleFiling(
            r.ticker,
            r.director_name or "?",
            r.filed,
            Decimal(str(r.total_consideration)) if r.total_consideration is not None else None,
        )
        for r in bq.query_and_wait(
            f"SELECT ticker, director_name, total_consideration, "  # noqa: S608
            f"DATE(announced_at, 'Australia/Sydney') AS filed "
            f"FROM `{dataset}.{EVENTS_TABLE}` "
            "WHERE trade_type='disposal' AND LOWER(nature) LIKE '%on-market%' "
            "AND DATE(announced_at, 'Australia/Sydney') >= DATE_SUB(@today, INTERVAL 40 DAY)",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("today", "DATE", today)]
            ),
        )
    ]
    results: dict[str, list[date]] = {}
    for r in bq.query_and_wait(
        f"SELECT ticker, DATE(announced_at, 'Australia/Sydney') AS d "  # noqa: S608
        f"FROM `{dataset}.announcements` "
        f"WHERE price_sensitive AND REGEXP_CONTAINS(headline, r'{RESULTS_RE}') "
        "AND NOT REGEXP_CONTAINS(headline, r'(?i)results of (annual general )?meeting')"
    ):
        results.setdefault(r.ticker.upper(), []).append(r.d)
    trading_days = [
        r.date
        for r in bq.query_and_wait(
            f"SELECT DISTINCT date FROM `{dataset}.daily_prices` "  # noqa: S608
            "WHERE ticker='XJO' ORDER BY date"
        )
    ]
    ledger = list(
        bq.query_and_wait(
            f"SELECT action, ticker, director, entry_date, filed_date "  # noqa: S608
            f"FROM `{dataset}.{LEDGER_TABLE}` WHERE mode=@mode",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("mode", "STRING", mode)]
            ),
        )
    )
    entered = {
        (r.ticker, (r.director or "").casefold(), r.entry_date)
        for r in ledger
        if r.action in ("ENTER", "DRY_ENTER")
    }
    exited = {
        (r.ticker, (r.director or "").casefold(), r.entry_date)
        for r in ledger
        if r.action in ("EXIT", "DRY_EXIT")
    }
    open_positions = [OpenPosition(t, d, e) for (t, d, e) in entered - exited if e is not None]
    recent_entry: dict[tuple[str, str], date] = {}
    for r in ledger:
        if r.action in ("ENTER", "DRY_ENTER") and r.filed_date is not None:
            key = (r.ticker.upper(), (r.director or "").casefold())
            if key not in recent_entry or r.filed_date > recent_entry[key]:
                recent_entry[key] = r.filed_date
    return filings, results, trading_days, open_positions, recent_entry


def append_ledger(bq: bigquery.Client, dataset: str, rows: list[dict[str, object]]) -> None:
    if rows:
        errors = bq.insert_rows_json(f"{dataset}.{LEDGER_TABLE}", rows)
        if errors:
            raise RuntimeError(f"ledger insert failed: {errors}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="place paper orders (default dry)")
    parser.add_argument("--skip-crawl", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--port", type=int, default=7497, help="TWS 7497 / Gateway 4002 (paper)")
    args = parser.parse_args()
    mode = "paper" if args.execute else "dry"

    load_dotenv()
    settings: Settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    ensure_tables(bq, dataset)

    freshen_pipeline(skip_crawl=args.skip_crawl, skip_extract=args.skip_extract)
    rebuild_events(settings)

    today = datetime.now(UTC).astimezone().date()
    filings, results, trading_days, open_pos, recent = load_state(bq, dataset, mode, today)
    entries, skips = select_entries(filings, results, open_pos, recent, today)
    exits = exits_due(open_pos, trading_days, today)
    log.info(
        "daily.signals",
        mode=mode,
        candidates=len(filings),
        entries=len(entries),
        exits=len(exits),
        skips=len(skips),
        open_before=len(open_pos),
    )

    now = datetime.now(UTC).isoformat()
    rows: list[dict[str, object]] = [
        {
            "ts": now,
            "mode": mode,
            "action": f"SKIP_{s.reason.name}",
            "ticker": s.ticker,
            "director": s.director,
            "filed_date": s.filed.isoformat(),
            "note": s.reason.value,
        }
        for s in skips
    ]

    if mode == "dry":
        for e in entries:
            rows.append(
                {
                    "ts": now,
                    "mode": mode,
                    "action": "DRY_ENTER",
                    "ticker": e.ticker,
                    "director": e.director,
                    "filed_date": e.filed.isoformat(),
                    "entry_date": today.isoformat(),
                    "size_aud": float(e.size_aud),
                    "note": f"gap={e.gap_days}d hold={HOLD_TRADING_DAYS}td",
                }
            )
        for p in exits:
            rows.append(
                {
                    "ts": now,
                    "mode": mode,
                    "action": "DRY_EXIT",
                    "ticker": p.ticker,
                    "director": p.director,
                    "entry_date": p.entry_date.isoformat(),
                }
            )
        append_ledger(bq, dataset, rows)
        print(
            f"\nDRY RUN {today} — book after today: "
            f"{len(open_pos) - len(exits) + len(entries)} positions"
        )
        for e in entries:
            print(
                f"  DRY ENTER  short {e.ticker:<5} A${e.size_aud:,}  "
                f"({e.director}, filed {e.filed}, gap {e.gap_days}d)"
            )
        for p in exits:
            print(f"  DRY EXIT   cover {p.ticker:<5} (entered {p.entry_date})")
        for s in skips:
            print(f"  SKIP [{s.reason.value}]  {s.ticker} {s.director} filed {s.filed}")
        return

    from asx_engine.trading.paper_broker import HEDGE_TICKER, PaperBroker

    with PaperBroker(port=args.port) as broker:
        for p in exits:
            qty = -broker.position_qty(p.ticker)
            if qty > 0:
                fill = broker.market_order(p.ticker, "BUY", qty)
                rows.append(
                    {
                        "ts": now,
                        "mode": mode,
                        "action": "EXIT",
                        "ticker": p.ticker,
                        "director": p.director,
                        "entry_date": p.entry_date.isoformat(),
                        "qty": qty,
                        "price": fill.avg_price,
                    }
                )
        for e in entries:
            try:
                price = broker.last_price(e.ticker)
                qty = max(1, int(e.size_aud / price))
                fill = broker.market_order(e.ticker, "SELL", qty)
                rows.append(
                    {
                        "ts": now,
                        "mode": mode,
                        "action": "ENTER",
                        "ticker": e.ticker,
                        "director": e.director,
                        "filed_date": e.filed.isoformat(),
                        "entry_date": today.isoformat(),
                        "qty": qty,
                        "price": fill.avg_price,
                        "size_aud": float(e.size_aud),
                        "note": f"gap={e.gap_days}d",
                    }
                )
            except Exception as exc:  # noqa: BLE001 - borrow/qualify failures are findings
                rows.append(
                    {
                        "ts": now,
                        "mode": mode,
                        "action": "SKIP_BORROW",
                        "ticker": e.ticker,
                        "director": e.director,
                        "filed_date": e.filed.isoformat(),
                        "note": str(exc)[:200],
                    }
                )
        # hedge: keep STW long ≈ total short notional
        n_open = len(open_pos) - len(exits) + len(entries)
        target = n_open * NOTIONAL_AUD
        stw_price = broker.last_price(HEDGE_TICKER)
        target_qty = int(target / stw_price)
        delta = target_qty - broker.position_qty(HEDGE_TICKER)
        if abs(delta * stw_price) > NOTIONAL_AUD / 2:
            fill = broker.market_order(HEDGE_TICKER, "BUY" if delta > 0 else "SELL", abs(delta))
            rows.append(
                {
                    "ts": now,
                    "mode": mode,
                    "action": "HEDGE",
                    "ticker": HEDGE_TICKER,
                    "qty": delta,
                    "price": fill.avg_price,
                }
            )
        eq = broker.equity()
        bq.insert_rows_json(
            f"{dataset}.{EQUITY_TABLE}",
            [{"ts": now, "mode": mode, "open_positions": n_open, **eq}],
        )
    append_ledger(bq, dataset, rows)
    log.info("daily.done", mode=mode, orders=len(rows))


if __name__ == "__main__":
    main()
