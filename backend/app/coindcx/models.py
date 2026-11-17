"""
CoinDCX ORM Models and Pydantic Schemas.
Stores simulated crypto paper orders, positions, and virtual wallet balances.
All tables are isolated with strict PAPER mode guarantees.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


# ── SQLAlchemy ORM Models ────────────────────────────────────


class CoinDCXOrder(Base):
    """Simulated crypto paper order."""

    __tablename__ = "coindcx_orders"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    order_id: str = Column(String(100), nullable=False, unique=True, index=True)  # type: ignore[assignment]
    market: str = Column(String(30), nullable=False, index=True)  # e.g. BTCINR, BTCUSDT
    pair: str = Column(String(30), nullable=False)  # e.g. I-BTC_INR, B-BTC_USDT
    side: str = Column(String(10), nullable=False)  # BUY or SELL
    order_type: str = Column(String(20), nullable=False, default="MARKET")
    quantity: float = Column(Float, nullable=False)
    price: float = Column(Float, nullable=False)
    fill_price: float = Column(Float, nullable=False)
    total_value: float = Column(Float, nullable=False)  # quantity * fill_price
    fee: float = Column(Float, nullable=False, default=0.0)  # CoinDCX 0.20%
    tds: float = Column(Float, nullable=False, default=0.0)  # Indian 1.0% TDS on sell leg
    slippage: float = Column(Float, nullable=False, default=0.0)
    status: str = Column(String(20), nullable=False, default="FILLED")
    rejection_reason: Optional[str] = Column(Text, nullable=True)
    mode: str = Column(String(10), nullable=False, default="PAPER")
    created_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    filled_at: Optional[datetime] = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<CoinDCXOrder {self.order_id} {self.side} {self.quantity}x{self.market} @ {self.fill_price}>"


class CoinDCXPosition(Base):
    """Open or closed crypto position in CoinDCX paper broker."""

    __tablename__ = "coindcx_positions"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    market: str = Column(String(30), nullable=False, unique=True, index=True)  # e.g. BTCINR
    base_currency: str = Column(String(10), nullable=False)  # e.g. INR, USDT
    target_currency: str = Column(String(10), nullable=False)  # e.g. BTC, ETH
    quantity: float = Column(Float, nullable=False, default=0.0)
    average_entry_price: float = Column(Float, nullable=False, default=0.0)
    current_price: float = Column(Float, nullable=False, default=0.0)
    unrealized_pnl: float = Column(Float, nullable=False, default=0.0)
    realized_pnl: float = Column(Float, nullable=False, default=0.0)
    total_fees: float = Column(Float, nullable=False, default=0.0)
    updated_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<CoinDCXPosition {self.market} qty={self.quantity} avg={self.average_entry_price:.2f}>"


class CoinDCXWallet(Base):
    """Virtual multi-currency wallet for CoinDCX paper trading."""

    __tablename__ = "coindcx_wallet"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    currency: str = Column(String(10), nullable=False, unique=True, index=True)  # "INR" or "USDT"
    balance: float = Column(Float, nullable=False, default=0.0)
    starting_balance: float = Column(Float, nullable=False, default=0.0)
    updated_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<CoinDCXWallet {self.currency}: {self.balance:.2f}>"


# ── Pydantic Market Data & Trading Schemas ─────────────────────


class MarketDetail(BaseModel):
    """CoinDCX market trading rules and precision constraints."""

    model_config = ConfigDict(extra="ignore")

    coindcx_name: str
    symbol: str = ""
    pair: str
    base_currency_short_name: str
    target_currency_short_name: str
    target_currency_name: str = ""
    base_currency_precision: int = 2
    target_currency_precision: int = 5
    min_quantity: float = 0.0001
    max_quantity: float = 1000.0
    min_price: float = 0.01
    max_price: float = 100000000.0
    min_notional: float = 100.0  # Min order value in base currency
    step: float = 0.0001
    status: str = "active"
    order_types: List[str] = Field(default_factory=list)


class CoinDCXTicker(BaseModel):
    """CoinDCX live market ticker."""

    market: str
    last_price: float
    bid: float
    ask: float
    high: float
    low: float
    volume: float
    change_24_hour: float
    timestamp: int
    spread: float = 0.0
    spread_pct: float = 0.0
    data_freshness_seconds: float = 0.0
    is_stale: bool = False


class CoinDCXOrderBook(BaseModel):
    """CoinDCX Level 2 Order Book."""

    pair: str
    timestamp: int
    bids: List[Tuple[float, float]] = Field(default_factory=list)  # (price, quantity) sorted desc
    asks: List[Tuple[float, float]] = Field(default_factory=list)  # (price, quantity) sorted asc
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0
    spread_pct: float = 0.0
    bid_depth_value: float = 0.0
    ask_depth_value: float = 0.0


class CoinDCXCandle(BaseModel):
    """CoinDCX historical candle."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class ArbitrageOpportunity(BaseModel):
    """
    Cross-Market Arbitrage & Opportunity Scanner Model.
    Compares Direct INR pairs vs Synthetic (USDT pair * USDT/INR exchange rate).
    """

    target_asset: str  # e.g. "BTC", "ETH", "SOL"
    inr_market: str  # "BTCINR"
    usdt_market: str  # "BTCUSDT"
    fx_market: str  # "USDTINR"
    inr_price: float  # Direct price on CoinDCX INR book
    usdt_price: float  # Global USDT price
    usdt_inr_rate: float  # Live USDT/INR exchange rate
    synthetic_inr_price: float  # usdt_price * usdt_inr_rate
    price_discrepancy_inr: float
    price_discrepancy_pct: float
    direction: str  # e.g. "BUY_DIRECT_SELL_SYNTHETIC" or "BUY_SYNTHETIC_SELL_DIRECT"
    estimated_trading_fees_pct: float  # 0.20% taker fee per leg
    estimated_slippage_pct: float  # Orderbook depth-aware estimated slippage
    estimated_statutory_tds_pct: float  # 1.0% Indian Section 194S TDS on crypto sale
    total_execution_cost_pct: float
    net_profit_pct: float
    is_executable: bool
    status: str  # "EXECUTABLE" vs "DETECTED_ONLY"
    execution_reason: str
    timestamp: str


class CoinDCXPaperOrderRequest(BaseModel):
    """Request payload to place a simulated crypto paper order."""

    market: str = Field(..., description="CoinDCX market symbol, e.g. BTCINR, BTCUSDT")
    side: str = Field(..., pattern="^(BUY|SELL)$")
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT)$")
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(default=None, ge=0)
