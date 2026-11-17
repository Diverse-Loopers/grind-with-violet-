"""
Instrument ORM model and Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from app.database import Base


class Instrument(Base):
    """Tradeable instrument (NSE equity)."""

    __tablename__ = "instruments"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    trading_symbol: str = Column(String(50), unique=True, nullable=False, index=True)  # type: ignore[assignment]
    exchange: str = Column(String(10), nullable=False, default="NSE")  # type: ignore[assignment]
    segment: str = Column(String(10), nullable=False, default="CASH")  # type: ignore[assignment]
    name: str = Column(String(200), nullable=False, default="")  # type: ignore[assignment]
    isin: str = Column(String(20), nullable=True)  # type: ignore[assignment]
    lot_size: int = Column(Integer, nullable=False, default=1)  # type: ignore[assignment]
    tick_size: float = Column(Float, nullable=False, default=0.05)  # type: ignore[assignment]
    is_active: bool = Column(Boolean, nullable=False, default=True)  # type: ignore[assignment]
    created_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # type: ignore[assignment]
    updated_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<Instrument {self.trading_symbol} ({self.exchange}:{self.segment})>"


# ── Pydantic Schemas ──────────────────────────────────────────


class InstrumentCreate(BaseModel):
    """Schema for creating an instrument."""

    trading_symbol: str = Field(..., min_length=1, max_length=50)
    exchange: str = Field(default="NSE", max_length=10)
    segment: str = Field(default="CASH", max_length=10)
    name: str = Field(default="", max_length=200)
    isin: Optional[str] = Field(default=None, max_length=20)
    lot_size: int = Field(default=1, ge=1)
    tick_size: float = Field(default=0.05, gt=0)
    is_active: bool = Field(default=True)


class InstrumentResponse(BaseModel):
    """Schema for instrument API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    trading_symbol: str
    exchange: str
    segment: str
    name: str
    isin: Optional[str] = None
    lot_size: int
    tick_size: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
