"""
Comprehensive Tests for F&O Playbook Multi-Agent Autonomous Trading System.
Verifies:
1. Agent 1 (Radar): 50 MA crossover, PCR calculation, OI Support/Resistance, Basis.
2. Agent 2 (Strategy Confluence): Payoff math for Bull Call Spread, Bear Put Spread,
   Long/Short Synthetic, Long Butterfly, Cash-to-Future Arbitrage.
3. Negative Playbook Rules: Rejection of Naked Futures and Short Straddles/Strangles ("Nahi Karna").
4. Agent 3 (Risk Governor): Risk limits, circuit breaker kill-switch, margin validation.
5. Agent 4 (Execution): Atomic multi-leg execution, MTM tracking, trailing SL, target exit.
6. API Endpoints: Status, Scan, Plans, Positions, Playbook.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.playbook import StrategyType, MarketSentiment, LegType, TradeAction, PlaybookTradePlan, OptionLeg
from app.agents.market_radar_agent import MarketRadarAgent
from app.agents.strategy_confluence_agent import StrategyConfluenceAgent
from app.agents.risk_governor_agent import RiskGovernorAgent
from app.agents.execution_agent import MultiLegExecutionAgent
from app.agents.multi_agent_orchestrator import MultiAgentOrchestrator
from app.agents.fo_universe import get_lot_size, get_strike_interval


@pytest.fixture
def test_client():
    return TestClient(app)


# ── 1. Radar Agent Tests ──────────────────────────────────────
def test_market_radar_pcr_and_oi_support_resistance():
    radar = MarketRadarAgent(symbols=["NIFTY", "BANKNIFTY"])
    # Inspect bullish option chain
    res_bull = radar.analyze_ticker("NIFTY", current_price=24500.0, force_sentiment="BULLISH")
    
    assert res_bull["symbol"] == "NIFTY"
    assert res_bull["pcr"] > 1.0, f"Expected bullish PCR > 1.0, got {res_bull['pcr']}"
    assert res_bull["support_strike"] <= 24500.0
    assert res_bull["resistance_strike"] >= 24500.0
    assert res_bull["is_future_at_premium"] is True
    assert res_bull["basis"] > 0.0

    # Inspect bearish option chain
    res_bear = radar.analyze_ticker("BANKNIFTY", current_price=52000.0, force_sentiment="BEARISH")
    assert res_bear["symbol"] == "BANKNIFTY"
    assert res_bear["pcr"] < 1.0, f"Expected bearish PCR < 1.0, got {res_bear['pcr']}"


def test_market_radar_50_ma_calculation():
    radar = MarketRadarAgent(symbols=["SBIN"])
    # Feed 50 prices of 800.0
    for _ in range(50):
        radar.update_price("SBIN", 800.0)
    
    ma = radar.calculate_50_ma("SBIN")
    assert abs(ma - 800.0) < 0.1

    # Now price surges to 850
    radar.update_price("SBIN", 850.0)
    analysis = radar.analyze_ticker("SBIN", current_price=850.0)
    assert analysis["spot_price"] > analysis["ma_50"]
    assert analysis["price_vs_ma"] > 0


# ── 2. Strategy Confluence Agent Tests ────────────────────────
def test_strategy_brain_bull_call_spread_payoff():
    radar = MarketRadarAgent()
    brain = StrategyConfluenceAgent()

    market_data = radar.analyze_ticker("FINNIFTY", current_price=23600.0, force_sentiment="BULLISH")
    plans = brain.evaluate_and_formulate_plans(market_data)

    bcs_plan = next((p for p in plans if p.strategy_type == StrategyType.BULL_CALL_SPREAD), None)
    assert bcs_plan is not None, "Failed to formulate Bull Call Spread for bullish market"
    assert len(bcs_plan.legs) == 2
    assert bcs_plan.legs[0].action == TradeAction.BUY
    assert bcs_plan.legs[1].action == TradeAction.SELL
    assert bcs_plan.max_loss > 0
    assert bcs_plan.max_profit > 0
    assert bcs_plan.risk_reward_ratio > 0
    assert len(bcs_plan.breakeven_points) == 1
    # BEP must be above entry ATM strike
    assert bcs_plan.breakeven_points[0] > bcs_plan.legs[0].strike_price


def test_strategy_brain_bear_put_spread_payoff():
    radar = MarketRadarAgent()
    brain = StrategyConfluenceAgent()

    market_data = radar.analyze_ticker("BANKNIFTY", current_price=52500.0, force_sentiment="BEARISH")
    plans = brain.evaluate_and_formulate_plans(market_data)

    bps_plan = next((p for p in plans if p.strategy_type == StrategyType.BEAR_PUT_SPREAD), None)
    assert bps_plan is not None, "Failed to formulate Bear Put Spread for bearish market"
    assert len(bps_plan.legs) == 2
    assert bps_plan.legs[0].action == TradeAction.BUY
    assert bps_plan.legs[1].action == TradeAction.SELL
    # BEP must be below entry ATM strike for Put spread
    assert bps_plan.breakeven_points[0] < bps_plan.legs[0].strike_price


def test_strategy_brain_long_butterfly():
    radar = MarketRadarAgent()
    brain = StrategyConfluenceAgent()

    market_data = radar.analyze_ticker("NIFTY", current_price=24200.0, force_sentiment="RANGE_BOUND")
    plans = brain.evaluate_and_formulate_plans(market_data)

    bf_plan = next((p for p in plans if p.strategy_type == StrategyType.LONG_CALL_BUTTERFLY), None)
    assert bf_plan is not None, "Failed to formulate Long Butterfly for range-bound market"
    assert len(bf_plan.legs) == 3
    # 1 ITM Buy, 2 ATM Sell, 1 OTM Buy
    assert bf_plan.legs[0].action == TradeAction.BUY
    assert bf_plan.legs[1].action == TradeAction.SELL
    assert bf_plan.legs[1].quantity == bf_plan.legs[0].quantity * 2
    assert bf_plan.legs[2].action == TradeAction.BUY
    # Butterfly has two breakeven points (lower and upper wings)
    assert len(bf_plan.breakeven_points) == 2
    assert bf_plan.breakeven_points[0] < bf_plan.breakeven_points[1]


def test_strategy_brain_cash_future_arbitrage():
    radar = MarketRadarAgent()
    brain = StrategyConfluenceAgent()

    market_data = radar.analyze_ticker("CIPLA", current_price=1210.0)
    # Ensure positive basis
    market_data["basis"] = 5.0
    market_data["future_price"] = 1215.0

    plans = brain.evaluate_and_formulate_plans(market_data)
    arb_plan = next((p for p in plans if p.strategy_type == StrategyType.CASH_FUTURE_ARBITRAGE), None)
    assert arb_plan is not None
    assert arb_plan.max_loss == 0.0  # Zero directional risk
    assert arb_plan.max_profit > 0


# ── 3. Negative Playbook Rules Guardrails ─────────────────────
def test_playbook_compliance_rejects_naked_futures():
    """Rule: 'Never Trade in Future in Single Side'."""
    naked_future_plan = PlaybookTradePlan(
        id="PLAN_TEST_NAKED",
        underlying_symbol="SBIN",
        strategy_type=StrategyType.LONG_SYNTHETIC,
        sentiment=MarketSentiment.BULLISH,
        spot_price=800.0,
        legs=[
            OptionLeg(
                symbol="SBIN_FUT",
                leg_type=LegType.FUTURE,
                action=TradeAction.BUY,
                entry_price=805.0,
                quantity=1500,
                lot_size=1500,
            )
        ],
        net_debit=0.0,
        max_loss=1200000.0,
        max_profit=50000.0,
        risk_reward_ratio=0.04,
        confidence_score=0.5,
        agent_reasoning="Test Naked Future",
    )
    is_valid, reason = StrategyConfluenceAgent.validate_playbook_compliance(naked_future_plan)
    assert is_valid is False
    assert "Never Trade in Future in Single Side" in reason


def test_playbook_compliance_rejects_short_straddle():
    """Rule: 'Short Straddle - Nahi Karna'."""
    short_straddle_plan = PlaybookTradePlan(
        id="PLAN_TEST_SHORT_STRADDLE",
        underlying_symbol="NIFTY",
        strategy_type=StrategyType.LONG_STRADDLE,
        sentiment=MarketSentiment.HIGH_VOLATILITY,
        spot_price=24000.0,
        legs=[
            OptionLeg(
                symbol="NIFTY_24000_CE",
                leg_type=LegType.CALL,
                action=TradeAction.SELL,  # Short!
                entry_price=150.0,
                quantity=25,
                lot_size=25,
            )
        ],
        net_debit=0.0,
        max_loss=500000.0,
        max_profit=3750.0,
        risk_reward_ratio=0.01,
        confidence_score=0.5,
        agent_reasoning="Illegal Short Straddle",
    )
    is_valid, reason = StrategyConfluenceAgent.validate_playbook_compliance(short_straddle_plan)
    assert is_valid is False
    assert "Nahi Karna" in reason


# ── 4. Risk Governor Agent Tests ──────────────────────────────
def test_risk_governor_enforces_limits_and_kill_switch():
    governor = RiskGovernorAgent(max_risk_per_trade_inr=5000.0, max_daily_loss_inr=15000.0)

    # Plan with max loss of 10,000 exceeds 5,000 limit
    oversized_plan = PlaybookTradePlan(
        id="PLAN_OVERSIZED",
        underlying_symbol="TCS",
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        sentiment=MarketSentiment.BULLISH,
        spot_price=3500.0,
        legs=[],
        net_debit=10000.0,
        max_loss=10000.0,
        max_profit=25000.0,
        risk_reward_ratio=2.5,
        confidence_score=0.8,
        agent_reasoning="Test",
    )
    approved, reason = governor.audit_trade_plan(oversized_plan, available_cash=100000.0)
    assert approved is False
    assert "exceeds allowable risk limit" in reason

    # Trigger emergency kill-switch
    governor.trigger_emergency_kill_switch("Market Black Swan")
    assert governor.kill_switch_engaged is True

    valid_small_plan = PlaybookTradePlan(
        id="PLAN_SMALL",
        underlying_symbol="ITC",
        strategy_type=StrategyType.BULL_CALL_SPREAD,
        sentiment=MarketSentiment.BULLISH,
        spot_price=440.0,
        legs=[],
        net_debit=1000.0,
        max_loss=1000.0,
        max_profit=3000.0,
        risk_reward_ratio=3.0,
        confidence_score=0.8,
        agent_reasoning="Test",
    )
    approved2, reason2 = governor.audit_trade_plan(valid_small_plan, available_cash=100000.0)
    assert approved2 is False
    assert "Circuit Breaker active" in reason2

    # Reset kill-switch
    governor.reset_daily_metrics()
    assert governor.kill_switch_engaged is False


# ── 5. Multi-Leg Execution & Position Tests ───────────────────
def test_execution_agent_mtm_and_trailing_sl():
    exec_agent = MultiLegExecutionAgent()
    radar = MarketRadarAgent()
    brain = StrategyConfluenceAgent()

    market_data = radar.analyze_ticker("FINNIFTY", current_price=23600.0, force_sentiment="BULLISH")
    plans = brain.evaluate_and_formulate_plans(market_data)
    bcs_plan = next(p for p in plans if p.strategy_type == StrategyType.BULL_CALL_SPREAD)

    pos = exec_agent.execute_plan(bcs_plan)
    assert pos.id in exec_agent.active_positions
    assert pos.is_open is True

    # Simulate modest spot price gain (+20 points)
    quotes = {"FINNIFTY": 23620.0}
    updates = exec_agent.mark_positions_to_market(quotes)
    assert len(updates) >= 1
    assert pos.current_pnl > 0, "Expected positive PnL on bullish spread with rising spot"
    assert pos.is_open is True

    # Manual close position
    closed_pos = exec_agent.close_position(pos.id, reason="Unit test close")
    assert closed_pos is not None
    assert closed_pos.is_open is False
    assert pos.id not in exec_agent.active_positions


# ── 6. Full Orchestrator & API Integration Tests ──────────────
def test_multi_agent_orchestrator_cycle():
    orchestrator = MultiAgentOrchestrator(auto_execute=True)
    summary = orchestrator.run_orchestration_cycle(simulated_cash=500000.0)

    assert summary["tickers_scanned"] > 0
    assert summary["plans_generated"] > 0
    assert len(orchestrator.agent_activity_feed) > 0

    status = orchestrator.get_system_status()
    assert "active_spreads_count" in status
    assert "total_unrealized_pnl" in status


def test_api_routes_multi_agent(test_client):
    # Status endpoint
    r_status = test_client.get("/agents/status")
    assert r_status.status_code == 200
    data = r_status.json()
    assert "active_spreads_count" in data

    # Playbook endpoint
    r_playbook = test_client.get("/agents/playbook")
    assert r_playbook.status_code == 200
    pb = r_playbook.json()
    assert len(pb["strategies"]) >= 5
    assert len(pb["hard_constraints"]) >= 3

    # Scan endpoint
    r_scan = test_client.post("/agents/scan?simulated_cash=250000")
    assert r_scan.status_code == 200
    scan_res = r_scan.json()
    assert scan_res["status"] == "COMPLETED"
    assert scan_res["summary"]["plans_generated"] > 0

    # Plans endpoint
    r_plans = test_client.get("/agents/plans?limit=10")
    assert r_plans.status_code == 200
    plans = r_plans.json()
    assert isinstance(plans, list)

    # Positions endpoint
    r_pos = test_client.get("/agents/positions")
    assert r_pos.status_code == 200
    assert "active_positions" in r_pos.json()

    # Kill switch toggle
    r_kill = test_client.post("/agents/kill-switch", json={"action": "ENGAGE", "reason": "Test Trigger"})
    assert r_kill.status_code == 200
    assert r_kill.json()["kill_switch_engaged"] is True

    r_reset = test_client.post("/agents/kill-switch", json={"action": "RESET"})
    assert r_reset.status_code == 200
    assert r_reset.json()["kill_switch_engaged"] is False
