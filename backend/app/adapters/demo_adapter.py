"""
Demo broker adapter that generates realistic synthetic Indian equity data.
All data is marked as data_quality=DEMO.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.adapters.base import (
    BrokerAdapter,
    BrokerPosition,
    Candle,
    Funds,
    Holding,
    MarketDepth,
    OrderResponse,
    OrderStatusResponse,
    Quote,
)
from app.utils.logging import get_logger
from app.utils.time_utils import IST, ist_now, is_market_open

logger = get_logger(__name__)

# ── Realistic base prices for active NSE large caps ───────────

_BASE_PRICES: dict[str, dict] = {
    "RELIANCE":    {"price": 1162.0, "name": "Reliance Industries Ltd", "vol_base": 12_000_000},
    "TCS":         {"price": 2450.0, "name": "Tata Consultancy Services Ltd", "vol_base": 2_500_000},
    "INFY":        {"price": 1115.0, "name": "Infosys Ltd", "vol_base": 6_000_000},
    "HDFCBANK":    {"price": 685.0,  "name": "HDFC Bank Ltd", "vol_base": 15_000_000},
    "ICICIBANK":   {"price": 1378.0, "name": "ICICI Bank Ltd", "vol_base": 7_000_000},
    "BHARTIARTL":  {"price": 1950.0, "name": "Bharti Airtel Ltd", "vol_base": 3_500_000},
    "ITC":         {"price": 472.0,  "name": "ITC Ltd", "vol_base": 10_000_000},
    "SBIN":        {"price": 840.0,  "name": "State Bank of India", "vol_base": 12_000_000},
    "KOTAKBANK":   {"price": 1780.0, "name": "Kotak Mahindra Bank Ltd", "vol_base": 2_000_000},
    "LT":          {"price": 3480.0, "name": "Larsen & Toubro Ltd", "vol_base": 1_500_000},
    "WIPRO":       {"price": 540.0,  "name": "Wipro Ltd", "vol_base": 4_000_000},
    "ASIANPAINT":  {"price": 3150.0, "name": "Asian Paints Ltd", "vol_base": 1_200_000},
    "MARUTI":      {"price": 12400.0,"name": "Maruti Suzuki India Ltd", "vol_base": 500_000},
    "TITAN":       {"price": 3580.0, "name": "Titan Company Ltd", "vol_base": 1_000_000},
    "NESTLEIND":   {"price": 2580.0, "name": "Nestle India Ltd", "vol_base": 300_000},
    "BAJFINANCE":  {"price": 7180.0, "name": "Bajaj Finance Ltd", "vol_base": 1_800_000},
    "HCLTECH":     {"price": 1690.0, "name": "HCL Technologies Ltd", "vol_base": 2_500_000},
    "SUNPHARMA":   {"price": 1720.0, "name": "Sun Pharma Industries", "vol_base": 2_000_000},
    "TATAMOTORS":  {"price": 820.0,  "name": "Tata Motors Ltd", "vol_base": 9_000_000},
    "HINDUNILVR":  {"price": 2480.0, "name": "Hindustan Unilever Ltd", "vol_base": 1_500_000},
    "ZOMATO":      {"price": 260.0,  "name": "Zomato Ltd", "vol_base": 25_000_000},
    "JIOFIN":      {"price": 315.0,  "name": "Jio Financial Services Ltd", "vol_base": 18_000_000},
    "PAYTM":       {"price": 1605.0, "name": "One97 Communications Ltd", "vol_base": 4_000_000},
    "ADANIENT":    {"price": 2890.0, "name": "Adani Enterprises Ltd", "vol_base": 3_000_000},
    "TATAPOWER":   {"price": 420.0,  "name": "Tata Power Company Ltd", "vol_base": 8_000_000},
}


class DemoAdapter(BrokerAdapter):
    """
    Generates realistic synthetic market data for demo/development.
    Uses random walk with mean reversion for price simulation.
    """

    def __init__(self, starting_balance: float = 1_000_000.0) -> None:
        self._balance = starting_balance
        self._starting_balance = starting_balance
        self._current_prices: dict[str, float] = {}
        self._price_history: dict[str, list[float]] = defaultdict(list)
        self._prev_close: dict[str, float] = {}
        self._intraday_high: dict[str, float] = {}
        self._intraday_low: dict[str, float] = {}
        self._session_volumes: dict[str, int] = defaultdict(int)
        self._tick_count: int = 0
        self._orders: dict[str, dict] = {}
        self._order_counter: int = 0

        # Initialize prices
        for symbol, info in _BASE_PRICES.items():
            base = info["price"]
            # Add initial random offset ±2%
            price = base * (1 + random.uniform(-0.02, 0.02))
            self._current_prices[symbol] = round(price, 2)
            self._prev_close[symbol] = base
            self._intraday_high[symbol] = price
            self._intraday_low[symbol] = price
            # Seed some price history
            for i in range(50):
                hist_price = base * (1 + random.gauss(0, 0.01))
                self._price_history[symbol].append(round(hist_price, 2))

        logger.info("DemoAdapter initialized with %d instruments", len(_BASE_PRICES))

    def _ensure_symbol_initialized(self, symbol: str) -> None:
        """Initialize price tracking for any of the 2600+ instruments dynamically."""
        if symbol in self._current_prices:
            return

        # 1. Try real live NSE market feed first
        try:
            from app.adapters.market_data_service import fetch_real_nse_quote
            rq = fetch_real_nse_quote(symbol)
            if rq and rq.ltp > 0:
                base = rq.close or rq.ltp
                price = rq.ltp
                self._current_prices[symbol] = price
                self._prev_close[symbol] = base
                self._intraday_high[symbol] = rq.high or price
                self._intraday_low[symbol] = rq.low or price
                _BASE_PRICES[symbol] = {"price": price, "name": symbol, "vol_base": rq.volume or 1_000_000}
                for _ in range(25):
                    self._price_history[symbol].append(round(base * (1 + random.gauss(0, 0.005)), 2))
                return
        except Exception:
            pass

        # 2. Fallback to deterministic baseline if instrument not found
        seed = sum(ord(c) for c in symbol)
        base = round(float((seed * 37) % 2200 + 45), 2)
        price = round(base * (1 + random.uniform(-0.015, 0.015)), 2)
        self._current_prices[symbol] = price
        self._prev_close[symbol] = base
        self._intraday_high[symbol] = round(price * 1.015, 2)
        self._intraday_low[symbol] = round(price * 0.985, 2)
        _BASE_PRICES[symbol] = {"price": base, "name": symbol, "vol_base": 1_000_000}
        for _ in range(25):
            self._price_history[symbol].append(round(base * (1 + random.gauss(0, 0.005)), 2))

    def _simulate_tick(self, symbol: str) -> float:
        """
        Simulate a single price tick using random walk + mean reversion.
        Returns the new price.
        """
        if symbol not in self._current_prices:
            self._ensure_symbol_initialized(symbol)

        current = self._current_prices[symbol]
        base = _BASE_PRICES[symbol]["price"]

        # Random walk component: ±0.05% per tick
        random_move = random.gauss(0, 0.0005) * current

        # Mean reversion: pull back toward base price
        deviation = (current - base) / base
        reversion = -deviation * 0.02 * current

        # Combine
        new_price = current + random_move + reversion
        new_price = max(new_price, base * 0.8)  # Floor at -20%
        new_price = min(new_price, base * 1.2)  # Cap at +20%
        new_price = round(new_price, 2)

        # Snap to tick size
        tick_size = 0.05
        new_price = round(round(new_price / tick_size) * tick_size, 2)

        self._current_prices[symbol] = new_price
        self._price_history[symbol].append(new_price)

        # Keep history manageable
        if len(self._price_history[symbol]) > 500:
            self._price_history[symbol] = self._price_history[symbol][-500:]

        # Update intraday range
        self._intraday_high[symbol] = max(self._intraday_high.get(symbol, new_price), new_price)
        self._intraday_low[symbol] = min(self._intraday_low.get(symbol, new_price), new_price)

        return new_price

    def _get_spread(self, symbol: str) -> tuple[float, float]:
        """
        Generate realistic bid-ask spread.
        Large caps: 0.01-0.05% spread.
        """
        price = self._current_prices.get(symbol, 1000.0)
        # Normal tight spread 0.02-0.05%, with occasional executable liquidity opportunities (0.35-0.55%)
        if random.random() < 0.15:
            base_spread_pct = random.uniform(0.0035, 0.0055)
        else:
            base_spread_pct = random.uniform(0.0002, 0.0006)
        half_spread = price * base_spread_pct / 2
        # Snap to tick
        half_spread = max(0.05, round(round(half_spread / 0.05) * 0.05, 2))
        bid = round(price - half_spread, 2)
        ask = round(price + half_spread, 2)
        return bid, ask

    def _simulate_volume(self, symbol: str) -> int:
        """
        Simulate volume with realistic intraday pattern:
        Higher at open (9:15-10:00) and close (14:30-15:30).
        """
        base_vol = _BASE_PRICES.get(symbol, {}).get("vol_base", 1_000_000)
        now = ist_now()
        hour = now.hour + now.minute / 60.0

        # Volume multiplier based on time of day
        if 9.25 <= hour < 10.0:
            multiplier = random.uniform(1.5, 2.5)  # Opening rush
        elif 14.5 <= hour < 15.5:
            multiplier = random.uniform(1.3, 2.0)  # Closing rush
        elif 12.0 <= hour < 13.5:
            multiplier = random.uniform(0.5, 0.8)  # Lunch lull
        else:
            multiplier = random.uniform(0.8, 1.2)

        # Per-tick volume (fraction of daily)
        tick_volume = int(base_vol * multiplier * random.uniform(0.001, 0.005))
        self._session_volumes[symbol] += tick_volume
        return self._session_volumes[symbol]

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        """Get live quote from real market feed if reachable, or realistic simulated tick."""
        symbol = symbol.upper()

        # Try real live market quote first
        try:
            from app.adapters.market_data_service import fetch_real_nse_quote
            real_quote = fetch_real_nse_quote(symbol, exchange)
            if real_quote:
                return real_quote
        except Exception:
            pass

        if symbol not in self._current_prices:
            self._ensure_symbol_initialized(symbol)

        price = self._simulate_tick(symbol)
        bid, ask = self._get_spread(symbol)
        volume = self._simulate_volume(symbol)
        prev_close = self._prev_close.get(symbol, price)
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

        return Quote(
            trading_symbol=symbol,
            exchange=exchange,
            segment="CASH",
            ltp=price,
            open=self._prev_close.get(symbol, price) * (1 + random.uniform(-0.005, 0.005)),
            high=self._intraday_high.get(symbol, price),
            low=self._intraday_low.get(symbol, price),
            close=prev_close,
            change=change,
            change_pct=change_pct,
            bid_price=bid,
            bid_qty=random.randint(50, 5000) * _BASE_PRICES[symbol].get("lot_size", 1),
            ask_price=ask,
            ask_qty=random.randint(50, 5000) * _BASE_PRICES[symbol].get("lot_size", 1),
            volume=volume,
            avg_traded_price=round(price * random.uniform(0.998, 1.002), 2),
            timestamp=datetime.now(timezone.utc),
            data_quality="DEMO",
        )

    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
        interval_minutes: int = 5,
    ) -> list[Candle]:
        """Generate synthetic historical candles."""
        symbol = symbol.upper()
        base = _BASE_PRICES.get(symbol, {}).get("price", 1000.0)
        base_vol = _BASE_PRICES.get(symbol, {}).get("vol_base", 1_000_000)

        candles: list[Candle] = []
        current_time = start
        current_price = base * (1 + random.uniform(-0.05, 0.05))
        is_session_start = True

        while current_time <= end:
            # Skip weekends
            if current_time.weekday() >= 5:
                current_time += timedelta(days=1)
                current_time = current_time.replace(hour=9, minute=15)
                is_session_start = True
                continue

            # Market hours only (IST 9:15 to 15:30)
            ist_time = current_time.astimezone(IST) if current_time.tzinfo else current_time.replace(tzinfo=IST)
            if ist_time.hour < 9 or (ist_time.hour == 9 and ist_time.minute < 15):
                current_time = current_time.replace(hour=9, minute=15)
                is_session_start = True
                continue
            if ist_time.hour > 15 or (ist_time.hour == 15 and ist_time.minute > 30):
                current_time += timedelta(days=1)
                current_time = current_time.replace(hour=9, minute=15)
                # Overnight session gap
                overnight_gap = random.gauss(0, 0.015)  # ~1.5% overnight news jump
                current_price = round(current_price * (1.0 + overnight_gap), 2)
                is_session_start = True
                continue

            # Simulate realistic opening jump if session start or micro-gap intrabar
            if is_session_start:
                open_gap = random.gauss(0, 0.01)
                open_price = round(current_price * (1.0 + open_gap), 2)
                is_session_start = False
            else:
                open_price = round(current_price, 2)

            # Simulate OHLCV for this candle
            drift = random.gauss(0, 0.003)
            reversion = -(open_price - base) / base * 0.008
            move = (drift + reversion) * open_price

            close_price = round(open_price + move, 2)
            high_price = round(max(open_price, close_price) * (1 + abs(random.gauss(0, 0.004))), 2)
            low_price = round(min(open_price, close_price) * (1 - abs(random.gauss(0, 0.004))), 2)
            volume = int(base_vol * random.uniform(0.01, 0.03) / (375 / interval_minutes))

            candles.append(Candle(
                timestamp=current_time,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=max(1, volume),
            ))

            current_price = close_price
            current_time += timedelta(minutes=interval_minutes)

        return candles

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> float:
        """Get last traded price."""
        symbol = symbol.upper()
        if symbol in self._current_prices:
            return self._simulate_tick(symbol)
        raise ValueError(f"Unknown demo symbol: {symbol}")

    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> MarketDepth:
        """Generate synthetic order book."""
        symbol = symbol.upper()
        price = self._current_prices.get(symbol)
        if price is None:
            raise ValueError(f"Unknown demo symbol: {symbol}")

        tick = 0.05
        bids: list[tuple[float, int]] = []
        asks: list[tuple[float, int]] = []

        for i in range(5):
            bid_price = round(price - (i + 1) * tick * random.uniform(1, 3), 2)
            ask_price = round(price + (i + 1) * tick * random.uniform(1, 3), 2)
            bids.append((bid_price, random.randint(100, 10000)))
            asks.append((ask_price, random.randint(100, 10000)))

        return MarketDepth(
            trading_symbol=symbol,
            exchange=exchange,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc),
        )

    def get_holdings(self) -> list[Holding]:
        """Return empty holdings (demo has none)."""
        return []

    def get_positions(self) -> list[BrokerPosition]:
        """Return empty positions (demo has none)."""
        return []

    def get_order_status(self, order_id: str) -> OrderStatusResponse:
        """Check demo order status."""
        order = self._orders.get(order_id)
        if not order:
            return OrderStatusResponse(order_id=order_id, status="NOT_FOUND", message="Order not found")
        return OrderStatusResponse(
            order_id=order_id,
            status=order.get("status", "FILLED"),
            filled_quantity=order.get("quantity", 0),
            average_price=order.get("price", 0.0),
        )

    def place_order(
        self,
        trading_symbol: str,
        exchange: str,
        transaction_type: str,
        order_type: str,
        quantity: int,
        price: float | None = None,
        trigger_price: float | None = None,
        product: str = "CNC",
        order_reference_id: str | None = None,
    ) -> OrderResponse:
        """Simulate placing an order (demo mode — instant fill)."""
        self._order_counter += 1
        order_id = f"DEMO-{self._order_counter:06d}"

        fill_price = price or self._current_prices.get(trading_symbol.upper(), 1000.0)
        self._orders[order_id] = {
            "symbol": trading_symbol,
            "type": transaction_type,
            "quantity": quantity,
            "price": fill_price,
            "status": "FILLED",
        }

        logger.info("[DEMO] Order placed: %s %d x %s @ %.2f", transaction_type, quantity, trading_symbol, fill_price)
        return OrderResponse(
            success=True,
            order_id=order_id,
            broker_order_id=order_id,
            message=f"DEMO order filled: {transaction_type} {quantity}x{trading_symbol} @ {fill_price}",
            status="FILLED",
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a demo order."""
        if order_id in self._orders:
            self._orders[order_id]["status"] = "CANCELLED"
            return True
        return False

    def get_funds(self) -> Funds:
        """Return simulated fund balance."""
        return Funds(
            available_cash=self._balance,
            used_margin=0.0,
            total_balance=self._balance,
            collateral=0.0,
        )

    def is_market_open(self) -> bool:
        """
        Returns True Mon-Fri 9:15-15:30 IST.
        In demo mode, always returns True so the scanner works.
        """
        return True

    def get_available_symbols(self) -> list[str]:
        """Return list of available demo symbols."""
        return list(_BASE_PRICES.keys())

    def get_symbol_info(self, symbol: str) -> dict:
        """Get base info for a symbol."""
        symbol = symbol.upper()
        info = _BASE_PRICES.get(symbol)
        if not info:
            raise ValueError(f"Unknown demo symbol: {symbol}")
        return {
            "trading_symbol": symbol,
            "name": info["name"],
            "base_price": info["price"],
            "exchange": "NSE",
            "segment": "CASH",
        }
