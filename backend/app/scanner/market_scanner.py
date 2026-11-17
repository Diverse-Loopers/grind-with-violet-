"""
Market Scanner Module.
Monitors watchlists, computes analytical statistics (volatility, moving average deviations, spreads),
and produces enriched ScannerRow representations for dashboard and strategy feeds.
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.adapters.base import BrokerAdapter, Quote
from app.engine.cost_calculator import TransactionCostCalculator
from app.scanner.watchlist import WatchlistManager
from app.utils.logging import logger


@dataclass
class ScannerRow:
    trading_symbol: str
    exchange: str
    name: str
    ltp: float
    bid: float
    ask: float
    spread_pct: float
    change_pct: float
    volume: int
    relative_volume: float
    high: float
    low: float
    volatility: float
    deviation_from_ma: float
    gap_pct: float
    net_edge_pct: float
    data_quality: str
    quote_timestamp: Optional[datetime]
    data_freshness_ms: int


class MarketScanner:
    """Core market scanner engine."""

    def __init__(self, adapter: BrokerAdapter):
        self.adapter = adapter
        self.watchlist_mgr = WatchlistManager()
        self.cost_calc = TransactionCostCalculator()
        # Rolling price and volume histories for statistical calculations (symbol -> deque of floats)
        self.price_history: Dict[str, deque[float]] = {}
        self.volume_history: Dict[str, deque[int]] = {}
        self.cached_rows: Dict[str, ScannerRow] = {}
        self.last_scan_time: Optional[datetime] = None

    def scan_all(self) -> List[ScannerRow]:
        """Polls current watchlist quotes and computes analytical signals."""
        now = datetime.now(timezone.utc)
        self.last_scan_time = now
        active_instruments = self.watchlist_mgr.get_active_instruments()
        rows: List[ScannerRow] = []

        for inst in active_instruments:
            sym = inst.trading_symbol
            try:
                quote = self.adapter.get_quote(sym, inst.exchange)
                row = self._enrich_quote(quote, inst.name)
                self.cached_rows[sym] = row
                rows.append(row)
            except Exception as e:
                logger.error(f"Error fetching quote for {sym}: {e}")
                if sym in self.cached_rows:
                    rows.append(self.cached_rows[sym])

        return rows

    def _enrich_quote(self, quote: Quote, company_name: str) -> ScannerRow:
        now = datetime.now(timezone.utc)
        sym = quote.trading_symbol

        # Update price history (up to 30 snapshots)
        if sym not in self.price_history:
            self.price_history[sym] = deque(maxlen=30)
            self.volume_history[sym] = deque(maxlen=30)

        if quote.ltp > 0:
            self.price_history[sym].append(quote.ltp)
        if quote.volume > 0:
            self.volume_history[sym].append(quote.volume)

        prices = list(self.price_history[sym])
        vols = list(self.volume_history[sym])

        # 1. Volatility (sample standard deviation of recent prices as %)
        if len(prices) >= 2:
            std_dev = statistics.stdev(prices)
            mean_p = statistics.mean(prices)
            volatility = round((std_dev / mean_p) * 100.0, 3) if mean_p > 0 else 0.0
        else:
            volatility = 0.0

        # 2. Moving Average & Deviation
        if prices:
            ma = statistics.mean(prices)
            dev_ma = round(((quote.ltp - ma) / ma) * 100.0, 3) if ma > 0 else 0.0
        else:
            dev_ma = 0.0

        # 3. Relative Volume (vs average of recent ticks)
        if len(vols) >= 2:
            avg_vol = statistics.mean(vols)
            rel_vol = round(quote.volume / avg_vol, 2) if avg_vol > 0 else 1.0
        else:
            rel_vol = 1.0

        # 4. Bid-Ask Spread %
        if quote.bid_price > 0 and quote.ask_price > 0:
            gross_spread = quote.ask_price - quote.bid_price
            spread_pct = round((gross_spread / quote.bid_price) * 100.0, 3)
        else:
            spread_pct = 0.0

        # 5. Potential Gap % (e.g. Deviation from Close / Previous reference)
        ref_price = quote.close if quote.close > 0 else quote.open
        if ref_price > 0 and quote.ltp > 0:
            gap_pct = round(((quote.ltp - ref_price) / ref_price) * 100.0, 2)
        else:
            gap_pct = quote.change_pct

        # 6. Estimated Net Opportunity Edge after full transaction friction
        # Modeled with bid-ask spread, round-trip statutory costs, and execution slippage
        exec_buy_price = quote.ask_price if quote.ask_price > 0 else quote.ltp
        exec_sell_price = quote.bid_price if quote.bid_price > 0 else quote.ltp

        costs = self.cost_calc.calculate_round_trip_cost(
            entry_price=exec_buy_price,
            exit_price=exec_sell_price,
            quantity=100,
            product="CNC",
        )
        total_friction_pct = round(costs.cost_pct + spread_pct + 0.10, 3)  # Statutory costs + spread + 0.10% slippage
        # A historical price move or gap is not guaranteed profit; net edge requires move to exceed full friction
        expected_move_pct = abs(gap_pct)
        net_edge = round(expected_move_pct - total_friction_pct, 3)

        # 7. Quote Freshness (ms)
        q_time = quote.timestamp or now
        if q_time.tzinfo is None:
            q_time = q_time.replace(tzinfo=timezone.utc)
        freshness_ms = max(0, int((now - q_time).total_seconds() * 1000))

        return ScannerRow(
            trading_symbol=sym,
            exchange=quote.exchange,
            name=company_name,
            ltp=quote.ltp,
            bid=quote.bid_price,
            ask=quote.ask_price,
            spread_pct=spread_pct,
            change_pct=quote.change_pct,
            volume=quote.volume,
            relative_volume=rel_vol,
            high=quote.high,
            low=quote.low,
            volatility=volatility,
            deviation_from_ma=dev_ma,
            gap_pct=gap_pct,
            net_edge_pct=net_edge,
            data_quality=quote.data_quality,
            quote_timestamp=q_time,
            data_freshness_ms=freshness_ms,
        )

    def get_latest_rows(self) -> List[ScannerRow]:
        if not self.cached_rows:
            return self.scan_all()
        return list(self.cached_rows.values())

    def get_row(self, symbol: str) -> Optional[ScannerRow]:
        return self.cached_rows.get(symbol.upper())
