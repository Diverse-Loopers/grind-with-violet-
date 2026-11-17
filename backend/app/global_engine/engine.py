"""
Global 24/7 Engine Orchestrator.
Coordinates market feed, paper broker, TradingView webhook bridge,
and the MAX PROFIT confluence optimizer in a unified runtime.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from app.global_engine.broker import GlobalPaperBroker
from app.global_engine.feed import GlobalMarketFeed
from app.global_engine.models import (
    GlobalAction,
    GlobalCandle,
    GlobalPosition,
    GlobalQuote,
    MaxProfitResult,
    StrategySignal,
    TradingViewAlertRecord,
)
from app.global_engine.strategies.max_profit_optimizer import MaxProfitOptimizer
from app.global_engine.tradingview_bridge import TradingViewBridge
from app.utils.logging import logger


class Global247Engine:
    """Master controller for 24/7 trading, TradingView bridge, and profit optimization."""

    def __init__(self):
        self.feed = GlobalMarketFeed()
        self.broker = GlobalPaperBroker(starting_balance=10_000.0, leverage=50)
        self.bridge = TradingViewBridge(self.feed, self.broker)
        self.optimizer = MaxProfitOptimizer()
        self.auto_confluence_trade: bool = False
        self.confluence_threshold: float = 65.0
        self.confluence_lot_size: float = 0.10
        self._last_scan_time = 0.0
        self._active_signals: List[StrategySignal] = []
        self._confluence_score: float = 0.0
        self._market_sentiment: str = "NEUTRAL"
        self._loop_task: Optional[asyncio.Task] = None

    def tick_cycle(self) -> Dict[str, Any]:
        """Runs a tick cycle: updates quotes, monitors positions for SL/TP, checks confluence."""
        # 1. Update quotes
        quote = self.feed.tick("XAUUSD")
        self.feed.tick("BTCUSD")
        self.feed.tick("EURUSD")

        # 2. Update open positions and trigger TP / SL
        closed_positions = self.broker.update_positions_on_tick(quote)

        # 3. Periodically evaluate strategies (every 5 seconds)
        now = time.time()
        if now - self._last_scan_time >= 5.0:
            self._last_scan_time = now
            candles = self.feed.get_candles("XAUUSD", count=60)
            indicators = self.feed.calculate_indicators("XAUUSD")

            signals, score, sentiment = self.optimizer.evaluate_all(
                symbol="XAUUSD",
                candles=candles,
                indicators=indicators,
                tv_signal=self.bridge.last_signal,
            )
            self._active_signals = signals
            self._confluence_score = score
            self._market_sentiment = sentiment

            # 4. Auto-confluence trade execution if enabled
            if self.auto_confluence_trade and abs(score) >= self.confluence_threshold:
                # Check if we already have an open position in this direction
                open_pos = self.broker.get_open_positions()
                target_action = GlobalAction.BUY if score > 0 else GlobalAction.SELL

                has_direction_pos = any(p.side == target_action and p.symbol == "XAUUSD" for p in open_pos)
                if not has_direction_pos and len(open_pos) < 5:
                    try:
                        atr = indicators.get("atr14", 3.5)
                        sl = quote.ltp - (1.5 * atr) if target_action == GlobalAction.BUY else quote.ltp + (1.5 * atr)
                        tp = quote.ltp + (3.0 * atr) if target_action == GlobalAction.BUY else quote.ltp - (3.0 * atr)

                        self.broker.open_position(
                            symbol="XAUUSD",
                            side=target_action,
                            lots=self.confluence_lot_size,
                            quote=quote,
                            sl=round(sl, 2),
                            tp=round(tp, 2),
                            strategy=f"Confluence MaxProfit ({score:+.0f}%)",
                        )
                        logger.info(f"Auto-executed 24/7 Confluence trade: {target_action.value} XAUUSD ({score:+.0f}%)")
                    except Exception as e:
                        logger.warning(f"Failed auto-confluence trade: {e}")

        return {
            "quote": quote,
            "closed_positions": closed_positions,
            "signals": self._active_signals,
            "confluence_score": self._confluence_score,
            "market_sentiment": self._market_sentiment,
        }

    async def start_background_loop(self):
        """Starts the non-blocking 24/7 background worker."""
        logger.info("Starting Global 24/7 Market Engine background loop...")
        while True:
            try:
                self.tick_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Global 24/7 background loop: {e}", exc_info=True)
            await asyncio.sleep(4.0)

    def optimize(self) -> MaxProfitResult:
        """Runs the Max Profit Multi-Strategy Optimizer."""
        candles = self.feed.get_candles("XAUUSD", count=100)
        account = self.broker.get_account_summary()
        return self.optimizer.optimize_for_max_profit(
            candles=candles,
            starting_capital=account.balance,
            lot_size=self.confluence_lot_size,
            leverage=self.broker.leverage,
        )


# Global Engine Singleton
global_engine = Global247Engine()
