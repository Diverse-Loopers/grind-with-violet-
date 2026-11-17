"""
Position ORM model and Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class Position(Base):
    """Open or closed trading position."""

    __tablename__ = "positions"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    instrument_id: int = Column(Integer, nullable=True, index=True)  # type: ignore[assignment]
    trading_symbol: str = Column(String(50), nullable=False, index=True)  # type: ignore[assignment]
    exchange: str = Column(String(10), nullable=False, default="NSE")  # type: ignore[assignment]
    quantity: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    average_entry_price: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    current_price: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    unrealized_pnl: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    realized_pnl: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    total_fees: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    strategy: str = Column(String(20), nullable=True)  # type: ignore[assignment]
    mode: str = Column(String(10), nullable=False, default="PAPER")  # type: ignore[assignment]
    opened_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # type: ignore[assignment]
    updated_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))  # type: ignore[assignment]
    closed_at: datetime = Column(DateTime, nullable=True)  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<Position {self.trading_symbol} qty={self.quantity} pnl={self.unrealized_pnl:.2f}>"


# ── Pydantic Schemas ──────────────────────────────────────────


class PositionResponse(BaseModel):
    """Schema for position API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_id: Optional[int] = None
    trading_symbol: str
    exchange: str
    quantity: int
    average_entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_fees: float
    strategy: Optional[str] = None
    mode: str
    opened_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
