"""
Strategy B: Intraday Price-Gap and Breakout Detector.
Identifies significant intraday price gaps, deviations from moving averages,
and sudden volume spikes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from app.config import settings
from app.engine.cost_calculator import TransactionCostCalculator
from app.models.signal import Signal, StrategyType, SignalType, SignalStatus
from app.scanner.market_scanner import ScannerRow


class GapDetector:
    """Strategy B: Intraday price gap and anomaly detection."""

    def __init__(
        self,
        gap_threshold_pct: Optional[float] = None,
        volume_multiplier: Optional[float] = None,
        min_net_edge_pct: float = 0.2,
    ):
        self.gap_threshold_pct = gap_threshold_pct or settings.gap_threshold_pct
        self.volume_multiplier = volume_multiplier or settings.gap_volume_multiplier
        self.min_net_edge_pct = min_net_edge_pct
        self.cost_calc = TransactionCostCalculator(
            brokerage_pct=settings.brokerage_pct,
            brokerage_flat=settings.brokerage_flat,
            use_flat_brokerage=settings.use_flat_brokerage,
        )

    def evaluate_row(self, row: ScannerRow, instrument_id: int = 1) -> Optional[Signal]:
        """
        Evaluates row for gap or momentum breakout conditions:
        - Price change >= threshold
        - Or Deviation from MA >= threshold
        - Accompanied by relative volume confirmation
        """
        if row.ltp <= 0:
            return None

        # Check conditions
        abs_change = abs(row.change_pct)
        abs_dev_ma = abs(row.deviation_from_ma)
        has_price_gap = abs_change >= self.gap_threshold_pct or abs_dev_ma >= self.gap_threshold_pct
        has_volume_spike = row.relative_volume >= self.volume_multiplier

        if not has_price_gap:
            return None

        # Determine signal direction
        is_bullish = (row.change_pct > 0) or (row.deviation_from_ma > 0)
        signal_type = SignalType.BUY.value if is_bullish else SignalType.SELL.value

        # Calculate estimated round trip cost (buying at Ask, exiting at Bid)
        exec_entry = row.ask if row.ask > 0 else row.ltp
        cost_breakdown = self.cost_calc.calculate_round_trip_cost(
            entry_price=exec_entry,
            exit_price=exec_entry * (1.0 + (abs_change / 100.0)),
            quantity=50,
            product="CNC",
        )

        # Expected target edge incorporates spread friction + slippage
        spread_friction = row.spread_pct if row.spread_pct > 0 else 0.10
        total_costs_pct = cost_breakdown.cost_pct + spread_friction + 0.10  # 0.10% round-trip slippage

        # Gross edge from observed price gap or momentum breakout
        expected_gross_edge = round(max(abs_change, abs_dev_ma), 2)
        net_edge = round(expected_gross_edge - total_costs_pct, 2)

        # In Indian Cash Delivery (CNC), short selling is prohibited under SEBI regulations
        if not is_bullish:
            passed = False
            status = SignalStatus.REJECTED.value
            rejection_reason = "Short selling prohibited in cash delivery (CNC) equity under SEBI regulations."
        else:
            passed = (net_edge >= self.min_net_edge_pct) and has_volume_spike
            status = SignalStatus.PENDING.value if passed else SignalStatus.REJECTED.value
            rejection_reason = None if passed else (
                f"Net edge {net_edge:.2f}% below threshold {self.min_net_edge_pct}% or missing volume confirmation "
                f"(Expected: {expected_gross_edge:.2f}%, Friction: {total_costs_pct:.2f}%, Vol: {row.relative_volume:.1f}x)."
            )

        # Statistical confidence score combining gap size and volume confirmation
        vol_score = min(1.0, row.relative_volume / 3.0)
        gap_score = min(1.0, expected_gross_edge / 3.0)
        confidence = round((gap_score * 0.6) + (vol_score * 0.4), 2)

        reason_elements = []
        if abs_change >= self.gap_threshold_pct:
            reason_elements.append(f"Price change {row.change_pct:+.2f}%")
        if abs_dev_ma >= self.gap_threshold_pct:
            reason_elements.append(f"MA deviation {row.deviation_from_ma:+.2f}%")
        if has_volume_spike:
            reason_elements.append(f"Volume spike {row.relative_volume:.1f}x")
        else:
            reason_elements.append(f"Normal volume ({row.relative_volume:.1f}x)")

        full_reason = f"Candidate gap signal: {', '.join(reason_elements)}. Net edge {net_edge:.2f}%."
        now = datetime.now(timezone.utc)

        return Signal(
            instrument_id=instrument_id,
            trading_symbol=row.trading_symbol,
            strategy=StrategyType.GAP.value,
            signal_type=signal_type,
            entry_price=row.ltp,
            reference_price=round(row.ltp / (1.0 + (row.change_pct / 100.0)), 2) if row.change_pct != 0 else row.ltp,
            expected_edge_pct=round(expected_gross_edge, 3),
            estimated_cost_pct=round(cost_breakdown.cost_pct, 3),
            net_edge_pct=round(net_edge, 3),
            confidence_score=confidence,
            reason=full_reason,
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

    def scan(self, rows: List[ScannerRow]) -> List[Signal]:
        signals: List[Signal] = []
        for row in rows:
            sig = self.evaluate_row(row)
            if sig:
                signals.append(sig)
        return signals
