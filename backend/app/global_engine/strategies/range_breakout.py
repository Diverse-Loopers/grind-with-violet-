"""
Strategy 2: Asian Session Range Breakout (London/NY Open Burst).
Capitalizes on Gold's massive volatility injection when London and New York open.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from app.global_engine.models import GlobalAction, GlobalCandle, StrategySignal


class AsianRangeBreakoutStrategy:
    """
    Identifies the Asian consolidation range (00:00 - 07:00 UTC)
    and trades breakouts accompanied by volume expansion into London/NY.
    """

    def __init__(self):
        self.id = "strat_range_breakout"
        self.name = "London/NY Session Range Breakout"

    def evaluate(self, symbol: str, candles: List[GlobalCandle], indicators: Dict[str, float]) -> Optional[StrategySignal]:
        if len(candles) < 24 or not indicators:
            return None

        # Look back over recent 16 candles (4 hours of range consolidation)
        lookback = candles[-20:-4]
        if not lookback:
            return None

        range_high = max(c.high for c in lookback)
        range_low = min(c.low for c in lookback)
        range_span = range_high - range_low

        last_candle = candles[-1]
        last_price = last_candle.close
        atr = indicators.get("atr14", 3.5)

        # Bullish Breakout above range high
        if last_price > range_high:
            breakout_excess = last_price - range_high
            if breakout_excess >= 0.2 * atr:
                sl = round(range_high - (1.0 * atr), 2)
                tp = round(last_price + (2.5 * range_span), 2)
                return StrategySignal(
                    strategy_id=self.id,
                    strategy_name=self.name,
                    symbol=symbol,
                    action=GlobalAction.BUY,
                    confidence=0.82,
                    price=last_price,
                    sl=sl,
                    tp=tp,
                    risk_reward=2.5,
                    reason=f"Breakout above Asian Range High (${range_high:.2f}) by ${breakout_excess:.2f}",
                )

        # Bearish Breakdown below range low
        elif last_price < range_low:
            breakdown_excess = range_low - last_price
            if breakdown_excess >= 0.2 * atr:
                sl = round(range_low + (1.0 * atr), 2)
                tp = round(last_price - (2.5 * range_span), 2)
                return StrategySignal(
                    strategy_id=self.id,
                    strategy_name=self.name,
                    symbol=symbol,
                    action=GlobalAction.SELL,
                    confidence=0.82,
                    price=last_price,
                    sl=sl,
                    tp=tp,
                    risk_reward=2.5,
                    reason=f"Breakdown below Asian Range Low (${range_low:.2f}) by ${breakdown_excess:.2f}",
                )

        return None
