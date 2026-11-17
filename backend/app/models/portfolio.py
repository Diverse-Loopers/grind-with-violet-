"""
PortfolioSnapshot ORM model and Pydantic schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class PortfolioSnapshot(Base):
    """Point-in-time snapshot of portfolio state."""

    __tablename__ = "portfolio_snapshots"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    timestamp: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)  # type: ignore[assignment]
    cash_balance: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    positions_value: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    total_equity: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    daily_pnl: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    cumulative_pnl: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    drawdown_pct: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    mode: str = Column(String(10), nullable=False, default="PAPER")  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<PortfolioSnapshot equity={self.total_equity:.2f} pnl={self.daily_pnl:.2f}>"


# ── Pydantic Schema ───────────────────────────────────────────


class PortfolioSnapshotResponse(BaseModel):
    """Schema for portfolio snapshot API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    cash_balance: float
    positions_value: float
    total_equity: float
    daily_pnl: float
    cumulative_pnl: float
    drawdown_pct: float
    mode: str
