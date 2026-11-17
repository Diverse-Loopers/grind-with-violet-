"""
Continuous 24/7 Global Market Feed for XAU/USD (Gold Spot), BTC/USD, and EUR/USD.
Generates realistic high-fidelity tick updates, maintains historical candle bars,
tracks global market sessions (Tokyo, London, New York), and computes technical indicators.
"""

from __future__ import annotations

import math
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.global_engine.models import GlobalCandle, GlobalQuote, MarketSession
from app.utils.logging import logger


class GlobalMarketFeed:
    """24/7 market data generator and indicator calculation engine."""

    def __init__(self):
        # Base realistic prices
        self._prices: Dict[str, float] = {
            "XAUUSD": 2748.50,   # Gold Spot / USD
            "BTCUSD": 68450.00,  # Bitcoin / USD (pure 24/7)
            "EURUSD": 1.0825,    # Euro / US Dollar
        }
        self._daily_stats: Dict[str, Dict[str, float]] = {
            "XAUUSD": {"open": 2735.00, "high": 2758.20, "low": 2731.40, "vol": 184500.0},
            "BTCUSD": {"open": 67200.00, "high": 69100.00, "low": 66950.00, "vol": 34200.0},
            "EURUSD": {"open": 1.0810, "high": 1.0865, "low": 1.0795, "vol": 920000.0},
        }
        # Pre-seed 120 candles for 15-minute timeframe (~30 hours of continuous data)
        self._candles_15m: Dict[str, List[GlobalCandle]] = {
            "XAUUSD": self._generate_seed_candles("XAUUSD", 2735.0, 120, interval_mins=15, vol_per_bar=2.8),
            "BTCUSD": self._generate_seed_candles("BTCUSD", 67500.0, 120, interval_mins=15, vol_per_bar=240.0),
            "EURUSD": self._generate_seed_candles("EURUSD", 1.0815, 120, interval_mins=15, vol_per_bar=0.0020),
        }
        self._last_tick_time = time.time()

    def get_current_session(self) -> str:
        """Determines active forex/commodity session based on current UTC time."""
        utc_hour = datetime.now(timezone.utc).hour
        if 0 <= utc_hour < 7:
            return "Tokyo / Asian Session"
        elif 7 <= utc_hour < 12:
            return "London Open Session"
        elif 12 <= utc_hour < 16:
            return "London & NY Overlap (Peak Gold Volatility)"
        elif 16 <= utc_hour < 21:
            return "New York Afternoon"
        else:
            return "Sydney / Pacific Open"

    def _generate_seed_candles(
        self, symbol: str, start_price: float, count: int, interval_mins: int = 15, vol_per_bar: float = 3.0
    ) -> List[GlobalCandle]:
        candles: List[GlobalCandle] = []
        now_ts = int(time.time())
        # Step back in time
        curr_price = start_price
        base_ts = now_ts - (count * interval_mins * 60)

        for i in range(count):
            bar_ts = base_ts + (i * interval_mins * 60)
            # Drift with cyclical volatility
            cycle = math.sin(i / 10.0) * vol_per_bar
            shock = random.gauss(0, vol_per_bar * 0.8)
            o = round(curr_price, 2 if symbol != "EURUSD" else 5)
            c = round(curr_price + cycle + shock, 2 if symbol != "EURUSD" else 5)
            h = round(max(o, c) + abs(random.gauss(0, vol_per_bar * 0.5)), 2 if symbol != "EURUSD" else 5)
            l = round(min(o, c) - abs(random.gauss(0, vol_per_bar * 0.5)), 2 if symbol != "EURUSD" else 5)
            v = round(random.uniform(500, 2500), 1)

            candles.append(GlobalCandle(time=bar_ts, open=o, high=h, low=l, close=c, volume=v))
            curr_price = c

        return candles

    def tick(self, symbol: str = "XAUUSD") -> GlobalQuote:
        """Simulates next high-resolution price tick."""
        curr = self._prices.get(symbol, 2748.50)
        session = self.get_current_session()

        # Session volatility factor
        if "Overlap" in session:
            step_vol = 0.45 if symbol == "XAUUSD" else (25.0 if symbol == "BTCUSD" else 0.0003)
        elif "London" in session:
            step_vol = 0.35 if symbol == "XAUUSD" else (20.0 if symbol == "BTCUSD" else 0.0002)
        else:
            step_vol = 0.20 if symbol == "XAUUSD" else (15.0 if symbol == "BTCUSD" else 0.0001)

        delta = random.gauss(0, step_vol)
        # Gentle mean-reversion anchor
        center = 2750.0 if symbol == "XAUUSD" else (68500.0 if symbol == "BTCUSD" else 1.0830)
        reversion = (center - curr) * 0.01
        new_price = round(curr + delta + reversion, 2 if symbol != "EURUSD" else 5)
        self._prices[symbol] = new_price

        # Update 24h stats
        stats = self._daily_stats[symbol]
        stats["high"] = max(stats["high"], new_price)
        stats["low"] = min(stats["low"], new_price)
        stats["vol"] += round(abs(delta) * 10, 1)

        # Spreads: Gold typical 0.25 - 0.35 USD (2.5 - 3.5 pips)
        spread = 0.30 if symbol == "XAUUSD" else (5.0 if symbol == "BTCUSD" else 0.00015)
        half_spread = spread / 2.0
        bid = round(new_price - half_spread, 2 if symbol != "EURUSD" else 5)
        ask = round(new_price + half_spread, 2 if symbol != "EURUSD" else 5)

        # Pip value: for XAUUSD, 1 pip = $0.10, so spread 0.30 is 3.0 pips
        spread_pips = round(spread / (0.10 if symbol == "XAUUSD" else (1.0 if symbol == "BTCUSD" else 0.0001)), 1)
        chg = round(new_price - stats["open"], 2 if symbol != "EURUSD" else 5)
        chg_pct = round((chg / stats["open"]) * 100.0, 2)

        # Update latest candle
        if self._candles_15m[symbol]:
            latest = self._candles_15m[symbol][-1]
            now_ts = int(time.time())
            if now_ts - latest.time >= 15 * 60:
                # Start new candle
                self._candles_15m[symbol].append(
                    GlobalCandle(
                        time=latest.time + (15 * 60),
                        open=new_price,
                        high=new_price,
                        low=new_price,
                        close=new_price,
                        volume=10.0,
                    )
                )
                if len(self._candles_15m[symbol]) > 200:
                    self._candles_15m[symbol].pop(0)
            else:
                latest.close = new_price
                latest.high = max(latest.high, new_price)
                latest.low = min(latest.low, new_price)
                latest.volume += 2.0

        return GlobalQuote(
            symbol=symbol,
            name="Gold Spot / US Dollar" if symbol == "XAUUSD" else ("Bitcoin / USD" if symbol == "BTCUSD" else "Euro / US Dollar"),
            bid=bid,
            ask=ask,
            ltp=new_price,
            spread=spread,
            spread_pips=spread_pips,
            change_24h=chg,
            change_24h_pct=chg_pct,
            high_24h=stats["high"],
            low_24h=stats["low"],
            open_24h=stats["open"],
            volume=stats["vol"],
            session=session,
            is_open_24_7=True,
        )

    def get_quote(self, symbol: str = "XAUUSD") -> GlobalQuote:
        """Returns the latest quote (triggering tick update if needed)."""
        return self.tick(symbol)

    def get_all_quotes(self) -> List[GlobalQuote]:
        """Returns quotes for all monitored 24/7 assets."""
        return [self.get_quote(s) for s in ["XAUUSD", "BTCUSD", "EURUSD"]]

    def get_candles(self, symbol: str = "XAUUSD", count: int = 100) -> List[GlobalCandle]:
        """Returns recent OHLCV candle bars."""
        candles = self._candles_15m.get(symbol, [])
        return candles[-count:]

    def calculate_indicators(self, symbol: str = "XAUUSD") -> Dict[str, float]:
        """Calculates core technical indicators (EMAs, RSI, Bollinger Bands, ATR) for the symbol."""
        candles = self._candles_15m.get(symbol, [])
        if len(candles) < 30:
            return {}

        closes = [c.close for c in candles]

        # EMA helper
        def calc_ema(series: List[float], period: int) -> float:
            if len(series) < period:
                return series[-1]
            multiplier = 2.0 / (period + 1)
            ema = series[0]
            for val in series[1:]:
                ema = (val - ema) * multiplier + ema
            return round(ema, 2)

        ema9 = calc_ema(closes, 9)
        ema21 = calc_ema(closes, 21)
        ema50 = calc_ema(closes, 50)
        ema200 = calc_ema(closes, min(len(closes), 200))

        # RSI (14)
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(d, 0.0) for d in deltas]
        losses = [abs(min(d, 0.0)) for d in deltas]

        avg_gain = sum(gains[-14:]) / 14.0 if len(gains) >= 14 else 1.0
        avg_loss = sum(losses[-14:]) / 14.0 if len(losses) >= 14 else 1.0
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = round(100.0 - (100.0 / (1.0 + rs)), 2)

        # Bollinger Bands (20, 2.0)
        recent_20 = closes[-20:]
        sma20 = sum(recent_20) / len(recent_20)
        variance = sum((x - sma20) ** 2 for x in recent_20) / len(recent_20)
        std_dev = math.sqrt(variance)
        bb_upper = round(sma20 + (2.0 * std_dev), 2)
        bb_lower = round(sma20 - (2.0 * std_dev), 2)
        bb_middle = round(sma20, 2)

        # ATR (14)
        trs = []
        for i in range(1, min(15, len(candles))):
            prev_close = candles[-i - 1].close
            high = candles[-i].high
            low = candles[-i].low
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        atr14 = round(sum(trs) / len(trs) if trs else 3.50, 2)

        return {
            "ema9": ema9,
            "ema21": ema21,
            "ema50": ema50,
            "ema200": ema200,
            "rsi14": rsi,
            "bb_upper": bb_upper,
            "bb_middle": bb_middle,
            "bb_lower": bb_lower,
            "atr14": atr14,
            "last_close": closes[-1],
        }
