"use client";

import React, { useState } from "react";
import { useWalletOverview } from "@/hooks/useApi";
import { formatINR, formatPct } from "@/lib/format";
import { postData } from "@/lib/api";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Layers,
  RotateCcw,
  PlusCircle,
  X,
  PieChart,
  ArrowUpRight,
} from "lucide-react";

export const WalletCard: React.FC<{ className?: string }> = ({ className = "" }) => {
  const { data: wallet, mutate: refreshWallet } = useWalletOverview();
  const [showResetModal, setShowResetModal] = useState(false);
  const [customAmount, setCustomAmount] = useState(1000000);
  const [resetting, setResetting] = useState(false);

  const cash = wallet?.cash_balance ?? 1000000;
  const invested = wallet?.invested_amount ?? 0;
  const totalEquity = wallet?.total_equity ?? 1000000;
  const dailyPnl = wallet?.daily_pnl ?? 0;
  const realizedPnl = wallet?.realized_pnl ?? 0;
  const unrealizedPnl = wallet?.unrealized_pnl ?? 0;
  const cashPct = wallet?.allocation?.cash_pct ?? 100;
  const investedPct = wallet?.allocation?.invested_pct ?? 0;

  const handleResetWallet = async (amount: number) => {
    try {
      setResetting(true);
      await postData("/api/portfolio/wallet/reset", { starting_balance: amount });
      await refreshWallet();
      setShowResetModal(false);
    } catch (err: any) {
      alert(`Error resetting wallet: ${err.message}`);
    } finally {
      setResetting(false);
    }
  };

  return (
    <>
      <div className={`bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 rounded-2xl p-6 text-white shadow-md border border-slate-700/80 ${className}`}>
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-700/60 gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <Wallet className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                Virtual Paper Wallet (Simulated)
                <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30 font-semibold">
                  PAPER MODE
                </span>
              </div>
              <h2 className="text-xl font-black font-mono tracking-tight text-white flex items-center gap-2">
                {formatINR(totalEquity)}
                <span className="text-xs font-sans font-normal text-slate-400">Simulated Net Equity</span>
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowResetModal(true)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-xs font-semibold text-slate-200 transition shadow-xs"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
              <span>Reset Capital</span>
            </button>
          </div>
        </div>

        {/* 3 Main Stat Pillars */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 py-4 border-b border-slate-700/60">
          {/* Available Cash */}
          <div className="bg-slate-800/60 p-3.5 rounded-xl border border-slate-700/50">
            <div className="text-[11px] font-semibold text-slate-400 flex items-center justify-between">
              <span>Available Cash in Wallet</span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                {cashPct}% Ready
              </span>
            </div>
            <div className="text-lg font-bold font-mono text-white mt-1">
              {formatINR(cash)}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Liquid funds for new orders
            </div>
          </div>

          {/* Invested in Stocks */}
          <div className="bg-slate-800/60 p-3.5 rounded-xl border border-slate-700/50">
            <div className="text-[11px] font-semibold text-slate-400 flex items-center justify-between">
              <span>Invested in Positions</span>
              <span className="text-[10px] font-mono text-indigo-400 bg-indigo-950/60 px-1.5 py-0.5 rounded border border-indigo-800/40">
                {investedPct}% Active
              </span>
            </div>
            <div className="text-lg font-bold font-mono text-white mt-1">
              {formatINR(invested)}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              {wallet?.open_positions_count ?? 0} active position(s) held
            </div>
          </div>

          {/* Today's P&L */}
          <div className="bg-slate-800/60 p-3.5 rounded-xl border border-slate-700/50">
            <div className="text-[11px] font-semibold text-slate-400 flex items-center justify-between">
              <span>Live Unrealized P&amp;L</span>
              <span className="text-[10px] font-mono text-slate-400">Mark to market</span>
            </div>
            <div className="text-lg font-bold font-mono mt-1 flex items-center gap-1.5">
              <span className={unrealizedPnl >= 0 ? "text-emerald-400" : "text-rose-400"}>
                {unrealizedPnl >= 0 ? `+${formatINR(unrealizedPnl)}` : `-${formatINR(Math.abs(unrealizedPnl))}`}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
              Realized P&amp;L:{" "}
              <span className={realizedPnl >= 0 ? "text-emerald-400" : "text-rose-400"}>
                {realizedPnl >= 0 ? `+${formatINR(realizedPnl)}` : `-${formatINR(Math.abs(realizedPnl))}`}
              </span>
            </div>
          </div>
        </div>

        {/* Capital Allocation Bar */}
        <div className="pt-4">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-2">
            <span className="flex items-center gap-1.5">
              <PieChart className="w-3.5 h-3.5 text-emerald-400" />
              Capital Allocation
            </span>
            <div className="flex items-center gap-3 font-mono text-[11px]">
              <span className="flex items-center gap-1 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                Cash: {cashPct}%
              </span>
              <span className="flex items-center gap-1 text-indigo-400">
                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                Holdings: {investedPct}%
              </span>
            </div>
          </div>
          <div className="w-full bg-slate-700/60 rounded-full h-2.5 overflow-hidden flex shadow-inner">
            <div
              className="bg-emerald-500 h-full transition-all duration-500"
              style={{ width: `${cashPct}%` }}
              title={`Cash: ${cashPct}%`}
            />
            <div
              className="bg-indigo-500 h-full transition-all duration-500"
              style={{ width: `${investedPct}%` }}
              title={`Positions: ${investedPct}%`}
            />
          </div>
        </div>
      </div>

      {/* Reset Capital Modal */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 border border-slate-200 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <RotateCcw className="w-4 h-4 text-emerald-600" />
                Reset Paper Wallet Capital
              </h3>
              <button
                onClick={() => setShowResetModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-500 mt-3 leading-relaxed">
              Select or enter your desired starting virtual capital to test how the algorithm sizes positions and manages risk:
            </p>

            <div className="grid grid-cols-3 gap-2 my-4">
              {[500000, 1000000, 2500000].map((amt) => (
                <button
                  key={amt}
                  onClick={() => setCustomAmount(amt)}
                  className={`py-2 px-1 text-xs font-mono font-bold rounded-xl border transition ${
                    customAmount === amt
                      ? "bg-slate-900 text-white border-slate-900 shadow-xs"
                      : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  ₹{(amt / 100000).toFixed(0)} Lakh
                </button>
              ))}
            </div>

            <div className="space-y-1.5 mb-5">
              <label className="text-xs font-semibold text-slate-700">Custom Amount (INR)</label>
              <input
                type="number"
                step="50000"
                min="50000"
                value={customAmount}
                onChange={(e) => setCustomAmount(parseFloat(e.target.value) || 100000)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowResetModal(false)}
                className="flex-1 py-2.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => handleResetWallet(customAmount)}
                disabled={resetting}
                className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition shadow-xs"
              >
                {resetting ? "Resetting..." : `Set to ${formatINR(customAmount)}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
