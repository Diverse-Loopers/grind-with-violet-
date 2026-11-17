"use client";

import React, { useState, useEffect } from "react";
import {
  Bot,
  Play,
  Pause,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  Activity,
  Layers,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Zap,
  History,
  Radio,
} from "lucide-react";

interface OptionLeg {
  symbol: string;
  leg_type: string;
  action: string;
  strike_price: number;
  entry_price: number;
  quantity: number;
  lot_size: number;
  moneyness: string;
}

interface TradePlan {
  id: string;
  underlying_symbol: string;
  strategy_type: string;
  sentiment: string;
  spot_price: number;
  legs: OptionLeg[];
  net_debit: number;
  max_loss: number;
  max_profit: number;
  risk_reward_ratio: number;
  breakeven_points: number[];
  margin_required: number;
  confidence_score: number;
  agent_reasoning: string;
  status: string;
  rejection_reason?: string;
  created_at: string;
}

interface ActivePosition {
  id: string;
  plan: TradePlan;
  opened_at: string;
  current_pnl: number;
  pnl_percentage: number;
  trailing_sl: number;
  target_profit: number;
  is_open: boolean;
  closed_at?: string;
  realized_pnl?: number;
}

interface AgentLog {
  timestamp: string;
  agent: string;
  level: string;
  message: string;
}

interface ScanResult {
  symbol: string;
  spot_price: number;
  ma_50: number;
  price_vs_ma: number;
  pct_from_ma: number;
  future_price: number;
  basis: number;
  pcr: number;
  support_strike: number;
  resistance_strike: number;
  sentiment: string;
  volume_trend: string;
  delivery_trend: string;
  is_genuine_trend: boolean;
  timestamp: string;
}

interface AgentStatus {
  auto_execute: boolean;
  kill_switch_engaged: boolean;
  kill_switch_reason?: string;
  active_spreads_count: number;
  closed_spreads_count: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  active_positions: ActivePosition[];
  recent_plans: TradePlan[];
  recent_agent_logs: AgentLog[];
}

export default function AgentsDashboardPage() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [closedHistory, setClosedHistory] = useState<ActivePosition[]>([]);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [activeTab, setActiveTab] = useState<"ACTIVE" | "HISTORY" | "RADAR">("ACTIVE");

  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch("http://localhost:8000/agents/status");
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error("Failed to load agent status", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch("http://localhost:8000/agents/history?limit=100");
      if (res.ok) {
        const data = await res.json();
        setClosedHistory(data.history || []);
      }
    } catch (err) {
      console.error("Failed to load closed history", err);
    }
  };

  const fetchScanResults = async () => {
    try {
      const res = await fetch("http://localhost:8000/agents/scan-results");
      if (res.ok) {
        const data = await res.json();
        setScanResults(data || []);
      }
    } catch (err) {
      console.error("Failed to load scan results", err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchHistory();
    fetchScanResults();
    const interval = setInterval(() => {
      fetchStatus();
      if (activeTab === "HISTORY") fetchHistory();
      if (activeTab === "RADAR") fetchScanResults();
    }, 3000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const triggerScan = async () => {
    setScanning(true);
    setActionMsg("Multi-agent radar pass initiated...");
    try {
      const res = await fetch("http://localhost:8000/agents/scan?simulated_cash=250000", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setActionMsg(`Scan complete: ${data.summary.plans_generated} plans evaluated, ${data.summary.executions_completed} spreads executed.`);
        fetchStatus();
        fetchHistory();
        fetchScanResults();
      }
    } catch {
      setActionMsg("Failed to execute scan pass.");
    } finally {
      setScanning(false);
    }
  };

  const toggleAutoTrade = async () => {
    if (!status) return;
    const nextState = !status.auto_execute;
    try {
      const res = await fetch("http://localhost:8000/agents/toggle-auto-trade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: nextState }),
      });
      if (res.ok) {
        setActionMsg(`Autonomous Execution ${nextState ? "Enabled" : "Paused"}`);
        fetchStatus();
      }
    } catch {
      setActionMsg("Failed to toggle auto-execution.");
    }
  };

  const toggleKillSwitch = async () => {
    if (!status) return;
    const action = status.kill_switch_engaged ? "RESET" : "ENGAGE";
    try {
      const res = await fetch("http://localhost:8000/agents/kill-switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, reason: "User Dashboard Control" }),
      });
      if (res.ok) {
        setActionMsg(action === "ENGAGE" ? "Emergency Kill Switch ENGAGED" : "Kill Switch Reset");
        fetchStatus();
      }
    } catch {
      setActionMsg("Failed to toggle circuit breaker.");
    }
  };

  const closePosition = async (posId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/agents/close/${posId}`, { method: "POST" });
      if (res.ok) {
        setActionMsg(`Position ${posId} squared off.`);
        fetchStatus();
        fetchHistory();
      }
    } catch {
      setActionMsg(`Failed to close position ${posId}`);
    }
  };

  if (loading && !status) {
    return (
      <div className="p-8 text-center text-slate-500 flex items-center justify-center gap-3">
        <RefreshCw className="w-5 h-5 animate-spin text-emerald-600" />
        Connecting to Autonomous Multi-Agent Brain...
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Top Banner & Control Console */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-600 font-bold shadow-xs">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                Autonomous Multi-Agent F&O System
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 font-mono">
                  Playbook Edition
                </span>
              </h1>
              <p className="text-xs text-slate-500">
                Multi-strategy confluence: Bull Call & Bear Put Spreads, Synthetics, Butterfly & Arbitrage.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={triggerScan}
            disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} />
            {scanning ? "Scanning Market..." : "Trigger Multi-Agent Scan"}
          </button>

          <button
            onClick={toggleAutoTrade}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold border transition ${
              status?.auto_execute
                ? "bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100"
                : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200"
            }`}
          >
            {status?.auto_execute ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            Auto-Execution: {status?.auto_execute ? "ACTIVE" : "PAUSED"}
          </button>

          <button
            onClick={toggleKillSwitch}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold border transition ${
              status?.kill_switch_engaged
                ? "bg-rose-600 text-white border-rose-700 hover:bg-rose-700"
                : "bg-slate-50 text-rose-600 border-rose-200 hover:bg-rose-50"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            {status?.kill_switch_engaged ? "KILL SWITCH ENGAGED (RESET)" : "Circuit Breaker"}
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="p-3 bg-slate-900 text-emerald-400 text-xs font-mono rounded-xl border border-slate-800 flex items-center justify-between">
          <span>{actionMsg}</span>
          <button onClick={() => setActionMsg(null)} className="text-slate-400 hover:text-white text-xs">✕</button>
        </div>
      )}

      {/* 4 Agent Specialists Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Agent 1 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Agent 1: Perception</span>
            <Activity className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-sm font-bold text-slate-900">Market Radar Agent</div>
          <p className="text-xs text-slate-500">
            Computes 1H 50 MA, Put-Call Ratio (PCR), and identifies dynamic OI Support & Resistance levels.
          </p>
          <div className="pt-2 text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-1 rounded border border-emerald-100">
            Status: Continuous Scanning (40+ F&O Tickers)
          </div>
        </div>

        {/* Agent 2 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Agent 2: Alpha Brain</span>
            <Layers className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-sm font-bold text-slate-900">Strategy Confluence</div>
          <p className="text-xs text-slate-500">
            Builds Bull Call, Bear Put Spreads, Long Synthetics, Butterfly & Arbitrage. Rejects naked futures.
          </p>
          <div className="pt-2 text-[11px] font-mono text-purple-700 bg-purple-50 px-2 py-1 rounded border border-purple-100">
            Playbook: 6 Active Rules
          </div>
        </div>

        {/* Agent 3 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Agent 3: Guardian</span>
            <ShieldCheck className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-sm font-bold text-slate-900">Chief Risk Governor</div>
          <p className="text-xs text-slate-500">
            Enforces strict capital limits (₹25k max risk), daily drawdown halts, and minimum R:R ratios.
          </p>
          <div className="pt-2 text-[11px] font-mono text-blue-700 bg-blue-50 px-2 py-1 rounded border border-blue-100">
            Circuit Breaker: {status?.kill_switch_engaged ? "HALTED" : "ARMED"}
          </div>
        </div>

        {/* Agent 4 */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Agent 4: Execution</span>
            <Zap className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-sm font-bold text-slate-900">Multi-Leg Manager</div>
          <p className="text-xs text-slate-500">
            Executes atomic spreads, tracks live MTM, and manages dynamic trailing stop-losses.
          </p>
          <div className="pt-2 text-[11px] font-mono text-amber-700 bg-amber-50 px-2 py-1 rounded border border-amber-100">
            Active Spreads: {status?.active_spreads_count || 0}
          </div>
        </div>
      </div>

      {/* PnL Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs text-slate-500 font-medium">Unrealized MTM P&L</div>
          <div className={`text-2xl font-bold mt-1 ${(status?.total_unrealized_pnl || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
            ₹{status?.total_unrealized_pnl?.toFixed(2) || "0.00"}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Currently open trades</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs text-slate-500 font-medium">Realized Spreads P&L</div>
          <div className={`text-2xl font-bold mt-1 ${(status?.total_realized_pnl || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
            ₹{status?.total_realized_pnl?.toFixed(2) || "0.00"}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Locked-in banked profits</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs text-slate-500 font-medium">Closed Positions Audit</div>
          <div className="text-2xl font-bold text-slate-800 mt-1">
            {status?.closed_spreads_count || 0} Spreads Completed
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Exited at profit targets</div>
        </div>
      </div>

      {/* Interactive Multi-Tab Workspace */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Navigation Tabs */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between flex-wrap gap-3 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab("ACTIVE")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition ${
                activeTab === "ACTIVE"
                  ? "bg-white text-emerald-700 shadow-xs border border-slate-200"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
              Live Active Spreads ({status?.active_positions?.length || 0})
            </button>

            <button
              onClick={() => setActiveTab("HISTORY")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition ${
                activeTab === "HISTORY"
                  ? "bg-white text-purple-700 shadow-xs border border-slate-200"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <History className="w-3.5 h-3.5 text-purple-600" />
              Closed Trades Audit ({status?.closed_spreads_count || 0})
            </button>

            <button
              onClick={() => setActiveTab("RADAR")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition ${
                activeTab === "RADAR"
                  ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <Radio className="w-3.5 h-3.5 text-blue-600" />
              Market Radar Scanner ({scanResults.length || 40} Tickers)
            </button>
          </div>

          <span className="text-xs text-slate-400 font-mono">
            {activeTab === "ACTIVE" && "Real-time MTM & Trailing SL Monitoring"}
            {activeTab === "HISTORY" && "Complete Log of All Bought & Sold Contracts"}
            {activeTab === "RADAR" && "Full F&O Universe Technical & OI Screening"}
          </span>
        </div>

        {/* Tab 1: Live Active Spreads */}
        {activeTab === "ACTIVE" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                <tr>
                  <th className="p-3.5 font-semibold">Strategy & Asset</th>
                  <th className="p-3.5 font-semibold">Legs Breakdown</th>
                  <th className="p-3.5 font-semibold">Net Debit / Margin</th>
                  <th className="p-3.5 font-semibold">Max Profit / Loss</th>
                  <th className="p-3.5 font-semibold">Trailing SL / Target</th>
                  <th className="p-3.5 font-semibold">Live MTM P&L</th>
                  <th className="p-3.5 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {status?.active_positions && status.active_positions.length > 0 ? (
                  status.active_positions.map((pos) => (
                    <tr key={pos.id} className="hover:bg-slate-50/70 transition">
                      <td className="p-3.5">
                        <div className="font-bold text-slate-900">{pos.plan.underlying_symbol}</div>
                        <div className="text-[10px] text-purple-700 font-mono bg-purple-50 inline-block px-1.5 py-0.5 rounded border border-purple-200 mt-0.5">
                          {pos.plan.strategy_type}
                        </div>
                      </td>
                      <td className="p-3.5 space-y-1">
                        {pos.plan.legs.map((leg, i) => (
                          <div key={i} className="text-[11px] font-mono flex items-center gap-1.5">
                            <span className={`px-1 py-0.2 rounded font-bold text-[9px] ${leg.action === "BUY" ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>
                              {leg.action}
                            </span>
                            <span>{leg.symbol}</span>
                            <span className="text-slate-400">@{leg.entry_price}</span>
                          </div>
                        ))}
                      </td>
                      <td className="p-3.5">
                        <div className="font-semibold text-slate-900">₹{pos.plan.net_debit.toFixed(2)}</div>
                        <div className="text-[10px] text-slate-400">Margin: ₹{pos.plan.margin_required.toFixed(0)}</div>
                      </td>
                      <td className="p-3.5">
                        <div className="text-emerald-700 font-semibold">+₹{pos.plan.max_profit.toFixed(2)}</div>
                        <div className="text-rose-600 text-[10px]">-₹{pos.plan.max_loss.toFixed(2)} (R:R {pos.plan.risk_reward_ratio}:1)</div>
                      </td>
                      <td className="p-3.5 text-[11px] font-mono">
                        <div className="text-slate-700">SL: ₹{pos.trailing_sl.toFixed(2)}</div>
                        <div className="text-emerald-600">Target: +₹{pos.target_profit.toFixed(2)}</div>
                      </td>
                      <td className="p-3.5">
                        <div className={`font-bold text-sm ${pos.current_pnl >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                          {pos.current_pnl >= 0 ? "+" : ""}₹{pos.current_pnl.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-slate-400">{pos.pnl_percentage.toFixed(1)}% of risk</div>
                      </td>
                      <td className="p-3.5 text-right">
                        <button
                          onClick={() => closePosition(pos.id)}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-semibold bg-slate-100 hover:bg-rose-50 hover:text-rose-600 text-slate-700 border border-slate-200 transition"
                        >
                          Square Off
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="p-10 text-center text-slate-500">
                      <div className="font-semibold text-slate-700 text-sm">No Active Open Positions Right Now</div>
                      <div className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                        All prior spreads reached their profit target or trailing stop-loss and were automatically squared off. Click the <strong>"Closed Trades Audit"</strong> tab above to see the full list of bought and sold stocks.
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: Closed Trades Audit (What was bought & sold) */}
        {activeTab === "HISTORY" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                <tr>
                  <th className="p-3.5 font-semibold">Position ID & Asset</th>
                  <th className="p-3.5 font-semibold">Strategy & Legs Bought / Sold</th>
                  <th className="p-3.5 font-semibold">Entry Net Cost</th>
                  <th className="p-3.5 font-semibold">Exit Target</th>
                  <th className="p-3.5 font-semibold">Realized Profit / Loss</th>
                  <th className="p-3.5 font-semibold">Exit Trigger</th>
                  <th className="p-3.5 font-semibold text-right">Closed At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {closedHistory.length > 0 ? (
                  closedHistory.slice(0, 50).map((pos) => (
                    <tr key={pos.id} className="hover:bg-slate-50/70 transition">
                      <td className="p-3.5">
                        <div className="font-bold text-slate-900">{pos.plan.underlying_symbol}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{pos.id}</div>
                      </td>
                      <td className="p-3.5 space-y-1">
                        <div className="text-[11px] font-semibold text-purple-700 font-mono">
                          {pos.plan.strategy_type}
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {pos.plan.legs.map((leg, i) => (
                            <span key={i} className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                              <span className={leg.action === "BUY" ? "text-emerald-700 font-bold" : "text-rose-700 font-bold"}>
                                {leg.action}
                              </span>{" "}
                              {leg.symbol} @ {leg.entry_price}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="p-3.5">
                        <div className="font-semibold text-slate-800">₹{pos.plan.net_debit.toFixed(2)}</div>
                        <div className="text-[10px] text-slate-400">Margin: ₹{pos.plan.margin_required.toFixed(0)}</div>
                      </td>
                      <td className="p-3.5">
                        <div className="text-slate-700 font-medium">+₹{pos.target_profit.toFixed(2)}</div>
                        <div className="text-[10px] text-slate-400">Max: ₹{pos.plan.max_profit.toFixed(0)}</div>
                      </td>
                      <td className="p-3.5">
                        <div className={`font-bold text-sm ${(pos.realized_pnl || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                          {(pos.realized_pnl || 0) >= 0 ? "+" : ""}₹{(pos.realized_pnl || 0).toFixed(2)}
                        </div>
                        <div className="text-[10px] text-emerald-600 font-medium">Banked to Balance</div>
                      </td>
                      <td className="p-3.5">
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Target Profit Reached
                        </span>
                      </td>
                      <td className="p-3.5 text-right font-mono text-[11px] text-slate-500">
                        {pos.closed_at ? new Date(pos.closed_at).toLocaleTimeString() : "Recent"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-400">
                      No closed trades history available yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 3: Market Radar Scanner (12 Tickers) */}
        {activeTab === "RADAR" && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                <tr>
                  <th className="p-3.5 font-semibold">Symbol</th>
                  <th className="p-3.5 font-semibold">Spot Price</th>
                  <th className="p-3.5 font-semibold">1H 50 MA</th>
                  <th className="p-3.5 font-semibold">Distance to 50 MA</th>
                  <th className="p-3.5 font-semibold">Put-Call Ratio (PCR)</th>
                  <th className="p-3.5 font-semibold">OI Support / Resistance</th>
                  <th className="p-3.5 font-semibold">Volume & Delivery</th>
                  <th className="p-3.5 font-semibold text-right">Radar Sentiment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {scanResults.length > 0 ? (
                  scanResults.map((ticker) => (
                    <tr key={ticker.symbol} className="hover:bg-slate-50/70 transition">
                      <td className="p-3.5 font-bold text-slate-900">{ticker.symbol}</td>
                      <td className="p-3.5 font-semibold text-slate-900">₹{ticker.spot_price.toFixed(2)}</td>
                      <td className="p-3.5 font-mono text-slate-700">₹{ticker.ma_50.toFixed(2)}</td>
                      <td className="p-3.5 font-mono">
                        <span className={ticker.price_vs_ma >= 0 ? "text-emerald-600 font-semibold" : "text-rose-600 font-semibold"}>
                          {ticker.price_vs_ma >= 0 ? "+" : ""}{ticker.price_vs_ma.toFixed(2)} ({ticker.pct_from_ma >= 0 ? "+" : ""}{ticker.pct_from_ma.toFixed(2)}%)
                        </span>
                      </td>
                      <td className="p-3.5 font-mono">
                        <span className={`px-2 py-0.5 rounded font-bold text-[11px] ${ticker.pcr >= 1.05 ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : ticker.pcr <= 0.95 ? "bg-rose-50 text-rose-700 border border-rose-200" : "bg-slate-100 text-slate-700"}`}>
                          {ticker.pcr.toFixed(2)}
                        </span>
                      </td>
                      <td className="p-3.5 font-mono text-[11px]">
                        <span className="text-emerald-700">Supp: ₹{ticker.support_strike}</span>{" "}
                        <span className="text-slate-300">|</span>{" "}
                        <span className="text-rose-700">Res: ₹{ticker.resistance_strike}</span>
                      </td>
                      <td className="p-3.5 text-[11px]">
                        <span className="text-emerald-700 font-medium">Vol ↑ + Del ↑ (Genuine)</span>
                      </td>
                      <td className="p-3.5 text-right">
                        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wide uppercase ${
                          ticker.sentiment === "BULLISH"
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : ticker.sentiment === "BEARISH"
                            ? "bg-rose-100 text-rose-800 border border-rose-300"
                            : "bg-amber-100 text-amber-800 border border-amber-300"
                        }`}>
                          {ticker.sentiment}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-slate-400">
                      Loading market radar analysis...
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Two Columns: Recent Agent Plans & Live Activity Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Formulated Plans */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-600" />
              Recent AI Trade Plans & Math Payoffs
            </h3>
            <span className="text-xs text-slate-400">Confluence Audited</span>
          </div>

          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            {status?.recent_plans && status.recent_plans.length > 0 ? (
              status.recent_plans.slice(-8).reverse().map((plan) => (
                <div key={plan.id} className="p-3.5 rounded-xl border border-slate-100 bg-slate-50/50 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">{plan.underlying_symbol}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-semibold">
                        {plan.strategy_type}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {plan.status === "APPROVED" || plan.status === "EXECUTED" ? (
                        <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> {plan.status}
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200 flex items-center gap-1">
                          <XCircle className="w-3 h-3" /> {plan.status}
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-600 leading-relaxed font-sans">
                    {plan.agent_reasoning}
                  </p>

                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 pt-1 border-t border-slate-200/50">
                    <span>Max Profit: ₹{plan.max_profit.toFixed(0)}</span>
                    <span>Max Loss: ₹{plan.max_loss.toFixed(0)}</span>
                    <span>R:R {plan.risk_reward_ratio}:1</span>
                    <span>Confidence: {(plan.confidence_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-slate-400 text-xs">No recent plans formulated yet.</div>
            )}
          </div>
        </div>

        {/* Live Agent Communication Feed */}
        <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 shadow-sm text-slate-200 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-emerald-400 flex items-center gap-2 font-mono">
              <Bot className="w-4 h-4" />
              Live Agent Activity Feed
            </h3>
            <span className="text-[11px] font-mono text-slate-500">Autonomous Telemetry</span>
          </div>

          <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1 font-mono text-xs">
            {status?.recent_agent_logs && status.recent_agent_logs.length > 0 ? (
              status.recent_agent_logs.slice(-15).reverse().map((log, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/80 space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span className="font-bold text-purple-400">[{log.agent}]</span>
                    <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className={`text-[11px] ${log.level === "CRITICAL" || log.level === "WARNING" ? "text-rose-400" : log.level === "SUCCESS" ? "text-emerald-300" : "text-slate-300"}`}>
                    {log.message}
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-slate-500 text-xs">Agent communication feed is standing by...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
