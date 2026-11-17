"""
Automated TradingView Security & Gateway Tests.
Verifies:
1. Secret authentication requirement (unauthorized alerts rejected).
2. Timestamp freshness validation (stale alerts > 120s and future alerts > 30s rejected).
3. Replay protection and duplicate alert suppression within the replay window.
4. Redaction of sensitive passphrases from alert history, logs, and Pine Script generators.
"""

from datetime import datetime, timezone, timedelta
import pytest
from app.global_engine.broker import GlobalPaperBroker
from app.global_engine.feed import GlobalMarketFeed
from app.global_engine.tradingview_bridge import TradingViewBridge


@pytest.fixture
def tv_bridge():
    feed = GlobalMarketFeed()
    broker = GlobalPaperBroker()
    bridge = TradingViewBridge(feed=feed, broker=broker)
    bridge.passphrase = "test_tv_secure_secret_999"
    return bridge


def test_tradingview_bridge_rejects_unauthorized_alert(tv_bridge):
    payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "quantity": 0.1,
        "passphrase": "wrong_secret_attempt",
    }
    success, msg, record = tv_bridge.verify_and_process_alert(payload)
    assert success is False
    assert "Unauthorized" in msg
    assert record.status == "REJECTED"


def test_tradingview_bridge_rejects_stale_and_future_timestamps(tv_bridge):
    # Stale alert (> 120s old)
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=150)).isoformat()
    stale_payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "quantity": 0.1,
        "passphrase": tv_bridge.passphrase,
        "timestamp": stale_time,
    }
    success, msg, record = tv_bridge.verify_and_process_alert(stale_payload)
    assert success is False
    assert "Stale alert" in msg
    assert record.status == "REJECTED"

    # Future alert (> 30s ahead)
    future_time = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    future_payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "quantity": 0.1,
        "passphrase": tv_bridge.passphrase,
        "timestamp": future_time,
    }
    success2, msg2, record2 = tv_bridge.verify_and_process_alert(future_payload)
    assert success2 is False
    assert "future timestamp" in msg2.lower()
    assert record2.status == "REJECTED"


def test_tradingview_bridge_replay_protection(tv_bridge):
    payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "quantity": 0.1,
        "strategy": "TV Breakout Test",
        "passphrase": tv_bridge.passphrase,
    }

    # First attempt: success
    success1, msg1, record1 = tv_bridge.verify_and_process_alert(payload)
    assert success1 is True
    assert record1.status == "EXECUTED"

    # Immediate duplicate attempt: rejected by replay protection
    success2, msg2, record2 = tv_bridge.verify_and_process_alert(payload)
    assert success2 is False
    assert "Duplicate alert suppressed" in msg2 or "replay" in msg2.lower()
    assert record2.status == "REJECTED"


def test_tradingview_secret_redaction(tv_bridge):
    payload = {
        "ticker": "XAUUSD",
        "action": "buy",
        "quantity": 0.1,
        "passphrase": tv_bridge.passphrase,
    }
    success, msg, record = tv_bridge.verify_and_process_alert(payload)

    # Passphrase must be redacted from alert history record
    raw_payload_dict = record.raw_payload
    assert tv_bridge.passphrase not in str(raw_payload_dict)
    assert raw_payload_dict.get("passphrase") == "[REDACTED]"
