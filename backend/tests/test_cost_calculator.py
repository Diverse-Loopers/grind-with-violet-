"""
Unit tests for Indian Cash Equity Transaction Cost Calculator.
"""

from app.engine.cost_calculator import TransactionCostCalculator


def test_cost_calculator_delivery_round_trip():
    calc = TransactionCostCalculator(brokerage_pct=0.03, brokerage_flat=20.0, use_flat_brokerage=False)
    # Buy 100 shares of Reliance at Rs 2800 = Turnover Rs 2,80,000
    # Sell 100 shares of Reliance at Rs 2850 = Turnover Rs 2,85,000
    breakdown = calc.calculate_round_trip_cost(entry_price=2800.0, exit_price=2850.0, quantity=100, product="CNC")

    assert breakdown.turnover == 565000.0
    # Brokerage should be capped at Rs 20 on each leg = Rs 40 total
    assert breakdown.brokerage == 40.0
    # STT delivery: 0.1% on buy (280) + 0.1% on sell (285) = Rs 565.0
    assert breakdown.stt == 565.0
    # Stamp duty: 0.015% on buy leg = 42.0
    assert breakdown.stamp_duty == 42.0
    # Total cost should be positive and realistic
    assert breakdown.total_cost > 600.0
    # Total cost percentage should be around 0.2 - 0.3% of entry turnover
    assert 0.15 <= breakdown.cost_pct <= 0.40


def test_cost_calculator_zero_turnover():
    calc = TransactionCostCalculator()
    breakdown = calc.calculate_round_trip_cost(entry_price=0.0, exit_price=0.0, quantity=0)
    assert breakdown.total_cost == 0.0
    assert breakdown.cost_pct == 0.0


def test_cost_calculator_intraday_vs_delivery():
    calc = TransactionCostCalculator()
    cnc = calc.calculate_round_trip_cost(entry_price=1000.0, exit_price=1020.0, quantity=100, product="CNC")
    intraday = calc.calculate_round_trip_cost(entry_price=1000.0, exit_price=1020.0, quantity=100, product="INTRADAY")

    # STT on intraday (0.025% on sell only) is much lower than CNC (0.1% buy + 0.1% sell)
    assert intraday.stt < cnc.stt
    assert intraday.total_cost < cnc.total_cost
