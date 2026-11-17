"""
API route integration tests for 24/7 Global Engine and TradingView Webhook endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.global_engine.engine import global_engine

client = TestClient(app)


def test_api_global_overview():
    res = client.get("/api/global/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["market"] == "24/7 Global Spot & Forex"
    assert "quote" in data
    assert "account" in data
    assert data["quote"]["symbol"] == "XAUUSD"


def test_api_global_quotes():
    res = client.get("/api/global/quotes")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 3
    symbols = [q["symbol"] for q in data]
    assert "XAUUSD" in symbols
    assert "BTCUSD" in symbols


def test_api_global_order_and_positions():
    from app.global_engine.engine import global_engine
    global_engine.broker.positions.clear()
    global_engine.broker.balance = 10000.0

    # Place Long order
    order_res = client.post(
        "/api/global/order",
        json={"symbol": "XAUUSD", "side": "BUY", "lots": 0.10, "sl": 2730.0, "tp": 2770.0},
    )
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["success"] is True
    pos_id = order_data["position"]["id"]

    # Check positions
    pos_res = client.get("/api/global/positions")
    assert pos_res.status_code == 200
    pos_data = pos_res.json()
    open_ids = [p["id"] for p in pos_data["open_positions"]]
    assert pos_id in open_ids

    # Close position
    close_res = client.post("/api/global/close-position", json={"position_id": pos_id})
    assert close_res.status_code == 200
    assert close_res.json()["success"] is True


def test_api_tradingview_webhook_and_pinescript():
    # Fetch Pine Script
    ps_res = client.get("/api/tradingview/pinescript")
    assert ps_res.status_code == 200
    assert "//@version=5" in ps_res.json()["pinescript"]

    # Send valid webhook alert
    wh_payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "quantity": 0.10,
        "strategy": "TV Webhook Test",
        "passphrase": global_engine.bridge.passphrase,
    }
    wh_res = client.post("/api/tradingview/webhook", json=wh_payload)
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "success"

    # Query alert logs
    alerts_res = client.get("/api/tradingview/alerts")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) > 0


def test_api_max_profit_optimizer():
    res = client.post("/api/global/optimize-max-profit")
    assert res.status_code == 200
    data = res.json()
    assert "best_strategy" in data
    assert "max_profit" in data
    assert len(data["strategies_compared"]) >= 3


def test_api_stock_candles_and_trades():
    res = client.get("/api/scanner/candles/RELIANCE?count=40")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "RELIANCE"
    assert len(data["candles"]) > 0
    c0 = data["candles"][0]
    assert "open" in c0 and "high" in c0 and "low" in c0 and "close" in c0


def test_api_wallet_and_demo_trade():
    # Test wallet endpoint
    w_res = client.get("/api/portfolio/wallet")
    assert w_res.status_code == 200
    w_data = w_res.json()
    assert "cash_balance" in w_data
    assert "total_equity" in w_data
    assert w_data["currency"] == "INR"

    # Trigger instant demo trade
    t_res = client.post("/api/dashboard/trigger-demo-trade?symbol=INFY&side=BUY")
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert "symbol" in t_data
    assert t_data["symbol"] == "INFY"

    # Check activity feed
    feed_res = client.get("/api/dashboard/activity-feed")
    assert feed_res.status_code == 200
    feed_data = feed_res.json()
    assert feed_data["count"] > 0

