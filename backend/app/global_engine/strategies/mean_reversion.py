"""
Strategy 3: Dynamic Mean Reversion & RSI Bollinger Scalper.
Specialized for range-bound hours and sharp overextended spikes.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from app.global_engine.models import GlobalAction, GlobalCandle, StrategySignal


class GoldRsiBollingerScalper:
    """
    Identifies overbought/oversold turns at Bollinger Band extremes with RSI exhaustion.
    """

    def __init__(self):
        self.id = "strat_rsi_bollinger"
        self.name = "Gold RSI & Bollinger Scalper"

    def evaluate(self, symbol: str, candles: List[GlobalCandle], indicators: Dict[str, float]) -> Optional[StrategySignal]:
        if len(candles) < 20 or not indicators:
            return None

        last_price = indicators.get("last_close", candles[-1].close)
        bb_upper = indicators.get("bb_upper", 0.0)
        bb_lower = indicators.get("bb_lower", 0.0)
        bb_middle = indicators.get("bb_middle", 0.0)
        rsi = indicators.get("rsi14", 50.0)
        atr = indicators.get("atr14", 3.5)

        # Overbought reversal: Price piercing or near upper BB and RSI > 70
        if last_price >= bb_upper - (0.1 * atr) and rsi >= 70.0:
            sl = round(last_price + (1.2 * atr), 2)
            tp = round(bb_middle, 2)
            confidence = min(0.90, round(0.70 + (rsi - 70.0) / 50.0, 2))
            return StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                symbol=symbol,
                action=GlobalAction.SELL,
                confidence=confidence,
                price=last_price,
                sl=sl,
                tp=tp,
                risk_reward=1.8,
                reason=f"Overbought at Upper Bollinger (${bb_upper:.2f}) with RSI={rsi:.1f} exhaustion",
            )

        # Oversold reversal: Price piercing or near lower BB and RSI < 30
        elif last_price <= bb_lower + (0.1 * atr) and rsi <= 30.0:
            sl = round(last_price - (1.2 * atr), 2)
            tp = round(bb_middle, 2)
            confidence = min(0.90, round(0.70 + (30.0 - rsi) / 50.0, 2))
            return StrategySignal(
                strategy_id=self.id,
                strategy_name=self.name,
                symbol=symbol,
                action=GlobalAction.BUY,
                confidence=confidence,
                price=last_price,
                sl=sl,
                tp=tp,
                risk_reward=1.8,
                reason=f"Oversold at Lower Bollinger (${bb_lower:.2f}) with RSI={rsi:.1f} exhaustion",
            )

        return None
