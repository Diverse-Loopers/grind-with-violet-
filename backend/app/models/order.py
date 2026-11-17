"""
Order ORM model and Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ProductType(str, Enum):
    CNC = "CNC"
    INTRADAY = "INTRADAY"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TradingMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class Order(Base):
    """Trade order (paper or live)."""

    __tablename__ = "orders"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    signal_id: int = Column(Integer, nullable=True, index=True)  # type: ignore[assignment]
    instrument_id: int = Column(Integer, nullable=True, index=True)  # type: ignore[assignment]
    trading_symbol: str = Column(String(50), nullable=False, index=True)  # type: ignore[assignment]
    exchange: str = Column(String(10), nullable=False, default="NSE")  # type: ignore[assignment]
    order_type: str = Column(String(10), nullable=False, default=OrderType.MARKET.value)  # type: ignore[assignment]
    transaction_type: str = Column(String(10), nullable=False)  # type: ignore[assignment]
    product: str = Column(String(20), nullable=False, default=ProductType.CNC.value)  # type: ignore[assignment]
    quantity: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    price: float = Column(Float, nullable=True)  # type: ignore[assignment]
    trigger_price: float = Column(Float, nullable=True)  # type: ignore[assignment]
    status: str = Column(String(20), nullable=False, default=OrderStatus.PENDING.value, index=True)  # type: ignore[assignment]
    filled_quantity: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    average_fill_price: float = Column(Float, nullable=True)  # type: ignore[assignment]
    simulated_slippage: float = Column(Float, nullable=True)  # type: ignore[assignment]
    fees: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    paper_or_live: str = Column(String(10), nullable=False, default=TradingMode.PAPER.value)  # type: ignore[assignment]
    broker_order_id: str = Column(String(100), nullable=True)  # type: ignore[assignment]
    order_reference_id: str = Column(String(100), nullable=True, unique=True)  # type: ignore[assignment]
    created_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # type: ignore[assignment]
    updated_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<Order {self.id} {self.transaction_type} {self.quantity}x{self.trading_symbol} [{self.status}]>"


# ── Pydantic Schemas ──────────────────────────────────────────


class OrderCreate(BaseModel):
    """Schema for creating an order."""

    signal_id: Optional[int] = None
    instrument_id: Optional[int] = None
    trading_symbol: str = Field(..., min_length=1)
    exchange: str = Field(default="NSE")
    order_type: OrderType = OrderType.MARKET
    transaction_type: TransactionType
    product: ProductType = ProductType.CNC
    quantity: int = Field(..., gt=0)
    price: Optional[float] = Field(default=None, ge=0)
    trigger_price: Optional[float] = Field(default=None, ge=0)


class OrderResponse(BaseModel):
    """Schema for order API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_id: Optional[int] = None
    instrument_id: Optional[int] = None
    trading_symbol: str
    exchange: str
    order_type: str
    transaction_type: str
    product: str
    quantity: int
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    status: str
    filled_quantity: int
    average_fill_price: Optional[float] = None
    simulated_slippage: Optional[float] = None
    fees: float
    paper_or_live: str
    broker_order_id: Optional[str] = None
    order_reference_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
