"""
Abstract Broker Adapter interface and shared data models.
All broker implementations must inherit from BrokerAdapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Shared Data Models ────────────────────────────────────────


class Quote(BaseModel):
    """Live market quote for an instrument."""

    trading_symbol: str
    exchange: str = "NSE"
    segment: str = "CASH"
    ltp: float = Field(..., description="Last traded price")
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    bid_price: float = 0.0
    bid_qty: int = 0
    ask_price: float = 0.0
    ask_qty: int = 0
    volume: int = 0
    avg_traded_price: float = 0.0
    oi: int = 0
    timestamp: Optional[datetime] = None
    data_quality: str = "DEMO"


class Candle(BaseModel):
    """OHLCV candle."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDepth(BaseModel):
    """Order book depth."""

    trading_symbol: str
    exchange: str = "NSE"
    bids: list[tuple[float, int]] = Field(default_factory=list, description="List of (price, quantity)")
    asks: list[tuple[float, int]] = Field(default_factory=list, description="List of (price, quantity)")
    timestamp: Optional[datetime] = None


class Holding(BaseModel):
    """Portfolio holding."""

    trading_symbol: str
    exchange: str = "NSE"
    isin: str = ""
    quantity: int = 0
    avg_price: float = 0.0
    ltp: float = 0.0
    pnl: float = 0.0
    day_change: float = 0.0
    day_change_pct: float = 0.0


class BrokerPosition(BaseModel):
    """Broker-reported position."""

    trading_symbol: str
    exchange: str = "NSE"
    product: str = "CNC"
    quantity: int = 0
    avg_price: float = 0.0
    ltp: float = 0.0
    pnl: float = 0.0
    buy_qty: int = 0
    sell_qty: int = 0
    buy_avg: float = 0.0
    sell_avg: float = 0.0


class Funds(BaseModel):
    """Account fund details."""

    available_cash: float = 0.0
    used_margin: float = 0.0
    total_balance: float = 0.0
    collateral: float = 0.0


class OrderResponse(BaseModel):
    """Response from placing an order."""

    success: bool
    order_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    message: str = ""
    status: str = "PENDING"


class OrderStatusResponse(BaseModel):
    """Response from order status query."""

    order_id: str
    status: str
    filled_quantity: int = 0
    average_price: float = 0.0
    message: str = ""


# ── Abstract Adapter ──────────────────────────────────────────


class BrokerAdapter(ABC):
    """Abstract base for all broker integrations."""

    @abstractmethod
    def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        """Get live quote for a symbol."""
        ...

    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
        interval_minutes: int = 5,
    ) -> list[Candle]:
        """Get historical OHLCV candles."""
        ...

    @abstractmethod
    def get_ltp(self, symbol: str, exchange: str = "NSE") -> float:
        """Get last traded price."""
        ...

    @abstractmethod
    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> MarketDepth:
        """Get order book depth."""
        ...

    @abstractmethod
    def get_holdings(self) -> list[Holding]:
        """Get portfolio holdings."""
        ...

    @abstractmethod
    def get_positions(self) -> list[BrokerPosition]:
        """Get open positions."""
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatusResponse:
        """Check status of a placed order."""
        ...

    @abstractmethod
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
        """Place a new order."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        ...

    @abstractmethod
    def get_funds(self) -> Funds:
        """Get account fund details."""
        ...

    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        ...
