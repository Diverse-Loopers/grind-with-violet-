"""
Agent 3: Risk Governor (Chief Risk Officer).
Acts as an independent safety barrier between strategy generation and trade execution.
Enforces:
1. Playbook Compliance (no naked futures, no short straddles/strangles).
2. Maximum allowable risk per trade.
3. Daily cumulative drawdown kill-switch.
4. Margin and capital availability checks.
5. Max concurrent active positions.
6. Minimum Risk:Reward ratio threshold.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.models.playbook import PlaybookTradePlan, StrategyType
from app.agents.strategy_confluence_agent import StrategyConfluenceAgent
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RiskGovernorAgent:
    """Independent risk validation agent with hard circuit breakers."""

    def __init__(
        self,
        max_risk_per_trade_inr: float = 25000.0,
        max_daily_loss_inr: float = 50000.0,
        min_risk_reward_ratio: float = 1.2,
        max_concurrent_spreads: int = 5,
    ):
        self.max_risk_per_trade_inr = max_risk_per_trade_inr
        self.max_daily_loss_inr = max_daily_loss_inr
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.max_concurrent_spreads = max_concurrent_spreads

        # Runtime risk tracking state
        self.daily_realized_loss: float = 0.0
        self.kill_switch_engaged: bool = False
        self.kill_switch_reason: Optional[str] = None
        self.active_position_count: int = 0

    def reset_daily_metrics(self):
        """Resets daily loss counter (e.g. at market open)."""
        self.daily_realized_loss = 0.0
        self.kill_switch_engaged = False
        self.kill_switch_reason = None

    def trigger_emergency_kill_switch(self, reason: str):
        """Immediately halts all automated execution."""
        self.kill_switch_engaged = True
        self.kill_switch_reason = reason
        logger.critical(f"🚨 [KILL SWITCH ENGAGED] {reason}")

    def audit_trade_plan(
        self,
        plan: PlaybookTradePlan,
        available_cash: float,
        current_active_spreads: int = 0
    ) -> tuple[bool, str]:
        """
        Audits a candidate trade plan against all risk rules.
        Returns (is_approved, explanation).
        """
        # 1. Kill Switch Check
        if self.kill_switch_engaged:
            msg = f"Rejected: Circuit Breaker active ({self.kill_switch_reason})"
            plan.status = "REJECTED"
            plan.rejection_reason = msg
            return False, msg

        # 2. Daily Loss Limit Check
        if self.daily_realized_loss >= self.max_daily_loss_inr:
            self.trigger_emergency_kill_switch(
                f"Cumulative daily loss (₹{self.daily_realized_loss:.2f}) reached limit (₹{self.max_daily_loss_inr:.2f})"
            )
            plan.status = "REJECTED"
            plan.rejection_reason = "Daily loss limit breached"
            return False, "Daily loss limit breached"

        # 3. Playbook Compliance Check
        is_compliant, compliance_msg = StrategyConfluenceAgent.validate_playbook_compliance(plan)
        if not is_compliant:
            plan.status = "REJECTED"
            plan.rejection_reason = compliance_msg
            logger.warning(f"Risk Governor rejected plan {plan.id}: {compliance_msg}")
            return False, compliance_msg

        # 4. Max Capital Risk Per Trade Check
        if plan.max_loss > self.max_risk_per_trade_inr:
            msg = (
                f"Max loss of ₹{plan.max_loss:.2f} exceeds allowable risk limit of "
                f"₹{self.max_risk_per_trade_inr:.2f} per trade"
            )
            plan.status = "REJECTED"
            plan.rejection_reason = msg
            return False, msg

        # 5. Risk-to-Reward Check (for directional spreads)
        if plan.strategy_type in (StrategyType.BULL_CALL_SPREAD, StrategyType.BEAR_PUT_SPREAD):
            if plan.risk_reward_ratio < self.min_risk_reward_ratio:
                msg = (
                    f"R:R ratio {plan.risk_reward_ratio:.2f}:1 is below minimum threshold "
                    f"{self.min_risk_reward_ratio}:1"
                )
                plan.status = "REJECTED"
                plan.rejection_reason = msg
                return False, msg

        # 6. Concurrency Check
        if current_active_spreads >= self.max_concurrent_spreads:
            msg = (
                f"Max concurrent active positions ({self.max_concurrent_spreads}) reached. "
                "Waiting for position closures."
            )
            plan.status = "REJECTED"
            plan.rejection_reason = msg
            return False, msg

        # 7. Margin / Cash Requirement Check
        if plan.margin_required > available_cash:
            msg = (
                f"Insufficient capital: Plan requires ₹{plan.margin_required:.2f} margin, "
                f"but available cash is ₹{available_cash:.2f}"
            )
            plan.status = "REJECTED"
            plan.rejection_reason = msg
            return False, msg

        # All checks passed!
        plan.status = "APPROVED"
        logger.info(f"✓ Risk Governor APPROVED plan {plan.id} ({plan.strategy_type.value} on {plan.underlying_symbol})")
        return True, "Risk Governor approved trade plan."
