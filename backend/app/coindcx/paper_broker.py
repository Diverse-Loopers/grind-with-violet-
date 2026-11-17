"""
CoinDCX Paper Trading Broker and Multi-Currency Portfolio Accounting.
Executes simulated orders against real CoinDCX top-of-book market prices and order books.
Strictly validates minimum order quantities, step sizes, precision, and minimum notional values.
Persists all simulated orders, fills, balances, and P&L in SQLite.
Guarantees NO live broker orders are placed.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import delete, select, update

if TYPE_CHECKING:
    from app.adapters.coindcx_adapter import CoinDCXAdapter
from app.coindcx.models import (
    CoinDCXOrder,
    CoinDCXPosition,
    CoinDCXWallet,
    MarketDetail,
)
from app.database import get_db_context
from app.engine.accounting_engine import AccountingEngine
from app.models.ledger import AccountType
from app.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_STARTING_INR = 1_000_000.0
_DEFAULT_STARTING_USDT = 10_000.0


class CoinDCXPaperBroker:
    """Simulated execution engine and accounting for CoinDCX crypto trading."""

    def __init__(
        self,
        adapter: Optional[CoinDCXAdapter] = None,
        starting_inr: float = _DEFAULT_STARTING_INR,
        starting_usdt: float = _DEFAULT_STARTING_USDT,
    ):
        if adapter is None:
            from app.adapters.coindcx_adapter import CoinDCXAdapter
            self.adapter = CoinDCXAdapter()
        else:
            self.adapter = adapter
        self.starting_inr = starting_inr
        self.starting_usdt = starting_usdt
        # CoinDCX standard taker fee: 0.20%
        self.taker_fee_pct = 0.002
        # Indian Section 194S TDS: 1.0% on crypto sales
        self.crypto_tds_pct = 0.01
        self._ensure_wallet()

    def _ensure_wallet(self):
        """Initializes virtual wallet balances in SQLite if not present and synchronizes with unified ledger."""
        with get_db_context() as db:
            inr_wallet = db.execute(select(CoinDCXWallet).where(CoinDCXWallet.currency == "INR")).scalars().first()
            if not inr_wallet:
                inr_wallet = CoinDCXWallet(currency="INR", balance=self.starting_inr, starting_balance=self.starting_inr)
                db.add(inr_wallet)
                db.commit()
                AccountingEngine.record_deposit(
                    account_type=AccountType.CRYPTO.value,
                    currency="INR",
                    amount=self.starting_inr,
                    reference_id=f"INIT-CRYPTO-INR-{int(datetime.now(timezone.utc).timestamp())}",
                    description="Initial Virtual Crypto INR Balance",
                )

            usdt_wallet = db.execute(select(CoinDCXWallet).where(CoinDCXWallet.currency == "USDT")).scalars().first()
            if not usdt_wallet:
                usdt_wallet = CoinDCXWallet(currency="USDT", balance=self.starting_usdt, starting_balance=self.starting_usdt)
                db.add(usdt_wallet)
                db.commit()
                AccountingEngine.record_deposit(
                    account_type=AccountType.CRYPTO.value,
                    currency="USDT",
                    amount=self.starting_usdt,
                    reference_id=f"INIT-CRYPTO-USDT-{int(datetime.now(timezone.utc).timestamp())}",
                    description="Initial Virtual Crypto USDT Balance",
                )

    def get_wallet_overview(self) -> Dict[str, Any]:
        """
        Returns full multi-currency wallet funds, open crypto holdings, and mark-to-market valuations.
        """
        self._ensure_wallet()
        with get_db_context() as db:
            wallets = db.execute(select(CoinDCXWallet)).scalars().all()
            wallet_map = {w.currency: w.balance for w in wallets}

            inr_cash = wallet_map.get("INR", self.starting_inr)
            usdt_cash = wallet_map.get("USDT", self.starting_usdt)

            positions = db.execute(select(CoinDCXPosition).where(CoinDCXPosition.quantity > 0)).scalars().all()

            # Mark to market positions with latest CoinDCX live tickers
            tickers = self.adapter.get_all_tickers()
            fx_rate = tickers.get("USDTINR").last_price if tickers.get("USDTINR") else 101.80

            total_crypto_val_inr = 0.0
            total_unrealized_inr = 0.0
            total_realized_inr = 0.0
            holdings_list = []

            for p in positions:
                t = tickers.get(p.market)
                curr_price = t.last_price if (t and t.last_price > 0) else p.current_price
                p.current_price = curr_price
                unrealized = (curr_price - p.average_entry_price) * p.quantity
                p.unrealized_pnl = round(unrealized, 2)

                # Normalize valuation to INR
                is_usdt_base = p.base_currency.upper() == "USDT"
                multiplier = fx_rate if is_usdt_base else 1.0

                mkt_val_inr = curr_price * p.quantity * multiplier
                total_crypto_val_inr += mkt_val_inr
                total_unrealized_inr += unrealized * multiplier
                total_realized_inr += p.realized_pnl * multiplier

                holdings_list.append({
                    "id": p.id,
                    "market": p.market,
                    "target_currency": p.target_currency,
                    "base_currency": p.base_currency,
                    "quantity": p.quantity,
                    "average_entry_price": p.average_entry_price,
                    "current_price": curr_price,
                    "market_value_base": round(curr_price * p.quantity, 2),
                    "market_value_inr": round(mkt_val_inr, 2),
                    "unrealized_pnl_base": round(unrealized, 2),
                    "unrealized_pnl_inr": round(unrealized * multiplier, 2),
                    "unrealized_pnl_pct": round(((curr_price - p.average_entry_price) / p.average_entry_price * 100.0), 2) if p.average_entry_price > 0 else 0.0,
                    "total_fees": p.total_fees,
                })

            db.commit()

            total_equity_inr = round(inr_cash + (usdt_cash * fx_rate) + total_crypto_val_inr, 2)
            cum_pnl_inr = round(total_equity_inr - (self.starting_inr + (self.starting_usdt * fx_rate)), 2)

            return {
                "currency": "INR",
                "inr_cash": round(inr_cash, 2),
                "usdt_cash": round(usdt_cash, 2),
                "usdt_inr_rate": fx_rate,
                "total_crypto_value_inr": round(total_crypto_val_inr, 2),
                "total_equity_inr": total_equity_inr,
                "realized_pnl_inr": round(total_realized_inr, 2),
                "unrealized_pnl_inr": round(total_unrealized_inr, 2),
                "cumulative_pnl_inr": cum_pnl_inr,
                "holdings_count": len(holdings_list),
                "holdings": holdings_list,
                "starting_balance_inr": self.starting_inr,
                "starting_balance_usdt": self.starting_usdt,
            }

    def place_paper_order(
        self,
        market: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes a paper order against live CoinDCX market data.
        Validates minimums, increments, precision, notional value, and data freshness.
        """
        clean_market = market.strip().upper()
        clean_side = side.strip().upper()
        now_utc = datetime.now(timezone.utc)
        order_ref = f"CDX-PAPER-{int(now_utc.timestamp() * 1000)}-{random.randint(1000, 9999)}"

        # 1. Retrieve market rules and live quote
        detail = self.adapter.get_market_detail(clean_market)
        if not detail:
            return {"success": False, "message": f"Market {clean_market} not found on CoinDCX."}

        ticker = self.adapter.get_ticker(clean_market)
        if not ticker or ticker.last_price <= 0:
            return {"success": False, "message": f"Live quote unavailable for {clean_market}."}

        # 2. Check data freshness (reject stale data)
        if ticker.is_stale:
            reason = f"Rejected: Stale market data for {clean_market} ({ticker.data_freshness_seconds:.1f}s old, limit {self.adapter.stale_threshold_seconds}s)."
            self._record_rejected_order(order_ref, clean_market, detail.pair, clean_side, order_type, quantity, ticker.last_price, reason)
            return {"success": False, "message": reason, "status": "REJECTED"}

        # 3. Determine execution price based on live order book
        ref_price = price or ticker.last_price
        if clean_side == "BUY":
            fill_price = ticker.ask if ticker.ask > 0 else ticker.last_price
        else:
            fill_price = ticker.bid if ticker.bid > 0 else ticker.last_price

        # 4. Strictly validate CoinDCX market constraints
        is_valid, validation_err, constraints = self.adapter.validate_order_rules(
            market=clean_market,
            side=clean_side,
            quantity=quantity,
            price=fill_price,
        )
        if not is_valid:
            self._record_rejected_order(order_ref, clean_market, detail.pair, clean_side, order_type, quantity, fill_price, validation_err)
            return {
                "success": False,
                "message": validation_err,
                "status": "REJECTED",
                "constraints": constraints,
            }

        base_curr = detail.base_currency_short_name.upper()
        target_curr = detail.target_currency_short_name.upper()
        total_turnover = fill_price * quantity
        fee = total_turnover * self.taker_fee_pct

        # Indian 1% TDS applied on crypto sell orders with INR base
        tds = (total_turnover * self.crypto_tds_pct) if (clean_side == "SELL" and base_curr == "INR") else 0.0

        # 5. Check balance availability and execute in atomic DB transaction
        with get_db_context() as db:
            wallet = db.execute(select(CoinDCXWallet).where(CoinDCXWallet.currency == base_curr)).scalars().first()
            if not wallet:
                wallet = CoinDCXWallet(currency=base_curr, balance=self.starting_inr if base_curr == "INR" else self.starting_usdt, starting_balance=self.starting_inr if base_curr == "INR" else self.starting_usdt)
                db.add(wallet)
                db.flush()

            pos = db.execute(select(CoinDCXPosition).where(CoinDCXPosition.market == clean_market)).scalars().first()

            if clean_side == "BUY":
                required_funds = total_turnover + fee
                if wallet.balance < required_funds:
                    msg = f"Insufficient virtual {base_curr} balance: Required {required_funds:.2f}, Available {wallet.balance:.2f}"
                    self._record_rejected_order(order_ref, clean_market, detail.pair, clean_side, order_type, quantity, fill_price, msg)
                    return {"success": False, "message": msg, "status": "REJECTED"}

                wallet.balance -= required_funds

                if not pos:
                    pos = CoinDCXPosition(
                        market=clean_market,
                        base_currency=base_curr,
                        target_currency=target_curr,
                        quantity=quantity,
                        average_entry_price=fill_price,
                        current_price=fill_price,
                        unrealized_pnl=0.0,
                        realized_pnl=0.0,
                        total_fees=fee,
                    )
                    db.add(pos)
                else:
                    new_qty = pos.quantity + quantity
                    new_avg = ((pos.quantity * pos.average_entry_price) + total_turnover) / new_qty
                    pos.quantity = new_qty
                    pos.average_entry_price = round(new_avg, detail.base_currency_precision)
                    pos.current_price = fill_price
                    pos.total_fees += fee

            else:  # SELL
                available_crypto = pos.quantity if pos else 0.0
                if available_crypto < quantity:
                    msg = f"Insufficient {target_curr} holdings to sell: Holding {available_crypto}, Requested {quantity}."
                    self._record_rejected_order(order_ref, clean_market, detail.pair, clean_side, order_type, quantity, fill_price, msg)
                    return {"success": False, "message": msg, "status": "REJECTED"}

                cost_basis = quantity * pos.average_entry_price
                realized_pnl_delta = (total_turnover - cost_basis) - fee - tds
                pos.realized_pnl += round(realized_pnl_delta, 2)
                pos.quantity -= quantity
                pos.total_fees += fee
                pos.current_price = fill_price

                # Credit cash net of fees and statutory TDS
                wallet.balance += (total_turnover - fee - tds)

            # Persist filled order
            slippage = round(abs(fill_price - ticker.last_price), 8)
            order = CoinDCXOrder(
                order_id=order_ref,
                market=clean_market,
                pair=detail.pair,
                side=clean_side,
                order_type=order_type,
                quantity=quantity,
                price=ref_price,
                fill_price=fill_price,
                total_value=round(total_turnover, 2),
                fee=round(fee, 2),
                tds=round(tds, 2),
                slippage=slippage,
                status="FILLED",
                mode="PAPER",
                created_at=now_utc,
                filled_at=now_utc,
            )
            db.add(order)
            db.commit()

            # Record in unified ledger
            AccountingEngine.record_trade(
                account_type=AccountType.CRYPTO.value,
                reference_id=order_ref,
                symbol=clean_market,
                side=clean_side,
                quantity=quantity,
                fill_price=fill_price,
                fee=fee,
                tax=tds,
                currency=base_curr,
                description=f"COINDCX PAPER {clean_side} {quantity} {clean_market} @ {fill_price:.2f}",
            )

        logger.info(
            f"[COINDCX PAPER] {clean_side} {quantity} {clean_market} @ {fill_price} | Fees: {fee:.2f} {base_curr} | TDS: {tds:.2f} | Ref: {order_ref}"
        )

        return {
            "success": True,
            "order_id": order_ref,
            "market": clean_market,
            "side": clean_side,
            "quantity": quantity,
            "fill_price": fill_price,
            "total_value": round(total_turnover, 2),
            "fee": round(fee, 2),
            "tds": round(tds, 2),
            "base_currency": base_curr,
            "status": "FILLED",
            "message": f"Successfully filled {clean_side} {quantity} {clean_market} @ {fill_price:.2f} {base_curr} (PAPER)",
        }

    def _record_rejected_order(
        self,
        order_ref: str,
        market: str,
        pair: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float,
        reason: str,
    ):
        """Persists rejected orders for transparent auditability."""
        try:
            with get_db_context() as db:
                order = CoinDCXOrder(
                    order_id=order_ref,
                    market=market,
                    pair=pair,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                    fill_price=0.0,
                    total_value=0.0,
                    fee=0.0,
                    tds=0.0,
                    slippage=0.0,
                    status="REJECTED",
                    rejection_reason=reason,
                    mode="PAPER",
                    created_at=datetime.now(timezone.utc),
                )
                db.add(order)
                db.commit()
        except Exception as e:
            logger.error("Failed recording rejected CoinDCX order: %s", e)

    def reset_wallet(self, starting_inr: float = _DEFAULT_STARTING_INR, starting_usdt: float = _DEFAULT_STARTING_USDT) -> Dict[str, Any]:
        """Resets virtual wallet balances and clears crypto positions."""
        self.starting_inr = starting_inr
        self.starting_usdt = starting_usdt
        with get_db_context() as db:
            db.execute(delete(CoinDCXPosition))
            db.execute(
                update(CoinDCXWallet).where(CoinDCXWallet.currency == "INR").values(balance=starting_inr, starting_balance=starting_inr)
            )
            db.execute(
                update(CoinDCXWallet).where(CoinDCXWallet.currency == "USDT").values(balance=starting_usdt, starting_balance=starting_usdt)
            )
            db.commit()

        AccountingEngine.reset_account(AccountType.CRYPTO.value, "INR", starting_inr, "CoinDCX Reset Virtual INR Balance")
        AccountingEngine.reset_account(AccountType.CRYPTO.value, "USDT", starting_usdt, "CoinDCX Reset Virtual USDT Balance")

        logger.info("Reset CoinDCX paper wallet: INR %s, USDT %s", starting_inr, starting_usdt)
        return {"success": True, "message": f"CoinDCX virtual balance reset to ₹{starting_inr:,.2f} INR and ${starting_usdt:,.2f} USDT."}

    def get_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves historical simulated crypto orders."""
        with get_db_context() as db:
            orders = db.execute(select(CoinDCXOrder).order_by(CoinDCXOrder.id.desc()).limit(limit)).scalars().all()
            return [
                {
                    "id": o.id,
                    "order_id": o.order_id,
                    "market": o.market,
                    "pair": o.pair,
                    "side": o.side,
                    "order_type": o.order_type,
                    "quantity": o.quantity,
                    "price": o.price,
                    "fill_price": o.fill_price,
                    "total_value": o.total_value,
                    "fee": o.fee,
                    "tds": o.tds,
                    "slippage": o.slippage,
                    "status": o.status,
                    "rejection_reason": o.rejection_reason,
                    "mode": o.mode,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ]
