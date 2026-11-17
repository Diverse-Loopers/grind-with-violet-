"""
Backtest API Routes.
Provides endpoints for executing historical backtests, retrieving institutional metrics,
and exporting trade logs to CSV.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.backtest.backtester import HistoricalBacktester
from app.database import get_db_context
from app.models.backtest import BacktestRun, BacktestTrade

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class StartBacktestRequest(BaseModel):
    strategy: str = Field(default="GAP")
    symbols: List[str] = Field(default_factory=lambda: ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"])
    start_date: str = Field(default="2026-09-01T09:15:00Z")
    end_date: str = Field(default="2026-10-28T15:30:00Z")
    initial_capital: float = Field(default=1_000_000.0, gt=0)
    gap_threshold_pct: float = Field(default=1.0, gt=0)
    stop_loss_pct: float = Field(default=1.5, gt=0)
    take_profit_pct: float = Field(default=2.5, gt=0)


@router.post("/run")
def run_backtest_endpoint(payload: StartBacktestRequest) -> Dict[str, Any]:
    from app.main import scanner

    backtester = HistoricalBacktester(scanner.adapter)
    run = backtester.run_backtest(
        strategy=payload.strategy,
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
        initial_capital=payload.initial_capital,
        gap_threshold_pct=payload.gap_threshold_pct,
        stop_loss_pct=payload.stop_loss_pct,
        take_profit_pct=payload.take_profit_pct,
    )
    return {
        "id": run.id,
        "strategy": run.strategy,
        "status": run.status,
        "total_trades": run.total_trades,
        "win_rate": run.win_rate,
        "net_return_pct": run.net_return_pct,
        "max_drawdown_pct": run.max_drawdown_pct,
        "profit_factor": run.profit_factor,
        "sharpe_ratio": run.sharpe_ratio,
        "expectancy": run.expectancy,
        "benchmark_return_pct": run.benchmark_return_pct,
        "out_of_sample_return_pct": run.out_of_sample_return_pct,
        "final_capital": run.final_capital,
    }


@router.get("/results")
def list_backtests(limit: int = Query(default=20, le=100)) -> Dict[str, Any]:
    with get_db_context() as db:
        runs = db.execute(
            select(BacktestRun).order_by(BacktestRun.id.desc()).limit(limit)
        ).scalars().all()

        return {
            "count": len(runs),
            "runs": [
                {
                    "id": r.id,
                    "strategy": r.strategy,
                    "start_date": r.start_date,
                    "end_date": r.end_date,
                    "initial_capital": r.initial_capital,
                    "final_capital": r.final_capital,
                    "total_trades": r.total_trades,
                    "winning_trades": r.winning_trades,
                    "losing_trades": r.losing_trades,
                    "win_rate": r.win_rate,
                    "max_drawdown_pct": r.max_drawdown_pct,
                    "net_return_pct": r.net_return_pct,
                    "profit_factor": r.profit_factor,
                    "avg_profit": r.avg_profit,
                    "avg_loss": r.avg_loss,
                    "sharpe_ratio": r.sharpe_ratio,
                    "expectancy": r.expectancy,
                    "benchmark_return_pct": r.benchmark_return_pct,
                    "out_of_sample_return_pct": r.out_of_sample_return_pct,
                    "total_fees": r.total_fees,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in runs
            ],
        }


@router.get("/results/{run_id}")
def get_backtest_detail(run_id: int) -> Dict[str, Any]:
    with get_db_context() as db:
        run = db.execute(select(BacktestRun).where(BacktestRun.id == run_id)).scalars().first()
        if not run:
            raise HTTPException(status_code=404, detail="Backtest run not found")

        trades = db.execute(
            select(BacktestTrade).where(BacktestTrade.backtest_id == run_id).order_by(BacktestTrade.id.asc())
        ).scalars().all()

        return {
            "run": {
                "id": run.id,
                "strategy": run.strategy,
                "start_date": run.start_date,
                "end_date": run.end_date,
                "initial_capital": run.initial_capital,
                "final_capital": run.final_capital,
                "total_trades": run.total_trades,
                "winning_trades": run.winning_trades,
                "losing_trades": run.losing_trades,
                "win_rate": run.win_rate,
                "max_drawdown_pct": run.max_drawdown_pct,
                "net_return_pct": run.net_return_pct,
                "profit_factor": run.profit_factor,
                "avg_profit": run.avg_profit,
                "avg_loss": run.avg_loss,
                "sharpe_ratio": run.sharpe_ratio,
                "expectancy": run.expectancy,
                "benchmark_return_pct": run.benchmark_return_pct,
                "out_of_sample_return_pct": run.out_of_sample_return_pct,
                "total_fees": run.total_fees,
                "status": run.status,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            },
            "trades_count": len(trades),
        }


@router.get("/results/{run_id}/trades")
def get_backtest_trades(run_id: int) -> Dict[str, Any]:
    with get_db_context() as db:
        trades = db.execute(
            select(BacktestTrade).where(BacktestTrade.backtest_id == run_id).order_by(BacktestTrade.id.asc())
        ).scalars().all()

        return {
            "count": len(trades),
            "trades": [
                {
                    "id": t.id,
                    "trading_symbol": t.trading_symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "fees": t.fees,
                    "slippage": t.slippage,
                }
                for t in trades
            ],
        }


@router.get("/results/{run_id}/export")
def export_backtest_csv(run_id: int):
    with get_db_context() as db:
        trades = db.execute(
            select(BacktestTrade).where(BacktestTrade.backtest_id == run_id).order_by(BacktestTrade.id.asc())
        ).scalars().all()
        if not trades:
            raise HTTPException(status_code=404, detail="No trades found for this backtest")

        csv_content = HistoricalBacktester.export_trades_to_csv(trades)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=backtest_run_{run_id}_trades.csv"},
        )
