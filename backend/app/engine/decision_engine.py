"""
Trade Decision Engine.
Evaluates candidate signals from all strategies against the RiskEngine,
persists signals and audit records, and routes approved signals to the PaperBroker.
Live orders are strictly prevented.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, delete, func
from app.config import settings
from app.database import get_db_context
from app.models.signal import Signal, SignalStatus
from app.models.position import Position
from app.engine.risk_engine import RiskEngine, RiskDecision
from app.engine.paper_broker import PaperBroker
from app.engine.activity_logger import activity_logger
from app.adapters.base import BrokerAdapter, Quote
from app.utils.logging import logger


class TradeDecisionEngine:
    """Central arbiter for signal validation and paper execution."""

    def __init__(self, adapter: BrokerAdapter, paper_broker: PaperBroker, risk_engine: Optional[RiskEngine] = None):
        self.adapter = adapter
        self.paper_broker = paper_broker
        self.risk_engine = risk_engine or RiskEngine()

    def process_candidate_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        Evaluates signals against the risk engine.
        Saves all signals to DB with either ACCEPTED or REJECTED status.
        Routes ACCEPTED signals to paper execution.
        """
        # In DEMO or PAPER mode, allow after-hours simulated execution for testing
        is_market_open = True if (settings.is_demo or settings.is_paper) else self.adapter.is_market_open()
        funds = self.paper_broker.get_funds()

        with get_db_context() as db:
            open_positions = db.execute(
                select(Position).where(Position.mode == "PAPER", Position.quantity > 0)
            ).scalars().all()
            positions_by_symbol = {p.trading_symbol: p for p in open_positions}
            open_positions_count = len(open_positions)
            daily_loss = max(0.0, -funds.get("daily_pnl", 0.0))

            processed: List[Signal] = []

            to_execute: List[tuple[Signal, int]] = []

            for sig in signals:
                # If already rejected upstream (e.g. negative net edge or pairs research)
                if sig.status == SignalStatus.REJECTED.value:
                    db.add(sig)
                    processed.append(sig)
                    continue

                existing_pos = positions_by_symbol.get(sig.trading_symbol)
                existing_qty = existing_pos.quantity if existing_pos else 0

                # Standard size sizing for evaluation
                target_quantity = max(1, int(25000 / sig.entry_price)) if sig.entry_price > 0 else 1

                risk_decision: RiskDecision = self.risk_engine.evaluate_order(
                    trading_symbol=sig.trading_symbol,
                    strategy=sig.strategy,
                    side=sig.signal_type,
                    quantity=target_quantity,
                    price=sig.entry_price,
                    quote_timestamp=sig.quote_timestamp,
                    current_equity=funds.get("total_equity", 1_000_000.0),
                    current_open_positions_count=open_positions_count,
                    existing_position_qty_for_symbol=existing_qty,
                    daily_realized_loss=daily_loss,
                    is_market_open=is_market_open,
                    net_edge_pct=sig.net_edge_pct,
                    volume=sig.volume,
                    system_healthy=True,
                )

                if risk_decision.passed:
                    sig.status = SignalStatus.ACCEPTED.value
                    sig.rejection_reason = None
                    db.add(sig)
                    to_execute.append((sig, target_quantity))

                    # Update intra-batch state so subsequent signals strictly respect max positions limit
                    if sig.signal_type == "BUY" and existing_qty == 0:
                        open_positions_count += 1
                        positions_by_symbol[sig.trading_symbol] = Position(
                            trading_symbol=sig.trading_symbol,
                            quantity=target_quantity,
                            average_entry_price=sig.entry_price,
                        )

                    activity_logger.log(
                        event_type="RISK_PASS",
                        symbol=sig.trading_symbol,
                        side=sig.signal_type,
                        price=sig.entry_price,
                        quantity=target_quantity,
                        message=f"🛡️ Risk approved {sig.signal_type} {target_quantity}x {sig.trading_symbol} @ ₹{sig.entry_price:.2f} ({sig.strategy})",
                    )
                else:
                    sig.status = SignalStatus.REJECTED.value
                    sig.rejection_reason = "; ".join(risk_decision.rejection_reasons)
                    db.add(sig)
                    activity_logger.log(
                        event_type="RISK_REJECT",
                        symbol=sig.trading_symbol,
                        side=sig.signal_type,
                        message=f"⚠️ Signal rejected for {sig.trading_symbol}: {sig.rejection_reason}",
                    )

                processed.append(sig)

            db.commit()
            for s in processed:
                try:
                    db.refresh(s)
                    db.expunge(s)
                except Exception:
                    pass

        # Execute accepted signals outside the outer DB session to avoid SQLite nested write locks
        for sig, target_quantity in to_execute:
            quote = self.adapter.get_quote(sig.trading_symbol)
            order_res = self.paper_broker.place_paper_order(
                trading_symbol=sig.trading_symbol,
                transaction_type=sig.signal_type,
                quantity=target_quantity,
                order_type="MARKET",
                product="CNC",
                price=sig.entry_price,
                strategy=sig.strategy,
                signal_id=sig.id,
                quote=quote,
            )
            if order_res.success:
                activity_logger.log(
                    event_type="ORDER_FILLED",
                    symbol=sig.trading_symbol,
                    side=sig.signal_type,
                    price=sig.entry_price,
                    quantity=target_quantity,
                    message=f"✅ PAPER ORDER FILLED: {sig.signal_type} {target_quantity}x {sig.trading_symbol} @ ₹{sig.entry_price:.2f}",
                )

        # Periodic pruning to keep SQLite DB fast and lightweight (<5,000 signals)
        self._scan_counter = getattr(self, "_scan_counter", 0) + 1
        if self._scan_counter % 20 == 0:
            try:
                with get_db_context() as prune_db:
                    total_sigs = prune_db.execute(select(func.count(Signal.id))).scalar() or 0
                    if total_sigs > 5000:
                        cutoff_id = prune_db.execute(
                            select(Signal.id).order_by(Signal.id.desc()).offset(2000).limit(1)
                        ).scalar()
                        if cutoff_id:
                            prune_db.execute(
                                delete(Signal).where(
                                    Signal.id < cutoff_id,
                                    Signal.status != SignalStatus.ACCEPTED.value,
                                )
                            )
                            prune_db.commit()
            except Exception as e:
                logger.debug(f"Signal pruning notice: {e}")

        return processed
