"""
Risk settings Pydantic model and AuditLog ORM model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.database import Base


class RiskSettingsRecord(Base):
    """Persistent storage for risk parameters and emergency kill switch."""

    __tablename__ = "risk_settings"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    max_position_pct: float = Column(Float, nullable=False, default=10.0)
    max_daily_loss: float = Column(Float, nullable=False, default=50_000.0)
    max_open_positions: int = Column(Integer, nullable=False, default=10)
    max_single_order_value: float = Column(Float, nullable=False, default=100_000.0)
    quote_max_age_seconds: float = Column(Float, nullable=False, default=30.0)
    min_net_edge_pct: float = Column(Float, nullable=False, default=0.1)
    kill_switch_active: bool = Column(Boolean, nullable=False, default=False)
    strategy_spread_enabled: bool = Column(Boolean, nullable=False, default=True)
    strategy_gap_enabled: bool = Column(Boolean, nullable=False, default=True)
    strategy_pairs_enabled: bool = Column(Boolean, nullable=False, default=True)
    updated_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class RiskSettings(BaseModel):
    """Configurable risk management limits."""

    max_position_pct: float = Field(default=10.0, ge=0, le=100, description="Max single position as % of equity")
    max_daily_loss: float = Field(default=50_000.0, ge=0, description="Max daily loss in INR")
    max_open_positions: int = Field(default=10, ge=1, description="Max number of open positions")
    max_single_order_value: float = Field(default=100_000.0, ge=0, description="Max single order value in INR")
    quote_max_age_seconds: float = Field(default=30.0, ge=1, description="Max acceptable quote age in seconds")
    min_net_edge_pct: float = Field(default=0.1, ge=0, description="Minimum net edge after costs (%)")
    kill_switch_active: bool = Field(default=False, description="Emergency halt for all trading")
    strategy_spread_enabled: bool = Field(default=True)
    strategy_gap_enabled: bool = Field(default=True)
    strategy_pairs_enabled: bool = Field(default=True)
    max_slippage_pct: float = Field(default=0.1, ge=0, description="Max simulated slippage (%)")
    min_volume_threshold: int = Field(default=1000, ge=0, description="Min volume to consider liquid")


class AuditLog(Base):
    """Audit log for risk decisions and system events."""

    __tablename__ = "audit_logs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    timestamp: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)  # type: ignore[assignment]
    event_type: str = Column(String(50), nullable=False, index=True)  # type: ignore[assignment]
    component: str = Column(String(50), nullable=False)  # type: ignore[assignment]
    trading_symbol: str = Column(String(50), nullable=True)  # type: ignore[assignment]
    action: str = Column(String(50), nullable=False)  # type: ignore[assignment]
    details: str = Column(Text, nullable=True)  # type: ignore[assignment]
    outcome: str = Column(String(20), nullable=False, default="INFO")  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} {self.action} {self.outcome}>"


class AuditLogResponse(BaseModel):
    """Schema for audit log API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    event_type: str
    component: str
    trading_symbol: Optional[str] = None
    action: str
    details: Optional[str] = None
    outcome: str
