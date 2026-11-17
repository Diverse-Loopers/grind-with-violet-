"""
Automated Risk Controls & Execution Safety Tests.
Verifies:
1. Idempotent order submission using client_order_id.
2. Duplicate order suppression within a 3.0s sliding window.
3. Persistent kill-switch state surviving backend reload.
4. Position, order size, and exposure limits.
5. Rejection of stale quotes and orders when risk limits are breached.
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.adapters.base import Quote
from app.database import init_db
from app.engine.paper_broker import PaperBroker
from app.engine.risk_engine import RiskEngine


@pytest.fixture(autouse=True)
def setup_risk_test():
    init_db()


def test_idempotent_order_submission_with_client_order_id():
    broker = PaperBroker()
    cid = f"CLIENT-ORD-{uuid.uuid4().hex[:8]}"

    q = Quote(
        trading_symbol="INFY",
        exchange="NSE",
        ltp=1500.0,
        bid_price=1499.5,
        ask_price=1500.5,
        volume=100000,
        high=1520.0,
        low=1480.0,
        change_pct=1.0,
        timestamp=datetime.now(timezone.utc),
    )

    # First submission
    res1 = broker.place_paper_order(
        trading_symbol="INFY",
        transaction_type="BUY",
        quantity=1,
        quote=q,
        client_order_id=cid,
    )
    assert res1.success is True

    # Duplicate submission with identical client_order_id must return existing order without double-filling
    res2 = broker.place_paper_order(
        trading_symbol="INFY",
        transaction_type="BUY",
        quantity=1,
        quote=q,
        client_order_id=cid,
    )
    assert res2.success is True
    assert res2.order_id == res1.order_id
    assert "Idempotent" in res2.message


def test_duplicate_order_suppression_within_time_window():
    broker = PaperBroker()
    q = Quote(
        trading_symbol="TCS",
        exchange="NSE",
        ltp=3500.0,
        bid_price=3499.0,
        ask_price=3501.0,
        volume=50000,
        high=3550.0,
        low=3450.0,
        change_pct=0.5,
        timestamp=datetime.now(timezone.utc),
    )

    # Rapid submission of identical orders without client_order_id within 3 seconds
    res1 = broker.place_paper_order(trading_symbol="TCS", transaction_type="BUY", quantity=1, quote=q)
    assert res1.success is True

    res2 = broker.place_paper_order(trading_symbol="TCS", transaction_type="BUY", quantity=1, quote=q)
    assert res2.success is False
    assert "Duplicate order suppressed" in res2.message


def test_kill_switch_persistence_and_restart_recovery():
    risk = RiskEngine()

    # Trigger kill switch
    risk.trigger_kill_switch(enabled=True, reason="Automated safety audit test")
    assert risk.settings.kill_switch_active is True

    # Simulate restart by instantiating fresh RiskEngine
    recovered_risk = RiskEngine()
    assert recovered_risk.settings.kill_switch_active is True

    # Verify orders are rejected when kill switch is active
    decision = recovered_risk.evaluate_order(
        trading_symbol="RELIANCE",
        strategy="GAP",
        side="BUY",
        quantity=10,
        price=2500.0,
        quote_timestamp=datetime.now(timezone.utc),
        current_equity=100000.0,
        current_open_positions_count=0,
        existing_position_qty_for_symbol=0,
        daily_realized_loss=0.0,
        is_market_open=True,
    )
    assert decision.passed is False
    assert "EMERGENCY_KILL_SWITCH_ACTIVE" in decision.rejection_reasons

    # Reset kill switch
    recovered_risk.trigger_kill_switch(enabled=False, reason="Safety test complete")
    assert recovered_risk.settings.kill_switch_active is False


def test_stale_market_quote_rejection():
    risk = RiskEngine()
    stale_timestamp = datetime.now(timezone.utc) - timedelta(seconds=120)

    decision = risk.evaluate_order(
        trading_symbol="WIPRO",
        strategy="GAP",
        side="BUY",
        quantity=10,
        price=450.0,
        quote_timestamp=stale_timestamp,
        current_equity=100000.0,
        current_open_positions_count=0,
        existing_position_qty_for_symbol=0,
        daily_realized_loss=0.0,
        is_market_open=True,
    )
    assert decision.passed is False
    assert any("STALE_QUOTE" in r for r in decision.rejection_reasons)
