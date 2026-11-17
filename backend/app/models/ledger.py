"""
Unified Ledger ORM Model.
Provides an immutable double-entry style audit ledger for all cash movements,
trade executions, commissions, statutory taxes, and realized P&L across all markets
(Indian Equities, Crypto, and Global Forex/Gold).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class AccountType(str, Enum):
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    GLOBAL_FOREX = "GLOBAL_FOREX"


class LedgerEntryType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRADE_BUY = "TRADE_BUY"
    TRADE_SELL = "TRADE_SELL"
    COMMISSION = "COMMISSION"
    TAX = "TAX"
    REALIZED_PNL = "REALIZED_PNL"


class UnifiedLedgerEntry(Base):
    """Immutable ledger record representing a financial event."""

    __tablename__ = "unified_ledger"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    timestamp: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)  # type: ignore[assignment]
    account_type: str = Column(String(30), nullable=False, index=True)  # EQUITY, CRYPTO, GLOBAL_FOREX
    entry_type: str = Column(String(30), nullable=False, index=True)  # DEPOSIT, TRADE_BUY, etc.
    reference_id: str = Column(String(100), nullable=False, index=True)  # Order ID or transfer ID
    symbol: Optional[str] = Column(String(30), nullable=True)  # e.g. RELIANCE, BTCINR, XAUUSD
    currency: str = Column(String(10), nullable=False, default="INR")  # INR, USDT, USD
    amount: float = Column(Float, nullable=False)  # Net cash movement (+ credit, - debit)
    balance_after: float = Column(Float, nullable=False)  # Running cash balance after entry
    fee: float = Column(Float, nullable=False, default=0.0)  # Brokerage / taker fee
    tax: float = Column(Float, nullable=False, default=0.0)  # STT / GST / TDS
    description: str = Column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<LedgerEntry {self.id} {self.account_type} {self.entry_type} {self.currency} {self.amount:+.2f}>"


# ── Pydantic Response Schema ───────────────────────────────────


class LedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    account_type: str
    entry_type: str
    reference_id: str
    symbol: Optional[str] = None
    currency: str
    amount: float
    balance_after: float
    fee: float
    tax: float
    description: str
