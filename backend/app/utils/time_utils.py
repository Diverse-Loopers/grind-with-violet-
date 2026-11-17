"""
UTC / IST conversion helpers and NSE market hours checking.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone, date

# Indian Standard Time is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# NSE market hours (IST)
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# NSE holidays 2024-2026 (major ones; extend as needed)
NSE_HOLIDAYS: set[date] = {
    # 2024
    date(2024, 1, 26), date(2024, 3, 8), date(2024, 3, 25), date(2024, 3, 29),
    date(2024, 4, 11), date(2024, 4, 14), date(2024, 4, 17), date(2024, 4, 21),
    date(2024, 5, 1), date(2024, 5, 23), date(2024, 6, 17), date(2024, 7, 17),
    date(2024, 8, 15), date(2024, 10, 2), date(2024, 10, 12), date(2024, 11, 1),
    date(2024, 11, 15), date(2024, 12, 25),
    # 2025
    date(2025, 1, 26), date(2025, 2, 26), date(2025, 3, 14), date(2025, 3, 31),
    date(2025, 4, 10), date(2025, 4, 14), date(2025, 4, 18), date(2025, 5, 1),
    date(2025, 8, 15), date(2025, 8, 27), date(2025, 10, 2), date(2025, 10, 21),
    date(2025, 10, 22), date(2025, 11, 5), date(2025, 12, 25),
    # 2026
    date(2026, 1, 26), date(2026, 3, 10), date(2026, 3, 20), date(2026, 3, 30),
    date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 13),
    date(2026, 7, 7), date(2026, 8, 15), date(2026, 8, 17), date(2026, 10, 2),
    date(2026, 10, 20), date(2026, 11, 9), date(2026, 12, 25),
}


def utc_now() -> datetime:
    """Return current time in UTC."""
    return datetime.now(timezone.utc)


def to_ist(dt: datetime) -> datetime:
    """Convert any timezone-aware datetime to IST."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def to_utc(dt: datetime) -> datetime:
    """Convert any timezone-aware datetime to UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(timezone.utc)


def ist_now() -> datetime:
    """Return current time in IST."""
    return datetime.now(IST)


def is_market_open(dt: datetime | None = None) -> bool:
    """
    Check if NSE is open at the given time.
    Rules: Mon-Fri, 9:15-15:30 IST, excluding NSE holidays.
    """
    if dt is None:
        dt = ist_now()
    else:
        dt = to_ist(dt)

    # Weekend check
    if dt.weekday() >= 5:
        return False

    # Holiday check
    if dt.date() in NSE_HOLIDAYS:
        return False

    # Time window check
    current_time = dt.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def seconds_to_market_open(dt: datetime | None = None) -> float:
    """Return seconds until next market open. Returns 0 if market is open."""
    if dt is None:
        dt = ist_now()
    else:
        dt = to_ist(dt)

    if is_market_open(dt):
        return 0.0

    # Find next trading day
    next_day = dt.date()
    if dt.time() > MARKET_CLOSE or dt.weekday() >= 5 or dt.date() in NSE_HOLIDAYS:
        next_day += timedelta(days=1)

    while next_day.weekday() >= 5 or next_day in NSE_HOLIDAYS:
        next_day += timedelta(days=1)

    next_open = datetime.combine(next_day, MARKET_OPEN, tzinfo=IST)
    return max(0.0, (next_open - dt).total_seconds())


is_nse_market_open = is_market_open


def format_ist(dt: datetime) -> str:
    """Format datetime as IST string."""
    return to_ist(dt).strftime("%Y-%m-%d %H:%M:%S IST")


def get_market_session_info(dt: datetime | None = None) -> dict[str, Any]:
    """Provides detailed session status info."""
    from typing import Any
    now = ist_now() if dt is None else to_ist(dt)
    open_status = is_market_open(now)

    if open_status:
        session_name = "NORMAL_TRADING"
    elif now.weekday() >= 5:
        session_name = "WEEKEND_CLOSED"
    elif now.date() in NSE_HOLIDAYS:
        session_name = "HOLIDAY_CLOSED"
    elif now.time() < time(9, 0):
        session_name = "PRE_MARKET_CLOSED"
    elif time(9, 0) <= now.time() < MARKET_OPEN:
        session_name = "PRE_OPEN_SESSION"
    else:
        session_name = "POST_MARKET_CLOSED"

    return {
        "is_open": open_status,
        "session_name": session_name,
        "ist_time": format_ist(now),
        "seconds_to_open": seconds_to_market_open(now),
    }
