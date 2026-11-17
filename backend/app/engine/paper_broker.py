"""
Paper Trading Execution Engine.
Simulates realistic broker order execution with bid-ask awareness, slippage,
statutory transaction cost deductions, and complete portfolio accounting.
Marked explicitly as PAPER.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional, List, Dict

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db_context
from app.models.order import Order, OrderStatus, OrderType, TransactionType, ProductType, TradingMode
from app.models.position import Position
from app.models.portfolio import PortfolioSnapshot
from app.engine.cost_calculator import TransactionCostCalculator
from app.engine.accounting_engine import AccountingEngine
from app.models.ledger import AccountType
from app.adapters.base import Quote, OrderResponse, OrderStatusResponse
from app.utils.logging import logger


class PaperBroker:
    """Simulated execution venue for paper trading."""

    def __init__(self, starting_cash: Optional[float] = None, slippage_pct: float = 0.05):
        self.starting_cash = starting_cash or settings.paper_starting_balance
        self.slippage_pct = slippage_pct  # 0.05% default simulated slippage
        self.cost_calc = TransactionCostCalculator(
            brokerage_pct=settings.brokerage_pct,
            brokerage_flat=settings.brokerage_flat,
            use_flat_brokerage=settings.use_flat_brokerage,
        )
        self._ensure_initial_state()

    def _ensure_initial_state(self):
        """Initializes virtual cash balance if not present."""
        with get_db_context() as db:
            latest = db.execute(
                select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "PAPER").order_by(PortfolioSnapshot.id.desc())
            ).scalars().first()
            if not latest:
                initial_snap = PortfolioSnapshot(
                    cash_balance=self.starting_cash,
                    positions_value=0.0,
                    total_equity=self.starting_cash,
                    daily_pnl=0.0,
                    cumulative_pnl=0.0,
                    drawdown_pct=0.0,
                    mode="PAPER",
                )
                db.add(initial_snap)
                db.commit()
                # Record in unified ledger
                AccountingEngine.record_deposit(
                    account_type=AccountType.EQUITY.value,
                    currency="INR",
                    amount=self.starting_cash,
                    reference_id=f"INIT-EQUITY-{int(datetime.now(timezone.utc).timestamp())}",
                    description="Initial Virtual Paper Trading Capital",
                )
            else:
                # Ensure ledger has initial record
                curr_ledger_bal = AccountingEngine.get_latest_balance(AccountType.EQUITY.value, "INR")
                if curr_ledger_bal == 0.0 and latest.cash_balance > 0:
                    AccountingEngine.record_deposit(
                        account_type=AccountType.EQUITY.value,
                        currency="INR",
                        amount=latest.cash_balance,
                        reference_id=f"INIT-EQUITY-{int(datetime.now(timezone.utc).timestamp())}",
                        description="Synchronized Initial Virtual Capital to Ledger",
                    )

    def get_funds(self, db: Optional[Session] = None) -> Dict[str, float]:
        if db is not None:
            latest = db.execute(
                select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "PAPER").order_by(PortfolioSnapshot.id.desc())
            ).scalars().first()

            positions = db.execute(
                select(Position).where(Position.mode == "PAPER")
            ).scalars().all()
            open_pos = [p for p in positions if p.quantity > 0]
            unrealized = sum(p.unrealized_pnl for p in open_pos)
            realized = sum(p.realized_pnl for p in positions)
            pos_market_val = sum(p.quantity * p.current_price for p in open_pos)

            # Reconcile available cash directly from the snapshot & unified ledger
            cash = latest.cash_balance if latest else self.starting_cash
            ledger_cash = AccountingEngine.get_latest_balance(AccountType.EQUITY.value, "INR")
            if abs(ledger_cash - cash) > 0.01:
                AccountingEngine.reset_account(AccountType.EQUITY.value, "INR", cash, "Portfolio Snapshot Sync")

            total_equity = cash + (pos_market_val or (latest.positions_value if latest else 0.0))

            if latest:
                return {
                    "available_cash": round(cash, 2),
                    "positions_value": pos_market_val or latest.positions_value,
                    "total_equity": round(total_equity, 2),
                    "daily_pnl": latest.daily_pnl,
                    "cumulative_pnl": latest.cumulative_pnl,
                    "realized_pnl": round(realized, 2),
                    "unrealized_pnl": round(unrealized, 2),
                    "drawdown_pct": latest.drawdown_pct,
                }
            return {
                "available_cash": round(cash, 2),
                "positions_value": 0.0,
                "total_equity": round(cash, 2),
                "daily_pnl": 0.0,
                "cumulative_pnl": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "drawdown_pct": 0.0,
            }

        with get_db_context() as session:
            return self.get_funds(db=session)

    def place_paper_order(
        self,
        trading_symbol: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        product: str = "CNC",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        strategy: Optional[str] = "MANUAL",
        signal_id: Optional[int] = None,
        quote: Optional[Quote] = None,
        client_order_id: Optional[str] = None,
    ) -> OrderResponse:
        """
        Executes a paper order against latest quote with realistic fill model.
        Supports idempotency via client_order_id and rejects duplicate orders within 3 seconds.
        """
        now = datetime.now(timezone.utc)
        side = transaction_type.upper()
        order_ref = client_order_id or f"PAPER-{int(now.timestamp() * 1000)}-{random.randint(1000, 9999)}"

        with get_db_context() as db:
            # 1. Idempotency Check: if client_order_id supplied, check for existing order
            if client_order_id:
                existing_order = db.execute(
                    select(Order).where(Order.order_reference_id == client_order_id)
                ).scalars().first()
                if existing_order:
                    logger.info(f"[IDEMPOTENT] Duplicate order_ref {client_order_id} detected. Returning existing order.")
                    return OrderResponse(
                        success=existing_order.status == OrderStatus.FILLED.value,
                        order_id=str(existing_order.id),
                        broker_order_id=existing_order.broker_order_id or existing_order.order_reference_id,
                        message=f"Idempotent: Order {client_order_id} already processed ({existing_order.status})",
                        status=existing_order.status,
                    )

            # 2. Duplicate order prevention: check if identical order placed within 3.0 seconds
            recent_duplicate = db.execute(
                select(Order)
                .where(
                    Order.trading_symbol == trading_symbol,
                    Order.transaction_type == side,
                    Order.quantity == quantity,
                    Order.status == OrderStatus.FILLED.value,
                )
                .order_by(Order.id.desc())
            ).scalars().first()

            if recent_duplicate and recent_duplicate.created_at:
                diff_sec = (now - (recent_duplicate.created_at.replace(tzinfo=timezone.utc) if recent_duplicate.created_at.tzinfo is None else recent_duplicate.created_at)).total_seconds()
                if diff_sec < 3.0:
                    logger.warning(f"[RISK] Duplicate order suppressed for {quantity}x {trading_symbol} ({diff_sec:.1f}s ago)")
                    return OrderResponse(
                        success=False,
                        order_id="",
                        message=f"Duplicate order suppressed: Identical {side} {quantity}x {trading_symbol} placed {diff_sec:.1f}s ago.",
                        status="REJECTED",
                    )

            order = Order(
                signal_id=signal_id,
                trading_symbol=trading_symbol,
                exchange=quote.exchange if quote else "NSE",
                order_type=order_type,
                transaction_type=side,
                product=product,
                quantity=quantity,
                price=price,
                trigger_price=trigger_price,
                status=OrderStatus.PENDING.value,
                paper_or_live=TradingMode.PAPER.value,
                order_reference_id=order_ref,
            )
            db.add(order)
            db.commit()
            db.refresh(order)

            # Determine execution price based on quote & order type
            if not quote or quote.ltp <= 0:
                order.status = OrderStatus.REJECTED.value
                db.commit()
                return OrderResponse(
                    success=False,
                    order_id=str(order.id),
                    message="Missing or invalid market quote for paper execution",
                    status="REJECTED",
                )

            # Bid-Ask Aware pricing with slippage
            slippage_mult = (self.slippage_pct / 100.0)
            if side == "BUY":
                base_price = quote.ask_price if quote.ask_price > 0 else quote.ltp
                fill_price = round(base_price * (1.0 + slippage_mult), 2)
            else:
                base_price = quote.bid_price if quote.bid_price > 0 else quote.ltp
                fill_price = round(base_price * (1.0 - slippage_mult), 2)

            # Limit order validation
            if order_type.upper() == "LIMIT" and price is not None:
                if side == "BUY" and fill_price > price:
                    order.status = OrderStatus.ACCEPTED.value
                    db.commit()
                    return OrderResponse(
                        success=True,
                        order_id=str(order.id),
                        message="Paper limit buy order pending fill condition",
                        status="ACCEPTED",
                    )
                elif side == "SELL" and fill_price < price:
                    order.status = OrderStatus.ACCEPTED.value
                    db.commit()
                    return OrderResponse(
                        success=True,
                        order_id=str(order.id),
                        message="Paper limit sell order pending fill condition",
                        status="ACCEPTED",
                    )
                fill_price = price

            # Calculate statutory transaction costs
            costs = self.cost_calc.calculate_single_leg_cost(
                side=side, price=fill_price, quantity=quantity, product=product
            )
            total_turnover = fill_price * quantity
            funds = self.get_funds(db=db)

            if side == "BUY":
                required_cash = total_turnover + costs.total_cost
                if funds["available_cash"] < required_cash:
                    order.status = OrderStatus.REJECTED.value
                    db.commit()
                    return OrderResponse(
                        success=False,
                        order_id=str(order.id),
                        message=f"Insufficient paper funds: need Rs {required_cash:.2f}, available Rs {funds['available_cash']:.2f}",
                        status="REJECTED",
                    )

            # Process fill
            order.status = OrderStatus.FILLED.value
            order.filled_quantity = quantity
            order.average_fill_price = fill_price
            order.simulated_slippage = round(abs(fill_price - quote.ltp), 2)
            order.fees = costs.total_cost
            order.broker_order_id = f"BROKER-{order_ref}"

            # Update position
            pos = db.execute(
                select(Position).where(
                    Position.trading_symbol == trading_symbol,
                    Position.mode == "PAPER",
                )
            ).scalars().first()

            realized_pnl_delta = 0.0
            if side == "BUY":
                if not pos:
                    pos = Position(
                        trading_symbol=trading_symbol,
                        exchange=quote.exchange,
                        quantity=quantity,
                        average_entry_price=fill_price,
                        current_price=fill_price,
                        unrealized_pnl=0.0,
                        realized_pnl=0.0,
                        total_fees=costs.total_cost,
                        strategy=strategy,
                        mode="PAPER",
                    )
                    db.add(pos)
                else:
                    new_qty = pos.quantity + quantity
                    new_avg = ((pos.quantity * pos.average_entry_price) + total_turnover) / new_qty
                    pos.quantity = new_qty
                    pos.average_entry_price = round(new_avg, 2)
                    pos.current_price = fill_price
                    pos.total_fees += costs.total_cost
            else:  # SELL
                if pos and pos.quantity > 0:
                    sell_qty = min(quantity, pos.quantity)
                    cost_basis = sell_qty * pos.average_entry_price
                    realized_pnl_delta = (sell_qty * fill_price) - cost_basis - costs.total_cost
                    pos.realized_pnl += round(realized_pnl_delta, 2)
                    pos.quantity -= sell_qty
                    pos.total_fees += costs.total_cost
                    pos.current_price = fill_price
                    if pos.quantity == 0:
                        pos.closed_at = now

            # Update portfolio snapshot
            # Recalculate all open positions market value
            db.flush()
            all_positions = db.execute(
                select(Position).where(Position.mode == "PAPER", Position.quantity > 0)
            ).scalars().all()

            positions_value = sum(p.quantity * p.current_price for p in all_positions)
            unrealized_pnl = sum((p.current_price - p.average_entry_price) * p.quantity for p in all_positions)

            if side == "BUY":
                new_cash = funds["available_cash"] - (total_turnover + costs.total_cost)
            else:
                new_cash = funds["available_cash"] + (total_turnover - costs.total_cost)

            new_equity = new_cash + positions_value
            cum_pnl = new_equity - self.starting_cash

            # Correct drawdown: track the peak equity seen across all snapshots in DB
            latest_snap_for_peak = db.execute(
                select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "PAPER").order_by(PortfolioSnapshot.total_equity.desc()).limit(1)
            ).scalars().first()
            historical_peak = latest_snap_for_peak.total_equity if latest_snap_for_peak else self.starting_cash
            high_watermark = max(self.starting_cash, historical_peak, new_equity)
            drawdown = max(0.0, ((high_watermark - new_equity) / high_watermark) * 100.0)

            # daily_pnl stores today's session PnL; cumulative_pnl stores all-time PnL.
            # Both are cum_pnl until a proper day-boundary reset is wired in.
            snapshot = PortfolioSnapshot(
                cash_balance=round(new_cash, 2),
                positions_value=round(positions_value, 2),
                total_equity=round(new_equity, 2),
                daily_pnl=round(cum_pnl, 2),
                cumulative_pnl=round(cum_pnl, 2),
                drawdown_pct=round(drawdown, 2),
                mode="PAPER",
            )
            db.add(snapshot)
            db.commit()

            # Record in unified ledger
            AccountingEngine.record_trade(
                account_type=AccountType.EQUITY.value,
                reference_id=order_ref,
                symbol=trading_symbol,
                side=side,
                quantity=quantity,
                fill_price=fill_price,
                fee=costs.total_cost,
                tax=0.0,
                currency="INR",
                description=f"PAPER {side} {quantity}x {trading_symbol} @ Rs {fill_price:.2f}",
            )

            logger.info(
                f"[PAPER TRADE] {side} {quantity} {trading_symbol} @ Rs {fill_price:.2f} | Fees: Rs {costs.total_cost:.2f} | Ref: {order_ref}"
            )

            return OrderResponse(
                success=True,
                order_id=str(order.id),
                broker_order_id=order.broker_order_id,
                message=f"Filled {quantity} {trading_symbol} @ Rs {fill_price:.2f} (PAPER)",
                status="FILLED",
            )

    def mark_to_market(self, quotes: Dict[str, Quote]):
        """Updates open positions with latest market quotes to compute unrealized PnL."""
        with get_db_context() as db:
            positions = db.execute(
                select(Position).where(Position.mode == "PAPER", Position.quantity > 0)
            ).scalars().all()

            if not positions:
                return

            total_pos_val = 0.0
            for pos in positions:
                quote = quotes.get(pos.trading_symbol)
                if quote and quote.ltp > 0:
                    pos.current_price = quote.ltp
                    pos.unrealized_pnl = round((quote.ltp - pos.average_entry_price) * pos.quantity, 2)
                    total_pos_val += pos.quantity * quote.ltp
                else:
                    total_pos_val += pos.quantity * pos.current_price

            latest_snap = db.execute(
                select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "PAPER").order_by(PortfolioSnapshot.id.desc())
            ).scalars().first()

            if latest_snap:
                cash = latest_snap.cash_balance
                equity = cash + total_pos_val
                cum_pnl = equity - self.starting_cash
                latest_snap.positions_value = round(total_pos_val, 2)
                latest_snap.total_equity = round(equity, 2)
                latest_snap.daily_pnl = round(cum_pnl, 2)
                latest_snap.cumulative_pnl = round(cum_pnl, 2)

            db.commit()

    def reset_portfolio(self, starting_cash: Optional[float] = None) -> Dict[str, Any]:
        """Resets virtual paper portfolio, wipes open positions, and re-establishes clean starting cash."""
        cash = starting_cash or self.starting_cash
        self.starting_cash = cash
        with get_db_context() as db:
            from sqlalchemy import delete
            db.execute(delete(Position).where(Position.mode == "PAPER"))
            db.execute(delete(PortfolioSnapshot).where(PortfolioSnapshot.mode == "PAPER"))
            initial_snap = PortfolioSnapshot(
                cash_balance=cash,
                positions_value=0.0,
                total_equity=cash,
                daily_pnl=0.0,
                cumulative_pnl=0.0,
                drawdown_pct=0.0,
                mode="PAPER",
            )
            db.add(initial_snap)
            db.commit()

        AccountingEngine.reset_account(AccountType.EQUITY.value, "INR", cash, "Paper Portfolio Reset")
        return {"success": True, "message": f"Portfolio reset to Rs {cash:,.2f}"}
