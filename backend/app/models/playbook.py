"""
Playbook Data Models for Indian Derivatives (F&O) Multi-Agent System.
Codifies contracts, multi-leg option strategies, payoff profiles, and agent reasoning.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class StrategyType(str, Enum):
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    LONG_SYNTHETIC = "LONG_SYNTHETIC"
    SHORT_SYNTHETIC = "SHORT_SYNTHETIC"
    LONG_CALL_BUTTERFLY = "LONG_CALL_BUTTERFLY"
    LONG_PUT_BUTTERFLY = "LONG_PUT_BUTTERFLY"
    LONG_STRADDLE = "LONG_STRADDLE"
    LONG_STRANGLE = "LONG_STRANGLE"
    CASH_FUTURE_ARBITRAGE = "CASH_FUTURE_ARBITRAGE"
    COVERED_CALL = "COVERED_CALL"


class MarketSentiment(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    ARBITRAGE = "ARBITRAGE"


class LegType(str, Enum):
    CALL = "CE"
    PUT = "PE"
    FUTURE = "FUT"
    EQUITY = "EQ"


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OptionLeg(BaseModel):
    symbol: str
    leg_type: LegType
    action: TradeAction
    strike_price: float = 0.0
    expiry: Optional[str] = None
    entry_price: float
    current_price: float = 0.0
    quantity: int
    lot_size: int
    moneyness: str = "ATM"  # ITM, ATM, OTM


class PlaybookTradePlan(BaseModel):
    id: str = Field(description="Unique plan identifier")
    underlying_symbol: str
    strategy_type: StrategyType
    sentiment: MarketSentiment
    spot_price: float
    legs: List[OptionLeg]
    
    # Financial & Risk Profile
    net_debit: float = Field(description="Total cash outlay / net premium paid")
    max_loss: float = Field(description="Strict maximum theoretical loss")
    max_profit: float = Field(description="Maximum theoretical profit or target profit")
    risk_reward_ratio: float = Field(description="Ratio of Max Profit to Max Loss")
    breakeven_points: List[float] = Field(default_factory=list, description="Zero-profit underlying prices at expiry")
    margin_required: float = 0.0
    
    # Agent Intelligence & Confluence
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confluence score 0 to 1")
    agent_reasoning: str = Field(description="Full explanation of multi-indicator alignment")
    indicators_snapshot: Dict[str, Any] = Field(default_factory=dict)
    
    # Execution Lifecycle
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, EXECUTED, CLOSED
    rejection_reason: Optional[str] = None


class ActiveSpreadPosition(BaseModel):
    id: str
    plan: PlaybookTradePlan
    opened_at: str
    current_pnl: float = 0.0
    pnl_percentage: float = 0.0
    trailing_sl: Optional[float] = None
    target_profit: Optional[float] = None
    is_open: bool = True
    closed_at: Optional[str] = None
    exit_price_summary: Optional[Dict[str, float]] = None
    realized_pnl: float = 0.0
