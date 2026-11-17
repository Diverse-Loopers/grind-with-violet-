"""
WebSocket Streaming Route for Real-Time Scanner Updates.
Broadcasts refreshed watchlist and market metrics to connected frontend clients.
"""

from __future__ import annotations

import asyncio
import json
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.utils.logging import logger

router = APIRouter(tags=["websocket"])

active_connections: Set[WebSocket] = set()


@router.websocket("/ws/scanner")
async def scanner_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"WebSocket client connected. Active: {len(active_connections)}")

    try:
        from app.main import scanner

        while True:
            rows = scanner.get_latest_rows()
            payload = {
                "type": "SCANNER_UPDATE",
                "count": len(rows),
                "instruments": [
                    {
                        "trading_symbol": r.trading_symbol,
                        "exchange": r.exchange,
                        "name": r.name,
                        "ltp": r.ltp,
                        "bid": r.bid,
                        "ask": r.ask,
                        "spread_pct": r.spread_pct,
                        "change_pct": r.change_pct,
                        "volume": r.volume,
                        "relative_volume": r.relative_volume,
                        "high": r.high,
                        "low": r.low,
                        "volatility": r.volatility,
                        "deviation_from_ma": r.deviation_from_ma,
                        "gap_pct": r.gap_pct,
                        "net_edge_pct": r.net_edge_pct,
                        "data_quality": r.data_quality,
                        "quote_timestamp": r.quote_timestamp.isoformat() if r.quote_timestamp else None,
                        "data_freshness_ms": r.data_freshness_ms,
                    }
                    for r in rows
                ],
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(4.0)
    except WebSocketDisconnect:
        active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(active_connections)}")
    except Exception as e:
        active_connections.discard(websocket)
        logger.error(f"WebSocket error: {e}")
