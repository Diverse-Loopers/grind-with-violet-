"""
Independent Risk Management Engine.
Validates all candidate orders and enforces safety rules, limits, and kill-switches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List

from app.config import settings
from app.models.risk_settings import RiskSettings, RiskSettingsRecord, AuditLog
from app.database import get_db_context
from app.utils.logging import logger
from sqlalchemy import select, update


@dataclass
class RiskDecision:
    passed: bool
    rejection_reasons: list[str]
    risk_score: float
    timestamp: datetime


class RiskEngine:
    """Enforces strict, transparent pre-trade risk controls."""

    def __init__(self, custom_settings: Optional[RiskSettings] = None):
        if custom_settings:
            self.settings = custom_settings
        else:
            self.settings = self._load_persisted_settings()

    def _load_persisted_settings(self) -> RiskSettings:
        """Loads persisted risk parameters and kill switch state from SQLite database."""
        try:
            with get_db_context() as db:
                record = db.execute(
                    select(RiskSettingsRecord).order_by(RiskSettingsRecord.id.desc())
                ).scalars().first()

                if record:
                    return RiskSettings(
                        max_position_pct=record.max_position_pct,
                        max_daily_loss=record.max_daily_loss,
                        max_open_positions=record.max_open_positions,
                        max_single_order_value=record.max_single_order_value,
                        quote_max_age_seconds=record.quote_max_age_seconds,
                        min_net_edge_pct=record.min_net_edge_pct,
                        kill_switch_active=record.kill_switch_active,
                        strategy_spread_enabled=record.strategy_spread_enabled,
                        strategy_gap_enabled=record.strategy_gap_enabled,
                        strategy_pairs_enabled=record.strategy_pairs_enabled,
                    )
        except Exception as e:
            logger.error(f"Failed to load persisted risk settings: {e}")

        # Fallback to default settings
        return RiskSettings(
            max_position_pct=settings.max_position_pct,
            max_daily_loss=settings.max_daily_loss,
            max_open_positions=settings.max_open_positions,
            max_single_order_value=settings.max_single_order_value,
            quote_max_age_seconds=settings.quote_max_age_seconds,
            min_net_edge_pct=settings.spread_min_edge_pct,
            strategy_spread_enabled=settings.strategy_spread_enabled,
            strategy_gap_enabled=settings.strategy_gap_enabled,
            strategy_pairs_enabled=settings.strategy_pairs_enabled,
        )

    def persist_settings(self):
        """Saves current risk parameters and kill switch state to SQLite database."""
        try:
            with get_db_context() as db:
                record = db.execute(
                    select(RiskSettingsRecord).order_by(RiskSettingsRecord.id.desc())
                ).scalars().first()

                now = datetime.now(timezone.utc)
                if not record:
                    record = RiskSettingsRecord(
                        max_position_pct=self.settings.max_position_pct,
                        max_daily_loss=self.settings.max_daily_loss,
                        max_open_positions=self.settings.max_open_positions,
                        max_single_order_value=self.settings.max_single_order_value,
                        quote_max_age_seconds=self.settings.quote_max_age_seconds,
                        min_net_edge_pct=self.settings.min_net_edge_pct,
                        kill_switch_active=self.settings.kill_switch_active,
                        strategy_spread_enabled=self.settings.strategy_spread_enabled,
                        strategy_gap_enabled=self.settings.strategy_gap_enabled,
                        strategy_pairs_enabled=self.settings.strategy_pairs_enabled,
                        updated_at=now,
                    )
                    db.add(record)
                else:
                    record.max_position_pct = self.settings.max_position_pct
                    record.max_daily_loss = self.settings.max_daily_loss
                    record.max_open_positions = self.settings.max_open_positions
                    record.max_single_order_value = self.settings.max_single_order_value
                    record.quote_max_age_seconds = self.settings.quote_max_age_seconds
                    record.min_net_edge_pct = self.settings.min_net_edge_pct
                    record.kill_switch_active = self.settings.kill_switch_active
                    record.strategy_spread_enabled = self.settings.strategy_spread_enabled
                    record.strategy_gap_enabled = self.settings.strategy_gap_enabled
                    record.strategy_pairs_enabled = self.settings.strategy_pairs_enabled
                    record.updated_at = now
                db.commit()
                logger.info("[RISK] Risk settings successfully persisted to SQLite.")
        except Exception as e:
            logger.error(f"Failed to persist risk settings: {e}")

    def trigger_kill_switch(self, enabled: bool = True, reason: str = "Manual override"):
        self.settings.kill_switch_active = enabled
        self.persist_settings()
        self._log_audit(
            event_type="KILL_SWITCH",
            component="RiskEngine",
            action="ACTIVATE" if enabled else "DEACTIVATE",
            details=f"Kill switch set to {enabled}. Reason: {reason}",
            outcome="HALT" if enabled else "RESUME",
        )
        logger.warning(f"🚨 RiskEngine Kill Switch {'ACTIVATED' if enabled else 'DEACTIVATED'}: {reason}")

    def evaluate_order(
        self,
        trading_symbol: str,
        strategy: str,
        side: str,
        quantity: int,
        price: float,
        quote_timestamp: Optional[datetime],
        current_equity: float,
        current_open_positions_count: int,
        existing_position_qty_for_symbol: int,
        daily_realized_loss: float,
        is_market_open: bool,
        net_edge_pct: Optional[float] = None,
        volume: Optional[int] = None,
        system_healthy: bool = True,
    ) -> RiskDecision:
        """
        Validates all 10 pre-trade safety conditions:
        1. Market Open
        2. System Health & Kill Switch
        3. Strategy Enabled
        4. Quote Freshness
        5. Expected Net Edge
        6. Volume & Liquidity
        7. Max Order Value Limit
        8. Max Portfolio Exposure / Position Cap
        9. Max Open Positions Count
        10. Daily Loss Limit & Duplicate Exposure
        """
        rejections: list[str] = []
        now = datetime.now(timezone.utc)

        # 1. Kill Switch Check
        if self.settings.kill_switch_active:
            rejections.append("EMERGENCY_KILL_SWITCH_ACTIVE")

        # 2. Market Open Check
        if not is_market_open:
            rejections.append("MARKET_IS_CLOSED")

        # 3. System Health Check
        if not system_healthy:
            rejections.append("SYSTEM_UNHEALTHY")

        # 4. Strategy Enabled Check
        strat = strategy.upper()
        if strat == "SPREAD" and not self.settings.strategy_spread_enabled:
            rejections.append("STRATEGY_SPREAD_DISABLED")
        elif strat == "GAP" and not self.settings.strategy_gap_enabled:
            rejections.append("STRATEGY_GAP_DISABLED")
        elif strat == "PAIRS" and not self.settings.strategy_pairs_enabled:
            rejections.append("STRATEGY_PAIRS_DISABLED")

        # 5. Quote Freshness Check
        if quote_timestamp:
            # ensure tz-aware comparison
            if quote_timestamp.tzinfo is None:
                quote_timestamp = quote_timestamp.replace(tzinfo=timezone.utc)
            age = (now - quote_timestamp).total_seconds()
            if age > self.settings.quote_max_age_seconds:
                rejections.append(f"STALE_QUOTE_AGE_{age:.1f}S_LIMIT_{self.settings.quote_max_age_seconds}S")

        # 6. Expected Edge Check
        if net_edge_pct is not None and net_edge_pct < self.settings.min_net_edge_pct:
            rejections.append(f"EDGE_TOO_LOW_{net_edge_pct:.3f}%_MIN_{self.settings.min_net_edge_pct}%")

        # 7. Volume Liquidity Check
        if volume is not None and volume < self.settings.min_volume_threshold:
            rejections.append(f"INSUFFICIENT_VOLUME_{volume}_MIN_{self.settings.min_volume_threshold}")

        order_val = price * quantity

        # 8. Single Order Value Limit
        if order_val > self.settings.max_single_order_value:
            rejections.append(f"ORDER_VALUE_EXCEEDS_LIMIT_VAL_{order_val:.0f}_MAX_{self.settings.max_single_order_value:.0f}")

        # 9. Max Position % of Equity
        if current_equity > 0:
            max_allowed_pos = (self.settings.max_position_pct / 100.0) * current_equity
            target_pos_val = (existing_position_qty_for_symbol + quantity) * price
            if target_pos_val > max_allowed_pos:
                rejections.append(
                    f"POSITION_CONCENTRATION_BREACH_{target_pos_val:.0f}_MAX_{max_allowed_pos:.0f}"
                )

        # 10. Open Positions Count Check
        if existing_position_qty_for_symbol == 0 and side.upper() == "BUY":
            if current_open_positions_count >= self.settings.max_open_positions:
                rejections.append(f"MAX_OPEN_POSITIONS_REACHED_{current_open_positions_count}_MAX_{self.settings.max_open_positions}")

        # 11. Daily Loss Limit Check
        if daily_realized_loss >= self.settings.max_daily_loss:
            rejections.append(f"DAILY_LOSS_LIMIT_BREACHED_{daily_realized_loss:.0f}_MAX_{self.settings.max_daily_loss:.0f}")

        # 12. Duplicate / Conflicting Position Check (No Short Selling in cash equity)
        if side.upper() == "SELL" and existing_position_qty_for_symbol < quantity:
            rejections.append("SHORT_SELLING_PROHIBITED_IN_CASH_EQUITY")

        passed = len(rejections) == 0
        risk_score = 0.0 if passed else round(len(rejections) * 0.25, 2)

        # Log audit if rejected or significant
        outcome = "APPROVED" if passed else "REJECTED"
        self._log_audit(
            event_type="ORDER_RISK_CHECK",
            component="RiskEngine",
            trading_symbol=trading_symbol,
            action=f"{side}_{quantity}@{price}",
            details="Passed all checks" if passed else f"Rejections: {', '.join(rejections)}",
            outcome=outcome,
        )

        return RiskDecision(
            passed=passed,
            rejection_reasons=rejections,
            risk_score=risk_score,
            timestamp=now,
        )

    def _log_audit(
        self,
        event_type: str,
        component: str,
        action: str,
        details: str,
        outcome: str,
        trading_symbol: Optional[str] = None,
    ):
        try:
            with get_db_context() as db:
                log = AuditLog(
                    event_type=event_type,
                    component=component,
                    trading_symbol=trading_symbol,
                    action=action,
                    details=details,
                    outcome=outcome,
                )
                db.add(log)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to persist risk audit log: {e}")
