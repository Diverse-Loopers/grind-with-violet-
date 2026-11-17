"""
Unit tests for TradingView Webhook Bridge & Max Profit Optimizer.
"""

from app.global_engine.broker import GlobalPaperBroker
from app.global_engine.feed import GlobalMarketFeed
from app.global_engine.tradingview_bridge import TradingViewBridge
from app.global_engine.strategies.max_profit_optimizer import MaxProfitOptimizer


def test_tradingview_bridge_auth_failure():
    feed = GlobalMarketFeed()
    broker = GlobalPaperBroker()
    bridge = TradingViewBridge(feed, broker)
    bridge.passphrase = "super_secret_123"

    payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "quantity": 0.1,
        "passphrase": "wrong_password",
    }
    success, msg, record = bridge.verify_and_process_alert(payload)
    assert success is False
    assert "Unauthorized" in msg
    assert record.status == "REJECTED"


def test_tradingview_bridge_execution_and_exit():
    feed = GlobalMarketFeed()
    broker = GlobalPaperBroker()
    bridge = TradingViewBridge(feed, broker)
    bridge.passphrase = "secret_pass"

    # Ingest BUY alert
    buy_payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "price": 2750.0,
        "quantity": 0.1,
        "strategy": "TV EMA Trend",
        "passphrase": "secret_pass",
    }
    success, msg, record = bridge.verify_and_process_alert(buy_payload)
    assert success is True
    assert record.status == "EXECUTED"
    assert len(broker.get_open_positions()) == 1

    # Ingest CLOSE alert
    close_payload = {
        "ticker": "XAUUSD",
        "action": "close",
        "strategy": "TV EMA Trend Exit",
        "passphrase": "secret_pass",
    }
    success2, msg2, record2 = bridge.verify_and_process_alert(close_payload)
    assert success2 is True
    assert record2.status == "EXECUTED"
    assert len(broker.get_open_positions()) == 0


def test_tradingview_pinescript_generation():
    feed = GlobalMarketFeed()
    broker = GlobalPaperBroker()
    bridge = TradingViewBridge(feed, broker)
    code = bridge.generate_pine_script_code()
    assert "//@version=5" in code
    assert "strategy(" in code
    assert "ta.ema" in code
    assert "alert(" in code


def test_max_profit_optimizer():
    feed = GlobalMarketFeed()
    candles = feed.get_candles("XAUUSD", count=60)
    optimizer = MaxProfitOptimizer()
    result = optimizer.optimize_for_max_profit(candles, starting_capital=10_000.0, lot_size=0.10)

    assert result.max_profit != 0
    assert len(result.strategies_compared) >= 3
    assert result.best_strategy != ""
    assert result.recommendation_summary != ""
