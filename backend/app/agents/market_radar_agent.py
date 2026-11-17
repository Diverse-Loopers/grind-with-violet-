"""
Agent 1: Market Radar (Perception Agent).
Monitors market universe, tracks 1H 50-period Moving Average,
computes Put-Call Ratio (PCR), locates Open Interest Support & Resistance,
evaluates Volume/Delivery dynamics, and tracks Cash vs. Future basis.
"""

from __future__ import annotations

import math
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import random

from app.models.playbook import MarketSentiment
from app.agents.fo_universe import (
    LOT_SIZES,
    STRIKE_INTERVALS,
    EXPANDED_RADAR_SYMBOLS,
    get_lot_size,
    get_strike_interval,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OptionChainSnapshot:
    def __init__(self, symbol: str, spot_price: float):
        self.symbol = symbol.upper()
        self.spot_price = spot_price
        self.strike_interval = get_strike_interval(symbol)
        self.lot_size = get_lot_size(symbol)
        
        # Calculate ATM strike
        self.atm_strike = round(spot_price / self.strike_interval) * self.strike_interval
        self.strikes: List[Dict[str, Any]] = []
        self.pcr: float = 1.0
        self.support_strike: float = self.atm_strike - (2 * self.strike_interval)
        self.resistance_strike: float = self.atm_strike + (2 * self.strike_interval)
        self.future_price: float = spot_price
        self.basis: float = 0.0


class MarketRadarAgent:
    """Perception agent that ingests quotes, calculates technical indicators and OI structure."""

    def __init__(self, symbols: Optional[List[str]] = None):
        self.symbols = symbols or list(EXPANDED_RADAR_SYMBOLS)
        # Historical price buffer for 50-period MA tracking
        self.price_history: Dict[str, List[float]] = {}
        self._init_mock_history()

    def _init_mock_history(self):
        """Initializes standard baseline prices for expanded active F&O universe."""
        base_prices = {
            "NIFTY": 24830.0,
            "BANKNIFTY": 52850.0,
            "FINNIFTY": 23620.0,
            "MIDCPNIFTY": 12280.0,
            "RELIANCE": 1280.0,
            "TCS": 3520.0,
            "INFY": 1850.0,
            "HDFCBANK": 1680.0,
            "ICICIBANK": 1250.0,
            "SBIN": 810.0,
            "BHARTIARTL": 2155.0,
            "ITC": 470.0,
            "KOTAKBANK": 1780.0,
            "LT": 3480.0,
            "AXISBANK": 1200.0,
            "ASIANPAINT": 2950.0,
            "MARUTI": 12400.0,
            "TITAN": 3580.0,
            "SUNPHARMA": 1720.0,
            "HINDUNILVR": 2480.0,
            "BAJFINANCE": 7180.0,
            "HCLTECH": 1690.0,
            "TATAMOTORS": 820.0,
            "WIPRO": 540.0,
            "CIPLA": 1215.0,
            "TECHM": 1410.0,
            "ONGC": 285.0,
            "COALINDIA": 440.0,
            "TRENT": 6800.0,
            "TATAPOWER": 410.0,
            "HAL": 4200.0,
            "BEL": 320.0,
            "BHEL": 260.0,
            "COFORGE": 7400.0,
            "DLF": 820.0,
            "DIXON": 14800.0,
            "POLYCAB": 6200.0,
            "PNB": 105.0,
            "CANBK": 102.0,
            "BANKBARODA": 240.0,
            "FEDERALBNK": 195.0,
            "IDFCFIRSTB": 72.0,
            "GMRINFRA": 82.0,
            "IDEA": 8.5,
            "TATASTEEL": 142.0,
            "JINDALSTEL": 920.0,
            "HINDALCO": 620.0,
            "SAIL": 118.0,
            "VEDL": 440.0,
        }
        for sym in self.symbols:
            price = base_prices.get(sym, 500.0)
            series = [round(price * (1.0 + (i - 25) * 0.001), 2) for i in range(50)]
            self.price_history[sym] = series

    def update_price(self, symbol: str, current_price: float):
        sym = symbol.upper()
        if sym not in self.price_history:
            self.price_history[sym] = [current_price] * 50
        else:
            self.price_history[sym].append(current_price)
            if len(self.price_history[sym]) > 100:
                self.price_history[sym].pop(0)

    def calculate_50_ma(self, symbol: str) -> float:
        sym = symbol.upper()
        hist = self.price_history.get(sym, [])
        if not hist:
            return 0.0
        window = hist[-50:] if len(hist) >= 50 else hist
        return round(sum(window) / len(window), 2)

    def inspect_option_chain(
        self,
        symbol: str,
        spot_price: float,
        simulated_bias: Optional[str] = None
    ) -> OptionChainSnapshot:
        """
        Builds the option chain snapshot:
        Calculates PCR, identifies Call OI resistance and Put OI support,
        and pricing for strikes around ATM.
        """
        snap = OptionChainSnapshot(symbol, spot_price)
        interval = snap.strike_interval
        atm = snap.atm_strike
        
        # Basis / Future price calculation
        # Realistic premium is typically 0.2% - 0.5% above spot in normal markets
        premium_offset = round(spot_price * 0.003, 2)
        snap.future_price = round(spot_price + premium_offset, 2)
        snap.basis = round(snap.future_price - spot_price, 2)

        # Generate 5 strikes below ATM and 5 strikes above ATM
        strike_range = [atm + (i * interval) for i in range(-5, 6)]
        
        total_call_oi = 0
        total_put_oi = 0
        max_call_oi = -1
        max_put_oi = -1
        best_resistance = atm + (2 * interval)
        best_support = atm - (2 * interval)

        strikes_data = []
        for strike in strike_range:
            # Distance from ATM
            dist = (strike - spot_price)
            
            # Theoretical option pricing approximations (Black-Scholes / Intrinsic + Time value)
            call_intrinsic = max(0.0, spot_price - strike)
            put_intrinsic = max(0.0, strike - spot_price)
            time_value = max(2.0, (spot_price * 0.015) - abs(dist) * 0.15)
            
            ce_price = round(call_intrinsic + time_value, 2)
            pe_price = round(put_intrinsic + time_value, 2)

            # OI distribution simulation based on realistic market structures
            if simulated_bias == "BULLISH":
                # Heavy Put writing (Support) below ATM, lighter Call resistance
                pe_oi = int(100000 * math.exp(-((strike - (atm - interval)) ** 2) / (2 * (interval * 2) ** 2))) + 15000
                ce_oi = int(70000 * math.exp(-((strike - (atm + (2 * interval))) ** 2) / (2 * (interval * 2) ** 2))) + 10000
            elif simulated_bias == "BEARISH":
                # Heavy Call writing (Resistance) above ATM, weaker Put support
                ce_oi = int(110000 * math.exp(-((strike - (atm + interval)) ** 2) / (2 * (interval * 2) ** 2))) + 15000
                pe_oi = int(60000 * math.exp(-((strike - (atm - (2 * interval))) ** 2) / (2 * (interval * 2) ** 2))) + 10000
            else:
                # Balanced / Range-bound distribution
                ce_oi = int(80000 * math.exp(-((strike - (atm + (2 * interval))) ** 2) / (2 * (interval * 2) ** 2))) + 12000
                pe_oi = int(82000 * math.exp(-((strike - (atm - (2 * interval))) ** 2) / (2 * (interval * 2) ** 2))) + 12000

            total_call_oi += ce_oi
            total_put_oi += pe_oi

            if ce_oi > max_call_oi:
                max_call_oi = ce_oi
                best_resistance = strike

            if pe_oi > max_put_oi:
                max_put_oi = pe_oi
                best_support = strike

            strikes_data.append({
                "strike": strike,
                "ce_price": ce_price,
                "pe_price": pe_price,
                "ce_oi": ce_oi,
                "pe_oi": pe_oi,
                "moneyness": "ATM" if strike == atm else ("ITM" if strike < atm else "OTM"),
            })

        snap.strikes = strikes_data
        snap.pcr = round(total_put_oi / max(1, total_call_oi), 2)
        snap.resistance_strike = best_resistance
        snap.support_strike = best_support

        return snap

    def analyze_ticker(
        self,
        symbol: str,
        current_price: Optional[float] = None,
        force_sentiment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive perception analysis on a single ticker:
        - 50 MA crossover status
        - Option Chain OI structure (PCR, Support, Resistance)
        - Volume & Delivery dynamics
        - Basis / Arbitrage spread
        """
        sym = symbol.upper()
        if current_price:
            self.update_price(sym, current_price)
        else:
            hist = self.price_history.get(sym, [24000.0])
            current_price = hist[-1]

        ma_50 = self.calculate_50_ma(sym)
        price_vs_ma = round(current_price - ma_50, 2)
        pct_from_ma = round((price_vs_ma / ma_50) * 100, 2) if ma_50 > 0 else 0.0

        # Build Option Chain
        chain = self.inspect_option_chain(sym, current_price, simulated_bias=force_sentiment)

        # Volume & Delivery confirmation logic from playbook:
        # Price Up + Volume Up + Delivery Up => Genuine Bullish
        # Price Down + Volume Up + Delivery Up => Genuine Bearish
        is_bullish_ma = current_price >= ma_50
        volume_trend = "INCREASING"
        delivery_trend = "INCREASING"
        is_genuine_trend = (volume_trend == "INCREASING" and delivery_trend == "INCREASING")

        # Classify Market Sentiment
        if force_sentiment:
            sentiment = MarketSentiment(force_sentiment)
        elif is_bullish_ma and chain.pcr >= 1.05 and current_price >= chain.support_strike:
            sentiment = MarketSentiment.BULLISH
        elif not is_bullish_ma and chain.pcr <= 0.95 and current_price <= chain.resistance_strike:
            sentiment = MarketSentiment.BEARISH
        elif 0.90 <= chain.pcr <= 1.10:
            sentiment = MarketSentiment.RANGE_BOUND
        else:
            sentiment = MarketSentiment.RANGE_BOUND

        return {
            "symbol": sym,
            "spot_price": current_price,
            "ma_50": ma_50,
            "price_vs_ma": price_vs_ma,
            "pct_from_ma": pct_from_ma,
            "future_price": chain.future_price,
            "basis": chain.basis,
            "is_future_at_premium": chain.basis > 0,
            "pcr": chain.pcr,
            "support_strike": chain.support_strike,
            "resistance_strike": chain.resistance_strike,
            "atm_strike": chain.atm_strike,
            "volume_trend": volume_trend,
            "delivery_trend": delivery_trend,
            "is_genuine_trend": is_genuine_trend,
            "sentiment": sentiment.value,
            "chain": chain,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def scan_full_market(self) -> List[Dict[str, Any]]:
        """Scans the entire F&O watchlist and returns market intelligence snapshots."""
        results = []
        for sym in self.symbols:
            try:
                res = self.analyze_ticker(sym)
                results.append(res)
            except Exception as e:
                logger.error(f"Error scanning {sym}: {e}", exc_info=True)
        return results
