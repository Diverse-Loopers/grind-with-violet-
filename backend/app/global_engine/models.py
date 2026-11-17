"""
Data models and schemas for 24/7 Global Engine & TradingView Integration.
Supports XAU/USD (Gold), Forex, and Crypto instruments with lot sizing,
leverage margin accounting, and TradingView webhook payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class MarketSession(str, Enum):
    TOKYO = "Asian / Tokyo"
    LONDON = "London Open"
    NEW_YORK = "New York / US"
    SYDNEY = "Sydney / Pacific"
    WEEKEND_CRYPTO = "24/7 Continuous"


class GlobalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    HOLD = "HOLD"


class GlobalQuote(BaseModel):
    """Real-time quote for global 24/7 instruments like XAU/USD."""
    symbol: str = "XAUUSD"
    name: str = "Gold Spot / US Dollar"
    bid: float
    ask: float
    ltp: float
    spread: float
    spread_pips: float
    change_24h: float = 0.0
    change_24h_pct: float = 0.0
    high_24h: float
    low_24h: float
    open_24h: float
    volume: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session: str = "London / NY Overlap"
    is_open_24_7: bool = True


class GlobalCandle(BaseModel):
    """OHLCV candlestick."""
    time: int  # Unix timestamp in seconds for lightweight-charts
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class TradingViewAlertPayload(BaseModel):
    """
    Standard TradingView Alert Webhook JSON payload schema.
    Compatible with Pine Script alert() and Alert Webhook JSON formats.
    """
    ticker: str = Field(default="XAUUSD", description="Symbol, e.g. XAUUSD, GOLD, BTCUSD")
    action: str = Field(..., description="buy, sell, close, long, short")
    price: Optional[float] = Field(default=None, description="Trigger price")
    quantity: Optional[float] = Field(default=0.10, description="Lot size (e.g. 0.01 micro, 0.1 mini, 1.0 standard)")
    strategy: Optional[str] = Field(default="TradingView Strategy", description="Pine script or alert name")
    timeframe: Optional[str] = Field(default="15m", description="Bar timeframe")
    tp: Optional[float] = Field(default=None, description="Take profit price")
    sl: Optional[float] = Field(default=None, description="Stop loss price")
    comment: Optional[str] = Field(default="", description="Alert notes or signal description")
    passphrase: Optional[str] = Field(default="", description="Webhook security passphrase")


class TradingViewAlertRecord(BaseModel):
    """Stored history of received TradingView alerts."""
    id: str
    ticker: str
    action: str
    price: float
    quantity: float
    strategy: str
    timeframe: str
    tp: Optional[float] = None
    sl: Optional[float] = None
    status: str = "RECEIVED"  # RECEIVED, EXECUTED, REJECTED, IGNORED
    message: str = ""
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class GlobalPosition(BaseModel):
    """Open or closed position in the 24/7 Global Broker."""
    id: str
    symbol: str = "XAUUSD"
    side: GlobalAction
    lots: float = 0.10
    entry_price: float
    current_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    margin_used: float = 0.0
    pip_gain: float = 0.0
    strategy: str = "MANUAL"
    status: str = "OPEN"  # OPEN, CLOSED
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    close_price: Optional[float] = None
    close_reason: Optional[str] = None


class GlobalAccount(BaseModel):
    """Forex / CFD Margin Account details in USD."""
    currency: str = "USD"
    balance: float = 10_000.0
    equity: float = 10_000.0
    margin_used: float = 0.0
    free_margin: float = 10_000.0
    margin_level_pct: float = 0.0
    leverage: int = 50
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    open_positions_count: int = 0
    win_rate: float = 0.0


class StrategySignal(BaseModel):
    """Signal produced by a 24/7 strategy."""
    strategy_id: str
    strategy_name: str
    symbol: str = "XAUUSD"
    action: GlobalAction
    confidence: float = 0.0  # 0.0 to 1.0
    price: float
    sl: float
    tp: float
    risk_reward: float = 2.0
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OptimizationMetric(BaseModel):
    strategy_id: str
    name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    net_profit: float
    return_pct: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float


class MaxProfitResult(BaseModel):
    """Result of running the Max Profit Multi-Strategy Optimizer."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    best_strategy: str
    max_profit: float
    max_return_pct: float
    optimal_confluence_threshold: float
    optimal_tp_sl_ratio: float
    optimal_leverage: int
    recommended_lot_size: float
    strategies_compared: List[OptimizationMetric]
    ensemble_profit: float
    ensemble_win_rate: float
    ensemble_profit_factor: float
    confluence_score: float
    market_sentiment: str  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
    recommendation_summary: str
