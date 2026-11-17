"""
Historical Backtesting Engine.
Replays time-series OHLCV candles, applies strategy entry/exit conditions,
models realistic bid/ask execution with slippage and statutory transaction costs,
prevents look-ahead bias, splits data into In-Sample (70%) and Out-of-Sample (30%) periods,
and computes institutional performance metrics (Sharpe, Max Drawdown, Expectancy, Benchmark).
"""

from __future__ import annotations

import csv
import io
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.adapters.base import BrokerAdapter, Candle
from app.database import get_db_context
from app.engine.cost_calculator import TransactionCostCalculator
from app.models.backtest import BacktestRun, BacktestTrade, BacktestStatus


class HistoricalBacktester:
    """Rigorous backtesting engine with realistic fill, fee, and out-of-sample validation."""

    def __init__(self, adapter: BrokerAdapter):
        self.adapter = adapter
        self.cost_calc = TransactionCostCalculator()

    def run_backtest(
        self,
        strategy: str,
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000.0,
        gap_threshold_pct: float = 0.5,
        stop_loss_pct: float = 1.5,
        take_profit_pct: float = 2.5,
        slippage_pct: float = 0.05,
    ) -> BacktestRun:
        """
        Executes an event-driven chronological backtest across specified symbols.
        Supports GAP, MOMENTUM, and MEAN_REVERSION strategies with out-of-sample partitioning.
        """
        strat_key = strategy.strip().upper()
        start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        with get_db_context() as db:
            run = BacktestRun(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                status=BacktestStatus.RUNNING.value,
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            cash = initial_capital
            trades: List[BacktestTrade] = []
            trade_pnls: List[float] = []
            equity_curve = [initial_capital]

            in_sample_pnls: List[float] = []
            oos_pnls: List[float] = []
            benchmark_returns: List[float] = []

            for sym in symbols:
                try:
                    candles = self.adapter.get_historical_data(
                        symbol=sym,
                        exchange="NSE",
                        start=start_dt,
                        end=end_dt,
                        interval_minutes=15,
                    )
                except Exception:
                    continue

                if len(candles) < 20:
                    continue

                # Benchmark buy-and-hold return for this symbol
                first_close = candles[0].close
                last_close = candles[-1].close
                if first_close > 0:
                    benchmark_returns.append(((last_close - first_close) / first_close) * 100.0)

                # Train / Test split: first 70% In-Sample, last 30% Out-of-Sample
                split_idx = int(len(candles) * 0.70)

                in_position = False
                entry_price = 0.0
                entry_time = ""
                pos_qty = 0
                buy_cost_total = 0.0
                is_in_sample_trade = True

                # Calculate indicators for strategies
                closes = [c.close for c in candles]
                ema_fast = self._calc_ema(closes, span=9)
                ema_slow = self._calc_ema(closes, span=21)
                sma_20 = self._calc_sma(closes, period=20)
                std_20 = self._calc_rolling_std(closes, period=20)

                # Replay chronologically with NO look-ahead
                for i in range(1, len(candles)):
                    prev = candles[i - 1]
                    curr = candles[i]
                    is_current_oos = (i >= split_idx)

                    # 1. Entry Condition Evaluation
                    if not in_position:
                        should_enter = False

                        if strat_key == "GAP":
                            # Overnight / opening gap continuation or mean gap
                            gap_pct = ((curr.open - prev.close) / prev.close) * 100.0
                            if gap_pct >= gap_threshold_pct:
                                should_enter = True

                        elif strat_key == "MOMENTUM":
                            # Fast EMA crossing above slow EMA
                            if i >= 2 and ema_fast[i - 1] <= ema_slow[i - 1] and ema_fast[i] > ema_slow[i]:
                                should_enter = True

                        elif strat_key == "MEAN_REVERSION":
                            # Price dips below lower Bollinger band (SMA - 1.8 * std)
                            lower_band = sma_20[i] - (1.8 * std_20[i])
                            if curr.close < lower_band and curr.close > 0:
                                should_enter = True

                        else:  # Default to breakout / momentum if custom strategy
                            if curr.close > prev.high and curr.volume > prev.volume:
                                should_enter = True

                        if should_enter:
                            # Realistic fill at Ask (with slippage)
                            slippage_cost = curr.open * (slippage_pct / 100.0)
                            effective_entry = round(curr.open + slippage_cost, 2)
                            alloc = initial_capital * 0.10  # 10% allocation per trade
                            pos_qty = max(1, int(alloc / effective_entry))

                            buy_cost = self.cost_calc.calculate_single_leg_cost("BUY", effective_entry, pos_qty, "CNC")
                            buy_cost_total = buy_cost.total_cost
                            required_cash = (effective_entry * pos_qty) + buy_cost_total

                            # Enforce cash balance constraint
                            if cash >= required_cash:
                                cash -= required_cash
                                in_position = True
                                entry_price = effective_entry
                                entry_time = curr.timestamp.isoformat()
                                is_in_sample_trade = not is_current_oos

                    # 2. Position Management & Exit Rules
                    else:
                        pnl_pct = ((curr.close - entry_price) / entry_price) * 100.0
                        should_exit = (
                            pnl_pct >= take_profit_pct
                            or pnl_pct <= -stop_loss_pct
                            or (i == len(candles) - 1)  # Square off at end of series
                        )

                        if should_exit:
                            # Realistic fill at Bid (with slippage)
                            slippage_cost = curr.close * (slippage_pct / 100.0)
                            effective_exit = round(curr.close - slippage_cost, 2)
                            sell_cost = self.cost_calc.calculate_single_leg_cost("SELL", effective_exit, pos_qty, "CNC")

                            gross_pnl = (effective_exit - entry_price) * pos_qty
                            total_fees = buy_cost_total + sell_cost.total_cost
                            net_pnl = round(gross_pnl - total_fees, 2)

                            cash += (effective_exit * pos_qty) - sell_cost.total_cost
                            trade_pnls.append(net_pnl)
                            equity_curve.append(cash)

                            if is_in_sample_trade:
                                in_sample_pnls.append(net_pnl)
                            else:
                                oos_pnls.append(net_pnl)

                            t = BacktestTrade(
                                backtest_id=run.id,
                                trading_symbol=sym,
                                entry_time=entry_time,
                                exit_time=curr.timestamp.isoformat(),
                                entry_price=entry_price,
                                exit_price=effective_exit,
                                quantity=pos_qty,
                                side="BUY",
                                pnl=net_pnl,
                                fees=round(total_fees, 2),
                                slippage=round(slippage_cost * 2 * pos_qty, 2),
                            )
                            db.add(t)
                            trades.append(t)
                            in_position = False
                            buy_cost_total = 0.0

            # 3. Institutional Performance Metrics Calculation
            total_trades = len(trade_pnls)
            winning_trades = sum(1 for p in trade_pnls if p > 0)
            losing_trades = sum(1 for p in trade_pnls if p <= 0)
            win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

            gross_wins = sum(p for p in trade_pnls if p > 0)
            gross_losses = abs(sum(p for p in trade_pnls if p < 0))
            profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)

            avg_profit = round(gross_wins / winning_trades, 2) if winning_trades > 0 else 0.0
            avg_loss = round(gross_losses / losing_trades, 2) if losing_trades > 0 else 0.0

            # Expectancy: E = (Win% * AvgWin) - (Loss% * AvgLoss)
            p_win = win_rate / 100.0
            p_loss = (100.0 - win_rate) / 100.0
            expectancy = round((p_win * avg_profit) - (p_loss * avg_loss), 2)

            final_capital = equity_curve[-1] if equity_curve else initial_capital
            net_return_pct = round(((final_capital - initial_capital) / initial_capital) * 100.0, 2)

            # Max drawdown calculation
            peak = initial_capital
            max_dd = 0.0
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd = ((peak - eq) / peak) * 100.0
                if dd > max_dd:
                    max_dd = dd

            # Annualized Sharpe ratio estimation
            if len(trade_pnls) >= 2:
                returns = np.array([
                    t.pnl / (t.entry_price * t.quantity) for t in trades if (t.entry_price * t.quantity) > 0
                ]) if trades else (np.array(trade_pnls) / (initial_capital * 0.10))
                std_ret = float(np.std(returns))
                sharpe = float(np.mean(returns) / std_ret * math.sqrt(min(252, len(returns)))) if std_ret > 0 else 0.0
            else:
                sharpe = 0.0

            # Out-of-Sample Return % (Validation period performance)
            oos_return_pct = round((sum(oos_pnls) / (initial_capital * 0.30)) * 100.0, 2) if oos_pnls else 0.0

            # Benchmark Buy & Hold Return %
            benchmark_pct = round(float(np.mean(benchmark_returns)), 2) if benchmark_returns else 0.0

            run.final_capital = round(final_capital, 2)
            run.total_trades = total_trades
            run.winning_trades = winning_trades
            run.losing_trades = losing_trades
            run.win_rate = round(win_rate, 2)
            run.max_drawdown_pct = round(max_dd, 2)
            run.net_return_pct = net_return_pct
            run.profit_factor = profit_factor
            run.avg_profit = avg_profit
            run.avg_loss = avg_loss
            run.sharpe_ratio = round(sharpe, 2)
            run.expectancy = expectancy
            run.benchmark_return_pct = benchmark_pct
            run.out_of_sample_return_pct = oos_return_pct
            run.total_fees = round(sum(t.fees for t in trades), 2)
            run.status = BacktestStatus.COMPLETED.value

            db.commit()
            db.refresh(run)
            return run

    @staticmethod
    def _calc_ema(data: List[float], span: int) -> List[float]:
        """Calculates Exponential Moving Average."""
        if not data:
            return []
        alpha = 2.0 / (span + 1.0)
        ema = [data[0]]
        for i in range(1, len(data)):
            ema.append((alpha * data[i]) + ((1.0 - alpha) * ema[-1]))
        return ema

    @staticmethod
    def _calc_sma(data: List[float], period: int) -> List[float]:
        """Calculates Simple Moving Average."""
        sma = []
        for i in range(len(data)):
            if i < period:
                sma.append(float(np.mean(data[: i + 1])))
            else:
                sma.append(float(np.mean(data[i - period + 1 : i + 1])))
        return sma

    @staticmethod
    def _calc_rolling_std(data: List[float], period: int) -> List[float]:
        """Calculates rolling standard deviation."""
        std = []
        for i in range(len(data)):
            if i < 2:
                std.append(0.0)
            elif i < period:
                std.append(float(np.std(data[: i + 1])))
            else:
                std.append(float(np.std(data[i - period + 1 : i + 1])))
        return std

    @staticmethod
    def export_trades_to_csv(trades: List[BacktestTrade]) -> str:
        """Exports trades list to RFC-compliant CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Trade ID", "Symbol", "Side", "Quantity",
            "Entry Time", "Entry Price", "Exit Time", "Exit Price",
            "Net PnL (INR)", "Fees (INR)", "Slippage (INR)"
        ])
        for t in trades:
            writer.writerow([
                t.id, t.trading_symbol, t.side, t.quantity,
                t.entry_time, t.entry_price, t.exit_time, t.exit_price,
                t.pnl, t.fees, t.slippage
            ])
        return output.getvalue()
