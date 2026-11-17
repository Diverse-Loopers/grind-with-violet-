"""
Indian Equity Transaction Cost Calculator.
Accurately models NSE cash equity transaction costs for both delivery (CNC) and intraday.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class CostBreakdown:
    turnover: float
    brokerage: float
    stt: float
    exchange_charges: float
    gst: float
    sebi_turnover_charges: float
    stamp_duty: float
    total_cost: float
    cost_pct: float


class TransactionCostCalculator:
    """Calculates statutory and broker fees for Indian cash equities (NSE/BSE)."""

    def __init__(
        self,
        brokerage_pct: float = 0.03,  # 0.03% or Rs 20 whichever is lower typically for discount brokers
        brokerage_flat: float = 20.0,
        use_flat_brokerage: bool = False,
    ):
        self.brokerage_pct = brokerage_pct
        self.brokerage_flat = brokerage_flat
        self.use_flat_brokerage = use_flat_brokerage

    def calculate_single_leg_cost(
        self,
        side: Literal["BUY", "SELL"],
        price: float,
        quantity: int,
        product: str = "CNC",
    ) -> CostBreakdown:
        turnover = price * quantity
        if turnover <= 0:
            return CostBreakdown(0, 0, 0, 0, 0, 0, 0, 0, 0)

        # 1. Brokerage
        if self.use_flat_brokerage:
            brokerage = self.brokerage_flat
        else:
            # 0.03% capped at Rs 20
            brokerage = min((turnover * self.brokerage_pct) / 100.0, self.brokerage_flat)

        # 2. STT (Securities Transaction Tax)
        if product.upper() == "CNC":
            # Delivery: 0.1% on both Buy and Sell
            stt = (turnover * 0.1) / 100.0
        else:
            # Intraday: 0.025% on Sell only
            stt = (turnover * 0.025) / 100.0 if side == "SELL" else 0.0

        # 3. Exchange Transaction Charges (NSE Equity ~ 0.00345%)
        exchange_charges = (turnover * 0.00345) / 100.0

        # 4. GST: 18% on (Brokerage + Exchange Charges)
        gst = (brokerage + exchange_charges) * 0.18

        # 5. SEBI Turnover Charges: Rs 10 per crore (0.0001%)
        sebi_turnover = (turnover * 0.0001) / 100.0

        # 6. Stamp Duty: 0.015% on BUY side only for delivery, 0.003% for intraday
        if side == "BUY":
            stamp_rate = 0.015 if product.upper() == "CNC" else 0.003
            stamp_duty = (turnover * stamp_rate) / 100.0
        else:
            stamp_duty = 0.0

        total_cost = brokerage + stt + exchange_charges + gst + sebi_turnover + stamp_duty
        cost_pct = (total_cost / turnover) * 100.0

        return CostBreakdown(
            turnover=round(turnover, 2),
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_charges=round(exchange_charges, 2),
            gst=round(gst, 2),
            sebi_turnover_charges=round(sebi_turnover, 2),
            stamp_duty=round(stamp_duty, 2),
            total_cost=round(total_cost, 2),
            cost_pct=round(cost_pct, 4),
        )

    def calculate_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        product: str = "CNC",
    ) -> CostBreakdown:
        """Calculates total round trip (BUY then SELL) transaction costs."""
        buy_cost = self.calculate_single_leg_cost("BUY", entry_price, quantity, product)
        sell_cost = self.calculate_single_leg_cost("SELL", exit_price, quantity, product)

        total_turnover = buy_cost.turnover + sell_cost.turnover
        total_brokerage = buy_cost.brokerage + sell_cost.brokerage
        total_stt = buy_cost.stt + sell_cost.stt
        total_exch = buy_cost.exchange_charges + sell_cost.exchange_charges
        total_gst = buy_cost.gst + sell_cost.gst
        total_sebi = buy_cost.sebi_turnover_charges + sell_cost.sebi_turnover_charges
        total_stamp = buy_cost.stamp_duty + sell_cost.stamp_duty
        total_cost = (
            total_brokerage
            + total_stt
            + total_exch
            + total_gst
            + total_sebi
            + total_stamp
        )
        cost_pct = (total_cost / buy_cost.turnover) * 100.0 if buy_cost.turnover > 0 else 0.0

        return CostBreakdown(
            turnover=round(total_turnover, 2),
            brokerage=round(total_brokerage, 2),
            stt=round(total_stt, 2),
            exchange_charges=round(total_exch, 2),
            gst=round(total_gst, 2),
            sebi_turnover_charges=round(total_sebi, 2),
            stamp_duty=round(total_stamp, 2),
            total_cost=round(total_cost, 2),
            cost_pct=round(cost_pct, 4),
        )
