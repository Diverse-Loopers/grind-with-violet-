"""
CoinDCX API Routes for Market Data, Cross-Market Arbitrage Scanner, and Paper Trading Broker.
Provides public market data (tickers, orderbook, candles, market rules),
cross-exchange arbitrage opportunities with fee & TDS calculations,
and simulated paper trading with SQLite persistence.
Live trading is permanently disabled.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.adapters.coindcx_adapter import CoinDCXAdapter
from app.coindcx.models import (
    ArbitrageOpportunity,
    CoinDCXCandle,
    CoinDCXOrderBook,
    CoinDCXPaperOrderRequest,
    CoinDCXTicker,
    MarketDetail,
)
from app.coindcx.paper_broker import CoinDCXPaperBroker
from app.coindcx.scanner import CoinDCXScanner
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/coindcx", tags=["coindcx"])

# Engine Singletons
coindcx_adapter = CoinDCXAdapter()
coindcx_scanner = CoinDCXScanner(coindcx_adapter)
coindcx_broker = CoinDCXPaperBroker(coindcx_adapter)


# ── Request Models ────────────────────────────────────────────


class ResetWalletRequest(BaseModel):
    starting_inr: float = Field(default=1_000_000.0, ge=100.0, le=100_000_000.0)
    starting_usdt: float = Field(default=10_000.0, ge=10.0, le=1_000_000.0)


# ── Status & Info Endpoints ───────────────────────────────────


@router.get("/status")
def get_coindcx_status() -> Dict[str, Any]:
    """Returns CoinDCX adapter status, market count, and safety controls."""
    markets = coindcx_adapter.get_markets_details()
    tickers = coindcx_adapter.get_all_tickers()
    return {
        "status": "online" if markets else "degraded",
        "live_trading_enabled": False,
        "mode": "PAPER",
        "safety_guarantee": "STRICT PAPER ONLY - Live order submission is permanently disabled.",
        "active_markets_count": len(markets),
        "cached_tickers_count": len(tickers),
        "stale_threshold_seconds": coindcx_adapter.stale_threshold_seconds,
        "supported_candle_intervals": ["1m", "15m", "1h", "1d"],
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/markets")
def get_markets(
    search: Optional[str] = Query(None, description="Search market name or symbol"),
    base_currency: Optional[str] = Query(None, description="Filter by base currency e.g. INR or USDT"),
    limit: int = Query(50, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """Returns active CoinDCX markets with order constraints, precision, and step sizes."""
    markets = coindcx_adapter.get_markets_details()
    result = []
    search_lower = search.lower().strip() if search else None
    base_upper = base_currency.upper().strip() if base_currency else None

    for m in markets.values():
        if base_upper and m.base_currency_short_name.upper() != base_upper:
            continue
        if search_lower:
            match = (
                search_lower in m.coindcx_name.lower()
                or search_lower in m.target_currency_short_name.lower()
                or search_lower in m.target_currency_name.lower()
            )
            if not match:
                continue

        result.append(m.model_dump())
        if len(result) >= limit:
            break

    return result


@router.get("/markets/{market}")
def get_single_market(market: str) -> Dict[str, Any]:
    """Returns detailed constraints and step size for a single market (e.g. BTCINR, BTCUSDT)."""
    detail = coindcx_adapter.get_market_detail(market)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Market {market} not found on CoinDCX.")
    return detail.model_dump()


# ── Market Data: Tickers, Depth & Candles ──────────────────────


@router.get("/tickers")
def get_tickers(
    base_currency: Optional[str] = Query(None, description="Filter by base currency e.g. INR or USDT"),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Returns live tickers with spread, 24h change, freshness, and staleness flag."""
    tickers = coindcx_adapter.get_all_tickers()
    markets = coindcx_adapter.get_markets_details()
    base_upper = base_currency.upper().strip() if base_currency else None

    result = []
    # Prioritize popular markets
    priority_order = [
        "BTCINR", "BTCUSDT", "ETHINR", "ETHUSDT", "USDTINR",
        "SOLINR", "SOLUSDT", "XRPINR", "XRPUSDT", "DOGEINR",
        "DOGEUSDT", "ADAINR", "ADAUSDT", "BNBINR", "BNBUSDT",
        "POLINR", "POLUSDT",
    ]

    seen = set()
    for mkt in priority_order:
        t = tickers.get(mkt)
        if t:
            seen.add(mkt)
            if base_upper:
                m_detail = markets.get(mkt)
                if not m_detail or m_detail.base_currency_short_name.upper() != base_upper:
                    continue
            result.append(t.model_dump())

    for mkt, t in tickers.items():
        if mkt in seen:
            continue
        if base_upper:
            m_detail = markets.get(mkt)
            if not m_detail or m_detail.base_currency_short_name.upper() != base_upper:
                continue
        result.append(t.model_dump())
        if len(result) >= limit:
            break

    return result


@router.get("/quote/{market}")
def get_quote(market: str) -> Dict[str, Any]:
    """Returns real-time ticker quote for a specific market with timestamp and freshness."""
    t = coindcx_adapter.get_ticker(market)
    if not t:
        fallbacks = coindcx_adapter._get_fallback_tickers()
        t = fallbacks.get(market.strip().upper())
    if not t:
        raise HTTPException(status_code=404, detail=f"Market ticker for {market} not found.")
    return t.model_dump()


@router.get("/orderbook/{pair_or_market}")
def get_orderbook(pair_or_market: str) -> Dict[str, Any]:
    """
    Returns Level 2 orderbook with top bids/asks and cumulative liquidity depth.
    Accepts either pair (I-BTC_INR) or market symbol (BTCINR).
    """
    book = coindcx_adapter.get_order_book(pair_or_market)
    if not book:
        book = coindcx_adapter._get_fallback_orderbook(pair_or_market)
    return book.model_dump()


@router.get("/candles/{pair_or_market}")
def get_candles(
    pair_or_market: str,
    interval: str = Query("15m", description="Candle interval: 1m, 15m, 1h, 1d"),
    limit: int = Query(100, ge=10, le=500),
) -> List[Dict[str, Any]]:
    """Returns historical OHLCV candles from CoinDCX."""
    candles = coindcx_adapter.get_candles(pair_or_market, interval=interval, limit=limit)
    if not candles:
        candles = coindcx_adapter._get_fallback_candles(pair_or_market, limit=limit)
    return [c.model_dump() for c in candles]


# ── Scanner Endpoints ─────────────────────────────────────────


@router.get("/scanner/arbitrage")
def get_arbitrage_opportunities() -> List[Dict[str, Any]]:
    """
    Scans cross-market pairs (Direct INR vs Synthetic USDT * USDT/INR).
    Calculates estimated net profitability after CoinDCX taker fees (0.20%),
    statutory TDS (1.0% on sale), bid-ask spread, and slippage.
    Clearly distinguishes EXECUTABLE from DETECTED_ONLY opportunities.
    """
    opportunities = coindcx_scanner.scan_opportunities()
    return [o.model_dump() for o in opportunities]


@router.get("/scanner/momentum")
def get_market_momentum() -> List[Dict[str, Any]]:
    """Returns 24h momentum, volatility, and volume indicators across top crypto assets."""
    return coindcx_scanner.get_market_momentum()


# ── Paper Trading Broker Endpoints ────────────────────────────


@router.get("/paper/wallet")
def get_paper_wallet() -> Dict[str, Any]:
    """
    Returns virtual multi-currency wallet balances, open crypto positions,
    and mark-to-market valuations based on live CoinDCX prices.
    """
    return coindcx_broker.get_wallet_overview()


@router.post("/paper/wallet/reset")
def reset_paper_wallet(req: ResetWalletRequest) -> Dict[str, Any]:
    """Resets virtual wallet balances to specified starting amounts and clears positions."""
    return coindcx_broker.reset_wallet(starting_inr=req.starting_inr, starting_usdt=req.starting_usdt)


@router.post("/paper/order")
def place_paper_order(req: CoinDCXPaperOrderRequest) -> Dict[str, Any]:
    """
    Executes a simulated paper order against live CoinDCX prices and order books.
    Strictly validates minimum order quantity, step size, precision, and min notional.
    Rejects stale market data (>30s old).
    Persists order, fills, balances, and P&L in SQLite.
    """
    result = coindcx_broker.place_paper_order(
        market=req.market,
        side=req.side,
        quantity=req.quantity,
        order_type=req.order_type,
        price=req.price,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": result.get("message", "Order validation failed"),
                "status": result.get("status", "REJECTED"),
                "constraints": result.get("constraints"),
            },
        )
    return result


@router.get("/paper/orders")
def get_paper_orders(limit: int = Query(50, ge=1, le=200)) -> List[Dict[str, Any]]:
    """Returns historical simulated crypto orders (both FILLED and REJECTED with reasons)."""
    return coindcx_broker.get_orders(limit=limit)


# ── Live Trading Safety Barrier ────────────────────────────────


@router.post("/live/order")
def place_live_order_blocked():
    """
    Strict safety block: Live trading is permanently disabled.
    Prevents any unauthorized live order placement.
    """
    raise HTTPException(
        status_code=403,
        detail={
            "error": "Live trading disabled",
            "message": "Groww Lab operates in strict PAPER mode. Real order execution on CoinDCX is permanently blocked to safeguard capital.",
        },
    )
