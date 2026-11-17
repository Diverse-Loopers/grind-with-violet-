"""
Risk Management API Routes.
Exposes risk parameters, exposure monitors, kill switch toggles, and audit logs.
"""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.database import get_db_context
from app.models.risk_settings import RiskSettings, AuditLog
from app.models.position import Position

router = APIRouter(prefix="/api/risk", tags=["risk"])


class UpdateRiskSettingsRequest(BaseModel):
    max_position_pct: float
    max_daily_loss: float
    max_open_positions: int
    max_single_order_value: float
    quote_max_age_seconds: float
    min_net_edge_pct: float
    strategy_spread_enabled: bool
    strategy_gap_enabled: bool
    strategy_pairs_enabled: bool


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = "User manual trigger from Risk Console"


@router.get("/settings")
def get_risk_settings() -> Dict[str, Any]:
    from app.main import risk_engine

    return risk_engine.settings.model_dump()


@router.put("/settings")
def update_risk_settings(payload: UpdateRiskSettingsRequest) -> Dict[str, Any]:
    from app.main import risk_engine

    risk_engine.settings.max_position_pct = payload.max_position_pct
    risk_engine.settings.max_daily_loss = payload.max_daily_loss
    risk_engine.settings.max_open_positions = payload.max_open_positions
    risk_engine.settings.max_single_order_value = payload.max_single_order_value
    risk_engine.settings.quote_max_age_seconds = payload.quote_max_age_seconds
    risk_engine.settings.min_net_edge_pct = payload.min_net_edge_pct
    risk_engine.settings.strategy_spread_enabled = payload.strategy_spread_enabled
    risk_engine.settings.strategy_gap_enabled = payload.strategy_gap_enabled
    risk_engine.settings.strategy_pairs_enabled = payload.strategy_pairs_enabled
    risk_engine.persist_settings()

    return {"message": "Risk settings updated successfully and persisted", "settings": risk_engine.settings.model_dump()}


@router.post("/kill-switch")
def toggle_kill_switch(payload: KillSwitchRequest) -> Dict[str, Any]:
    from app.main import risk_engine

    risk_engine.trigger_kill_switch(enabled=payload.enabled, reason=payload.reason)
    return {
        "kill_switch_active": risk_engine.settings.kill_switch_active,
        "message": f"Kill switch {'ACTIVATED' if payload.enabled else 'DEACTIVATED'}",
    }


@router.get("/status")
def get_risk_status() -> Dict[str, Any]:
    from app.main import risk_engine, paper_broker

    funds = paper_broker.get_funds()

    with get_db_context() as db:
        open_positions = db.execute(
            select(Position).where(Position.mode == "PAPER", Position.quantity > 0)
        ).scalars().all()

        max_pos_val = max([p.quantity * p.current_price for p in open_positions], default=0.0)
        open_count = len(open_positions)

    equity = funds.get("total_equity", 1_000_000.0)
    pos_pct_used = (max_pos_val / equity * 100.0) if equity > 0 else 0.0

    alerts = []
    if risk_engine.settings.kill_switch_active:
        alerts.append({"level": "CRITICAL", "message": "Emergency Kill Switch is currently active!"})
    if pos_pct_used > (risk_engine.settings.max_position_pct * 0.9):
        alerts.append({"level": "WARNING", "message": f"Concentration near limit: {pos_pct_used:.1f}% used"})
    if open_count >= risk_engine.settings.max_open_positions:
        alerts.append({"level": "WARNING", "message": f"Max open positions reached ({open_count})"})

    return {
        "kill_switch_active": risk_engine.settings.kill_switch_active,
        "current_exposure": {
            "total_equity": equity,
            "max_single_position_value": round(max_pos_val, 2),
            "max_single_position_pct": round(pos_pct_used, 2),
            "max_single_position_pct_limit": risk_engine.settings.max_position_pct,
            "open_positions_count": open_count,
            "open_positions_limit": risk_engine.settings.max_open_positions,
            "daily_loss": round(max(0.0, -funds.get("daily_pnl", 0.0)), 2),
            "daily_loss_limit": risk_engine.settings.max_daily_loss,
        },
        "alerts": alerts,
    }


@router.get("/audit-log")
def get_audit_log(limit: int = Query(default=50, le=200)) -> Dict[str, Any]:
    with get_db_context() as db:
        logs = db.execute(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
        ).scalars().all()

        return {
            "count": len(logs),
            "logs": [
                {
                    "id": l.id,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                    "event_type": l.event_type,
                    "component": l.component,
                    "trading_symbol": l.trading_symbol,
                    "action": l.action,
                    "details": l.details,
                    "outcome": l.outcome,
                }
                for l in logs
            ],
        }
