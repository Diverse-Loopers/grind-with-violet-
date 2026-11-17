"""
Unit tests for 24/7 Global Engine, XAU/USD Feed, and Paper Broker.
"""

import pytest
from app.global_engine.broker import GlobalPaperBroker
from app.global_engine.feed import GlobalMarketFeed
from app.global_engine.models import GlobalAction, GlobalQuote


def test_global_market_feed_quotes():
    feed = GlobalMarketFeed()
    quote = feed.get_quote("XAUUSD")
    assert quote.symbol == "XAUUSD"
    assert quote.bid > 0
    assert quote.ask > quote.bid
    assert quote.spread > 0
    assert quote.is_open_24_7 is True


def test_global_market_feed_indicators():
    feed = GlobalMarketFeed()
    indicators = feed.calculate_indicators("XAUUSD")
    assert "ema9" in indicators
    assert "ema21" in indicators
    assert "rsi14" in indicators
    assert "bb_upper" in indicators
    assert "bb_lower" in indicators
    assert indicators["bb_upper"] >= indicators["bb_lower"]
    assert 0 <= indicators["rsi14"] <= 100


def test_global_paper_broker_margin_and_positions():
    broker = GlobalPaperBroker(starting_balance=10_000.0, leverage=50)
    quote = GlobalQuote(
        symbol="XAUUSD",
        name="Gold Spot",
        bid=2749.80,
        ask=2750.10,
        ltp=2750.00,
        spread=0.30,
        spread_pips=3.0,
        high_24h=2760.0,
        low_24h=2740.0,
        open_24h=2745.0,
    )

    # Open Long 0.10 lot
    # 0.10 lot * 100 oz = 10 oz. Price ~2750. Notional = $27,500.
    # At 1:50 leverage, margin = $550.
    pos = broker.open_position("XAUUSD", GlobalAction.BUY, lots=0.10, quote=quote, sl=2740.0, tp=2770.0)
    assert pos.status == "OPEN"
    assert pos.lots == 0.10
    assert pos.margin_used > 500.0

    account = broker.get_account_summary()
    assert account.margin_used == pos.margin_used
    assert account.free_margin < account.equity

    # Simulate price rise to $2760.00
    higher_quote = GlobalQuote(
        symbol="XAUUSD",
        name="Gold Spot",
        bid=2759.80,
        ask=2760.10,
        ltp=2760.00,
        spread=0.30,
        spread_pips=3.0,
        high_24h=2765.0,
        low_24h=2740.0,
        open_24h=2745.0,
    )
    broker.update_positions_on_tick(higher_quote)
    assert pos.unrealized_pnl > 0
    assert pos.pip_gain > 0

    # Close position manually
    closed = broker.close_position(pos.id, current_price=2760.0, reason="Test Close")
    assert closed.status == "CLOSED"
    assert closed.realized_pnl > 0
    assert len(broker.get_open_positions()) == 0


def test_global_paper_broker_auto_tp_sl():
    broker = GlobalPaperBroker(starting_balance=10_000.0, leverage=50)
    quote = GlobalQuote(
        symbol="XAUUSD",
        name="Gold Spot",
        bid=2750.0,
        ask=2750.3,
        ltp=2750.1,
        spread=0.3,
        spread_pips=3.0,
        high_24h=2755.0,
        low_24h=2745.0,
        open_24h=2748.0,
    )

    # Buy with TP at 2760.0
    pos = broker.open_position("XAUUSD", GlobalAction.BUY, lots=0.10, quote=quote, tp=2760.0, sl=2740.0)

    # Tick at 2765.0 (crosses TP)
    tp_quote = GlobalQuote(
        symbol="XAUUSD",
        name="Gold Spot",
        bid=2762.0,
        ask=2762.3,
        ltp=2762.0,
        spread=0.3,
        spread_pips=3.0,
        high_24h=2765.0,
        low_24h=2745.0,
        open_24h=2748.0,
    )
    closed_list = broker.update_positions_on_tick(tp_quote)
    assert len(closed_list) == 1
    assert closed_list[0].close_reason == "Take Profit Hit (TP)"
    assert closed_list[0].realized_pnl > 0
