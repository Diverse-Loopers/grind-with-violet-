"""
Central Multi-Agent Autonomous Orchestrator.
Coordinates the specialized agent network:
1. Agent 1: Market Radar (Perception)
2. Agent 2: Strategy Confluence (Alpha Formulation)
3. Agent 3: Risk Governor (Chief Risk Officer)
4. Agent 4: Execution & Position Manager (Low Latency Execution)
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from app.models.playbook import PlaybookTradePlan, ActiveSpreadPosition
from app.agents.market_radar_agent import MarketRadarAgent
from app.agents.strategy_confluence_agent import StrategyConfluenceAgent
from app.agents.risk_governor_agent import RiskGovernorAgent
from app.agents.execution_agent import MultiLegExecutionAgent
from app.engine.accounting_engine import AccountingEngine
from app.models.ledger import AccountType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MultiAgentOrchestrator:
    """Master agent coordinating autonomous scanning, reasoning, risk validation, and execution."""

    def __init__(self, auto_execute: bool = True):
        self.radar = MarketRadarAgent()
        self.strategy_brain = StrategyConfluenceAgent()
        self.risk_governor = RiskGovernorAgent()
        self.execution_agent = MultiLegExecutionAgent()
        
        self.auto_execute = auto_execute
        self.is_running = False
        self._loop_task: Optional[asyncio.Task] = None
        
        # In-memory history of recent scans, generated plans, and agent communications
        self.generated_plans: List[PlaybookTradePlan] = []
        self.agent_activity_feed: List[Dict[str, Any]] = []

    def log_agent_activity(self, agent_name: str, message: str, level: str = "INFO", details: Optional[Dict[str, Any]] = None):
        """Appends structured agent message to the activity feed."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "level": level,
            "message": message,
            "details": details or {},
        }
        self.agent_activity_feed.append(entry)
        if len(self.agent_activity_feed) > 200:
            self.agent_activity_feed.pop(0)
        logger.info(f"[{agent_name}] {message}")

    def run_orchestration_cycle(self, simulated_cash: float = 200000.0) -> Dict[str, Any]:
        """
        Executes one complete multi-agent cycle:
        Radar -> Strategy Brain -> Risk Governor -> Execution -> MTM Update
        """
        self.log_agent_activity("RadarAgent", "Initiating full F&O market radar pass across index and stock universe.")
        
        # Step 1: Perception scan
        market_snapshots = self.radar.scan_full_market()
        new_plans: List[PlaybookTradePlan] = []
        executed_positions: List[ActiveSpreadPosition] = []

        # Step 2 & 3: Strategy Brain + Risk Governor evaluation
        for snapshot in market_snapshots:
            sym = snapshot["symbol"]
            sentiment = snapshot["sentiment"]
            pcr = snapshot["pcr"]
            spot = snapshot["spot_price"]

            # Strategy Agent formulates candidate plans
            plans = self.strategy_brain.evaluate_and_formulate_plans(snapshot)
            for plan in plans:
                new_plans.append(plan)
                self.generated_plans.append(plan)
                
                self.log_agent_activity(
                    "StrategyBrain",
                    f"Formulated {plan.strategy_type.value} on {sym} | Net Debit: ₹{plan.net_debit:.2f} | R:R {plan.risk_reward_ratio}:1",
                    details={"plan_id": plan.id, "sentiment": sentiment, "pcr": pcr}
                )

                # Risk Governor audits the proposed plan
                active_count = len(self.execution_agent.active_positions)
                approved, risk_reason = self.risk_governor.audit_trade_plan(
                    plan, available_cash=simulated_cash, current_active_spreads=active_count
                )

                if approved:
                    self.log_agent_activity(
                        "RiskGovernor",
                        f"✓ Approved plan {plan.id} ({plan.strategy_type.value} on {sym}) | Sizing: ₹{plan.margin_required:.2f} margin",
                        level="SUCCESS"
                    )
                    # Step 4: Autonomous Execution
                    if self.auto_execute:
                        pos = self.execution_agent.execute_plan(plan)
                        executed_positions.append(pos)
                        self.log_agent_activity(
                            "ExecutionAgent",
                            f"⚡ Executed spread {pos.id} on {sym} with trailing SL target: +₹{pos.target_profit:.2f}",
                            level="SUCCESS"
                        )
                else:
                    self.log_agent_activity(
                        "RiskGovernor",
                        f"✗ Rejected plan {plan.id} on {sym}: {risk_reason}",
                        level="WARNING"
                    )

        # Step 5: Mark open positions to market
        current_quotes = {s["symbol"]: s["spot_price"] for s in market_snapshots}
        mtm_updates = self.execution_agent.mark_positions_to_market(current_quotes)

        # Summary
        summary = {
            "cycle_timestamp": datetime.now(timezone.utc).isoformat(),
            "tickers_scanned": len(market_snapshots),
            "plans_generated": len(new_plans),
            "plans_approved": len([p for p in new_plans if p.status in ("APPROVED", "EXECUTED")]),
            "executions_completed": len(executed_positions),
            "active_positions_count": len(self.execution_agent.active_positions),
            "mtm_updates": mtm_updates,
        }
        return summary

    def get_system_status(self) -> Dict[str, Any]:
        """Provides full telemetry of agents, active spreads, and P&L."""
        active_list = list(self.execution_agent.active_positions.values())
        total_unrealized_pnl = sum(p.current_pnl for p in active_list)
        total_realized_pnl = sum(p.realized_pnl for p in self.execution_agent.closed_positions)

        return {
            "auto_execute": self.auto_execute,
            "kill_switch_engaged": self.risk_governor.kill_switch_engaged,
            "kill_switch_reason": self.risk_governor.kill_switch_reason,
            "active_spreads_count": len(active_list),
            "closed_spreads_count": len(self.execution_agent.closed_positions),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "active_positions": [p.model_dump() for p in active_list],
            "recent_plans": [p.model_dump() for p in self.generated_plans[-15:]],
            "recent_agent_logs": self.agent_activity_feed[-20:],
        }


# Global singleton instance
multi_agent_system = MultiAgentOrchestrator(auto_execute=True)
