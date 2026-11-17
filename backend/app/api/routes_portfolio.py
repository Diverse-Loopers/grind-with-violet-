"""
Portfolio API Routes.
Exposes open positions, order books, mark-to-market valuations, equity curve history,
and simulated paper order placement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database import get_db_context
from app.models.position import Position, PositionResponse
from app.models.order import Order, OrderResponse as OrderModelResponse
from app.models.portfolio import PortfolioSnapshot

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class ManualOrderRequest(BaseModel):
    trading_symbol: str = Field(..., min_length=1)
    transaction_type: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: int = Field(..., gt=0)
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT)$")
    price: Optional[float] = None
    product: str = Field(default="CNC")
    client_order_id: Optional[str] = None


@router.get("/positions")
def get_positions(include_closed: bool = False) -> Dict[str, Any]:
    with get_db_context() as db:
        query = select(Position).where(Position.mode == "PAPER")
        if not include_closed:
            query = query.where(Position.quantity > 0)
        positions = db.execute(query.order_by(Position.id.desc())).scalars().all()

        total_val = sum(p.quantity * p.current_price for p in positions)
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        total_realized = sum(p.realized_pnl for p in positions)
        total_fees = sum(p.total_fees for p in positions)

        # Incorporate Multi-Agent F&O Autonomous Spreads into Portfolio
        from app.agents.multi_agent_orchestrator import multi_agent_system
        agent_exec = multi_agent_system.execution_agent
        agent_realized = sum(p.realized_pnl for p in agent_exec.closed_positions)
        agent_unrealized = sum(p.current_pnl for p in agent_exec.active_positions.values())
        agent_open_count = len(agent_exec.active_positions)

        total_unrealized += agent_unrealized
        total_realized += agent_realized

        res_positions = [
            {
                "id": p.id,
                "trading_symbol": p.trading_symbol,
                "exchange": p.exchange,
                "quantity": p.quantity,
                "average_entry_price": p.average_entry_price,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "realized_pnl": p.realized_pnl,
                "total_fees": p.total_fees,
                "strategy": p.strategy,
                "mode": p.mode,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            }
            for p in positions
        ]

        # Append multi-agent active spreads
        for pos_id, ap in agent_exec.active_positions.items():
            res_positions.insert(0, {
                "id": pos_id,
                "trading_symbol": f"{ap.plan.underlying_symbol} ({ap.plan.strategy_type.value})",
                "exchange": "NFO",
                "quantity": ap.plan.legs[0].lot_size if ap.plan.legs else 1,
                "average_entry_price": ap.plan.net_debit,
                "current_price": ap.plan.spot_price,
                "unrealized_pnl": ap.current_pnl,
                "realized_pnl": 0.0,
                "total_fees": 40.0,
                "strategy": ap.plan.strategy_type.value,
                "mode": "PAPER",
                "opened_at": ap.opened_at,
            })

        # Append recently closed spreads if include_closed is true
        if include_closed:
            for cp in reversed(agent_exec.closed_positions[-50:]):
                res_positions.append({
                    "id": cp.id,
                    "trading_symbol": f"{cp.plan.underlying_symbol} ({cp.plan.strategy_type.value})",
                    "exchange": "NFO",
                    "quantity": cp.plan.legs[0].lot_size if cp.plan.legs else 1,
                    "average_entry_price": cp.plan.net_debit,
                    "current_price": cp.plan.spot_price,
                    "unrealized_pnl": 0.0,
                    "realized_pnl": cp.realized_pnl,
                    "total_fees": 40.0,
                    "strategy": cp.plan.strategy_type.value,
                    "mode": "PAPER",
                    "opened_at": cp.opened_at,
                })

        return {
            "summary": {
                "total_positions_value": round(total_val, 2),
                "unrealized_pnl": round(total_unrealized, 2),
                "realized_pnl": round(total_realized, 2),
                "total_fees": round(total_fees + (len(agent_exec.closed_positions) * 40.0), 2),
                "open_count": len([p for p in positions if p.quantity > 0]) + agent_open_count,
            },
            "positions": res_positions,
        }


@router.get("/orders")
def get_orders(limit: int = Query(default=50, le=200)) -> Dict[str, Any]:
    with get_db_context() as db:
        orders = db.execute(
            select(Order).order_by(Order.id.desc()).limit(limit)
        ).scalars().all()

        formatted_orders = [
            {
                "id": o.id,
                "signal_id": o.signal_id,
                "trading_symbol": o.trading_symbol,
                "exchange": o.exchange,
                "order_type": o.order_type,
                "transaction_type": o.transaction_type,
                "product": o.product,
                "quantity": o.quantity,
                "price": o.price,
                "trigger_price": o.trigger_price,
                "status": o.status,
                "filled_quantity": o.filled_quantity,
                "average_fill_price": o.average_fill_price,
                "simulated_slippage": o.simulated_slippage,
                "fees": o.fees,
                "paper_or_live": o.paper_or_live,
                "broker_order_id": o.broker_order_id,
                "order_reference_id": o.order_reference_id,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]

        # Include Multi-Agent atomic executions in the order log
        from app.agents.multi_agent_orchestrator import multi_agent_system
        agent_exec = multi_agent_system.execution_agent
        for cp in reversed(agent_exec.closed_positions[-20:]):
            for leg in cp.plan.legs:
                formatted_orders.insert(0, {
                    "id": f"ORD_{cp.id[-4:]}_{leg.symbol[:10]}",
                    "signal_id": cp.plan.id,
                    "trading_symbol": leg.symbol,
                    "exchange": "NFO",
                    "order_type": "LIMIT",
                    "transaction_type": leg.action.value,
                    "product": "NRML",
                    "quantity": leg.quantity,
                    "price": leg.entry_price,
                    "trigger_price": None,
                    "status": "FILLED",
                    "filled_quantity": leg.quantity,
                    "average_fill_price": leg.entry_price,
                    "simulated_slippage": 0.05,
                    "fees": 20.0,
                    "paper_or_live": "PAPER",
                    "broker_order_id": f"BRK_{cp.id}",
                    "order_reference_id": cp.id,
                    "created_at": cp.opened_at,
                })

        return {
            "count": len(formatted_orders),
            "orders": formatted_orders[:limit],
        }


@router.get("/equity-curve")
def get_equity_curve(limit: int = Query(default=100, le=500)) -> Dict[str, Any]:
    from app.agents.multi_agent_orchestrator import multi_agent_system
    agent_exec = multi_agent_system.execution_agent
    closed = agent_exec.closed_positions

    # If multi-agent spreads have executed, render chronological growth curve
    if closed:
        data = []
        base_capital = 500000.0
        cum_pnl = 0.0
        step = max(1, len(closed) // limit)
        sample = closed[::step][-limit:]
        for p in sample:
            cum_pnl = round(cum_pnl + (p.realized_pnl or 0.0), 2)
            data.append({
                "timestamp": p.closed_at or p.opened_at,
                "cash_balance": round(base_capital + cum_pnl, 2),
                "positions_value": 0.0,
                "total_equity": round(base_capital + cum_pnl, 2),
                "daily_pnl": p.realized_pnl or 0.0,
                "cumulative_pnl": cum_pnl,
                "drawdown_pct": 0.0,
            })
        return {"count": len(data), "data": data}

    with get_db_context() as db:
        snaps = db.execute(
            select(PortfolioSnapshot).where(PortfolioSnapshot.mode == "PAPER").order_by(PortfolioSnapshot.id.desc()).limit(limit)
        ).scalars().all()
        snaps.reverse()

        return {
            "count": len(snaps),
            "data": [
                {
                    "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                    "cash_balance": s.cash_balance,
                    "positions_value": s.positions_value,
                    "total_equity": s.total_equity,
                    "daily_pnl": s.daily_pnl,
                    "cumulative_pnl": s.cumulative_pnl,
                    "drawdown_pct": s.drawdown_pct,
                }
                for s in snaps
            ],
        }


@router.post("/orders")
def place_manual_paper_order(payload: ManualOrderRequest) -> Dict[str, Any]:
    from app.main import paper_broker, scanner, risk_engine
    from app.config import settings
    from app.engine.activity_logger import activity_logger

    sym = payload.trading_symbol.upper().strip()
    side = payload.transaction_type.upper().strip()
    quote = scanner.adapter.get_quote(sym)
    price = payload.price or quote.ltp or 1000.0
    funds = paper_broker.get_funds()

    # Query current positions for risk limit verification
    with get_db_context() as db:
        open_positions = db.execute(
            select(Position).where(Position.mode == "PAPER", Position.quantity > 0)
        ).scalars().all()
        positions_by_symbol = {p.trading_symbol: p for p in open_positions}
        open_positions_count = len(open_positions)
        existing_pos = positions_by_symbol.get(sym)
        existing_qty = existing_pos.quantity if existing_pos else 0
        daily_loss = max(0.0, -funds.get("daily_pnl", 0.0))

    is_market_open = True if (settings.is_demo or settings.is_paper) else scanner.adapter.is_market_open()

    # Strictly evaluate risk limits before order routing
    risk_decision = risk_engine.evaluate_order(
        trading_symbol=sym,
        strategy="MANUAL",
        side=side,
        quantity=payload.quantity,
        price=price,
        quote_timestamp=quote.timestamp,
        current_equity=funds.get("total_equity", 1_000_000.0),
        current_open_positions_count=open_positions_count,
        existing_position_qty_for_symbol=existing_qty,
        daily_realized_loss=daily_loss,
        is_market_open=is_market_open,
        net_edge_pct=None,
        volume=quote.volume,
        system_healthy=True,
    )

    if not risk_decision.passed:
        rejection_str = "; ".join(risk_decision.rejection_reasons)
        activity_logger.log(
            event_type="RISK_REJECT",
            symbol=sym,
            side=side,
            message=f"⚠️ Manual order rejected for {sym}: {rejection_str}",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Order rejected by Risk Engine: {rejection_str}",
        )

    activity_logger.log(
        event_type="RISK_PASS",
        symbol=sym,
        side=side,
        price=price,
        quantity=payload.quantity,
        message=f"🛡️ Risk approved manual {side} {payload.quantity}x {sym} @ ₹{price:.2f}",
    )

    res = paper_broker.place_paper_order(
        trading_symbol=sym,
        transaction_type=side,
        quantity=payload.quantity,
        order_type=payload.order_type.upper(),
        product=payload.product.upper(),
        price=payload.price,
        strategy="MANUAL",
        quote=quote,
        client_order_id=payload.client_order_id,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)

    activity_logger.log(
        event_type="ORDER_FILLED",
        symbol=sym,
        side=side,
        price=price,
        quantity=payload.quantity,
        message=f"✅ PAPER ORDER FILLED: manual {side} {payload.quantity}x {sym} @ ₹{price:.2f}",
    )
    return res.model_dump()


@router.get("/broker-sync")
def get_broker_sync() -> Dict[str, Any]:
    from app.main import adapter
    from app.adapters.groww_adapter import GrowwAdapter

    if not isinstance(adapter, GrowwAdapter):
        return {
            "connected": False,
            "adapter": "DemoAdapter",
            "message": "Groww account not connected. Running in demo mode.",
            "holdings": [],
            "funds": None,
        }

    holdings = adapter.get_holdings()
    funds = adapter.get_funds()
    profile = adapter.get_profile()

    return {
        "connected": True,
        "adapter": "GrowwAdapter",
        "ucc": profile.get("ucc", ""),
        "active_segments": profile.get("active_segments", []),
        "funds": {
            "available_cash": funds.available_cash,
            "used_margin": funds.used_margin,
            "total_balance": funds.total_balance,
            "collateral": funds.collateral,
        },
        "holdings_count": len(holdings),
        "holdings": [
            {
                "trading_symbol": h.trading_symbol,
                "exchange": h.exchange,
                "isin": h.isin,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "ltp": h.ltp,
                "pnl": h.pnl,
            }
            for h in holdings
        ],
    }


class ResetWalletRequest(BaseModel):
    starting_balance: float = Field(default=1_000_000.0, ge=10_000.0)


@router.get("/wallet")
def get_wallet_overview() -> Dict[str, Any]:
    """Returns detailed wallet funds, cash balance, and margin allocation."""
    from app.main import paper_broker

    funds = paper_broker.get_funds()
    cash = round(funds["available_cash"], 2)
    invested = round(funds["positions_value"], 2)
    equity = round(funds["total_equity"], 2)
    daily_pnl = round(funds["daily_pnl"], 2)
    realized_pnl = round(funds.get("realized_pnl", funds["cumulative_pnl"]), 2)
    unrealized_pnl = round(funds.get("unrealized_pnl", 0.0), 2)

    cash_pct = round((cash / equity * 100.0), 1) if equity > 0 else 100.0
    invested_pct = round((invested / equity * 100.0), 1) if equity > 0 else 0.0

    with get_db_context() as db:
        open_pos_count = len(
            db.execute(select(Position).where(Position.mode == "PAPER", Position.quantity > 0)).scalars().all()
        )
        total_orders = len(
            db.execute(select(Order).where(Order.status == "FILLED")).scalars().all()
        )

    return {
        "currency": "INR",
        "cash_balance": cash,
        "invested_amount": invested,
        "total_equity": equity,
        "daily_pnl": daily_pnl,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "open_positions_count": open_pos_count,
        "total_filled_orders": total_orders,
        "allocation": {
            "cash_pct": cash_pct,
            "invested_pct": invested_pct,
        },
        "starting_balance": paper_broker.starting_cash,
    }


@router.post("/wallet/reset")
def reset_wallet(payload: ResetWalletRequest) -> Dict[str, Any]:
    """Resets the paper wallet balance back to starting capital."""
    from app.main import paper_broker
    from app.engine.activity_logger import activity_logger

    paper_broker.starting_cash = payload.starting_balance

    with get_db_context() as db:
        # Close any open paper positions
        from sqlalchemy import update
        db.execute(update(Position).where(Position.mode == "PAPER").values(quantity=0))
        # Insert fresh snapshot
        initial_snap = PortfolioSnapshot(
            cash_balance=payload.starting_balance,
            positions_value=0.0,
            total_equity=payload.starting_balance,
            daily_pnl=0.0,
            cumulative_pnl=0.0,
            drawdown_pct=0.0,
            mode="PAPER",
        )
        db.add(initial_snap)
        db.commit()

    activity_logger.log(
        event_type="INFO",
        message=f"💼 Wallet capital reset to ₹{payload.starting_balance:,.2f}",
    )

    from app.engine.accounting_engine import AccountingEngine
    from app.models.ledger import AccountType
    AccountingEngine.record_deposit(
        account_type=AccountType.EQUITY.value,
        currency="INR",
        amount=payload.starting_balance,
        reference_id=f"RESET-EQUITY-{int(datetime.now(timezone.utc).timestamp())}",
        description=f"Wallet Reset to Starting Balance: ₹{payload.starting_balance:,.2f}",
    )

    return {"success": True, "message": f"Wallet reset to ₹{payload.starting_balance:,.2f}"}


@router.get("/ledger")
def get_unified_ledger(
    account_type: Optional[str] = Query(None, description="EQUITY, CRYPTO, or GLOBAL_FOREX"),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Returns immutable unified ledger audit entries."""
    from app.engine.accounting_engine import AccountingEngine
    return AccountingEngine.get_recent_entries(account_type=account_type, limit=limit)


@router.get("/reconcile")
def reconcile_financial_ledger() -> Dict[str, Any]:
    """
    Automated accounting reconciliation.
    Reconciles reported dashboard cash balances and P&L against the underlying double-entry ledger.
    """
    from app.main import paper_broker
    from app.engine.accounting_engine import AccountingEngine
    from app.coindcx.paper_broker import CoinDCXPaperBroker
    from app.global_engine.engine import global_engine

    equity_funds = paper_broker.get_funds()
    equity_cash = equity_funds.get("available_cash", 1_000_000.0)

    try:
        coindcx_broker = CoinDCXPaperBroker()
        crypto_wallet = coindcx_broker.get_wallet_overview()
        crypto_inr = crypto_wallet.get("inr_cash", 1_000_000.0)
        crypto_usdt = crypto_wallet.get("usdt_cash", 10_000.0)
    except Exception:
        crypto_inr = 1_000_000.0
        crypto_usdt = 10_000.0

    global_account = global_engine.broker.get_account_summary()
    global_usd = global_account.balance

    return AccountingEngine.reconcile_all_accounts(
        current_equity_cash=equity_cash,
        current_crypto_inr=crypto_inr,
        current_crypto_usdt=crypto_usdt,
        current_global_usd=global_usd,
    )
