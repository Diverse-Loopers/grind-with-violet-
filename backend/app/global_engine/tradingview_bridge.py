"""
TradingView Webhook Gateway & Pine Script v5 Code Generator.
Receives, verifies, parses, and executes TradingView alerts with:
- Cryptographically secure non-hardcoded secrets from environment
- Timestamp freshness validation (rejects stale alerts > 120s)
- Replay protection & duplicate alert suppression
- Secret passphrase redaction from logs and storage
- Ready-to-use Pine Script v5 code generator
"""

from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.global_engine.broker import GlobalPaperBroker
from app.global_engine.feed import GlobalMarketFeed
from app.global_engine.models import (
    GlobalAction,
    StrategySignal,
    TradingViewAlertPayload,
    TradingViewAlertRecord,
)
from app.utils.logging import logger


class TradingViewBridge:
    """Secure Gateway for incoming TradingView alert webhooks and Pine Script generation."""

    def __init__(self, feed: GlobalMarketFeed, broker: GlobalPaperBroker):
        self.feed = feed
        self.broker = broker
        # Load secret from environment or generate a secure 32-character token (never hardcoded)
        env_secret = os.getenv("TRADINGVIEW_WEBHOOK_SECRET") or os.getenv("GROWW_TRADINGVIEW_SECRET")
        self.passphrase: str = env_secret.strip() if env_secret else secrets.token_hex(16)
        self.auto_trade_enabled: bool = True
        self.alerts_history: List[TradingViewAlertRecord] = []
        self.last_signal: Optional[StrategySignal] = None
        self._seen_signatures: Dict[str, float] = {}  # Signature -> timestamp for replay protection

    def verify_and_process_alert(
        self,
        payload_data: Any,
        header_token: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[TradingViewAlertRecord]]:
        """
        Validates, parses, and executes an incoming TradingView alert.
        Enforces authentication, timestamp freshness, replay protection, and secret redaction.
        """
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        alert_id = f"TV-{uuid.uuid4().hex[:8].upper()}"

        # 1. Parse JSON if string
        if isinstance(payload_data, (str, bytes)):
            try:
                data = json.loads(payload_data)
            except Exception:
                parts = str(payload_data).strip().split()
                if len(parts) >= 2:
                    data = {
                        "action": parts[0],
                        "ticker": parts[1],
                        "quantity": float(parts[2]) if len(parts) > 2 else 0.1,
                    }
                else:
                    return False, "Failed to parse webhook alert payload: invalid JSON", None
        elif isinstance(payload_data, dict):
            data = payload_data.copy()
        else:
            return False, "Invalid payload type", None

        # Redact passphrase in stored/logged payload
        raw_pass = data.get("passphrase", "")
        sanitized_payload = {k: v for k, v in data.items() if k != "passphrase"}
        sanitized_payload["passphrase"] = "[REDACTED]"

        # 2. Authentication check
        provided_pass = raw_pass or header_token or ""
        if self.passphrase and provided_pass != self.passphrase:
            record = TradingViewAlertRecord(
                id=alert_id,
                ticker=str(data.get("ticker", "UNKNOWN")),
                action=str(data.get("action", "UNKNOWN")).upper(),
                price=float(data.get("price", 0.0) or 0.0),
                quantity=float(data.get("quantity", 0.1) or 0.1),
                strategy=str(data.get("strategy", "TradingView Alert")),
                timeframe=str(data.get("timeframe", "15m")),
                status="REJECTED",
                message="Unauthorized: Passphrase mismatch",
                raw_payload=sanitized_payload,
            )
            self.alerts_history.insert(0, record)
            logger.warning(f"[TRADINGVIEW WEBHOOK] Unauthorized alert rejected ({alert_id})")
            return False, "Unauthorized: Passphrase mismatch. Check your TradingView alert webhook settings.", record

        # 3. Timestamp Freshness Check (reject alerts > 120s old or > 30s in future)
        alert_ts_val = data.get("timestamp")
        if alert_ts_val is not None:
            alert_ts = None
            try:
                alert_ts = float(alert_ts_val)
                if alert_ts > 1e11:
                    alert_ts /= 1000.0
            except (ValueError, TypeError):
                try:
                    dt = datetime.fromisoformat(str(alert_ts_val).replace("Z", "+00:00"))
                    alert_ts = dt.timestamp()
                except Exception:
                    pass

            if alert_ts is not None:
                age = now_ts - alert_ts
                if age > 120.0 or age < -30.0:
                    msg = (
                        f"Stale alert rejected: timestamp is {age:.1f}s old (limit 120s)"
                        if age > 120.0
                        else f"Future timestamp rejected: clock skew exceeds 30s limit ({abs(age):.1f}s in future)"
                    )
                    logger.warning(f"[TRADINGVIEW] {msg}")
                    record = TradingViewAlertRecord(
                        id=alert_id,
                        ticker=str(data.get("ticker", "UNKNOWN")),
                        action=str(data.get("action", "UNKNOWN")).upper(),
                        price=float(data.get("price", 0.0) or 0.0),
                        quantity=float(data.get("quantity", 0.1) or 0.1),
                        strategy=str(data.get("strategy", "TradingView Alert")),
                        timeframe=str(data.get("timeframe", "15m")),
                        status="REJECTED",
                        message=msg,
                        raw_payload=sanitized_payload,
                    )
                    self.alerts_history.insert(0, record)
                    return False, msg, record

        # 4. Extract and normalize parameters
        raw_ticker = str(data.get("ticker", "XAUUSD")).upper().replace("/", "")
        ticker = "XAUUSD" if "XAU" in raw_ticker or "GOLD" in raw_ticker else raw_ticker
        raw_action = str(data.get("action", "BUY")).upper()
        if "BUY" in raw_action or "LONG" in raw_action:
            action = GlobalAction.BUY
        elif "SELL" in raw_action or "SHORT" in raw_action:
            action = GlobalAction.SELL
        elif "CLOSE" in raw_action or "EXIT" in raw_action:
            action = GlobalAction.CLOSE
        else:
            action = GlobalAction.BUY

        quote = self.feed.get_quote(ticker)
        price = float(data.get("price") or quote.ltp)
        quantity = float(data.get("quantity") or 0.10)
        tp = float(data.get("tp")) if data.get("tp") else None
        sl = float(data.get("sl")) if data.get("sl") else None
        strategy_name = str(data.get("strategy") or "TradingView Pine Alert")
        timeframe = str(data.get("timeframe") or "15m")

        # 5. Replay Protection & Duplicate Alert Suppression
        custom_ref = str(data.get("alert_id") or data.get("order_id") or "")
        sig = custom_ref if custom_ref else f"{ticker}:{action.value}:{quantity:.2f}:{strategy_name}"

        # Clean expired signatures (>60s old)
        self._seen_signatures = {k: v for k, v in self._seen_signatures.items() if now_ts - v < 60.0}

        if sig in self._seen_signatures:
            last_seen = self._seen_signatures[sig]
            if now_ts - last_seen < 15.0:
                msg = f"Duplicate alert suppressed: Identical signal received {now_ts - last_seen:.1f}s ago (Replay Protection)"
                logger.warning(f"[TRADINGVIEW] {msg}")
                record = TradingViewAlertRecord(
                    id=alert_id,
                    ticker=ticker,
                    action=action.value,
                    price=price,
                    quantity=quantity,
                    strategy=strategy_name,
                    timeframe=timeframe,
                    tp=tp,
                    sl=sl,
                    status="REJECTED",
                    message=msg,
                    raw_payload=sanitized_payload,
                )
                self.alerts_history.insert(0, record)
                return False, msg, record

        self._seen_signatures[sig] = now_ts

        exec_msg = ""
        status = "RECEIVED"

        # 6. Order Routing (Paper mode execution only)
        if action == GlobalAction.CLOSE:
            matching = [p for p in self.broker.get_open_positions() if p.symbol == ticker]
            if matching:
                closed = self.broker.close_position(matching[0].id, price, reason=f"TradingView Exit Signal: {strategy_name}")
                status = "EXECUTED"
                exec_msg = f"Closed position {closed.id} at ${price:.2f}"
            else:
                status = "IGNORED"
                exec_msg = f"No open position found to close for {ticker}"

        elif self.auto_trade_enabled:
            try:
                pos = self.broker.open_position(
                    symbol=ticker,
                    side=action,
                    lots=quantity,
                    quote=quote,
                    sl=sl,
                    tp=tp,
                    strategy=f"TV: {strategy_name}",
                )
                status = "EXECUTED"
                exec_msg = f"Executed {action.value} {quantity} lots @ ${pos.entry_price} (Pos #{pos.id})"

                # Register as latest signal
                self.last_signal = StrategySignal(
                    strategy_id="strat_tradingview",
                    strategy_name=strategy_name,
                    symbol=ticker,
                    action=action,
                    confidence=0.88,
                    price=price,
                    sl=sl or (price - 4.0 if action == GlobalAction.BUY else price + 4.0),
                    tp=tp or (price + 8.0 if action == GlobalAction.BUY else price - 8.0),
                    risk_reward=2.0,
                    reason=f"TradingView webhook signal: {strategy_name} on {timeframe}",
                )
            except Exception as e:
                status = "ERROR"
                exec_msg = f"Execution error: {str(e)}"
                logger.error(f"TradingView execution error: {e}", exc_info=True)
        else:
            status = "PENDING"
            exec_msg = "Alert logged (Auto-trade disabled)"

        record = TradingViewAlertRecord(
            id=alert_id,
            ticker=ticker,
            action=action.value,
            price=price,
            quantity=quantity,
            strategy=strategy_name,
            timeframe=timeframe,
            tp=tp,
            sl=sl,
            status=status,
            message=exec_msg,
            raw_payload=sanitized_payload,
        )
        self.alerts_history.insert(0, record)
        if len(self.alerts_history) > 100:
            self.alerts_history.pop()

        return True, exec_msg, record

    def get_recent_alerts(self, limit: int = 50) -> List[TradingViewAlertRecord]:
        return self.alerts_history[:limit]

    def generate_pine_script_code(self) -> str:
        """
        Returns ready-to-paste TradingView Pine Script v5 code designed specifically
        for 24/7 XAU/USD Gold and automated Webhook alert delivery.
        """
        code = '''//@version=5
strategy("XAUUSD 24/7 Max Profit Algo - Groww Lab", overlay=true, initial_capital=10000, default_qty_type=strategy.cash, default_qty_value=1000)

// ── 1. Strategy Parameters ────────────────────────────────────
fastLength = input.int(9, "Fast EMA", minval=1)
mediumLength = input.int(21, "Medium EMA", minval=1)
slowLength = input.int(50, "Slow EMA", minval=1)
atrPeriod = input.int(14, "ATR Period", minval=1)
atrMultiplier = input.float(2.0, "ATR Stop Multiplier", step=0.1)
takeProfitMultiplier = input.float(3.0, "ATR Take Profit Multiplier", step=0.1)
passphrase = input.string("''' + self.passphrase + '''", "TradingView Webhook Passphrase")

// ── 2. Indicators Calculation ─────────────────────────────────
emaFast = ta.ema(close, fastLength)
emaMedium = ta.ema(close, mediumLength)
emaSlow = ta.ema(close, slowLength)
atrVal = ta.atr(atrPeriod)

// Plot EMAs
plot(emaFast, color=color.new(color.teal, 0), title="EMA 9 (Fast)", linewidth=1)
plot(emaMedium, color=color.new(color.amber, 0), title="EMA 21 (Medium)", linewidth=2)
plot(emaSlow, color=color.new(color.purple, 0), title="EMA 50 (Slow)", linewidth=2)

// ── 3. Strategy Logic (Trend Alignment + Pullback) ─────────────
bullishTrend = (emaFast > emaMedium) and (emaMedium > emaSlow)
bearishTrend = (emaFast < emaMedium) and (emaMedium < emaSlow)

longCondition = bullishTrend and ta.crossover(close, emaFast)
shortCondition = bearishTrend and ta.crossunder(close, emaFast)

// ── 4. Risk & Target Prices ───────────────────────────────────
longStopLoss = close - (atrVal * atrMultiplier)
longTakeProfit = close + (atrVal * takeProfitMultiplier)

shortStopLoss = close + (atrVal * atrMultiplier)
shortTakeProfit = close - (atrVal * takeProfitMultiplier)

// ── 5. Webhook Alert Payloads (Standard JSON) ──────────────────
longAlertJson = str.format('{{\\n  "ticker": "{0}",\\n  "action": "buy",\\n  "price": {1,number,0.00},\\n  "quantity": 0.10,\\n  "strategy": "TV Gold MaxProfit EMA",\\n  "tp": {2,number,0.00},\\n  "sl": {3,number,0.00},\\n  "passphrase": "{4}",\\n  "timestamp": {5,number,0}\\n}}', syminfo.ticker, close, longTakeProfit, longStopLoss, passphrase, timenow)

shortAlertJson = str.format('{{\\n  "ticker": "{0}",\\n  "action": "sell",\\n  "price": {1,number,0.00},\\n  "quantity": 0.10,\\n  "strategy": "TV Gold MaxProfit EMA",\\n  "tp": {2,number,0.00},\\n  "sl": {3,number,0.00},\\n  "passphrase": "{4}",\\n  "timestamp": {5,number,0}\\n}}', syminfo.ticker, close, shortTakeProfit, shortStopLoss, passphrase, timenow)

// ── 6. Order Placement & Alert Triggers ────────────────────────
if (longCondition)
    strategy.entry("Long", strategy.long)
    strategy.exit("TP/SL Long", "Long", stop=longStopLoss, limit=longTakeProfit)
    alert(longAlertJson, alert.freq_once_per_bar_close)

if (shortCondition)
    strategy.entry("Short", strategy.short)
    strategy.exit("TP/SL Short", "Short", stop=shortStopLoss, limit=shortTakeProfit)
    alert(shortAlertJson, alert.freq_once_per_bar_close)
'''
        return code
