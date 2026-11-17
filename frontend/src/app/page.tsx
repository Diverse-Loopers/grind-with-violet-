"use client";

import React, { useState } from "react";
import { useDashboardOverview, useSignals, useEquityCurve } from "@/hooks/useApi";
import { StatCard } from "@/components/StatCard";
import { ModeBadge } from "@/components/ModeBadge";
import { DataQualityBadge } from "@/components/DataQualityBadge";
import { EquityChart } from "@/components/EquityChart";
import { WalletCard } from "@/components/WalletCard";
import { LiveBotActivityFeed } from "@/components/LiveBotActivityFeed";
import { StockCandleChartModal } from "@/components/StockCandleChartModal";
import { GrowwConnectModal } from "@/components/GrowwConnectModal";
import { formatINR, formatPct, formatISTTime } from "@/lib/format";
import {
  Wallet,
  TrendingUp,
  Activity,
  Layers,
  CheckCircle2,
  XCircle,
  Play,
  Link2,
  ExternalLink,
} from "lucide-react";
import { postData } from "@/lib/api";

export default function DashboardPage() {
  const { data: overview, mutate: refreshOverview } = useDashboardOverview();
  const { data: signalsData } = useSignals(undefined, undefined);
  const { data: equityData } = useEquityCurve();

  const [scanning, setScanning] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [selectedChartSymbol, setSelectedChartSymbol] = useState<string | null>(null);

  const handleTriggerScan = async () => {
    try {
      setScanning(true);
      await postData("/api/scanner/scan-now");
      refreshOverview();
    } catch (e) {
      console.error(e);
    } finally {
      setScanning(false);
    }
  };

  const cash = overview?.cash_balance ?? 1_000_000;
  const equity = overview?.portfolio_equity ?? 1_000_000;
  const realizedPnl = overview?.realized_pnl ?? 0;
  const unrealizedPnl = overview?.unrealized_pnl ?? 0;
  const activePositions = overview?.active_positions ?? 0;
  const detectedCount = overview?.signals_detected ?? 0;
  const rejectedCount = overview?.signals_rejected ?? 0;
  const mode = overview?.mode ?? "DEMO";
  const isGrowwLive = mode === "PAPER" || mode === "LIVE";

  const recentSignals = signalsData?.signals?.slice(0, 6) || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner Alert */}
      {!isGrowwLive ? (
        <div className="p-4 rounded-2xl bg-purple-50 border border-purple-200/80 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-purple-500 animate-pulse" />
            <div>
              <div className="text-sm font-bold text-purple-950">
                Demonstration Mode Active — Synthetic Indian Equity Feeds
              </div>
              <div className="text-xs text-purple-700/80">
                You are currently running with synthetic quotes. Connect your official Groww API to test with live NSE market data.
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowConnectModal(true)}
              className="px-3.5 py-2 rounded-xl bg-purple-700 hover:bg-purple-800 text-xs font-semibold text-white flex items-center gap-1.5 transition shadow-xs"
            >
              <Link2 className="w-3.5 h-3.5" />
              <span>Connect Real Groww</span>
            </button>
            <button
              onClick={handleTriggerScan}
              disabled={scanning}
              className="px-3.5 py-2 rounded-xl bg-white hover:bg-slate-50 border border-purple-200 text-xs font-semibold text-purple-900 flex items-center gap-1.5 transition"
            >
              <Play className="w-3.5 h-3.5" />
              {scanning ? "Scanning..." : "Trigger Scan Pass"}
            </button>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <div>
              <div className="text-sm font-bold text-emerald-950">
                Connected to Groww Official Trading API — Live Market Data Feed
              </div>
              <div className="text-xs text-emerald-700">
                Real-time quotes are streaming from Groww. Executions are simulated in Paper mode with realistic brokerage and taxes.
              </div>
            </div>
          </div>
          <button
            onClick={() => setShowConnectModal(true)}
            className="px-3.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-emerald-300 text-xs font-semibold text-emerald-900 flex items-center gap-1.5 transition"
          >
            <Link2 className="w-3.5 h-3.5" />
            <span>Manage Groww Token</span>
          </button>
        </div>
      )}

      {/* Wallet Capital Section */}
      <WalletCard />

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Portfolio Equity"
          value={formatINR(equity)}
          subValue={`Cash: ${formatINR(cash)}`}
          icon={<Wallet className="w-4 h-4" />}
        />
        <StatCard
          label="Realized P&L"
          value={formatINR(realizedPnl)}
          isPositive={realizedPnl > 0}
          isNegative={realizedPnl < 0}
          subValue={`Cumulative Return: ${formatPct((realizedPnl / 1000000) * 100)}`}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <StatCard
          label="Unrealized P&L"
          value={formatINR(unrealizedPnl)}
          isPositive={unrealizedPnl > 0}
          isNegative={unrealizedPnl < 0}
          subValue="Mark-to-market positions"
          icon={<Activity className="w-4 h-4" />}
        />
        <StatCard
          label="Active Positions"
          value={activePositions}
          subValue={`${detectedCount} signals generated (${rejectedCount} rejected)`}
          icon={<Layers className="w-4 h-4" />}
        />
      </div>

      {/* Equity Curve & Live Bot Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Chart */}
        <div className="lg:col-span-1 bg-white border border-slate-200 rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Simulated Equity Curve</h2>
              <p className="text-xs text-slate-500">Chronological paper equity development</p>
            </div>
            <div className="text-xs font-mono text-emerald-700 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-200">
              ₹10L Base
            </div>
          </div>
          <EquityChart data={equityData?.data || []} height={260} />
        </div>

        {/* Live Bot Activity Stream */}
        <div className="lg:col-span-2">
          <LiveBotActivityFeed onSelectSymbol={(sym) => setSelectedChartSymbol(sym)} />
        </div>
      </div>

      {/* Recent Signals Section */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Recent Candidate Signals</h2>
            <p className="text-xs text-slate-500">
              Evaluated by Strategy A (Spread), Strategy B (Gap), and Strategy C (Pairs Research)
            </p>
          </div>
          <a href="/scanner" className="text-xs text-emerald-700 font-semibold hover:underline">
            View all signals in scanner →
          </a>
        </div>

        {recentSignals.length === 0 ? (
          <div className="py-10 text-center text-xs text-slate-500">
            No signals generated yet. Click "Trigger Scan Pass" above to scan the market watchlist.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-mono uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-3">Symbol</th>
                  <th className="py-3 px-3">Strategy</th>
                  <th className="py-3 px-3">Side</th>
                  <th className="py-3 px-3">Price</th>
                  <th className="py-3 px-3">Gross Edge</th>
                  <th className="py-3 px-3">Est. Cost</th>
                  <th className="py-3 px-3">Net Edge</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Reason / Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {recentSignals.map((s) => {
                  const isAccepted = s.status === "ACCEPTED";
                  return (
                    <tr
                      key={s.id}
                      onClick={() => setSelectedChartSymbol(s.trading_symbol)}
                      className="hover:bg-slate-50 transition cursor-pointer"
                    >
                      <td className="py-3 px-3 font-bold text-slate-900 flex items-center gap-1.5">
                        <span className="hover:text-emerald-700 hover:underline">{s.trading_symbol}</span>
                        <span className="text-[10px] text-emerald-600 font-normal">📈 Chart</span>
                      </td>
                      <td className="py-3 px-3 text-slate-600">{s.strategy}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            s.signal_type === "BUY"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}
                        >
                          {s.signal_type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-800">{formatINR(s.entry_price)}</td>
                      <td className="py-3 px-3 text-slate-600">{formatPct(s.expected_edge_pct)}</td>
                      <td className="py-3 px-3 text-slate-500">{formatPct(s.estimated_cost_pct, false)}</td>
                      <td
                        className={`py-3 px-3 font-semibold ${
                          (s.net_edge_pct ?? 0) > 0 ? "text-emerald-600" : "text-slate-500"
                        }`}
                      >
                        {formatPct(s.net_edge_pct)}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] font-semibold ${
                            isAccepted ? "text-emerald-700" : "text-amber-700"
                          }`}
                        >
                          {isAccepted ? (
                            <>
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" /> ACCEPTED
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3 h-3 text-amber-600" /> REJECTED
                            </>
                          )}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-[11px] text-slate-600 max-w-xs truncate font-sans">
                        {isAccepted ? s.reason : s.rejection_reason || s.reason}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Groww Connection Modal */}
      <GrowwConnectModal
        isOpen={showConnectModal}
        onClose={() => setShowConnectModal(false)}
        onConnected={() => refreshOverview()}
      />

      {/* Stock Candlestick & Trades Chart Modal */}
      {selectedChartSymbol && (
        <StockCandleChartModal
          symbol={selectedChartSymbol}
          onClose={() => setSelectedChartSymbol(null)}
          onTradeExecuted={() => refreshOverview()}
        />
      )}
    </div>
  );
}
