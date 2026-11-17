"""
Strategy A: Executable Spread Scanner.
Scans for executable bid-ask spread opportunities accounting for all statutory
taxes (STT, GST, Stamp Duty, SEBI turnover) and brokerage.
Rejects any signal where net edge after realistic costs does not clear minimum threshold.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from app.config import settings
from app.engine.cost_calculator import TransactionCostCalculator
from app.models.signal import Signal, StrategyType, SignalType, SignalStatus, DataQuality
from app.scanner.market_scanner import ScannerRow
from app.utils.logging import logger


class SpreadScanner:
    """Strategy A: Scans for positive net edge after full statutory cost modeling."""

    def __init__(self, min_net_edge_pct: Optional[float] = None, slippage_pct: float = 0.05):
        self.min_net_edge_pct = min_net_edge_pct or settings.spread_min_edge_pct
        self.slippage_pct = slippage_pct
        self.cost_calc = TransactionCostCalculator(
            brokerage_pct=settings.brokerage_pct,
            brokerage_flat=settings.brokerage_flat,
            use_flat_brokerage=settings.use_flat_brokerage,
        )

    def evaluate_row(self, row: ScannerRow, instrument_id: int = 1) -> Optional[Signal]:
        """
        Evaluates a single ScannerRow for executable spread edge.
        Requires valid, non-zero executable bid and ask quotes.
        """
        if row.bid <= 0 or row.ask <= 0 or row.ask <= row.bid:
            return None

        gross_spread = row.ask - row.bid
        gross_spread_pct = (gross_spread / row.bid) * 100.0

        # Calculate realistic round-trip statutory costs on 100 shares
        standard_qty = 100
        cost_breakdown = self.cost_calc.calculate_round_trip_cost(
            entry_price=row.ask,  # Taker BUY executes at Ask
            exit_price=row.bid,   # Taker SELL executes at Bid
            quantity=standard_qty,
            product="CNC",
        )

        # For a market order, the bid-ask spread is an execution friction (cost), not captured profit.
        # Capturing spread requires passive dual-sided market making; crossing the spread incurs loss.
        total_costs_pct = cost_breakdown.cost_pct + gross_spread_pct + (self.slippage_pct * 2.0)
        net_edge_pct = -total_costs_pct

        now = datetime.now(timezone.utc)
        passed = False  # Normal single-exchange taker orders cannot capture the bid-ask spread as profit
        status = SignalStatus.REJECTED.value
        rejection_reason = (
            f"Non-executable: Crossing bid-ask spread incurs total friction of {total_costs_pct:.3f}% "
            f"(Spread cost: {gross_spread_pct:.3f}%, Taxes & Fees: {cost_breakdown.cost_pct:.3f}%, Slippage: {self.slippage_pct*2:.2f}%). "
            f"Net edge {net_edge_pct:.3f}% is below minimum required threshold {self.min_net_edge_pct}%. "
            f"Market taker orders pay the spread rather than capturing it."
        )

        signal = Signal(
            instrument_id=instrument_id,
            trading_symbol=row.trading_symbol,
            strategy=StrategyType.SPREAD.value,
            signal_type=SignalType.BUY.value,
            entry_price=row.ask,
            reference_price=row.bid,
            expected_edge_pct=round(-gross_spread_pct, 3),
            estimated_cost_pct=round(total_costs_pct, 3),
            net_edge_pct=round(net_edge_pct, 3),
            confidence_score=0.0,
            reason=(
                f"Gross bid-ask spread of {gross_spread:.2f} INR ({gross_spread_pct:.2f}%). "
                f"Total estimated costs {total_costs_pct:.3f}%. Expected net edge {net_edge_pct:.3f}%."
            ),
            data_quality=row.data_quality,
            quote_timestamp=row.quote_timestamp or now,
            bid_price=row.bid,
            ask_price=row.ask,
            spread_pct=row.spread_pct,
            volume=row.volume,
            relative_volume=row.relative_volume,
            volatility=row.volatility,
            status=status,
            rejection_reason=rejection_reason,
        )

        return signal

    def scan(self, rows: List[ScannerRow], include_rejected: bool = False) -> List[Signal]:
        signals: List[Signal] = []
        for row in rows:
            sig = self.evaluate_row(row)
            if sig:
                if include_rejected or sig.status != SignalStatus.REJECTED.value:
                    signals.append(sig)
        return signals
