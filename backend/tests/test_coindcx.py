"""
Automated Test Suite for CoinDCX Integration.
Tests market data adapter, constraints & precision validation, stale data rejection,
cross-market arbitrage & net profitability math (fees + TDS + slippage),
paper broker multi-currency accounting, and failed API handling.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.adapters.coindcx_adapter import CoinDCXAdapter
from app.coindcx.models import CoinDCXTicker, MarketDetail
from app.coindcx.paper_broker import CoinDCXPaperBroker
from app.coindcx.scanner import CoinDCXScanner
from app.main import app

client = TestClient(app)


# ── Sample Fixtures ───────────────────────────────────────────


@pytest.fixture
def mock_market_detail() -> MarketDetail:
    return MarketDetail(
        coindcx_name="BTCINR",
        symbol="BTCINR",
        pair="I-BTC_INR",
        base_currency_short_name="INR",
        target_currency_short_name="BTC",
        target_currency_name="Bitcoin",
        base_currency_precision=2,
        target_currency_precision=5,
        min_quantity=0.0001,
        max_quantity=100.0,
        min_price=100.0,
        max_price=100_000_000.0,
        min_notional=100.0,
        step=0.0001,
        status="active",
        order_types=["market_order", "limit_order"],
    )


@pytest.fixture
def mock_adapter(mock_market_detail: MarketDetail) -> CoinDCXAdapter:
    adapter = CoinDCXAdapter(stale_threshold_seconds=30.0)
    now = time.time()

    # Pre-populate caches with clean mock data
    adapter._markets_cache = {"BTCINR": mock_market_detail}
    adapter._markets_by_pair = {"I-BTC_INR": mock_market_detail}
    adapter._markets_cache_time = now

    ticker = CoinDCXTicker(
        market="BTCINR",
        last_price=8_500_000.0,
        bid=8_495_000.0,
        ask=8_505_000.0,
        high=8_600_000.0,
        low=8_400_000.0,
        volume=120.5,
        change_24_hour=1.85,
        timestamp=int(now),
        spread=10_000.0,
        spread_pct=0.1177,
        data_freshness_seconds=0.1,
        is_stale=False,
    )
    adapter._tickers_cache = {"BTCINR": ticker}
    adapter._tickers_cache_time = now
    return adapter


# ── 1. Market Constraints and Validation Tests ────────────────


def test_order_rules_valid_order(mock_adapter: CoinDCXAdapter):
    """Valid order conforming to all CoinDCX rules should succeed."""
    is_valid, msg, constraints = mock_adapter.validate_order_rules(
        market="BTCINR",
        side="BUY",
        quantity=0.001,  # >= 0.0001 min_qty and multiple of step 0.0001
        price=8_500_000.0,  # notional = 8500 >= 100 min_notional
    )
    assert is_valid is True
    assert "conforms" in msg.lower()


def test_order_rules_below_min_quantity(mock_adapter: CoinDCXAdapter):
    """Order with quantity below minimum must be rejected."""
    is_valid, msg, _ = mock_adapter.validate_order_rules(
        market="BTCINR",
        side="BUY",
        quantity=0.00005,  # min is 0.0001
        price=8_500_000.0,
    )
    assert is_valid is False
    assert "below coindcx minimum quantity" in msg.lower()


def test_order_rules_exceeds_max_quantity(mock_adapter: CoinDCXAdapter):
    """Order exceeding max allowed quantity must be rejected."""
    is_valid, msg, _ = mock_adapter.validate_order_rules(
        market="BTCINR",
        side="BUY",
        quantity=500.0,  # max is 100.0
        price=8_500_000.0,
    )
    assert is_valid is False
    assert "exceeds coindcx maximum" in msg.lower()


def test_order_rules_invalid_step_increment(mock_adapter: CoinDCXAdapter):
    """Order that does not respect step increment must be rejected."""
    is_valid, msg, _ = mock_adapter.validate_order_rules(
        market="BTCINR",
        side="BUY",
        quantity=0.00015,  # step is 0.0001 -> remainder 0.00005 != 0
        price=8_500_000.0,
    )
    assert is_valid is False
    assert "step increment" in msg.lower()


def test_order_rules_below_min_notional(mock_adapter: CoinDCXAdapter):
    """Order below minimum notional (INR 100) must be rejected."""
    is_valid, msg, _ = mock_adapter.validate_order_rules(
        market="BTCINR",
        side="BUY",
        quantity=0.0001,
        price=500.0,  # 0.0001 * 500 = 0.05 < 100 min_notional
    )
    assert is_valid is False
    assert "below coindcx minimum notional value" in msg.lower()


def test_order_rules_price_out_of_bounds(mock_adapter: CoinDCXAdapter):
    """Order with negative or zero price must be rejected."""
    is_valid, msg, _ = mock_adapter.validate_order_rules(
        market="BTCINR",
        side="BUY",
        quantity=0.001,
        price=-10.0,
    )
    assert is_valid is False
    assert "positive" in msg.lower()


# ── 2. Stale Market Data Rejection Tests ───────────────────────


def test_stale_market_data_rejection(mock_adapter: CoinDCXAdapter):
    """Orders attempted against stale market data (>30s old) must be rejected."""
    # Set ticker timestamp to 45 seconds ago
    stale_ts = int(time.time() - 45)
    mock_adapter._tickers_cache["BTCINR"] = CoinDCXTicker(
        market="BTCINR",
        last_price=8_500_000.0,
        bid=8_495_000.0,
        ask=8_505_000.0,
        high=8_600_000.0,
        low=8_400_000.0,
        volume=100.0,
        change_24_hour=1.0,
        timestamp=stale_ts,
        spread=10000.0,
        spread_pct=0.12,
        data_freshness_seconds=45.0,
        is_stale=True,
    )

    broker = CoinDCXPaperBroker(adapter=mock_adapter)
    res = broker.place_paper_order(market="BTCINR", side="BUY", quantity=0.001)

    assert res["success"] is False
    assert res["status"] == "REJECTED"
    assert "stale market data" in res["message"].lower()


# ── 3. Scanner Net Profitability, Fee & TDS Calculations ──────


def test_scanner_distinguishes_detected_vs_executable():
    """
    Scanner must calculate net edge after 0.40% fees, 1.0% TDS, and half-spread slippage.
    Normal tight spreads (~0.3%) should be classified as DETECTED_ONLY because friction is ~1.5%.
    """
    adapter = CoinDCXAdapter()
    now = int(time.time())

    # Mock Tickers: USDTINR = 100.0, BTCUSDT = 85000.0 -> Synthetic INR = 8,500,000
    # Direct BTCINR = 8,525,500 (Gross discrepancy: +0.30%)
    adapter._tickers_cache = {
        "USDTINR": CoinDCXTicker(
            market="USDTINR",
            last_price=100.0,
            bid=99.9,
            ask=100.1,
            high=101.0,
            low=99.0,
            volume=50000.0,
            change_24_hour=0.1,
            timestamp=now,
            spread=0.2,
            spread_pct=0.2,
            data_freshness_seconds=0.1,
            is_stale=False,
        ),
        "BTCUSDT": CoinDCXTicker(
            market="BTCUSDT",
            last_price=85_000.0,
            bid=84_990.0,
            ask=85_010.0,
            high=86_000.0,
            low=84_000.0,
            volume=500.0,
            change_24_hour=1.2,
            timestamp=now,
            spread=20.0,
            spread_pct=0.02,
            data_freshness_seconds=0.1,
            is_stale=False,
        ),
        "BTCINR": CoinDCXTicker(
            market="BTCINR",
            last_price=8_525_500.0,
            bid=8_520_000.0,
            ask=8_530_000.0,
            high=8_600_000.0,
            low=8_400_000.0,
            volume=150.0,
            change_24_hour=1.5,
            timestamp=now,
            spread=10_000.0,
            spread_pct=0.12,
            data_freshness_seconds=0.1,
            is_stale=False,
        ),
    }
    adapter._tickers_cache_time = time.time()

    scanner = CoinDCXScanner(adapter=adapter)
    opps = scanner.scan_opportunities()

    assert len(opps) >= 1
    btc_opp = next(o for o in opps if o.target_asset == "BTC")

    # Verify mathematical calculations:
    assert btc_opp.synthetic_inr_price == 8_500_000.0
    assert btc_opp.estimated_trading_fees_pct == 0.40  # 2 legs @ 0.20%
    assert btc_opp.estimated_statutory_tds_pct == 1.00  # 1.0% TDS
    assert btc_opp.total_execution_cost_pct > 1.40  # 0.40 + 1.0 + slippage > 1.40%
    assert btc_opp.net_profit_pct < 0.0  # 0.30% gross - 1.5% costs = negative net
    assert btc_opp.status == "DETECTED_ONLY"
    assert btc_opp.is_executable is False
    assert "insufficient to overcome transaction friction" in btc_opp.execution_reason.lower()


def test_scanner_flags_executable_when_gross_edge_exceeds_friction():
    """When discrepancy exceeds total friction (e.g. 5.0% gross edge), it must flag EXECUTABLE."""
    adapter = CoinDCXAdapter()
    now = int(time.time())

    # Direct BTCINR = 8,950,000 vs Synthetic 8,500,000 -> Gross discrepancy > 5.2%
    adapter._tickers_cache = {
        "USDTINR": CoinDCXTicker(
            market="USDTINR",
            last_price=100.0,
            bid=99.9,
            ask=100.1,
            high=101.0,
            low=99.0,
            volume=50000.0,
            change_24_hour=0.1,
            timestamp=now,
            spread=0.2,
            spread_pct=0.2,
            data_freshness_seconds=0.1,
            is_stale=False,
        ),
        "BTCUSDT": CoinDCXTicker(
            market="BTCUSDT",
            last_price=85_000.0,
            bid=84_990.0,
            ask=85_010.0,
            high=86_000.0,
            low=84_000.0,
            volume=500.0,
            change_24_hour=1.2,
            timestamp=now,
            spread=20.0,
            spread_pct=0.02,
            data_freshness_seconds=0.1,
            is_stale=False,
        ),
        "BTCINR": CoinDCXTicker(
            market="BTCINR",
            last_price=8_950_000.0,
            bid=8_940_000.0,
            ask=8_960_000.0,
            high=9_000_000.0,
            low=8_400_000.0,
            volume=150.0,
            change_24_hour=5.0,
            timestamp=now,
            spread=20_000.0,
            spread_pct=0.22,
            data_freshness_seconds=0.1,
            is_stale=False,
        ),
    }
    adapter._tickers_cache_time = time.time()

    scanner = CoinDCXScanner(adapter=adapter)
    opps = scanner.scan_opportunities()

    btc_opp = next(o for o in opps if o.target_asset == "BTC")
    assert btc_opp.status == "EXECUTABLE"
    assert btc_opp.is_executable is True
    assert btc_opp.net_profit_pct > 3.0
    assert "actionable edge" in btc_opp.execution_reason.lower()


# ── 4. Paper Broker Accounting & Order Execution Tests ────────


def test_paper_broker_full_lifecycle(mock_adapter: CoinDCXAdapter):
    """
    Tests complete accounting lifecycle:
    1. Reset wallet to known balance
    2. Place BUY order -> verify balance deduction, position creation, fee deduction
    3. Place partial SELL order -> verify realized P&L, 1.0% TDS, balance credit
    4. Verify historical order log persistence
    """
    broker = CoinDCXPaperBroker(adapter=mock_adapter, starting_inr=500_000.0, starting_usdt=5_000.0)
    broker.reset_wallet(starting_inr=500_000.0, starting_usdt=5_000.0)

    # 1. Check initial wallet
    wallet = broker.get_wallet_overview()
    assert wallet["inr_cash"] == 500_000.0
    assert wallet["usdt_cash"] == 5_000.0
    assert wallet["holdings_count"] == 0

    # 2. Buy 0.01 BTC @ ask price 8,505,000
    # Turnover = 85,050 INR. Fee (0.20%) = 170.10 INR. Total cost = 85,220.10 INR
    buy_res = broker.place_paper_order(market="BTCINR", side="BUY", quantity=0.01)
    assert buy_res["success"] is True
    assert buy_res["status"] == "FILLED"
    assert buy_res["fill_price"] == 8_505_000.0
    assert buy_res["fee"] == 170.10

    # Verify wallet after BUY
    wallet_after_buy = broker.get_wallet_overview()
    expected_inr = 500_000.0 - 85_220.10
    assert abs(wallet_after_buy["inr_cash"] - expected_inr) < 1.0
    assert wallet_after_buy["holdings_count"] == 1
    btc_pos = wallet_after_buy["holdings"][0]
    assert btc_pos["target_currency"] == "BTC"
    assert btc_pos["quantity"] == 0.01

    # 3. Sell 0.005 BTC (half position) @ bid price 8,495,000
    # Turnover = 0.005 * 8,495,000 = 42,475 INR
    # Fee (0.20%) = 84.95 INR
    # TDS (1.0% on sell leg) = 424.75 INR
    # Net cash credit = 42,475 - 84.95 - 424.75 = 41,965.30 INR
    sell_res = broker.place_paper_order(market="BTCINR", side="SELL", quantity=0.005)
    assert sell_res["success"] is True
    assert sell_res["status"] == "FILLED"
    assert sell_res["fill_price"] == 8_495_000.0
    assert sell_res["fee"] == 84.95
    assert sell_res["tds"] == 424.75

    # Check position remainder
    wallet_after_sell = broker.get_wallet_overview()
    assert wallet_after_sell["holdings_count"] == 1
    assert abs(wallet_after_sell["holdings"][0]["quantity"] - 0.005) < 1e-6

    # 4. Check orders log persistence
    orders = broker.get_orders(limit=10)
    assert len(orders) >= 2
    sides = [o["side"] for o in orders[:2]]
    assert "SELL" in sides
    assert "BUY" in sides


# ── 5. Error Handling and Live Trading Safety Lock Tests ───────


def test_failed_api_handling_does_not_crash(mock_adapter: CoinDCXAdapter):
    """When CoinDCX network returns HTTP error / timeout, adapter must fail gracefully."""
    with patch.object(mock_adapter, "_http_get", side_effect=Exception("Connection timeout")):
        # Should not raise exception, but return cached or empty safely
        candles = mock_adapter.get_candles("BTCINR")
        assert candles == []

        orderbook = mock_adapter.get_order_book("BTCINR")
        assert orderbook is None


def test_live_trading_endpoint_blocked_by_safety_lock():
    """Attempting live trading must be rejected with HTTP 403 Forbidden."""
    res = client.post("/api/coindcx/live/order", json={"symbol": "BTCINR", "side": "BUY", "quantity": 1.0})
    assert res.status_code == 403
    data = res.json()
    assert "disabled" in data["detail"]["error"].lower()


# ── 6. FastAPI Routes Integration Tests ────────────────────────


def test_api_coindcx_status():
    """Tests GET /api/coindcx/status returns correct configuration."""
    res = client.get("/api/coindcx/status")
    assert res.status_code == 200
    data = res.json()
    assert data["live_trading_enabled"] is False
    assert data["mode"] == "PAPER"
    assert "PAPER ONLY" in data["safety_guarantee"]


def test_api_coindcx_paper_wallet():
    """Tests GET /api/coindcx/paper/wallet returns valid structure."""
    res = client.get("/api/coindcx/paper/wallet")
    assert res.status_code == 200
    data = res.json()
    assert "inr_cash" in data
    assert "usdt_cash" in data
    assert "total_equity_inr" in data
    assert "holdings" in data


def test_api_coindcx_paper_order_validation_failure():
    """Tests POST /api/coindcx/paper/order rejects invalid quantity with HTTP 400."""
    res = client.post(
        "/api/coindcx/paper/order",
        json={"market": "BTCINR", "side": "BUY", "quantity": 0.00000001, "order_type": "MARKET"},
    )
    assert res.status_code == 400
    data = res.json()
    assert "detail" in data
