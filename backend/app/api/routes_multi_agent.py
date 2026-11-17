"""
REST API Endpoints for Multi-Agent Trading System.
Provides full observability, real-time agent reasoning logs,
manual overrides, plan approval, and position lifecycle management.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.agents.multi_agent_orchestrator import multi_agent_system
from app.models.playbook import PlaybookTradePlan, ActiveSpreadPosition

router = APIRouter(prefix="/agents", tags=["Multi-Agent Autonomous System"])


class KillSwitchRequest(BaseModel):
    action: str  # "ENGAGE" or "RESET"
    reason: str = "Manual User Trigger"


class AutoTradeRequest(BaseModel):
    enabled: bool


@router.get("/status")
def get_agents_status() -> Dict[str, Any]:
    """Returns the live operational status, P&L, open positions, and agent logs."""
    return multi_agent_system.get_system_status()


@router.post("/scan")
def trigger_agent_scan(simulated_cash: float = Query(200000.0, description="Available simulated cash for margin")) -> Dict[str, Any]:
    """Triggers an immediate multi-agent scanning, planning, and execution cycle."""
    summary = multi_agent_system.run_orchestration_cycle(simulated_cash=simulated_cash)
    return {
        "status": "COMPLETED",
        "summary": summary,
        "system_status": multi_agent_system.get_system_status(),
    }


@router.get("/plans", response_model=List[PlaybookTradePlan])
def get_trade_plans(limit: int = 20) -> List[PlaybookTradePlan]:
    """Retrieves recently formulated trade plans with agent reasoning and payoff details."""
    return multi_agent_system.generated_plans[-limit:]


@router.post("/execute/{plan_id}")
def manually_execute_plan(plan_id: str) -> Dict[str, Any]:
    """Manually triggers execution of an approved plan."""
    target_plan = next((p for p in multi_agent_system.generated_plans if p.id == plan_id), None)
    if not target_plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")

    if target_plan.status == "REJECTED":
        raise HTTPException(status_code=400, detail=f"Cannot execute rejected plan: {target_plan.rejection_reason}")

    pos = multi_agent_system.execution_agent.execute_plan(target_plan)
    return {"status": "EXECUTED", "position": pos.model_dump()}


@router.get("/positions")
def get_active_spread_positions() -> Dict[str, Any]:
    """Returns all open multi-leg spread positions with live MTM and trailing SL."""
    active = [p.model_dump() for p in multi_agent_system.execution_agent.active_positions.values()]
    closed = [p.model_dump() for p in multi_agent_system.execution_agent.closed_positions[-20:]]
    return {
        "active_positions": active,
        "closed_positions": closed,
        "total_active": len(active),
        "total_closed": len(multi_agent_system.execution_agent.closed_positions),
    }


@router.get("/history")
def get_closed_spreads_history(limit: int = Query(default=100, le=500)) -> Dict[str, Any]:
    """Returns historical closed spreads showing what was bought, sold, and realized profit."""
    closed = multi_agent_system.execution_agent.closed_positions
    sliced = closed[-limit:] if len(closed) > limit else closed
    return {
        "total_closed_count": len(closed),
        "history": [p.model_dump() for p in reversed(sliced)],
    }


@router.get("/scan-results")
def get_latest_scan_results() -> List[Dict[str, Any]]:
    """Returns the market radar analysis for all tickers in the F&O universe."""
    snapshots = multi_agent_system.radar.scan_full_market()
    return [
        {
            "symbol": s["symbol"],
            "spot_price": s["spot_price"],
            "ma_50": s["ma_50"],
            "price_vs_ma": s["price_vs_ma"],
            "pct_from_ma": s["pct_from_ma"],
            "future_price": s["future_price"],
            "basis": s["basis"],
            "pcr": s["pcr"],
            "support_strike": s["support_strike"],
            "resistance_strike": s["resistance_strike"],
            "sentiment": s["sentiment"],
            "volume_trend": s["volume_trend"],
            "delivery_trend": s["delivery_trend"],
            "is_genuine_trend": s["is_genuine_trend"],
            "timestamp": s["timestamp"],
        }
        for s in snapshots
    ]


@router.post("/close/{position_id}")
def close_spread_position(position_id: str, reason: str = "Manual User Close") -> Dict[str, Any]:
    """Atomically closes all legs of an active spread position."""
    pos = multi_agent_system.execution_agent.close_position(position_id, reason=reason)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Active position {position_id} not found.")
    return {"status": "CLOSED", "position": pos.model_dump()}


@router.post("/kill-switch")
def toggle_emergency_kill_switch(req: KillSwitchRequest) -> Dict[str, Any]:
    """Engages or resets the emergency circuit breaker."""
    if req.action.upper() == "ENGAGE":
        multi_agent_system.risk_governor.trigger_emergency_kill_switch(req.reason)
        multi_agent_system.log_agent_activity("RiskGovernor", f"🚨 Emergency Kill Switch ENGAGED: {req.reason}", level="CRITICAL")
    elif req.action.upper() == "RESET":
        multi_agent_system.risk_governor.reset_daily_metrics()
        multi_agent_system.log_agent_activity("RiskGovernor", "✓ Emergency Kill Switch RESET. Resuming normal operations.", level="INFO")
    else:
        raise HTTPException(status_code=400, detail="Action must be 'ENGAGE' or 'RESET'")

    return {
        "kill_switch_engaged": multi_agent_system.risk_governor.kill_switch_engaged,
        "reason": multi_agent_system.risk_governor.kill_switch_reason,
    }


@router.post("/toggle-auto-trade")
def toggle_autonomous_trading(req: AutoTradeRequest) -> Dict[str, Any]:
    """Toggles whether the agent network executes approved trades automatically."""
    multi_agent_system.auto_execute = req.enabled
    status_str = "ENABLED" if req.enabled else "PAUSED"
    multi_agent_system.log_agent_activity("Orchestrator", f"Autonomous Auto-Execution {status_str}.", level="INFO")
    return {"auto_execute": multi_agent_system.auto_execute}


@router.get("/playbook")
def get_playbook_specifications() -> Dict[str, Any]:
    """Returns the codified strategies, mathematical definitions, and negative constraints."""
    return {
        "strategies": [
            {
                "name": "Bull Call Spread",
                "sentiment": "BULLISH",
                "rules": "1H 50 MA Cross Above + PCR > 1.05. Buy 1 ATM Call + Sell 1 OTM Call.",
                "risk_profile": "Defined Risk (Net Debit), Capped Profit (Spread - Net Debit). Theta offset.",
            },
            {
                "name": "Bear Put Spread",
                "sentiment": "BEARISH",
                "rules": "1H 50 MA Cross Below + PCR < 0.95. Buy 1 ATM Put + Sell 1 OTM Put.",
                "risk_profile": "Defined Risk (Net Debit), Capped Profit (Spread - Net Debit). Theta offset.",
            },
            {
                "name": "Long Synthetic",
                "sentiment": "BULLISH",
                "rules": "High Conviction 50 MA Breakout. Buy 1 Future + Buy 1 ATM Put Hedge.",
                "risk_profile": "Defined Downside Risk (Put absorbs drop), Unlimited Upside.",
            },
            {
                "name": "Short Synthetic",
                "sentiment": "BEARISH",
                "rules": "High Conviction 50 MA Breakdown. Short 1 Future + Buy 1 ATM Call Hedge.",
                "risk_profile": "Defined Upside Risk (Call absorbs rally), Unlimited Downside.",
            },
            {
                "name": "Long Call Butterfly",
                "sentiment": "RANGE_BOUND",
                "rules": "PCR ~ 1.0, between OI Support and Resistance. Buy 1 ITM + Sell 2 ATM + Buy 1 OTM.",
                "risk_profile": "Ultra-low net debit risk, asymmetric payout at ATM pin.",
            },
            {
                "name": "Cash-to-Future Arbitrage",
                "sentiment": "ARBITRAGE",
                "rules": "Future Basis > 0.2% over Spot. Buy Spot NSE + Short Future. Strictly avoid if discount.",
                "risk_profile": "Zero directional risk, pure basis convergence profit.",
            },
        ],
        "hard_constraints": [
            "Never Trade in Future in Single Side (Naked Future is strictly forbidden).",
            "Short Straddle is forbidden ('Nahi Karna' due to unlimited risk).",
            "Short Strangle is forbidden ('Nahi Karna' due to unlimited risk).",
            "All trades must have strictly defined and capped maximum theoretical loss.",
        ],
    }
