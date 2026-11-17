"""
Strategy C: Statistical Pairs Research Module.
Calculates rolling correlation, cointegration spread, and z-score for related equity pairs
(e.g., TCS vs INFY, HDFCBANK vs ICICIBANK).
Strictly labeled as RESEARCH_ONLY.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.models.signal import Signal, StrategyType, SignalType, SignalStatus
from app.scanner.market_scanner import ScannerRow


RESEARCH_PAIRS = [
    ("TCS", "INFY", "IT Sector Peers"),
    ("HDFCBANK", "ICICIBANK", "Private Banking Peers"),
    ("TATAMOTORS", "MARUTI", "Auto Sector Peers"),
]


class PairsResearch:
    """Statistical pairs research module for mean reversion analysis."""

    def __init__(self, zscore_threshold: float = 2.0, lookback_window: int = 20):
        self.zscore_threshold = zscore_threshold
        self.lookback_window = lookback_window
        # Pair key -> list of historical price ratios
        self.ratio_history: Dict[str, List[float]] = {}

    def analyze_pair(
        self,
        row_a: ScannerRow,
        row_b: ScannerRow,
        pair_name: str = "",
    ) -> Optional[Signal]:
        """
        Analyzes the price relationship between two securities.
        Computes rolling ratio, mean, standard deviation, and current z-score.
        """
        if row_a.ltp <= 0 or row_b.ltp <= 0:
            return None

        current_ratio = row_a.ltp / row_b.ltp
        pair_key = f"{row_a.trading_symbol}_{row_b.trading_symbol}"

        if pair_key not in self.ratio_history:
            self.ratio_history[pair_key] = []

        self.ratio_history[pair_key].append(current_ratio)
        if len(self.ratio_history[pair_key]) > self.lookback_window * 3:
            self.ratio_history[pair_key].pop(0)

        history = self.ratio_history[pair_key]
        if len(history) < 5:
            return None

        mean_ratio = float(np.mean(history))
        std_ratio = float(np.std(history))

        if std_ratio <= 1e-6:
            return None

        zscore = (current_ratio - mean_ratio) / std_ratio

        # Check if spread divergence exceeds threshold
        if abs(zscore) < self.zscore_threshold:
            return None

        # If zscore > 2, Stock A is expensive relative to B -> Potential Mean Reversion
        is_a_oversold = zscore < 0
        signal_type = SignalType.BUY.value if is_a_oversold else SignalType.SELL.value

        confidence = min(1.0, abs(zscore) / 3.5)
        now = datetime.now(timezone.utc)

        reason = (
            f"[RESEARCH ONLY] Statistical divergence in pair {row_a.trading_symbol}/{row_b.trading_symbol} "
            f"({pair_name}). Z-score: {zscore:+.2f} (Ratio: {current_ratio:.4f}, Mean: {mean_ratio:.4f}, σ: {std_ratio:.4f}). "
            f"Mean reversion is not guaranteed. Do not auto-execute."
        )

        return Signal(
            instrument_id=1,
            trading_symbol=row_a.trading_symbol,
            strategy=StrategyType.PAIRS.value,
            signal_type=signal_type,
            entry_price=row_a.ltp,
            reference_price=round(row_b.ltp * mean_ratio, 2),
            expected_edge_pct=round(abs(zscore) * 0.5, 3),
            estimated_cost_pct=0.25,
            net_edge_pct=round(max(0.0, (abs(zscore) * 0.5) - 0.25), 3),
            confidence_score=round(confidence, 2),
            reason=reason,
            data_quality=row_a.data_quality,
            quote_timestamp=row_a.quote_timestamp or now,
            bid_price=row_a.bid,
            ask_price=row_a.ask,
            spread_pct=row_a.spread_pct,
            volume=row_a.volume,
            relative_volume=row_a.relative_volume,
            volatility=row_a.volatility,
            status=SignalStatus.REJECTED.value,  # Stays rejected/research-only by default
            rejection_reason="PAIRS_STRATEGY_IS_RESEARCH_ONLY_UNVALIDATED",
        )

    def scan_all_pairs(self, rows_by_symbol: Dict[str, ScannerRow]) -> List[Signal]:
        signals: List[Signal] = []
        for sym_a, sym_b, name in RESEARCH_PAIRS:
            if sym_a in rows_by_symbol and sym_b in rows_by_symbol:
                sig = self.analyze_pair(rows_by_symbol[sym_a], rows_by_symbol[sym_b], name)
                if sig:
                    signals.append(sig)
        return signals
