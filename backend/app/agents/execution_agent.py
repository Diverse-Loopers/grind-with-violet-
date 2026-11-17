"""
Agent 4: Multi-Leg Execution Agent & Position Manager.
Executes approved multi-leg options and synthetic futures orders atomically.
Tracks open spreads, calculates real-time Mark-to-Market (MTM),
manages dynamic trailing stop-losses, and squares off positions at targets.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from app.models.playbook import (
    PlaybookTradePlan,
    ActiveSpreadPosition,
    TradeAction,
    LegType,
)
from app.engine.accounting_engine import AccountingEngine
from app.models.ledger import AccountType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MultiLegExecutionAgent:
    """Orchestrates atomic multi-leg execution and position lifecycle."""

    def __init__(self):
        self.active_positions: Dict[str, ActiveSpreadPosition] = {}
        self.closed_positions: List[ActiveSpreadPosition] = []

    def execute_plan(self, plan: PlaybookTradePlan) -> ActiveSpreadPosition:
        """
        Executes an approved plan atomically.
        Creates an active spread position with trailing profit logic.
        """
        pos_id = f"POS_{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        # Target profit rule: take profit when 75% of theoretical max profit is achieved
        target_profit = round(plan.max_profit * 0.75, 2)
        # Initial stop-loss is set to max allowable loss for this plan
        initial_sl = -round(plan.max_loss, 2)

        pos = ActiveSpreadPosition(
            id=pos_id,
            plan=plan,
            opened_at=now,
            current_pnl=0.0,
            pnl_percentage=0.0,
            trailing_sl=initial_sl,
            target_profit=target_profit,
            is_open=True,
        )
        self.active_positions[pos_id] = pos
        plan.status = "EXECUTED"

        # Record in unified ledger
        try:
            AccountingEngine.record_trade(
                account_type=AccountType.EQUITY.value,
                reference_id=pos_id,
                symbol=plan.underlying_symbol,
                side="BUY" if plan.net_debit > 0 else "SELL",
                quantity=1.0,
                fill_price=plan.net_debit,
                fee=40.0,  # ~Rs. 20 per leg brokerage
                tax=round(plan.net_debit * 0.001, 2),
                currency="INR",
                description=f"Multi-Leg Execution: {plan.strategy_type.value} on {plan.underlying_symbol}",
            )
        except Exception as e:
            logger.warning(f"Could not record ledger entry for {pos_id}: {e}")

        logger.info(
            f"⚡ [EXECUTION] Executed {plan.strategy_type.value} on {plan.underlying_symbol} | "
            f"Net Debit: ₹{plan.net_debit:.2f} | Max Profit: ₹{plan.max_profit:.2f} | PosID: {pos_id}"
        )
        return pos

    def mark_positions_to_market(self, quotes: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Updates MTM and PnL for all open spread positions using underlying spot quotes.
        Applies trailing stop-loss logic and checks target profit triggers.
        """
        updates = []
        for pos_id, pos in list(self.active_positions.items()):
            if not pos.is_open:
                continue

            spot = quotes.get(pos.plan.underlying_symbol, pos.plan.spot_price)
            pnl = self._estimate_position_pnl(pos, spot)
            pos.current_pnl = pnl
            pos.pnl_percentage = round((pnl / max(1.0, pos.plan.max_loss)) * 100, 2)

            # Trailing Stop-Loss logic:
            # If position is in profit > 30% of target, trail SL to lock in break-even + 10%
            if pnl > (pos.target_profit * 0.30) and pos.trailing_sl < 0:
                pos.trailing_sl = round(pnl * 0.20, 2)
                logger.info(f"🛡️ Trailing SL raised to +₹{pos.trailing_sl:.2f} for {pos.id}")

            # Check Auto-Exit Triggers:
            # 1. Target Profit Hit
            if pnl >= pos.target_profit:
                self.close_position(pos_id, reason=f"Target Profit Reached (+₹{pnl:.2f})", exit_spot=spot)
            # 2. Trailing SL Hit
            elif pnl <= pos.trailing_sl:
                self.close_position(pos_id, reason=f"Stop-Loss Hit (₹{pnl:.2f})", exit_spot=spot)

            updates.append({
                "pos_id": pos_id,
                "symbol": pos.plan.underlying_symbol,
                "strategy": pos.plan.strategy_type.value,
                "current_spot": spot,
                "pnl": pos.current_pnl,
                "pnl_percentage": pos.pnl_percentage,
                "is_open": pos.is_open,
            })
        return updates

    def _estimate_position_pnl(self, pos: ActiveSpreadPosition, current_spot: float) -> float:
        """Estimates current mark-to-market P&L based on spot price movement from entry."""
        spot_change = current_spot - pos.plan.spot_price
        plan = pos.plan

        # Estimate delta-based payoff for spreads
        if plan.strategy_type.value == "BULL_CALL_SPREAD":
            # Net positive delta (~0.3 to 0.5)
            pts = max(-plan.max_loss / plan.legs[0].lot_size, min(plan.max_profit / plan.legs[0].lot_size, spot_change * 0.45))
            return round(pts * plan.legs[0].lot_size, 2)

        elif plan.strategy_type.value == "BEAR_PUT_SPREAD":
            # Net negative delta
            pts = max(-plan.max_loss / plan.legs[0].lot_size, min(plan.max_profit / plan.legs[0].lot_size, -spot_change * 0.45))
            return round(pts * plan.legs[0].lot_size, 2)

        elif plan.strategy_type.value == "LONG_SYNTHETIC":
            # 1:1 delta above ATM, capped below ATM
            lot = plan.legs[0].lot_size
            if current_spot >= pos.plan.spot_price:
                return round(spot_change * lot, 2)
            else:
                return -round(min(plan.max_loss, abs(spot_change) * lot), 2)

        elif plan.strategy_type.value == "SHORT_SYNTHETIC":
            lot = plan.legs[0].lot_size
            if current_spot <= pos.plan.spot_price:
                return round(abs(spot_change) * lot, 2)
            else:
                return -round(min(plan.max_loss, spot_change * lot), 2)

        elif plan.strategy_type.value == "LONG_CALL_BUTTERFLY":
            # Pins around ATM
            dist = abs(current_spot - plan.spot_price)
            interval = abs(plan.breakeven_points[1] - plan.breakeven_points[0]) / 2.0
            if dist < interval:
                decay_factor = 1.0 - (dist / interval)
                return round(plan.max_profit * decay_factor, 2)
            else:
                return -round(plan.max_loss, 2)

        elif plan.strategy_type.value == "CASH_FUTURE_ARBITRAGE":
            # Constant accrual toward basis convergence
            return round(plan.max_profit * 0.5, 2)

        return 0.0

    def close_position(self, pos_id: str, reason: str = "Manual Close", exit_spot: Optional[float] = None) -> Optional[ActiveSpreadPosition]:
        """Closes an active position and records realized P&L."""
        pos = self.active_positions.get(pos_id)
        if not pos or not pos.is_open:
            return None

        pos.is_open = False
        pos.closed_at = datetime.now(timezone.utc).isoformat()
        pos.realized_pnl = pos.current_pnl
        pos.plan.status = "CLOSED"

        # Move to closed history
        self.closed_positions.append(pos)
        del self.active_positions[pos_id]

        logger.info(
            f"🏁 [CLOSED] Position {pos_id} ({pos.plan.strategy_type.value} on {pos.plan.underlying_symbol}) "
            f"closed. Realized PnL: ₹{pos.realized_pnl:.2f} | Reason: {reason}"
        )
        return pos
