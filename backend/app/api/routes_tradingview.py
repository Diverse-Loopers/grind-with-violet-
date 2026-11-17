"""
API Routes for Global 24/7 Market (XAU/USD Gold, Forex, Crypto),
TradingView Webhook Integration Gateway, and MAX PROFIT Multi-Strategy Optimization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.global_engine.engine import global_engine
from app.global_engine.models import (
    GlobalAction,
    MaxProfitResult,
    TradingViewAlertPayload,
)
from app.utils.logging import logger

router = APIRouter(tags=["global-tradingview"])


# ── Pydantic Request Schemas ──────────────────────────────────


class ManualOrderRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
    side: str = Field(..., description="BUY or SELL")
    lots: float = Field(default=0.10, ge=0.01, le=10.0)
    sl: Optional[float] = None
    tp: Optional[float] = None


class ClosePositionRequest(BaseModel):
    position_id: str


class StrategyToggleRequest(BaseModel):
    strategy_id: Optional[str] = None
    enabled: Optional[bool] = None
    auto_confluence_trade: Optional[bool] = None
    confluence_threshold: Optional[float] = None
    confluence_lot_size: Optional[float] = None


class TradingViewSettingsRequest(BaseModel):
    passphrase: Optional[str] = None
    auto_trade: Optional[bool] = None
    leverage: Optional[int] = None


class TestAlertRequest(BaseModel):
    ticker: str = "XAUUSD"
    action: str = "BUY"
    price: Optional[float] = None
    quantity: float = 0.10
    strategy: str = "Test TradingView Alert"


# ── Global Market Endpoints ───────────────────────────────────


@router.get("/api/global/overview")
def get_global_overview() -> Dict[str, Any]:
    """Returns real-time 24/7 dashboard overview for XAU/USD and account."""
    quote = global_engine.feed.get_quote("XAUUSD")
    account = global_engine.broker.get_account_summary()
    indicators = global_engine.feed.calculate_indicators("XAUUSD")

    return {
        "market": "24/7 Global Spot & Forex",
        "primary_asset": "XAUUSD (Gold vs US Dollar)",
        "quote": quote.model_dump(),
        "account": account.model_dump(),
        "session": quote.session,
        "is_open_24_7": True,
        "confluence_score": global_engine._confluence_score,
        "market_sentiment": global_engine._market_sentiment,
        "auto_trade_enabled": global_engine.bridge.auto_trade_enabled,
        "auto_confluence_trading": global_engine.auto_confluence_trade,
        "active_signals_count": len(global_engine._active_signals),
        "indicators": indicators,
    }


@router.get("/api/global/quotes")
def get_global_quotes() -> List[Dict[str, Any]]:
    """Returns quotes for all monitored 24/7 assets (Gold, Bitcoin, EUR/USD)."""
    quotes = global_engine.feed.get_all_quotes()
    return [q.model_dump() for q in quotes]


@router.get("/api/global/candles")
def get_global_candles(symbol: str = "XAUUSD", count: int = 100) -> List[Dict[str, Any]]:
    """Returns OHLCV candlesticks for charts."""
    candles = global_engine.feed.get_candles(symbol=symbol, count=count)
    return [c.model_dump() for c in candles]


@router.get("/api/global/positions")
def get_global_positions() -> Dict[str, Any]:
    """Returns currently open and recently closed 24/7 positions."""
    return {
        "open_positions": [p.model_dump() for p in global_engine.broker.get_open_positions()],
        "closed_positions": [p.model_dump() for p in global_engine.broker.get_closed_positions(limit=30)],
    }


@router.post("/api/global/order")
def place_global_order(req: ManualOrderRequest) -> Dict[str, Any]:
    """Manually opens a Long or Short position on Gold or Forex."""
    action = GlobalAction.BUY if req.side.upper() == "BUY" else GlobalAction.SELL
    quote = global_engine.feed.get_quote(req.symbol)

    try:
        pos = global_engine.broker.open_position(
            symbol=req.symbol,
            side=action,
            lots=req.lots,
            quote=quote,
            sl=req.sl,
            tp=req.tp,
            strategy="MANUAL",
        )
        return {"success": True, "position": pos.model_dump(), "message": f"Successfully opened {action.value} order"}
    except Exception as e:
        logger.error(f"Error placing global order: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/global/close-position")
def close_global_position(req: ClosePositionRequest) -> Dict[str, Any]:
    """Closes an active 24/7 position."""
    pos = global_engine.broker.positions.get(req.position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found or already closed")

    quote = global_engine.feed.get_quote(pos.symbol)
    closed = global_engine.broker.close_position(req.position_id, quote.ltp, reason="User Request")
    return {"success": True, "position": closed.model_dump()}


# ── Strategy & Max Profit Endpoints ───────────────────────────


@router.get("/api/global/strategies")
def get_global_strategies() -> Dict[str, Any]:
    """Returns active strategies, signals, and confluence metrics."""
    return {
        "strategies": [
            {
                "id": global_engine.optimizer.strat_trend.id,
                "name": global_engine.optimizer.strat_trend.name,
                "description": "EMA 9/21/50 alignment with ATR trailing stop for riding multi-day Gold trends",
                "enabled": global_engine.optimizer.active_strategies.get(global_engine.optimizer.strat_trend.id, True),
            },
            {
                "id": global_engine.optimizer.strat_breakout.id,
                "name": global_engine.optimizer.strat_breakout.name,
                "description": "Exploits high-volume explosive breakouts out of Asian consolidation when London/NY opens",
                "enabled": global_engine.optimizer.active_strategies.get(global_engine.optimizer.strat_breakout.id, True),
            },
            {
                "id": global_engine.optimizer.strat_mean_reversion.id,
                "name": global_engine.optimizer.strat_mean_reversion.name,
                "description": "Mean reversion scalper catching overbought/oversold exhaustion at Bollinger extremes",
                "enabled": global_engine.optimizer.active_strategies.get(global_engine.optimizer.strat_mean_reversion.id, True),
            },
            {
                "id": "strat_tradingview",
                "name": "TradingView Inbound Webhook Signals",
                "description": "Executes external Pine Script alerts received via Webhook listener",
                "enabled": global_engine.optimizer.active_strategies.get("strat_tradingview", True),
            },
        ],
        "active_signals": [s.model_dump() for s in global_engine._active_signals],
        "confluence_score": global_engine._confluence_score,
        "market_sentiment": global_engine._market_sentiment,
        "auto_confluence_trade": global_engine.auto_confluence_trade,
        "confluence_threshold": global_engine.confluence_threshold,
        "confluence_lot_size": global_engine.confluence_lot_size,
    }


@router.post("/api/global/strategies/toggle")
def toggle_global_strategy(req: StrategyToggleRequest) -> Dict[str, Any]:
    """Enables or disables strategies and configures auto-trading."""
    if req.strategy_id and req.enabled is not None:
        global_engine.optimizer.active_strategies[req.strategy_id] = req.enabled

    if req.auto_confluence_trade is not None:
        global_engine.auto_confluence_trade = req.auto_confluence_trade

    if req.confluence_threshold is not None:
        global_engine.confluence_threshold = req.confluence_threshold

    if req.confluence_lot_size is not None:
        global_engine.confluence_lot_size = req.confluence_lot_size

    return {"success": True, "message": "Strategy settings updated"}


@router.post("/api/global/optimize-max-profit")
def run_max_profit_optimizer() -> Dict[str, Any]:
    """
    Executes the Max Profit Multi-Strategy Optimizer.
    Evaluates historical data across all strategies and finds optimal parameter configuration.
    """
    result = global_engine.optimize()
    return result.model_dump()


# ── TradingView Webhook & Gateway Endpoints ───────────────────


@router.post("/api/tradingview/webhook")
async def receive_tradingview_webhook(
    request: Request,
    x_tradingview_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Public webhook receiver for TradingView alerts.
    Processes JSON alert payloads sent by TradingView Pine Script or manual alerts.
    """
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        success, message, record = global_engine.bridge.verify_and_process_alert(
            body_str, header_token=x_tradingview_token
        )

        if not success:
            raise HTTPException(status_code=401, detail=message)

        return {
            "status": "success",
            "message": message,
            "alert": record.model_dump() if record else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling TradingView webhook: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Webhook processing error: {str(e)}")


@router.get("/api/tradingview/alerts")
def get_tradingview_alerts() -> List[Dict[str, Any]]:
    """Returns recent alerts received through the TradingView webhook."""
    records = global_engine.bridge.get_recent_alerts(limit=40)
    return [r.model_dump() for r in records]


@router.post("/api/tradingview/test-alert")
def send_test_tradingview_alert(req: TestAlertRequest) -> Dict[str, Any]:
    """Simulates an incoming TradingView alert to verify webhook processing."""
    payload = {
        "ticker": req.ticker,
        "action": req.action.lower(),
        "price": req.price,
        "quantity": req.quantity,
        "strategy": req.strategy,
        "passphrase": global_engine.bridge.passphrase,
        "timeframe": "15m",
        "comment": "Interactive Test Trigger from Dashboard UI",
    }
    success, msg, record = global_engine.bridge.verify_and_process_alert(payload)
    return {
        "success": success,
        "message": msg,
        "alert": record.model_dump() if record else None,
    }


@router.get("/api/tradingview/pinescript")
def get_tradingview_pinescript() -> Dict[str, Any]:
    """Generates ready-to-use Pine Script v5 code configured for user's webhook."""
    code = global_engine.bridge.generate_pine_script_code()
    pass_len = len(global_engine.bridge.passphrase)
    masked_pass = f"{global_engine.bridge.passphrase[:3]}***{global_engine.bridge.passphrase[-3:]}" if pass_len > 6 else "***"
    return {
        "pinescript": code,
        "webhook_url": "https://your-public-domain.com/api/tradingview/webhook",
        "webhook_path": "/api/tradingview/webhook",
        "passphrase_configured": True,
        "passphrase_preview": masked_pass,
        "networking_instructions": (
            "TradingView cloud servers (AWS us-east-1: 52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7) "
            "require a public HTTPS endpoint. To expose your local Groww Lab backend securely, use a TLS reverse proxy: "
            "'cloudflared tunnel --url http://localhost:8000' or 'ngrok http 8000', and configure your TradingView alert "
            "webhook URL to 'https://<your-subdomain>/api/tradingview/webhook'. Never expose raw HTTP ports without TLS."
        ),
    }


@router.post("/api/tradingview/settings")
def update_tradingview_settings(req: TradingViewSettingsRequest) -> Dict[str, Any]:
    """Updates TradingView webhook passphrase and leverage settings."""
    if req.passphrase is not None:
        global_engine.bridge.passphrase = req.passphrase.strip()

    if req.auto_trade is not None:
        global_engine.bridge.auto_trade_enabled = req.auto_trade

    if req.leverage is not None and req.leverage >= 1:
        global_engine.broker.leverage = req.leverage

    return {
        "success": True,
        "passphrase": global_engine.bridge.passphrase,
        "auto_trade": global_engine.bridge.auto_trade_enabled,
        "leverage": global_engine.broker.leverage,
    }
