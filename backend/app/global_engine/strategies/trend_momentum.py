"""
Strategy 1: Gold EMA Trend Momentum & ATR Trailing Stop.
Specialized for XAU/USD multi-session trending phases.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from app.global_engine.models import GlobalAction, GlobalCandle, StrategySignal


class GoldTrendMomentumStrategy:
    """
    Rides major Gold trends using 9/21/50 EMA alignment and ATR risk buffers.
    """

    def __init__(self):
        self.id = "strat_gold_trend"
        self.name = "Gold EMA Trend Momentum"

    def evaluate(self, symbol: str, candles: List[GlobalCandle], indicators: Dict[str, float]) -> Optional[StrategySignal]:
        if len(candles) < 30 or not indicators:
            return None

        ema9 = indicators.get("ema9", 0.0)
        ema21 = indicators.get("ema21", 0.0)
        ema50 = indicators.get("ema50", 0.0)
        rsi = indicators.get("rsi14", 50.0)
        atr = indicators.get("atr14", 3.5)
        last_price = indicators.get("last_close", candles[-1].close)

        # Bullish Trend: EMA9 > EMA21 > EMA50, price above EMA50, RSI healthy (48-68)
        if ema9 > ema21 > ema50 and last_price > ema21 and 48.0 <= rsi <= 68.0:
            sl = round(last_price - (1.5 * atr), 2)
            tp = round(last_price + (3.0 * atr), 2)
            confidence = min(0.95, round(0.65 + (ema9 - ema21) / (2.0 * atr), 2))
            return StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                symbol=symbol,
                action=GlobalAction.BUY,
                confidence=confidence,
                price=last_price,
                sl=sl,
                tp=tp,
                risk_reward=2.0,
                reason=f"Bullish EMA alignment (9={ema9} > 21={ema21} > 50={ema50}) with RSI {rsi:.1f} pullback",
            )

        # Bearish Trend: EMA9 < EMA21 < EMA50, price below EMA21, RSI weak (32-52)
        elif ema9 < ema21 < ema50 and last_price < ema21 and 32.0 <= rsi <= 52.0:
            sl = round(last_price + (1.5 * atr), 2)
            tp = round(last_price - (3.0 * atr), 2)
            confidence = min(0.95, round(0.65 + (ema21 - ema9) / (2.0 * atr), 2))
            return StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                symbol=symbol,
                action=GlobalAction.SELL,
                confidence=confidence,
                price=last_price,
                sl=sl,
                tp=tp,
                risk_reward=2.0,
                reason=f"Bearish EMA alignment (9={ema9} < 21={ema21} < 50={ema50}) with RSI {rsi:.1f} momentum",
            )

        return None
