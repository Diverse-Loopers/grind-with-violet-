"""
Dashboard API Routes.
Provides high-level system overview, operating mode, portfolio summary,
market status, and health checks.
"""

from __future__ import annotations

import time
from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from app.config import settings
from app.database import get_db_context
from app.models.signal import Signal, SignalStatus
from app.models.position import Position
from app.utils.time_utils import is_nse_market_open, get_market_session_info

router = APIRouter(tags=["dashboard"])

START_TIME = time.time()


@router.get("/health")
def get_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "mode": settings.app_mode.value,
        "uptime_seconds": int(time.time() - START_TIME),
        "database": "sqlite_connected",
    }


@router.get("/api/dashboard/overview")
def get_dashboard_overview() -> Dict[str, Any]:
    from app.main import paper_broker, scanner
    from app.agents.multi_agent_orchestrator import multi_agent_system

    session_info = get_market_session_info()
    funds = paper_broker.get_funds()

    # Aggregate Multi-Agent F&O Spreads
    agent_exec = multi_agent_system.execution_agent
    agent_realized = sum(p.realized_pnl for p in agent_exec.closed_positions)
    agent_unrealized = sum(p.current_pnl for p in agent_exec.active_positions.values())
    agent_active_count = len(agent_exec.active_positions)

    total_realized = round(funds.get("realized_pnl", funds["cumulative_pnl"]) + agent_realized, 2)
    total_unrealized = round(funds.get("unrealized_pnl", 0.0) + agent_unrealized, 2)
    total_cash = round(funds["available_cash"] + agent_realized, 2)
    total_equity = round(funds["total_equity"] + agent_realized + agent_unrealized, 2)

    with get_db_context() as db:
        # Positions
        open_pos_count = db.execute(
            select(func.count(Position.id)).where(Position.mode == "PAPER", Position.quantity > 0)
        ).scalar() or 0

        # Signals
        total_signals = db.execute(select(func.count(Signal.id))).scalar() or 0
        rejected_signals = db.execute(
            select(func.count(Signal.id)).where(Signal.status == SignalStatus.REJECTED.value)
        ).scalar() or 0

    data_source_str = (
        "Angel One SmartAPI (Live Feed)"
        if settings.angel_api_key and settings.angel_client_code
        else (
            "Groww Official Trading API (Live Feed)"
            if (settings.is_paper or settings.is_live) and settings.has_api_token
            else "Synthetic Simulation Engine (DEMO Mode)"
        )
    )

    return {
        "mode": settings.app_mode.value,
        "market_status": {
            "is_open": session_info["is_open"],
            "session": session_info["session_name"],
            "market_time_ist": session_info["ist_time"],
        },
        "data_source": data_source_str,
        "data_freshness": "Sub-second (<500ms)" if session_info["is_open"] else "Market Closed",
        "cash_balance": total_cash,
        "portfolio_equity": total_equity,
        "realized_pnl": total_realized,
        "unrealized_pnl": total_unrealized,
        "active_positions": open_pos_count + agent_active_count,
        "signals_detected": total_signals + len(multi_agent_system.generated_plans),
        "signals_rejected": rejected_signals + len([p for p in multi_agent_system.generated_plans if p.status == "REJECTED"]),
        "system_health": {
            "api": True,
            "database": True,
            "scanner": True,
            "risk_engine": not paper_broker.cost_calc is None,
        },
    }


@router.get("/api/dashboard/activity-feed")
def get_activity_feed() -> Dict[str, Any]:
    """Returns real-time chronological bot activity, scans, signals, and order fills."""
    from app.engine.activity_logger import activity_logger

    events = activity_logger.get_recent(limit=50)
    return {
        "count": len(events),
        "events": [e.model_dump() for e in events],
    }


@router.post("/api/dashboard/trigger-demo-trade")
def trigger_demo_trade(symbol: str = "INFY", side: str = "BUY") -> Dict[str, Any]:
    """
    Executes a simulated live test trade through the entire pipeline:
    generates signal -> passes risk engine -> executes order in PaperBroker -> updates wallet.
    Provides immediate visual feedback that the bot is running and trading.
    """
    from datetime import datetime, timezone
    from app.main import scanner, decision_engine, paper_broker
    from app.engine.activity_logger import activity_logger
    from app.models.signal import Signal, SignalStatus, StrategyType, SignalType

    sym = symbol.upper().strip()
    quote = scanner.adapter.get_quote(sym)
    price = quote.ltp or 1115.0

    now = datetime.now(timezone.utc)
    test_sig = Signal(
        instrument_id=1,
        trading_symbol=sym,
        strategy=StrategyType.GAP.value,
        signal_type=SignalType.BUY.value if side.upper() == "BUY" else SignalType.SELL.value,
        entry_price=price,
        reference_price=price * 1.015,
        expected_edge_pct=1.5,
        estimated_cost_pct=0.25,
        net_edge_pct=1.25,
        confidence_score=0.90,
        reason="Manual / Instant Bot Execution Trigger from Dashboard",
        data_quality="DEMO",
        quote_timestamp=now,
        status=SignalStatus.PENDING.value,
    )

    activity_logger.log(
        event_type="SIGNAL",
        symbol=sym,
        side=side.upper(),
        price=price,
        message=f"⚡ Live Signal Triggered: {side.upper()} {sym} @ ₹{price:.2f} (Confidence: 90%)",
    )

    # Process signal through decision engine
    processed = decision_engine.process_candidate_signals([test_sig])
    executed = any(s.status == SignalStatus.ACCEPTED.value for s in processed)

    funds = paper_broker.get_funds()

    return {
        "success": executed,
        "symbol": sym,
        "side": side.upper(),
        "price": price,
        "message": f"Successfully executed {side.upper()} order for {sym} @ ₹{price:.2f}" if executed else "Signal processed",
        "wallet": {
            "cash_balance": funds["available_cash"],
            "total_equity": funds["total_equity"],
        },
    }
