"""
Backtest ORM models and Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class BacktestStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BacktestRun(Base):
    """Record of a backtest execution."""

    __tablename__ = "backtest_runs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    strategy: str = Column(String(20), nullable=False)  # type: ignore[assignment]
    start_date: str = Column(String(20), nullable=False)  # type: ignore[assignment]
    end_date: str = Column(String(20), nullable=False)  # type: ignore[assignment]
    initial_capital: float = Column(Float, nullable=False, default=1_000_000.0)  # type: ignore[assignment]
    final_capital: float = Column(Float, nullable=True)  # type: ignore[assignment]
    total_trades: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    winning_trades: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    losing_trades: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    win_rate: float = Column(Float, nullable=True)  # type: ignore[assignment]
    max_drawdown_pct: float = Column(Float, nullable=True)  # type: ignore[assignment]
    net_return_pct: float = Column(Float, nullable=True)  # type: ignore[assignment]
    profit_factor: float = Column(Float, nullable=True)  # type: ignore[assignment]
    avg_profit: float = Column(Float, nullable=True)  # type: ignore[assignment]
    avg_loss: float = Column(Float, nullable=True)  # type: ignore[assignment]
    sharpe_ratio: float = Column(Float, nullable=True)  # type: ignore[assignment]
    expectancy: float = Column(Float, nullable=True)  # Expected return per trade in INR
    benchmark_return_pct: float = Column(Float, nullable=True)  # Buy & Hold return
    out_of_sample_return_pct: float = Column(Float, nullable=True)  # Validation return (last 30%)
    total_fees: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    status: str = Column(String(20), nullable=False, default=BacktestStatus.RUNNING.value)  # type: ignore[assignment]
    error_message: str = Column(Text, nullable=True)  # type: ignore[assignment]
    created_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<BacktestRun {self.id} {self.strategy} {self.status}>"


class BacktestTrade(Base):
    """Individual trade within a backtest."""

    __tablename__ = "backtest_trades"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    backtest_id: int = Column(Integer, nullable=False, index=True)  # type: ignore[assignment]
    trading_symbol: str = Column(String(50), nullable=False)  # type: ignore[assignment]
    entry_time: str = Column(String(30), nullable=False)  # type: ignore[assignment]
    exit_time: str = Column(String(30), nullable=True)  # type: ignore[assignment]
    entry_price: float = Column(Float, nullable=False)  # type: ignore[assignment]
    exit_price: float = Column(Float, nullable=True)  # type: ignore[assignment]
    quantity: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    side: str = Column(String(10), nullable=False)  # type: ignore[assignment]
    pnl: float = Column(Float, nullable=True)  # type: ignore[assignment]
    fees: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    slippage: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<BacktestTrade {self.trading_symbol} {self.side} pnl={self.pnl}>"


# ── Pydantic Schemas ──────────────────────────────────────────


class BacktestRunCreate(BaseModel):
    """Schema for starting a backtest."""

    strategy: str = Field(..., min_length=1)
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_capital: float = Field(default=1_000_000.0, gt=0)
    symbols: list[str] = Field(default_factory=list)
    train_test_split: float = Field(default=0.7, ge=0.1, le=1.0)


class BacktestRunResponse(BaseModel):
    """Schema for backtest run API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: Optional[float] = None
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    net_return_pct: Optional[float] = None
    profit_factor: Optional[float] = None
    avg_profit: Optional[float] = None
    avg_loss: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    expectancy: Optional[float] = None
    benchmark_return_pct: Optional[float] = None
    out_of_sample_return_pct: Optional[float] = None
    total_fees: float
    status: str
    error_message: Optional[str] = None
    created_at: datetime


class BacktestTradeResponse(BaseModel):
    """Schema for backtest trade API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    backtest_id: int
    trading_symbol: str
    entry_time: str
    exit_time: Optional[str] = None
    entry_price: float
    exit_price: Optional[float] = None
    quantity: int
    side: str
    pnl: Optional[float] = None
    fees: float
    slippage: float
