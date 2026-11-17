"""
Groww Account Connection and Token Management API Routes.
Provides live token verification, connection health check, and dynamic adapter activation.
"""

from __future__ import annotations

import re
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings, AppMode
from app.adapters.groww_adapter import GrowwAdapter
from app.adapters.demo_adapter import DemoAdapter
from app.utils.logging import logger

router = APIRouter(prefix="/api/groww", tags=["groww"])


class ConnectGrowwRequest(BaseModel):
    token: str = Field(..., min_length=10, description="Daily Groww Bearer API token")
    app_mode: str = Field(default="PAPER", description="PAPER or LIVE (live orders remain safety locked)")


@router.get("/status")
def get_groww_status() -> Dict[str, Any]:
    from app.main import adapter

    is_groww = isinstance(adapter, GrowwAdapter)
    masked = ""
    profile_info = {}
    if settings.groww_api_token:
        t = settings.groww_api_token
        masked = f"{t[:6]}...{t[-4:]}" if len(t) > 10 else "***"
        if is_groww:
            profile_info = adapter.get_profile()

    return {
        "is_connected": is_groww,
        "mode": settings.app_mode.value,
        "adapter_type": "GrowwAdapter (Official API)" if is_groww else "DemoAdapter (Synthetic Simulation)",
        "has_token": bool(settings.groww_api_token),
        "masked_token": masked,
        "ucc": profile_info.get("ucc", ""),
        "active_segments": profile_info.get("active_segments", []),
        "token_expiry_info": "Groww tokens expire daily at ~6:00 AM IST. Refresh required every morning.",
    }


@router.post("/verify-and-connect")
def verify_and_connect(payload: ConnectGrowwRequest) -> Dict[str, Any]:
    import app.main as main_mod

    raw_token = payload.token.strip()
    if raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:].strip()

    logger.info("Attempting verification of provided Groww API token...")

    # 1. Instantiate GrowwAdapter and verify account authentication
    try:
        test_adapter = GrowwAdapter(token=raw_token, base_url=settings.groww_api_base_url)
        profile = test_adapter.get_profile()
        ucc = profile.get("ucc") or "Active"
        logger.info(f"Verified Groww account successfully! UCC: {ucc}")
    except Exception as exc:
        err_msg = str(exc)
        logger.warning(f"Groww token verification failed: {err_msg}")
        if "expired" in err_msg.lower() or "401" in err_msg or "auth" in err_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="Authentication failed. The token is either invalid, malformed, or has expired (daily expiry at 6 AM IST).",
            )
        elif "rate" in err_msg.lower() or "429" in err_msg:
            raise HTTPException(
                status_code=429,
                detail="Groww API rate limit exceeded. Please wait a few seconds before retrying.",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Groww connection check failed: {err_msg}",
            )

    # Check whether market data permissions or fallback are active
    sample_quote = test_adapter.get_quote("RELIANCE", "NSE")
    has_live_feed = sample_quote.data_quality == "LIVE"

    # If verification passed, activate the live adapter in main!
    target_mode = AppMode.PAPER if payload.app_mode.upper() == "PAPER" else AppMode.LIVE
    settings.app_mode = target_mode
    settings.groww_api_token = raw_token

    # Hot swap the adapter in memory
    main_mod.adapter = test_adapter
    main_mod.scanner.adapter = test_adapter
    main_mod.decision_engine.adapter = test_adapter

    # Update backend/.env so it persists across restarts
    try:
        from pathlib import Path
        backend_dir = Path(__file__).resolve().parent.parent.parent
        env_path = backend_dir / ".env"
        env_content = f"""# Auto-updated by Groww Trading Lab
APP_MODE={target_mode.value}
GROWW_API_TOKEN={raw_token}
GROWW_API_BASE_URL={settings.groww_api_base_url}
PAPER_STARTING_BALANCE={settings.paper_starting_balance}
DB_URL={settings.db_url}
"""
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
    except Exception as e:
        logger.error(f"Could not persist .env: {e}")

    # Run immediate scan
    try:
        main_mod.scanner.scan_all()
    except Exception as e:
        logger.warning(f"Initial scan had warnings: {e}")

    logger.info(f"✓ Groww Official API successfully connected (UCC: {ucc}) in {target_mode.value} mode!")

    return {
        "success": True,
        "message": f"Successfully connected to Groww Official API! Account UCC: {ucc} verified.",
        "mode": target_mode.value,
        "ucc": ucc,
        "active_segments": profile.get("active_segments", ["CASH"]),
        "has_live_feed": has_live_feed,
        "sample_quote": {
            "symbol": sample_quote.trading_symbol,
            "ltp": sample_quote.ltp,
            "bid": sample_quote.bid_price,
            "ask": sample_quote.ask_price,
            "data_quality": sample_quote.data_quality,
        },
    }


@router.post("/disconnect")
def disconnect_groww() -> Dict[str, Any]:
    import app.main as main_mod

    settings.app_mode = AppMode.DEMO
    settings.groww_api_token = ""
    demo_adapter = DemoAdapter()

    main_mod.adapter = demo_adapter
    main_mod.scanner.adapter = demo_adapter
    main_mod.decision_engine.adapter = demo_adapter
    main_mod.scanner.scan_all()

    logger.info("Disconnected Groww API. Reverted to DemoAdapter.")

    return {
        "success": True,
        "message": "Disconnected Groww API. Switched back to DEMO mode (Synthetic simulation).",
        "mode": "DEMO",
    }
