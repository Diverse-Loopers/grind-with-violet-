"""
Watchlist Manager.
Manages the tracked instruments across database and memory.
"""

from __future__ import annotations

from typing import List
from sqlalchemy import select
from app.database import get_db_context
from app.models.instrument import Instrument


DEFAULT_WATCHLIST = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "INFY", "name": "Infosys Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "ITC", "name": "ITC Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "SBIN", "name": "State Bank of India", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "LT", "name": "Larsen & Toubro Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "WIPRO", "name": "Wipro Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "ASIANPAINT", "name": "Asian Paints Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "TITAN", "name": "Titan Company Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "NESTLEIND", "name": "Nestle India Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "HCLTECH", "name": "HCL Technologies Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "exchange": "NSE", "tick_size": 0.05},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd", "exchange": "NSE", "tick_size": 0.05},
]


class WatchlistManager:
    """Manages active instrument watchlist."""

    def __init__(self):
        self.initialize_defaults()

    def initialize_defaults(self):
        """Seeds default watchlist if empty."""
        with get_db_context() as db:
            existing = db.execute(select(Instrument)).scalars().all()
            if not existing:
                for item in DEFAULT_WATCHLIST:
                    inst = Instrument(
                        trading_symbol=item["symbol"],
                        name=item["name"],
                        exchange=item["exchange"],
                        segment="CASH",
                        tick_size=item["tick_size"],
                        is_active=True,
                    )
                    db.add(inst)
                db.commit()

    def get_active_instruments(self) -> List[Instrument]:
        with get_db_context() as db:
            return list(db.execute(select(Instrument).where(Instrument.is_active == True)).scalars().all())

    def add_instrument(self, symbol: str, name: str = "", exchange: str = "NSE") -> Instrument:
        with get_db_context() as db:
            existing = db.execute(select(Instrument).where(Instrument.trading_symbol == symbol.upper())).scalars().first()
            if existing:
                existing.is_active = True
                db.commit()
                db.refresh(existing)
                return existing
            inst = Instrument(
                trading_symbol=symbol.upper(),
                name=name or symbol.upper(),
                exchange=exchange.upper(),
                segment="CASH",
                is_active=True,
            )
            db.add(inst)
            db.commit()
            db.refresh(inst)
            return inst

    def remove_instrument(self, symbol: str) -> bool:
        with get_db_context() as db:
            existing = db.execute(select(Instrument).where(Instrument.trading_symbol == symbol.upper())).scalars().first()
            if existing:
                existing.is_active = False
                db.commit()
                return True
            return False
