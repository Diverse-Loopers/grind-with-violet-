"""
Real-time Engine Activity Logger.
Maintains an in-memory chronological stream of bot events:
scans, strategy detections, risk checks, order fills, and mark-to-market events.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActivityEvent(BaseModel):
    id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str  # SCAN, SIGNAL, RISK_PASS, RISK_REJECT, ORDER_FILLED, ORDER_CLOSED, INFO
    symbol: Optional[str] = None
    side: Optional[str] = None  # BUY, SELL, HOLD
    price: Optional[float] = None
    quantity: Optional[int] = None
    message: str
    details: Optional[Dict[str, Any]] = None


class ActivityLogger:
    """Thread-safe event logger for the live trading feed."""

    def __init__(self, max_events: int = 100):
        self._events: List[ActivityEvent] = []
        self._max_events = max_events
        self._seq = 0
        # Seed with initial startup event
        self.log(
            event_type="INFO",
            message="Trading Engine initialized and monitoring market opportunities",
        )

    def log(
        self,
        event_type: str,
        message: str,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        price: Optional[float] = None,
        quantity: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        self._seq += 1
        event = ActivityEvent(
            id=f"EVT-{int(time.time()*1000)}-{self._seq}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            message=message,
            details=details,
        )
        self._events.insert(0, event)
        if len(self._events) > self._max_events:
            self._events.pop()
        return event

    def get_recent(self, limit: int = 50) -> List[ActivityEvent]:
        return self._events[:limit]


# Global singleton
activity_logger = ActivityLogger()
