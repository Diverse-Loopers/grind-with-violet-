"""
Main FastAPI Application Entrypoint for Groww Trading Lab.
Initializes broker adapters, market scanner, risk engine, paper broker, and API routes.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, AppMode
from app.database import init_db
from app.adapters.base import BrokerAdapter
from app.adapters.demo_adapter import DemoAdapter
from app.adapters.groww_adapter import GrowwAdapter
from app.scanner.market_scanner import MarketScanner
from app.engine.risk_engine import RiskEngine
from app.engine.paper_broker import PaperBroker
from app.engine.decision_engine import TradeDecisionEngine
from app.strategies.spread_scanner import SpreadScanner
from app.strategies.gap_detector import GapDetector
from app.strategies.pairs_research import PairsResearch
from app.models.signal import Signal
from app.engine.activity_logger import activity_logger
from app.utils.logging import logger

# Routers
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_scanner import router as scanner_router
from app.api.routes_portfolio import router as portfolio_router
from app.api.routes_risk import router as risk_router
from app.api.routes_backtest import router as backtest_router
from app.api.routes_groww import router as groww_router
from app.api.websocket import router as ws_router
from app.api.routes_tradingview import router as tradingview_router
from app.api.routes_coindcx import router as coindcx_router
from app.api.routes_multi_agent import router as multi_agent_router
from app.agents.multi_agent_orchestrator import multi_agent_system
from app.global_engine.engine import global_engine


# ── Global Engine Singletons ──────────────────────────────────
adapter: BrokerAdapter = DemoAdapter()
scanner: MarketScanner = MarketScanner(adapter)
risk_engine: RiskEngine = RiskEngine()
paper_broker: PaperBroker = PaperBroker()
decision_engine: TradeDecisionEngine = TradeDecisionEngine(adapter, paper_broker, risk_engine)
spread_scanner: SpreadScanner = SpreadScanner()
gap_detector: GapDetector = GapDetector()
pairs_research: PairsResearch = PairsResearch()

scanner_task: asyncio.Task | None = None


def run_scan_cycle() -> List[Signal]:
    """Executes a single market scan cycle across all active strategies."""
    rows = scanner.scan_all()
    rows_by_sym = {r.trading_symbol: r for r in rows}

    # Mark open positions to market
    quotes = {r.trading_symbol: scanner.adapter.get_quote(r.trading_symbol) for r in rows}
    paper_broker.mark_to_market(quotes)

    candidate_signals: List[Signal] = []

    # 1. Strategy A: Spread Scanner
    if risk_engine.settings.strategy_spread_enabled:
        candidate_signals.extend(spread_scanner.scan(rows))

    # 2. Strategy B: Gap Detector
    if risk_engine.settings.strategy_gap_enabled:
        candidate_signals.extend(gap_detector.scan(rows))

    # 3. Strategy C: Pairs Research (Research Only)
    if risk_engine.settings.strategy_pairs_enabled:
        candidate_signals.extend(pairs_research.scan_all_pairs(rows_by_sym))

    # Evaluate candidates through Risk and Decision Engine
    processed = decision_engine.process_candidate_signals(candidate_signals)
    accepted_count = sum(1 for s in processed if s.status == "ACCEPTED")

    if candidate_signals:
        activity_logger.log(
            event_type="SCAN",
            message=f"🔍 Scan pass: evaluated {len(candidate_signals)} candidate signals ({accepted_count} approved for paper execution)",
        )
    return processed


async def background_scanner_loop():
    """Background polling worker for market scanner and strategy evaluation."""
    interval = max(5.0, settings.scanner_poll_interval)
    logger.info(f"Starting background market scanner loop with interval {interval}s")

    while True:
        try:
            await asyncio.to_thread(run_scan_cycle)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in scanner loop: {e}", exc_info=True)

        await asyncio.sleep(interval)


async def background_multi_agent_loop():
    """Background autonomous loop for F&O Multi-Agent System."""
    logger.info("🤖 Starting background F&O multi-agent autonomous loop (15s interval)")
    while True:
        try:
            if not multi_agent_system.risk_governor.kill_switch_engaged and multi_agent_system.auto_execute:
                await asyncio.to_thread(multi_agent_system.run_orchestration_cycle)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in multi-agent autonomous loop: {e}", exc_info=True)

        await asyncio.sleep(15.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global adapter, scanner, risk_engine, paper_broker, decision_engine
    global spread_scanner, gap_detector, pairs_research, scanner_task

    logger.info(f"🚀 Initializing Groww Trading Lab in mode: {settings.app_mode.value}")

    # 1. Database
    init_db()

    # 2. Broker Adapter Selection
    if settings.angel_api_key and settings.angel_client_code and settings.angel_mpin and settings.angel_totp_secret:
        try:
            from app.adapters.angel_one_adapter import AngelOneAdapter
            adapter = AngelOneAdapter()
            logger.info("✓ Initialized Angel One SmartAPI Live Broker Adapter")
        except Exception as e:
            logger.warning(f"Failed to initialize Angel One SmartAPI: {e}. Falling back to DemoAdapter.")
            adapter = DemoAdapter()
    elif settings.app_mode in (AppMode.PAPER, AppMode.LIVE) and settings.has_api_token:
        try:
            adapter = GrowwAdapter(token=settings.groww_api_token, base_url=settings.groww_api_base_url)
            logger.info("✓ Initialized Groww Official Trading API Adapter")
        except Exception as e:
            logger.warning(f"Failed to connect to Groww API: {e}. Falling back to DemoAdapter.")
            adapter = DemoAdapter()
    else:
        logger.info("✓ Running with DemoAdapter (Realistic Synthetic Equity Feeds)")
        adapter = DemoAdapter()

    # 3. Engines
    scanner = MarketScanner(adapter)
    risk_engine = RiskEngine()
    paper_broker = PaperBroker()
    decision_engine = TradeDecisionEngine(adapter, paper_broker, risk_engine)
    spread_scanner = SpreadScanner()
    gap_detector = GapDetector()
    pairs_research = PairsResearch()

    # 4. Start background scanner non-blocking
    scanner_task = asyncio.create_task(background_scanner_loop())
    global_engine_task = asyncio.create_task(global_engine.start_background_loop())
    agent_task = asyncio.create_task(background_multi_agent_loop())

    yield

    # Shutdown
    if scanner_task:
        scanner_task.cancel()
        try:
            await scanner_task
        except asyncio.CancelledError:
            pass
    if global_engine_task:
        global_engine_task.cancel()
        try:
            await global_engine_task
        except asyncio.CancelledError:
            pass
    if agent_task:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
    logger.info("Groww Trading Lab shut down gracefully.")


app = FastAPI(
    title="Groww Trading Lab",
    description="Local Algorithmic Trading Research & Paper-Trading Platform for Indian Equities",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware (Localhost only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(dashboard_router)
app.include_router(scanner_router)
app.include_router(portfolio_router)
app.include_router(risk_router)
app.include_router(backtest_router)
app.include_router(groww_router)
app.include_router(ws_router)
app.include_router(tradingview_router)
app.include_router(coindcx_router)
app.include_router(multi_agent_router)
