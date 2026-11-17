"""
Unit tests for Strategy A: Spread Scanner.
"""

from datetime import datetime, timezone
from app.strategies.spread_scanner import SpreadScanner
from app.scanner.market_scanner import ScannerRow


def test_spread_scanner_rejects_narrow_spread_when_cost_exceeds_gross():
    # Min edge 0.1%. If gross spread is only 0.05%, cost (~0.25%) makes net edge negative.
    scanner = SpreadScanner(min_net_edge_pct=0.1)
    now = datetime.now(timezone.utc)

    row = ScannerRow(
        trading_symbol="HDFCBANK",
        exchange="NSE",
        name="HDFC Bank Ltd",
        ltp=1600.0,
        bid=1599.8,
        ask=1600.2,  # spread 0.4 on 1600 = 0.025%
        spread_pct=0.025,
        change_pct=0.1,
        volume=200000,
        relative_volume=1.0,
        high=1610.0,
        low=1595.0,
        volatility=0.3,
        deviation_from_ma=0.0,
        gap_pct=0.025,
        net_edge_pct=-0.2,
        data_quality="DEMO",
        quote_timestamp=now,
        data_freshness_ms=50,
    )

    sig = scanner.evaluate_row(row)
    assert sig is not None
    # Must be REJECTED because net edge is negative after costs
    assert sig.status == "REJECTED"
    assert "below minimum required" in sig.rejection_reason
