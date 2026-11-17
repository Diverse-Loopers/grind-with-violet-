"""
Forex & Gold (XAU/USD) 24/7 Paper Execution Broker.
Supports USD margin accounts, leverage (1:20 to 1:100), standard/mini/micro lot sizing,
bid-ask execution slippage, commission accounting, and automatic SL/TP monitoring.
"""

from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.global_engine.models import (
    GlobalAccount,
    GlobalAction,
    GlobalPosition,
    GlobalQuote,
)
from app.engine.accounting_engine import AccountingEngine
from app.models.ledger import AccountType
from app.utils.logging import logger


class GlobalPaperBroker:
    """Simulated 24/7 execution venue for Gold and Forex contracts."""

    def __init__(self, starting_balance: float = 10_000.0, leverage: int = 50):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.leverage = leverage  # 1:50 standard CFD / Forex leverage
        self.positions: Dict[str, GlobalPosition] = {}
        self.closed_positions: List[GlobalPosition] = []
        self.commission_per_lot = 5.0  # $5.00 round-turn commission per standard lot
        self.last_updated = datetime.now(timezone.utc)
        self._ensure_initial_deposit()

    def _ensure_initial_deposit(self):
        curr_bal = AccountingEngine.get_latest_balance(AccountType.GLOBAL_FOREX.value, "USD")
        if curr_bal == 0.0:
            AccountingEngine.record_deposit(
                account_type=AccountType.GLOBAL_FOREX.value,
                currency="USD",
                amount=self.starting_balance,
                reference_id=f"INIT-GLOBAL-USD-{int(datetime.now(timezone.utc).timestamp())}",
                description="Initial Virtual Capital for 24/7 Global Spot & Forex",
            )
            self.balance = self.starting_balance
        else:
            self.balance = curr_bal

    def get_contract_size(self, symbol: str) -> float:
        """Units per 1.00 lot: Gold = 100 troy oz, EURUSD = 100,000 units, BTC = 1 coin."""
        if symbol == "XAUUSD":
            return 100.0
        elif symbol == "EURUSD":
            return 100_000.0
        elif symbol == "BTCUSD":
            return 1.0
        return 100.0

    def get_account_summary(self) -> GlobalAccount:
        """Returns real-time equity, margin, free margin, and performance stats."""
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_margin = sum(p.margin_used for p in self.positions.values())
        equity = round(self.balance + total_unrealized, 2)
        free_margin = max(0.0, round(equity - total_margin, 2))
        margin_level = round((equity / total_margin * 100.0), 2) if total_margin > 0 else 0.0

        all_closed = self.closed_positions
        wins = [p for p in all_closed if p.realized_pnl > 0]
        win_rate = round((len(wins) / len(all_closed) * 100.0), 1) if all_closed else 0.0
        total_realized_pnl = round(sum(p.realized_pnl for p in all_closed), 2)

        return GlobalAccount(
            currency="USD",
            balance=round(self.balance, 2),
            equity=equity,
            margin_used=round(total_margin, 2),
            free_margin=free_margin,
            margin_level_pct=margin_level,
            leverage=self.leverage,
            daily_pnl=round(total_unrealized, 2),
            total_pnl=total_realized_pnl,
            open_positions_count=len(self.positions),
            win_rate=win_rate,
        )

    def open_position(
        self,
        symbol: str,
        side: GlobalAction,
        lots: float,
        quote: GlobalQuote,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        strategy: str = "MANUAL",
    ) -> GlobalPosition:
        """Executes a market order to open a new Long or Short position."""
        lots = round(max(0.01, lots), 2)
        contract_size = self.get_contract_size(symbol)

        # Execution pricing: BUY hits Ask, SELL hits Bid
        fill_price = quote.ask if side == GlobalAction.BUY else quote.bid
        # Slight simulated slippage (0.05 - 0.10 pips)
        slippage = 0.05 if symbol == "XAUUSD" else (0.5 if symbol == "BTCUSD" else 0.00005)
        if side == GlobalAction.BUY:
            fill_price = round(fill_price + slippage, 2 if symbol != "EURUSD" else 5)
        else:
            fill_price = round(fill_price - slippage, 2 if symbol != "EURUSD" else 5)

        # Margin calculation: (Price * Quantity) / Leverage
        notional_value = fill_price * lots * contract_size
        margin_required = round(notional_value / self.leverage, 2)

        account = self.get_account_summary()
        if account.free_margin < margin_required:
            raise ValueError(
                f"Insufficient Free Margin: Need ${margin_required:.2f}, available ${account.free_margin:.2f}"
            )

        # Deduct commission
        commission = round(self.commission_per_lot * lots, 2)
        self.balance -= commission

        pos_id = f"POS-{uuid.uuid4().hex[:8].upper()}"
        pos = GlobalPosition(
            id=pos_id,
            symbol=symbol,
            side=side,
            lots=lots,
            entry_price=fill_price,
            current_price=fill_price,
            sl=sl,
            tp=tp,
            unrealized_pnl=-commission,  # start slightly negative due to commission & spread
            realized_pnl=0.0,
            margin_used=margin_required,
            pip_gain=0.0,
            strategy=strategy,
            status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )

        self.positions[pos_id] = pos

        # Record entry commission in unified ledger
        AccountingEngine.record_trade(
            account_type=AccountType.GLOBAL_FOREX.value,
            reference_id=pos_id,
            symbol=symbol,
            side=side.value,
            quantity=lots,
            fill_price=fill_price,
            fee=commission,
            tax=0.0,
            currency="USD",
            description=f"GLOBAL OPEN {side.value} {lots}L {symbol} @ ${fill_price:.2f}",
        )

        logger.info(
            f"Opened 24/7 position {pos_id}: {side.value} {lots} lots {symbol} @ ${fill_price} (Margin: ${margin_required})"
        )
        return pos

    def update_positions_on_tick(self, quote: GlobalQuote) -> List[GlobalPosition]:
        """Updates P&L for open positions on new quote tick and triggers SL/TP exits."""
        symbol = quote.symbol
        closed_this_tick: List[GlobalPosition] = []
        contract_size = self.get_contract_size(symbol)

        for pos_id, pos in list(self.positions.items()):
            if pos.symbol != symbol or pos.status != "OPEN":
                continue

            current_price = quote.bid if pos.side == GlobalAction.BUY else quote.ask
            pos.current_price = current_price

            # P&L calculation
            if pos.side == GlobalAction.BUY:
                pnl = (current_price - pos.entry_price) * pos.lots * contract_size
                pip_factor = 0.10 if symbol == "XAUUSD" else (1.0 if symbol == "BTCUSD" else 0.0001)
                pos.pip_gain = round((current_price - pos.entry_price) / pip_factor, 1)
            else:
                pnl = (pos.entry_price - current_price) * pos.lots * contract_size
                pip_factor = 0.10 if symbol == "XAUUSD" else (1.0 if symbol == "BTCUSD" else 0.0001)
                pos.pip_gain = round((pos.entry_price - current_price) / pip_factor, 1)

            pos.unrealized_pnl = round(pnl, 2)

            # Check SL trigger
            hit_sl = False
            if pos.sl is not None:
                if pos.side == GlobalAction.BUY and current_price <= pos.sl:
                    hit_sl = True
                elif pos.side == GlobalAction.SELL and current_price >= pos.sl:
                    hit_sl = True

            # Check TP trigger
            hit_tp = False
            if pos.tp is not None:
                if pos.side == GlobalAction.BUY and current_price >= pos.tp:
                    hit_tp = True
                elif pos.side == GlobalAction.SELL and current_price <= pos.tp:
                    hit_tp = True

            if hit_tp:
                closed_pos = self.close_position(pos_id, current_price, reason="Take Profit Hit (TP)")
                closed_this_tick.append(closed_pos)
            elif hit_sl:
                closed_pos = self.close_position(pos_id, current_price, reason="Stop Loss Triggered (SL)")
                closed_this_tick.append(closed_pos)

        return closed_this_tick

    def close_position(self, pos_id: str, current_price: float, reason: str = "Manual Close") -> GlobalPosition:
        """Closes an active position and crystallizes realized P&L."""
        if pos_id not in self.positions:
            raise KeyError(f"Position {pos_id} not found")

        pos = self.positions.pop(pos_id)
        contract_size = self.get_contract_size(pos.symbol)

        if pos.side == GlobalAction.BUY:
            pnl = (current_price - pos.entry_price) * pos.lots * contract_size
        else:
            pnl = (pos.entry_price - current_price) * pos.lots * contract_size

        # Deduct exit commission
        commission = round(self.commission_per_lot * pos.lots, 2)
        realized = round(pnl - commission, 2)

        self.balance += realized
        pos.status = "CLOSED"
        pos.realized_pnl = realized
        pos.unrealized_pnl = 0.0
        pos.close_price = current_price
        pos.close_reason = reason
        pos.closed_at = datetime.now(timezone.utc)

        self.closed_positions.insert(0, pos)

        # Record close trade in unified ledger
        close_side = "SELL" if pos.side == GlobalAction.BUY else "BUY"
        AccountingEngine.record_trade(
            account_type=AccountType.GLOBAL_FOREX.value,
            reference_id=f"CLOSE-{pos_id}",
            symbol=pos.symbol,
            side=close_side,
            quantity=pos.lots,
            fill_price=current_price,
            fee=commission,
            tax=0.0,
            currency="USD",
            description=f"GLOBAL CLOSE {pos.side.value} {pos.lots}L {pos.symbol} @ ${current_price:.2f} | Realized PnL: ${realized:+.2f}",
        )

        logger.info(
            f"Closed 24/7 position {pos_id}: {pos.side.value} {pos.lots} lots @ ${current_price}. Realized P&L: ${realized:+.2f} ({reason})"
        )
        return pos

    def get_open_positions(self) -> List[GlobalPosition]:
        return list(self.positions.values())

    def get_closed_positions(self, limit: int = 50) -> List[GlobalPosition]:
        return self.closed_positions[:limit]
