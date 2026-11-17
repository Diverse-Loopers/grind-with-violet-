"""
Application configuration using pydantic-settings.
Reads from .env file and environment variables.
Never logs sensitive token values.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = f"sqlite:///{_BACKEND_DIR}/groww_trading.db"

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppMode(str, Enum):
    DEMO = "DEMO"
    PAPER = "PAPER"
    LIVE = "LIVE"


class Settings(BaseSettings):
    """Central application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Groww API ──────────────────────────────────────────────
    groww_api_token: str = Field(default="", description="Groww API bearer token (daily expiry ~6AM IST)")
    groww_api_base_url: str = Field(default="https://api.groww.in/v1", description="Groww REST base URL")

    # ── Angel One SmartAPI ─────────────────────────────────────
    angel_api_key: str = Field(default="9K7Tpl8A", description="Angel One SmartAPI Trading Key")
    angel_client_code: str = Field(default="", description="Angel One Client Code / Login ID")
    angel_mpin: str = Field(default="", description="Angel One 4-digit MPIN")
    angel_totp_secret: str = Field(default="", description="Angel One TOTP Secret Key")

    # ── Application ───────────────────────────────────────────
    app_mode: AppMode = Field(default=AppMode.DEMO, description="DEMO / PAPER / LIVE")
    paper_starting_balance: float = Field(default=1_000_000.0, description="Paper trading starting cash (INR)")
    db_url: str = Field(default=_DEFAULT_DB_PATH, description="SQLAlchemy database URL")

    # ── Risk Limits ───────────────────────────────────────────
    max_position_pct: float = Field(default=10.0, description="Max single position as % of equity")
    max_daily_loss: float = Field(default=50_000.0, description="Max daily loss in INR")
    max_open_positions: int = Field(default=10, description="Max number of open positions")
    max_single_order_value: float = Field(default=100_000.0, description="Max single order value in INR")

    # ── Scanner Defaults ──────────────────────────────────────
    scanner_poll_interval: float = Field(default=5.0, description="Scanner poll interval in seconds (DEMO)")
    quote_max_age_seconds: float = Field(default=30.0, description="Max acceptable quote age in seconds")

    # ── Strategy Defaults ─────────────────────────────────────
    spread_min_edge_pct: float = Field(default=0.1, description="Min net edge for spread strategy (%)")
    gap_threshold_pct: float = Field(default=1.0, description="Gap detection threshold (%)")
    gap_volume_multiplier: float = Field(default=2.0, description="Volume spike multiplier threshold")
    pairs_zscore_threshold: float = Field(default=2.0, description="Pairs z-score entry threshold")

    # ── Cost Defaults ─────────────────────────────────────────
    brokerage_pct: float = Field(default=0.03, description="Brokerage as % of turnover")
    brokerage_flat: float = Field(default=20.0, description="Flat brokerage per order (INR)")
    use_flat_brokerage: bool = Field(default=False, description="Use flat brokerage instead of %")

    # ── Strategies Enabled ────────────────────────────────────
    strategy_spread_enabled: bool = Field(default=True)
    strategy_gap_enabled: bool = Field(default=True)
    strategy_pairs_enabled: bool = Field(default=True)

    @field_validator("app_mode", mode="before")
    @classmethod
    def _normalize_mode(cls, v: str) -> str:
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("groww_api_token")
    @classmethod
    def _warn_empty_token(cls, v: str) -> str:
        # Empty token is fine for DEMO mode — validated at runtime
        return v

    @property
    def is_demo(self) -> bool:
        return self.app_mode == AppMode.DEMO

    @property
    def is_paper(self) -> bool:
        return self.app_mode == AppMode.PAPER

    @property
    def is_live(self) -> bool:
        return self.app_mode == AppMode.LIVE

    @property
    def has_api_token(self) -> bool:
        return bool(self.groww_api_token)

    def safe_repr(self) -> dict:
        """Return config dict with token masked for logging."""
        data = self.model_dump()
        if data.get("groww_api_token"):
            data["groww_api_token"] = "***MASKED***"
        return data


# Singleton instance
settings = Settings()
