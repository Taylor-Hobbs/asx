"""IBKR paper-account executor. PAPER ONLY — port guard enforces it.

ib_insync against a locally running TWS / IB Gateway with the API enabled.
Paper ports are 7497 (TWS) and 4002 (Gateway); the live ports (7496/4001)
are REFUSED at construction — this module must never be able to touch real
capital, per the project boundary.

Import of ib_insync is lazy so the rest of the package (and CI) works
without a gateway or the dependency configured.
"""

from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()

PAPER_PORTS = frozenset({7497, 4002})
HEDGE_TICKER = "STW"


@dataclass(frozen=True)
class Fill:
    ticker: str
    action: str  # BUY / SELL
    qty: int
    avg_price: float


class LivePortRefusedError(Exception):
    """Constructed with a live-trading port. The answer is no (CLAUDE.md)."""


class PaperBroker:
    """Thin, synchronous wrapper over ib_insync for the PR-002 book."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 17) -> None:
        if port not in PAPER_PORTS:
            raise LivePortRefusedError(
                f"port {port} is not a paper port {sorted(PAPER_PORTS)}; "
                "live trading is out of scope, permanently"
            )
        from ib_insync import IB  # lazy: CI has no gateway

        self._ib = IB()
        self._host, self._port, self._client_id = host, port, client_id

    def __enter__(self) -> "PaperBroker":
        self._ib.connect(self._host, self._port, clientId=self._client_id, timeout=20)
        account = self._ib.managedAccounts()
        # Paper account ids start with 'D'. Belt to the port guard's braces.
        if account and not account[0].startswith("D"):
            self._ib.disconnect()
            raise LivePortRefusedError(f"account {account[0]} does not look like a paper account")
        log.info("broker.connected", account=account)
        return self

    def __exit__(self, *exc: object) -> None:
        self._ib.disconnect()

    def _stock(self, ticker: str) -> Any:
        from ib_insync import Stock

        contract = Stock(ticker, "ASX", "AUD")
        qualified = self._ib.qualifyContracts(contract)
        if not qualified:
            raise ValueError(f"could not qualify {ticker} on ASX")
        return qualified[0]

    def last_price(self, ticker: str) -> float:
        contract = self._stock(ticker)
        t = self._ib.reqMktData(contract, "", snapshot=True)
        self._ib.sleep(2.0)
        price = t.marketPrice()
        if price != price or price <= 0:  # NaN or nonsense
            raise ValueError(f"no market price for {ticker}")
        return float(price)

    def market_order(self, ticker: str, action: str, qty: int) -> Fill:
        """Place a market order and wait for the fill (paper fills fast)."""
        from ib_insync import MarketOrder

        contract = self._stock(ticker)
        trade = self._ib.placeOrder(contract, MarketOrder(action, qty))
        self._ib.sleep(1.0)
        for _ in range(30):
            if trade.isDone():
                break
            self._ib.sleep(1.0)
        if not trade.isDone() or not trade.orderStatus.avgFillPrice:
            raise RuntimeError(f"{action} {qty} {ticker} not filled: {trade.orderStatus.status}")
        fill = Fill(ticker, action, qty, float(trade.orderStatus.avgFillPrice))
        log.info("broker.filled", **fill.__dict__)
        return fill

    def equity(self) -> dict[str, float]:
        rows = {r.tag: r.value for r in self._ib.accountSummary()}
        return {
            "net_liquidation": float(rows.get("NetLiquidation", "nan")),
            "cash": float(rows.get("TotalCashValue", "nan")),
            "gross_position_value": float(rows.get("GrossPositionValue", "nan")),
        }

    def position_qty(self, ticker: str) -> int:
        for p in self._ib.positions():
            if p.contract.symbol == ticker and p.contract.exchange in ("ASX", ""):
                return int(p.position)
        return 0
