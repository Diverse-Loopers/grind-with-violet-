"""
Groww API broker adapter using the SDK and direct REST calls.
Implements all BrokerAdapter methods using verified Groww endpoints.
Never logs sensitive token values.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.adapters.base import (
    BrokerAdapter,
    BrokerPosition,
    Candle,
    Funds,
    Holding,
    MarketDepth,
    OrderResponse,
    OrderStatusResponse,
    Quote,
)
from app.config import settings
from app.utils.logging import get_logger
from app.utils.time_utils import is_market_open

logger = get_logger(__name__)

_TIMEOUT = 10.0  # seconds


class GrowwAdapter(BrokerAdapter):
    """
    Real Groww API adapter.
    Uses growwapi SDK where possible, falls back to direct REST via httpx.
    """

    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self._token = token or settings.groww_api_token
        self._base_url = (base_url or settings.groww_api_base_url).rstrip("/")
        self._sdk_client: Any = None
        self._sdk_feed: Any = None
        from app.adapters.demo_adapter import DemoAdapter
        self._fallback_adapter = DemoAdapter()

        if not self._token:
            raise ValueError(
                "Groww API token is required. Set GROWW_API_TOKEN in .env or pass token directly."
            )

        # Try to initialise the SDK client
        try:
            from growwapi import GrowwAPI, GrowwFeed  # type: ignore[import-untyped]
            self._sdk_client = GrowwAPI(self._token)
            logger.info("Groww SDK client initialized successfully")
            try:
                self._sdk_feed = GrowwFeed(self._sdk_client)
            except Exception as feed_err:
                logger.debug("GrowwFeed init skipped: %s", feed_err)
        except ImportError:
            logger.warning("growwapi SDK not installed — using direct REST calls only")
        except Exception as exc:
            logger.warning("Groww SDK init failed (%s) — falling back to REST", exc)

        self._http = httpx.Client(
            base_url=self._base_url,
            headers=self._build_headers(),
            timeout=_TIMEOUT,
        )
        logger.info("GrowwAdapter initialized (base_url=%s)", self._base_url)

        self._market_data_allowed: bool = False
        if self._sdk_client:
            try:
                q = self._sdk_client.get_quote(trading_symbol="RELIANCE", exchange="NSE", segment="CASH", timeout=3)
                if q and float(q.get("ltp", 0)) > 0:
                    self._market_data_allowed = True
                    logger.info("✓ Groww Market Data API stream active (LIVE quotes enabled)")
            except Exception:
                self._market_data_allowed = False
                logger.info("Groww Market Data permission not active on this plan — using synthetic simulator for scanner while real account is connected for portfolio/orders")

    def get_profile(self) -> dict:
        """Fetch user profile details from Groww."""
        if self._sdk_client:
            try:
                return self._sdk_client.get_user_profile()
            except Exception as e:
                logger.warning("Failed to fetch user profile via SDK: %s", e)
        return {}

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "X-API-VERSION": "1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _rest_get(self, path: str, params: dict | None = None) -> dict:
        """Make authenticated GET request to Groww API."""
        try:
            resp = self._http.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                logger.error("Groww API auth failure — token may have expired (daily expiry ~6AM IST)")
                raise ValueError("Authentication failed — Groww token expired or invalid") from exc
            elif exc.response.status_code == 429:
                logger.warning("Groww API rate limit hit")
                raise ValueError("Rate limit exceeded — slow down requests") from exc
            else:
                logger.error("Groww API error: %d %s", exc.response.status_code, exc.response.text[:200])
                raise
        except httpx.TimeoutException:
            logger.error("Groww API request timed out")
            raise ValueError("Groww API request timed out") from None

    def _rest_post(self, path: str, json_body: dict) -> dict:
        """Make authenticated POST request to Groww API."""
        try:
            resp = self._http.post(path, json=json_body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                logger.error("Groww API auth failure on POST")
                raise ValueError("Authentication failed — Groww token expired or invalid") from exc
            elif exc.response.status_code == 429:
                logger.warning("Groww API rate limit hit on POST")
                raise ValueError("Rate limit exceeded") from exc
            else:
                logger.error("Groww API POST error: %d %s", exc.response.status_code, exc.response.text[:200])
                raise
        except httpx.TimeoutException:
            logger.error("Groww API POST timed out")
            raise ValueError("Groww API request timed out") from None

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Quote:
        """Get live quote using Groww API, or real NSE exchange feed if market data role is not on plan."""
        if self._market_data_allowed and self._sdk_client:
            try:
                data = self._sdk_client.get_quote(
                    trading_symbol=symbol,
                    exchange=exchange,
                    segment="CASH",
                    timeout=3,
                )
                if data and isinstance(data, dict) and float(data.get("ltp", 0)) > 0:
                    return Quote(
                        trading_symbol=symbol,
                        exchange=exchange,
                        segment="CASH",
                        ltp=float(data.get("ltp", 0)),
                        open=float(data.get("open", 0)),
                        high=float(data.get("high", 0)),
                        low=float(data.get("low", 0)),
                        close=float(data.get("close", 0)),
                        change=float(data.get("change", 0)),
                        change_pct=float(data.get("change_pct", 0)),
                        bid_price=float(data.get("bid_price", 0)),
                        bid_qty=int(data.get("bid_qty", 0)),
                        ask_price=float(data.get("ask_price", 0)),
                        ask_qty=int(data.get("ask_qty", 0)),
                        volume=int(data.get("volume", 0)),
                        avg_traded_price=float(data.get("avg_traded_price", 0)),
                        timestamp=datetime.now(timezone.utc),
                        data_quality="LIVE",
                    )
            except Exception as exc:
                logger.warning("Live quote error for %s: %s — falling back", symbol, exc)

        # Real live market feed fallback
        from app.adapters.market_data_service import fetch_real_nse_quote
        real_quote = fetch_real_nse_quote(symbol, exchange)
        if real_quote:
            return real_quote

        return self._fallback_adapter.get_quote(symbol, exchange)

    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
        interval_minutes: int = 5,
    ) -> list[Candle]:
        """Get historical candle data from Groww API."""
        start_ts = start.isoformat() if start.tzinfo else start.replace(tzinfo=timezone.utc).isoformat()
        end_ts = end.isoformat() if end.tzinfo else end.replace(tzinfo=timezone.utc).isoformat()

        data = self._rest_get(
            "/historical/candle/range",
            params={
                "exchange": exchange,
                "segment": "CASH",
                "trading_symbol": symbol,
                "start_time": start_ts,
                "end_time": end_ts,
                "interval_in_minutes": str(interval_minutes),
            },
        )

        candles: list[Candle] = []
        candle_data = data.get("candles", data.get("data", []))
        for c in candle_data:
            if isinstance(c, list) and len(c) >= 6:
                candles.append(Candle(
                    timestamp=datetime.fromisoformat(str(c[0])) if isinstance(c[0], str) else datetime.fromtimestamp(c[0], tz=timezone.utc),
                    open=float(c[1]),
                    high=float(c[2]),
                    low=float(c[3]),
                    close=float(c[4]),
                    volume=int(c[5]),
                ))
            elif isinstance(c, dict):
                candles.append(Candle(
                    timestamp=datetime.fromisoformat(c.get("timestamp", c.get("time", ""))),
                    open=float(c.get("open", 0)),
                    high=float(c.get("high", 0)),
                    low=float(c.get("low", 0)),
                    close=float(c.get("close", 0)),
                    volume=int(c.get("volume", 0)),
                ))

        return candles

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> float:
        """Get last traded price."""
        quote = self.get_quote(symbol, exchange)
        return quote.ltp

    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> MarketDepth:
        """Get order book depth from Groww."""
        data = self._rest_get(
            "/live-data/quote",
            params={"exchange": exchange, "segment": "CASH", "trading_symbol": symbol},
        )

        bids: list[tuple[float, int]] = []
        asks: list[tuple[float, int]] = []

        for entry in data.get("depth", {}).get("buy", []):
            bids.append((float(entry.get("price", 0)), int(entry.get("quantity", 0))))
        for entry in data.get("depth", {}).get("sell", []):
            asks.append((float(entry.get("price", 0)), int(entry.get("quantity", 0))))

        return MarketDepth(
            trading_symbol=symbol,
            exchange=exchange,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc),
        )

    def get_holdings(self) -> list[Holding]:
        """Get portfolio holdings from Groww."""
        if self._sdk_client:
            try:
                res = self._sdk_client.get_holdings_for_user()
                holdings: list[Holding] = []
                for h in res.get("holdings", []):
                    holdings.append(Holding(
                        trading_symbol=h.get("trading_symbol", h.get("tradingsymbol", "")),
                        exchange=h.get("exchange", "NSE"),
                        isin=h.get("isin", ""),
                        quantity=int(h.get("quantity", 0)),
                        avg_price=float(h.get("average_price", 0)),
                        ltp=float(h.get("ltp", h.get("last_price", 0))),
                        pnl=float(h.get("pnl", 0)),
                    ))
                return holdings
            except Exception as e:
                logger.warning("SDK get_holdings_for_user failed: %s", e)

        try:
            data = self._rest_get("/portfolio/holdings")
            holdings = []
            for h in data.get("holdings", []):
                holdings.append(Holding(
                    trading_symbol=h.get("trading_symbol", h.get("tradingsymbol", "")),
                    exchange=h.get("exchange", "NSE"),
                    isin=h.get("isin", ""),
                    quantity=int(h.get("quantity", 0)),
                    avg_price=float(h.get("average_price", 0)),
                    ltp=float(h.get("ltp", h.get("last_price", 0))),
                    pnl=float(h.get("pnl", 0)),
                ))
            return holdings
        except Exception as exc:
            logger.error("Failed to get holdings: %s", exc)
            return []

    def get_positions(self) -> list[BrokerPosition]:
        """Get open positions from Groww."""
        if self._sdk_client:
            try:
                res = self._sdk_client.get_positions_for_user()
                positions: list[BrokerPosition] = []
                for p in res.get("positions", []):
                    positions.append(BrokerPosition(
                        trading_symbol=p.get("trading_symbol", p.get("tradingsymbol", "")),
                        exchange=p.get("exchange", "NSE"),
                        product=p.get("product", "CNC"),
                        quantity=int(p.get("quantity", 0)),
                        avg_price=float(p.get("average_price", 0)),
                        ltp=float(p.get("ltp", p.get("last_price", 0))),
                        pnl=float(p.get("pnl", 0)),
                        buy_qty=int(p.get("buy_quantity", 0)),
                        sell_qty=int(p.get("sell_quantity", 0)),
                        buy_avg=float(p.get("buy_price", 0)),
                        sell_avg=float(p.get("sell_price", 0)),
                    ))
                return positions
            except Exception as e:
                logger.warning("SDK get_positions_for_user failed: %s", e)

        try:
            data = self._rest_get("/portfolio/positions")
            positions = []
            for p in data.get("net", data.get("positions", [])):
                positions.append(BrokerPosition(
                    trading_symbol=p.get("trading_symbol", p.get("tradingsymbol", "")),
                    exchange=p.get("exchange", "NSE"),
                    product=p.get("product", "CNC"),
                    quantity=int(p.get("quantity", 0)),
                    avg_price=float(p.get("average_price", 0)),
                    ltp=float(p.get("ltp", p.get("last_price", 0))),
                    pnl=float(p.get("pnl", 0)),
                    buy_qty=int(p.get("buy_quantity", 0)),
                    sell_qty=int(p.get("sell_quantity", 0)),
                    buy_avg=float(p.get("buy_price", 0)),
                    sell_avg=float(p.get("sell_price", 0)),
                ))
            return positions
        except Exception as exc:
            logger.error("Failed to get positions: %s", exc)
            return []

    def get_order_status(self, order_id: str) -> OrderStatusResponse:
        """Check order status with Groww."""
        try:
            data = self._rest_get(
                f"/order/detail/{order_id}",
                params={"segment": "CASH"},
            )
            return OrderStatusResponse(
                order_id=order_id,
                status=data.get("status", "UNKNOWN"),
                filled_quantity=int(data.get("filled_quantity", data.get("filled_qty", 0))),
                average_price=float(data.get("average_price", data.get("avg_price", 0))),
                message=data.get("status_message", ""),
            )
        except Exception as exc:
            logger.error("Failed to get order status for %s: %s", order_id, exc)
            return OrderStatusResponse(
                order_id=order_id,
                status="ERROR",
                message=str(exc),
            )

    def place_order(
        self,
        trading_symbol: str,
        exchange: str,
        transaction_type: str,
        order_type: str,
        quantity: int,
        price: float | None = None,
        trigger_price: float | None = None,
        product: str = "CNC",
        order_reference_id: str | None = None,
    ) -> OrderResponse:
        """Place an order through Groww API."""
        # Strict safety barrier: Live broker execution is locked by default
        if not settings.is_live:
            logger.warning("[SAFETY BLOCK] Attempted live order placement while platform is in PAPER/DEMO mode.")
            return OrderResponse(
                success=False,
                message="Live broker order placement is safety-locked. Platform defaults to PAPER trading with no live orders.",
                status="REJECTED",
            )

        if not order_reference_id:
            order_reference_id = f"GRW-{uuid.uuid4().hex[:12].upper()}"

        body: dict[str, Any] = {
            "trading_symbol": trading_symbol,
            "exchange": exchange,
            "segment": "CASH",
            "transaction_type": transaction_type,
            "order_type": order_type,
            "product": product,
            "quantity": quantity,
            "validity": "DAY",
            "order_reference_id": order_reference_id,
        }

        if price is not None:
            body["price"] = price
        if trigger_price is not None:
            body["trigger_price"] = trigger_price

        try:
            data = self._rest_post("/order/create", body)
            return OrderResponse(
                success=True,
                order_id=data.get("order_id", data.get("groww_order_id", "")),
                broker_order_id=data.get("groww_order_id", data.get("order_id", "")),
                message=data.get("message", "Order placed successfully"),
                status=data.get("status", "ACCEPTED"),
            )
        except Exception as exc:
            logger.error("Failed to place order: %s", exc)
            return OrderResponse(
                success=False,
                message=str(exc),
                status="REJECTED",
            )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order on Groww."""
        try:
            self._rest_post(f"/order/cancel/{order_id}", {"segment": "CASH"})
            return True
        except Exception as exc:
            logger.error("Failed to cancel order %s: %s", order_id, exc)
            return False

    def get_funds(self) -> Funds:
        """Get account fund details from Groww."""
        if self._sdk_client:
            try:
                m = self._sdk_client.get_available_margin_details()
                clear_cash = float(m.get("clear_cash", 0.0))
                used = float(m.get("net_margin_used", 0.0))
                collateral = float(m.get("collateral_available", 0.0))
                return Funds(
                    available_cash=clear_cash,
                    used_margin=used,
                    total_balance=clear_cash + collateral,
                    collateral=collateral,
                )
            except Exception as e:
                logger.warning("SDK get_available_margin_details failed: %s", e)

        try:
            data = self._rest_get("/user/funds")
            return Funds(
                available_cash=float(data.get("available_cash", data.get("available", {}).get("cash", 0))),
                used_margin=float(data.get("used_margin", data.get("utilised", {}).get("debits", 0))),
                total_balance=float(data.get("total_balance", data.get("available", {}).get("opening_balance", 0))),
                collateral=float(data.get("collateral", 0)),
            )
        except Exception as exc:
            logger.error("Failed to get funds: %s", exc)
            return Funds()

    def is_market_open(self) -> bool:
        """Check if NSE is currently in trading hours."""
        return is_market_open()

    def close(self) -> None:
        """Clean up resources."""
        self._http.close()
