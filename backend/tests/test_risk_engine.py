"""
Unit tests for Independent Pre-Trade Risk Engine.
"""

from datetime import datetime, timezone, timedelta
from app.engine.risk_engine import RiskEngine
from app.models.risk_settings import RiskSettings


def get_test_engine() -> RiskEngine:
    cfg = RiskSettings(
        max_position_pct=10.0,
        max_daily_loss=50000.0,
        max_open_positions=5,
        max_single_order_value=100000.0,
        quote_max_age_seconds=30.0,
        min_net_edge_pct=0.1,
        kill_switch_active=False,
        strategy_spread_enabled=True,
        strategy_gap_enabled=True,
        min_volume_threshold=1000,
    )
    return RiskEngine(custom_settings=cfg)


def test_order_passes_when_all_conditions_healthy():
    engine = get_test_engine()
    now = datetime.now(timezone.utc)
    decision = engine.evaluate_order(
        trading_symbol="INFY",
        strategy="GAP",
        side="BUY",
        quantity=20,
        price=1800.0,  # Order val 36,000 < 100,000 max
        quote_timestamp=now,
        current_equity=1_000_000.0,
        current_open_positions_count=2,
        existing_position_qty_for_symbol=0,
        daily_realized_loss=1000.0,
        is_market_open=True,
        net_edge_pct=0.5,
        volume=50000,
        system_healthy=True,
    )
    assert decision.passed is True
    assert len(decision.rejection_reasons) == 0


def test_order_rejected_when_market_closed():
    engine = get_test_engine()
    decision = engine.evaluate_order(
        trading_symbol="INFY",
        strategy="GAP",
        side="BUY",
        quantity=10,
        price=1800.0,
        quote_timestamp=datetime.now(timezone.utc),
        current_equity=1_000_000.0,
        current_open_positions_count=0,
        existing_position_qty_for_symbol=0,
        daily_realized_loss=0.0,
        is_market_open=False,
    )
    assert decision.passed is False
    assert "MARKET_IS_CLOSED" in decision.rejection_reasons


def test_order_rejected_when_kill_switch_active():
    engine = get_test_engine()
    engine.trigger_kill_switch(True, "Emergency test")
    decision = engine.evaluate_order(
        trading_symbol="TCS",
        strategy="GAP",
        side="BUY",
        quantity=10,
        price=4000.0,
        quote_timestamp=datetime.now(timezone.utc),
        current_equity=1_000_000.0,
        current_open_positions_count=0,
        existing_position_qty_for_symbol=0,
        daily_realized_loss=0.0,
        is_market_open=True,
    )
    assert decision.passed is False
    assert "EMERGENCY_KILL_SWITCH_ACTIVE" in decision.rejection_reasons


def test_order_rejected_on_stale_quote():
    engine = get_test_engine()
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=45)
    decision = engine.evaluate_order(
        trading_symbol="RELIANCE",
        strategy="GAP",
        side="BUY",
        quantity=10,
        price=2800.0,
        quote_timestamp=stale_time,
        current_equity=1_000_000.0,
        current_open_positions_count=0,
        existing_position_qty_for_symbol=0,
        daily_realized_loss=0.0,
        is_market_open=True,
    )
    assert decision.passed is False
    assert any("STALE_QUOTE" in r for r in decision.rejection_reasons)


def test_order_rejected_on_max_order_value_breach():
    engine = get_test_engine()
    # 200 * 2800 = 560,000 > max 100,000
    decision = engine.evaluate_order(
        trading_symbol="RELIANCE",
        strategy="GAP",
        side="BUY",
        quantity=200,
        price=2800.0,
        quote_timestamp=datetime.now(timezone.utc),
        current_equity=1_000_000.0,
        current_open_positions_count=0,
        existing_position_qty_for_symbol=0,
        daily_realized_loss=0.0,
        is_market_open=True,
    )
    assert decision.passed is False
    assert any("ORDER_VALUE_EXCEEDS_LIMIT" in r for r in decision.rejection_reasons)
