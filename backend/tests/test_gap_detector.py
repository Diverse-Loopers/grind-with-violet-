"""
Unit tests for Strategy B: Gap Detector.
"""

from datetime import datetime, timezone
from app.strategies.gap_detector import GapDetector
from app.scanner.market_scanner import ScannerRow


def test_gap_detector_identifies_valid_gap():
    detector = GapDetector(gap_threshold_pct=1.0, volume_multiplier=1.5, min_net_edge_pct=0.2)
    now = datetime.now(timezone.utc)

    # 2.5% jump with 2.0x relative volume
    row = ScannerRow(
        trading_symbol="TATAMOTORS",
        exchange="NSE",
        name="Tata Motors Ltd",
        ltp=950.0,
        bid=949.5,
        ask=950.5,
        spread_pct=0.1,
        change_pct=2.5,
        volume=500000,
        relative_volume=2.0,
        high=960.0,
        low=940.0,
        volatility=0.8,
        deviation_from_ma=2.2,
        gap_pct=2.5,
        net_edge_pct=2.2,
        data_quality="DEMO",
        quote_timestamp=now,
        data_freshness_ms=100,
    )

    sig = detector.evaluate_row(row)
    assert sig is not None
    assert sig.trading_symbol == "TATAMOTORS"
    assert sig.signal_type == "BUY"
    assert sig.status == "PENDING"
    assert sig.net_edge_pct > 1.0


def test_gap_detector_ignores_small_moves():
    detector = GapDetector(gap_threshold_pct=1.0)
    now = datetime.now(timezone.utc)

    # 0.2% change -> below 1.0% threshold
    row = ScannerRow(
        trading_symbol="ITC",
        exchange="NSE",
        name="ITC Ltd",
        ltp=450.0,
        bid=449.9,
        ask=450.1,
        spread_pct=0.04,
        change_pct=0.2,
        volume=100000,
        relative_volume=1.0,
        high=452.0,
        low=448.0,
        volatility=0.2,
        deviation_from_ma=0.1,
        gap_pct=0.2,
        net_edge_pct=-0.1,
        data_quality="DEMO",
        quote_timestamp=now,
        data_freshness_ms=100,
    )

    sig = detector.evaluate_row(row)
    assert sig is None
