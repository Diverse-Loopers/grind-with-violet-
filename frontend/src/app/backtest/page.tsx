"use client";

import React, { useState } from "react";
import { useBacktests } from "@/hooks/useApi";
import { StatCard } from "@/components/StatCard";
import { formatINR, formatPct } from "@/lib/format";
import { postData, API_BASE } from "@/lib/api";
import { Play, Download } from "lucide-react";

export default function BacktestingPage() {
  const { data: runsData, mutate: refreshRuns } = useBacktests();

  const [strategy, setStrategy] = useState("GAP");
  const [symbols, setSymbols] = useState("RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK");
  const [capital, setCapital] = useState(1_000_000);
  const [gapPct, setGapPct] = useState(1.0);
  const [stopLoss, setStopLoss] = useState(1.5);
  const [takeProfit, setTakeProfit] = useState(2.5);
  const [running, setRunning] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  const runs = runsData?.runs || [];
  const activeRun = runs.find((r) => r.id === selectedRunId) || runs[0];

  const handleStartBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    try {
      const symList = symbols
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);

      const res: any = await postData("/api/backtest/run", {
        strategy,
        symbols: symList,
        start_date: "2026-09-01T09:15:00Z",
        end_date: "2026-10-28T15:30:00Z",
        initial_capital: Number(capital),
        gap_threshold_pct: Number(gapPct),
        stop_loss_pct: Number(stopLoss),
        take_profit_pct: Number(takeProfit),
      });

      refreshRuns();
      if (res.id) setSelectedRunId(res.id);
    } catch (err: any) {
      alert(`Backtest failed: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-base font-bold text-slate-900 flex items-center gap-2">
          Historical Backtesting & Strategy Lab
          <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
            EVENT-DRIVEN SIMULATION
          </span>
        </h1>
        <p className="text-xs text-slate-500">
          Chronological candle replay with complete statutory fees (STT, GST, Stamp Duty, Brokerage) and slippage modeling
        </p>
      </div>

      {/* Configuration & Parameter Form */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
          <Play className="w-4 h-4 text-emerald-600" /> Run New Backtest Simulation
        </h2>

        <form onSubmit={handleStartBacktest} className="space-y-4 text-xs font-mono">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-slate-600 block mb-1 font-semibold">Strategy</label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
              >
                <option value="GAP">Strategy B: Price Gap & Momentum</option>
                <option value="SPREAD">Strategy A: Executable Spread</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="text-slate-600 block mb-1 font-semibold">Watchlist Symbols (Comma Separated)</label>
              <input
                type="text"
                value={symbols}
                onChange={(e) => setSymbols(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="text-slate-600 block mb-1 font-semibold">Initial Capital (₹)</label>
              <input
                type="number"
                value={capital}
                onChange={(e) => setCapital(Number(e.target.value))}
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-slate-600 block mb-1 font-semibold">Gap Trigger Threshold %</label>
              <input
                type="number"
                step="0.1"
                value={gapPct}
                onChange={(e) => setGapPct(Number(e.target.value))}
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="text-slate-600 block mb-1 font-semibold">Stop Loss %</label>
              <input
                type="number"
                step="0.1"
                value={stopLoss}
                onChange={(e) => setStopLoss(Number(e.target.value))}
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="text-slate-600 block mb-1 font-semibold">Take Profit %</label>
              <input
                type="number"
                step="0.1"
                value={takeProfit}
                onChange={(e) => setTakeProfit(Number(e.target.value))}
                className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={running}
              className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition flex items-center gap-2 shadow-xs"
            >
              <Play className="w-4 h-4" />
              <span>{running ? "Simulating Market Replay..." : "Execute Backtest"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Selected Run Institutional Report */}
      {activeRun && (
        <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-5 shadow-xs">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                Backtest Run #{activeRun.id} — {activeRun.strategy} Strategy
                <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono font-medium">
                  COMPLETED
                </span>
              </div>
              <div className="text-xs text-slate-500 font-mono">
                {activeRun.start_date.substring(0, 10)} to {activeRun.end_date.substring(0, 10)} • Initial Capital: {formatINR(activeRun.initial_capital)}
              </div>
            </div>

            <a
              href={`${API_BASE}/api/backtest/results/${activeRun.id}/export`}
              download
              className="px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition font-mono border border-slate-200"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </a>
          </div>

          {/* Institutional Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <StatCard
              label="Net Return %"
              value={formatPct(activeRun.net_return_pct)}
              isPositive={(activeRun.net_return_pct ?? 0) > 0}
              isNegative={(activeRun.net_return_pct ?? 0) < 0}
            />
            <StatCard
              label="Win Rate"
              value={formatPct(activeRun.win_rate, false)}
              subValue={`${activeRun.winning_trades}W / ${activeRun.losing_trades}L`}
            />
            <StatCard
              label="Max Drawdown"
              value={formatPct(activeRun.max_drawdown_pct, false)}
              isNegative={(activeRun.max_drawdown_pct ?? 0) > 5}
            />
            <StatCard
              label="Profit Factor"
              value={(activeRun.profit_factor ?? 0).toFixed(2)}
              isPositive={(activeRun.profit_factor ?? 0) > 1.2}
            />
            <StatCard
              label="Sharpe Ratio"
              value={(activeRun.sharpe_ratio ?? 0).toFixed(2)}
              subValue="Annualized"
            />
            <StatCard
              label="Total Fees Paid"
              value={formatINR(activeRun.total_fees)}
              subValue={`${activeRun.total_trades} round trips`}
            />
          </div>
        </div>
      )}

      {/* Backtest Runs History Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <div className="p-4 border-b border-slate-100 font-bold text-sm text-slate-900">
          Historical Backtest Runs Log
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 text-slate-500 uppercase border-b border-slate-200">
              <tr>
                <th className="py-3 px-3">Run ID</th>
                <th className="py-3 px-3">Strategy</th>
                <th className="py-3 px-3 text-right">Trades</th>
                <th className="py-3 px-3 text-right">Win Rate</th>
                <th className="py-3 px-3 text-right">Net Return</th>
                <th className="py-3 px-3 text-right">Max DD</th>
                <th className="py-3 px-3 text-right">Profit Factor</th>
                <th className="py-3 px-3 text-right">Total Fees</th>
                <th className="py-3 px-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.map((r) => {
                const isSelected = r.id === selectedRunId;
                return (
                  <tr
                    key={r.id}
                    onClick={() => setSelectedRunId(r.id)}
                    className={`hover:bg-slate-50/80 cursor-pointer transition ${
                      isSelected ? "bg-slate-100/80" : ""
                    }`}
                  >
                    <td className="py-3 px-3 font-bold text-emerald-600">#{r.id}</td>
                    <td className="py-3 px-3 text-slate-700">{r.strategy}</td>
                    <td className="py-3 px-3 text-right text-slate-700">{r.total_trades}</td>
                    <td className="py-3 px-3 text-right text-slate-700">{formatPct(r.win_rate, false)}</td>
                    <td
                      className={`py-3 px-3 text-right font-bold ${
                        (r.net_return_pct ?? 0) > 0 ? "text-emerald-600" : (r.net_return_pct ?? 0) < 0 ? "text-rose-600" : "text-slate-600"
                      }`}
                    >
                      {formatPct(r.net_return_pct)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-700">{formatPct(r.max_drawdown_pct, false)}</td>
                    <td className="py-3 px-3 text-right text-slate-700">{(r.profit_factor ?? 0).toFixed(2)}</td>
                    <td className="py-3 px-3 text-right text-slate-500">{formatINR(r.total_fees)}</td>
                    <td className="py-3 px-3 text-center">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {r.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
