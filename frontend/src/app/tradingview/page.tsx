"use client";

import React, { useState } from "react";
import {
  useGlobalOverview,
  useGlobalPositions,
  useGlobalStrategies,
  useTradingViewAlerts,
  useTradingViewPineScript,
} from "@/hooks/useApi";
import { LiveXauusdChart } from "@/components/LiveXauusdChart";
import { postData } from "@/lib/api";
import {
  Zap,
  Globe,
  Clock,
  CheckCircle,
  Copy,
  Play,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  Sliders,
  Terminal,
  Activity,
  DollarSign,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  X,
  Code2,
  RefreshCw,
} from "lucide-react";
import { MaxProfitResult } from "@/types";

export default function TradingViewEnginePage() {
  const { data: overview, mutate: refreshOverview } = useGlobalOverview();
  const { data: positionsData, mutate: refreshPositions } = useGlobalPositions();
  const { data: stratData, mutate: refreshStrategies } = useGlobalStrategies();
  const { data: alertsData, mutate: refreshAlerts } = useTradingViewAlerts();
  const { data: pineScriptData } = useTradingViewPineScript();

  // Local state
  const [activeTab, setActiveTab] = useState<"positions" | "alerts" | "optimizer">("positions");
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedScript, setCopiedScript] = useState(false);
  const [showPineModal, setShowPineModal] = useState(false);
  const [orderSide, setOrderSide] = useState<"BUY" | "SELL">("BUY");
  const [orderLots, setOrderLots] = useState(0.10);
  const [orderSL, setOrderSL] = useState("");
  const [orderTP, setOrderTP] = useState("");
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [orderFeedback, setOrderFeedback] = useState<string | null>(null);

  // Optimizer state
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizationResult, setOptimizationResult] = useState<MaxProfitResult | null>(null);

  // Passphrase state
  const [passphraseInput, setPassphraseInput] = useState("");
  const [savingPassphrase, setSavingPassphrase] = useState(false);

  const quote = overview?.quote;
  const account = overview?.account;
  const openPositions = positionsData?.open_positions || [];
  const closedPositions = positionsData?.closed_positions || [];
  const alerts = alertsData || [];
  const strategies = stratData?.strategies || [];
  const confluenceScore = overview?.confluence_score ?? 0;
  const sentiment = overview?.market_sentiment ?? "NEUTRAL";

  const webhookUrl = pineScriptData?.webhook_url || "http://localhost:8000/api/tradingview/webhook";

  // Copy webhook URL
  const handleCopyUrl = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  // Copy Pine Script
  const handleCopyPineScript = () => {
    if (pineScriptData?.pinescript) {
      navigator.clipboard.writeText(pineScriptData.pinescript);
      setCopiedScript(true);
      setTimeout(() => setCopiedScript(false), 2000);
    }
  };

  // Send test alert
  const handleSendTestAlert = async () => {
    try {
      await postData("/api/tradingview/test-alert", {
        ticker: "XAUUSD",
        action: "BUY",
        quantity: 0.10,
        strategy: "UI Interactive Test Alert",
      });
      refreshAlerts();
      refreshPositions();
      refreshOverview();
      setOrderFeedback("✓ Test TradingView alert delivered and executed successfully!");
      setTimeout(() => setOrderFeedback(null), 3500);
    } catch (err: any) {
      setOrderFeedback(`❌ Test alert error: ${err.message}`);
    }
  };

  // Update passphrase & settings
  const handleSaveSettings = async () => {
    setSavingPassphrase(true);
    try {
      await postData("/api/tradingview/settings", {
        passphrase: passphraseInput,
      });
      setOrderFeedback("✓ TradingView passphrase saved successfully");
      setTimeout(() => setOrderFeedback(null), 3000);
    } catch (err: any) {
      setOrderFeedback(`❌ Error saving: ${err.message}`);
    } finally {
      setSavingPassphrase(false);
    }
  };

  // Toggle strategy
  const handleToggleStrategy = async (strategyId: string, currentEnabled: boolean) => {
    try {
      await postData("/api/global/strategies/toggle", {
        strategy_id: strategyId,
        enabled: !currentEnabled,
      });
      refreshStrategies();
    } catch (e: any) {
      console.error(e);
    }
  };

  // Toggle auto-confluence trading
  const handleToggleAutoConfluence = async (current: boolean) => {
    try {
      await postData("/api/global/strategies/toggle", {
        auto_confluence_trade: !current,
      });
      refreshStrategies();
      refreshOverview();
    } catch (e: any) {
      console.error(e);
    }
  };

  // Place manual order
  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingOrder(true);
    setOrderFeedback(null);
    try {
      await postData("/api/global/order", {
        symbol: "XAUUSD",
        side: orderSide,
        lots: Number(orderLots),
        sl: orderSL ? parseFloat(orderSL) : undefined,
        tp: orderTP ? parseFloat(orderTP) : undefined,
      });
      refreshPositions();
      refreshOverview();
      setOrderFeedback(`✓ Successfully opened ${orderSide} position for ${orderLots} lots of XAU/USD`);
      setOrderSL("");
      setOrderTP("");
    } catch (err: any) {
      setOrderFeedback(`❌ Order error: ${err.message}`);
    } finally {
      setIsSubmittingOrder(false);
      setTimeout(() => setOrderFeedback(null), 4000);
    }
  };

  // Close position
  const handleClosePosition = async (posId: string) => {
    try {
      await postData("/api/global/close-position", { position_id: posId });
      refreshPositions();
      refreshOverview();
    } catch (err: any) {
      alert(`Error closing position: ${err.message}`);
    }
  };

  // Run Max Profit Optimizer
  const handleRunOptimizer = async () => {
    setIsOptimizing(true);
    try {
      const res = await postData<MaxProfitResult>("/api/global/optimize-max-profit");
      setOptimizationResult(res);
      setActiveTab("optimizer");
    } catch (err: any) {
      alert(`Optimization error: ${err.message}`);
    } finally {
      setIsOptimizing(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* ── Top Hero Banner ─────────────────────────────────── */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 text-white shadow-lg border border-indigo-900/40 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            <span className="text-xs uppercase tracking-wider font-mono font-semibold text-emerald-400 bg-emerald-950/70 px-2.5 py-0.5 rounded-full border border-emerald-800/60">
              24/7 Global Engine Active
            </span>
            <span className="text-xs font-mono text-slate-400 bg-slate-800/80 px-2.5 py-0.5 rounded-full border border-slate-700">
              {overview?.session || "London & NY Overlap"}
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight flex items-center gap-2">
            XAU/USD Gold & TradingView Engine
          </h1>
          <p className="text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
            Continuous round-the-clock trading execution, TradingView webhook bridge, and multi-strategy profit maximization algorithm.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleRunOptimizer}
            disabled={isOptimizing}
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-slate-950 font-bold text-xs rounded-xl shadow-md transition disabled:opacity-50"
          >
            <Zap className={`w-4 h-4 ${isOptimizing ? "animate-spin" : ""}`} />
            <span>{isOptimizing ? "Optimizing Strategies..." : "Run Max Profit Optimizer"}</span>
          </button>

          <button
            onClick={() => setShowPineModal(true)}
            className="flex items-center gap-2 px-3.5 py-2.5 bg-slate-800/90 hover:bg-slate-700 text-white font-semibold text-xs rounded-xl border border-slate-700 shadow-sm transition"
          >
            <Code2 className="w-4 h-4 text-emerald-400" />
            <span>TradingView Pine Script</span>
          </button>
        </div>
      </div>

      {/* ── Key Stat Cards ──────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* XAU/USD Gold Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-700">XAU/USD (Gold Spot)</span>
            <span className="font-mono text-[11px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded border border-amber-200">
              Spread {quote?.spread_pips ?? 3.0} pips
            </span>
          </div>
          <div className="my-3">
            <div className="text-2xl font-black text-slate-900 font-mono tracking-tight">
              ${quote?.ltp ? quote.ltp.toFixed(2) : "2,748.50"}
            </div>
            <div className="flex items-center gap-2 text-xs font-semibold mt-1">
              <span className={`flex items-center ${(quote?.change_24h ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                {(quote?.change_24h ?? 0) >= 0 ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                {quote?.change_24h ? (quote.change_24h >= 0 ? `+$${quote.change_24h.toFixed(2)}` : `-$${Math.abs(quote.change_24h).toFixed(2)}`) : "+$12.50"}
                {" "}({quote?.change_24h_pct ? (quote.change_24h_pct >= 0 ? `+${quote.change_24h_pct.toFixed(2)}%` : `${quote.change_24h_pct.toFixed(2)}%`) : "+0.45%"})
              </span>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 flex justify-between font-mono pt-2 border-t border-slate-100">
            <span>Bid: ${quote?.bid?.toFixed(2) ?? "--"}</span>
            <span>Ask: ${quote?.ask?.toFixed(2) ?? "--"}</span>
          </div>
        </div>

        {/* Account USD Equity Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-700">24/7 Account Equity</span>
            <span className="font-mono text-[11px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded">
              Leverage 1:{account?.leverage || 50}
            </span>
          </div>
          <div className="my-3">
            <div className="text-2xl font-black text-slate-900 font-mono tracking-tight">
              ${account?.equity ? account.equity.toLocaleString(undefined, { minimumFractionDigits: 2 }) : "10,000.00"}
            </div>
            <div className="text-xs text-slate-500 mt-1 flex items-center gap-1 font-mono">
              Free Margin: <span className="font-semibold text-slate-800">${account?.free_margin?.toFixed(2) || "10,000.00"}</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 flex justify-between font-mono pt-2 border-t border-slate-100">
            <span>Margin Used: ${account?.margin_used?.toFixed(2) || "0.00"}</span>
            <span className="text-emerald-600 font-semibold">Total P&L: ${account?.total_pnl ? (account.total_pnl >= 0 ? `+${account.total_pnl.toFixed(2)}` : account.total_pnl.toFixed(2)) : "$0.00"}</span>
          </div>
        </div>

        {/* Confluence & Sentiment Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-700">Multi-Strategy Confluence</span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
              sentiment.includes("BUY") ? "bg-emerald-100 text-emerald-800 border border-emerald-300" :
              sentiment.includes("SELL") ? "bg-rose-100 text-rose-800 border border-rose-300" :
              "bg-slate-100 text-slate-700 border border-slate-300"
            }`}>
              {sentiment.replace("_", " ")}
            </span>
          </div>
          <div className="my-3">
            <div className="text-2xl font-black font-mono tracking-tight flex items-center gap-2">
              <span className={confluenceScore >= 0 ? "text-emerald-600" : "text-rose-600"}>
                {confluenceScore >= 0 ? `+${confluenceScore.toFixed(0)}%` : `${confluenceScore.toFixed(0)}%`}
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 mt-2 overflow-hidden flex">
              <div
                className={`h-full transition-all duration-500 ${confluenceScore >= 0 ? "bg-emerald-500" : "bg-rose-500"}`}
                style={{ width: `${Math.min(100, Math.abs(confluenceScore))}%` }}
              />
            </div>
          </div>
          <div className="text-[11px] text-slate-500 flex justify-between font-mono pt-2 border-t border-slate-100">
            <span>Signals: {overview?.active_signals_count ?? 0} active</span>
            <span>Target: &gt;65% edge</span>
          </div>
        </div>

        {/* TradingView Webhook Status Card */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="font-semibold text-slate-700">TradingView Gateway</span>
            <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-600 font-semibold">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              Ready
            </span>
          </div>
          <div className="my-3">
            <div className="text-lg font-bold text-slate-900 font-mono tracking-tight">
              Webhook Listener
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {alerts.length} alert(s) processed
            </div>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
            <button
              onClick={handleSendTestAlert}
              className="text-[11px] font-semibold text-emerald-700 hover:text-emerald-800 flex items-center gap-1 transition"
            >
              <Play className="w-3 h-3 fill-emerald-600" />
              <span>Test Alert Trigger</span>
            </button>
            <span className="text-[10px] text-slate-400 font-mono">Port 8000</span>
          </div>
        </div>
      </div>

      {/* ── TradingView Connection & Webhook Hub ──────────────── */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-emerald-600" />
              Connect TradingView Account to 24/7 Engine
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              TradingView sends automated alerts via Webhook. Paste this URL and Passphrase into your TradingView Alert setup.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyUrl}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition border border-slate-300"
            >
              <Copy className="w-3.5 h-3.5" />
              <span>{copiedUrl ? "Copied Webhook URL!" : "Copy Webhook URL"}</span>
            </button>
            <button
              onClick={() => setShowPineModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-semibold rounded-lg transition border border-emerald-300"
            >
              <Code2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Copy Pine Script</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-5">
          {/* Webhook Endpoint Box */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-700">Webhook Listener URL</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={webhookUrl}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800"
              />
            </div>
            <p className="text-[11px] text-slate-400">TradingView will POST JSON alert signals here.</p>
          </div>

          {/* Webhook Passphrase Box */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-700">Security Passphrase</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={passphraseInput}
                onChange={(e) => setPassphraseInput(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
              <button
                onClick={handleSaveSettings}
                disabled={savingPassphrase}
                className="px-3 py-2 bg-slate-900 text-white text-xs font-semibold rounded-xl hover:bg-slate-800 transition shrink-0"
              >
                {savingPassphrase ? "..." : "Save"}
              </button>
            </div>
            <p className="text-[11px] text-slate-400">Included in alert JSON to authenticate your requests.</p>
          </div>

          {/* Quick Setup Instructions */}
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200 text-xs space-y-1 text-slate-600">
            <div className="font-semibold text-slate-800 flex items-center gap-1">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
              3-Step Setup in TradingView:
            </div>
            <ol className="list-decimal list-inside text-[11px] space-y-0.5 text-slate-600">
              <li>Open XAUUSD chart in TradingView</li>
              <li>Click <strong>Alert</strong> → Check <strong>Webhook URL</strong></li>
              <li>Paste the URL above & copy our Pine Script</li>
            </ol>
          </div>
        </div>

        {orderFeedback && (
          <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 font-semibold flex items-center justify-between">
            <span>{orderFeedback}</span>
            <button onClick={() => setOrderFeedback(null)} className="text-slate-400 hover:text-slate-600">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* ── 24/7 Live XAU/USD Candlestick Chart ────────────── */}
      <LiveXauusdChart height={340} />

      {/* ── Max Profit Strategy Suite & Confluence Console ───── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Strategies & Confluence Engine */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-600" />
                  24/7 Max Profit Multi-Strategy Suite
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Strategies run concurrently on XAU/USD. When confluence aligns, edge is maximized.
                </p>
              </div>

              {/* Auto-Confluence Execution Toggle */}
              <div className="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
                <span className="text-xs font-semibold text-slate-700">Auto-Trade Confluence:</span>
                <button
                  onClick={() => handleToggleAutoConfluence(stratData?.auto_confluence_trade ?? false)}
                  className={`w-9 h-5 rounded-full transition-colors relative flex items-center p-0.5 ${
                    stratData?.auto_confluence_trade ? "bg-emerald-500" : "bg-slate-300"
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${
                      stratData?.auto_confluence_trade ? "translate-x-4" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Strategy Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {strategies.map((strat) => (
                <div
                  key={strat.id}
                  className={`p-4 rounded-xl border transition ${
                    strat.enabled ? "bg-white border-slate-200 shadow-xs" : "bg-slate-50 border-slate-200 opacity-60"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-xs font-bold text-slate-900">{strat.name}</div>
                      <div className="text-[11px] text-slate-500 mt-1 leading-relaxed">{strat.description}</div>
                    </div>
                    <button
                      onClick={() => handleToggleStrategy(strat.id, strat.enabled)}
                      className={`text-[10px] font-bold px-2 py-0.5 rounded border transition ${
                        strat.enabled
                          ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                          : "bg-slate-200 text-slate-600 border-slate-300"
                      }`}
                    >
                      {strat.enabled ? "ENABLED" : "PAUSED"}
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Live Strategy Signals */}
            {stratData?.active_signals && stratData.active_signals.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <div className="text-xs font-bold text-slate-700 mb-2">Live Strategy Signals Active:</div>
                <div className="space-y-2">
                  {stratData.active_signals.map((sig: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                            sig.action === "BUY"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {sig.action}
                        </span>
                        <span className="font-semibold text-slate-800">{sig.strategy_name}</span>
                        <span className="text-slate-400">@ ${sig.price}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        TP: ${sig.tp} • SL: ${sig.sl}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Col: Instant Trade Panel */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-1">
              <DollarSign className="w-4 h-4 text-emerald-600" />
              Quick Gold (XAU/USD) Execution
            </h3>
            <p className="text-xs text-slate-500 mb-4">Manual or automated paper order entry.</p>

            {/* Buy / Sell Toggle */}
            <div className="grid grid-cols-2 gap-2 p-1 bg-slate-100 rounded-xl mb-4">
              <button
                type="button"
                onClick={() => setOrderSide("BUY")}
                className={`py-2 text-xs font-bold rounded-lg transition ${
                  orderSide === "BUY" ? "bg-emerald-600 text-white shadow-xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                BUY / LONG
              </button>
              <button
                type="button"
                onClick={() => setOrderSide("SELL")}
                className={`py-2 text-xs font-bold rounded-lg transition ${
                  orderSide === "SELL" ? "bg-rose-600 text-white shadow-xs" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                SELL / SHORT
              </button>
            </div>

            <form onSubmit={handlePlaceOrder} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">Lot Size</label>
                <div className="grid grid-cols-4 gap-1.5 mb-2">
                  {[0.01, 0.05, 0.10, 0.50].map((l) => (
                    <button
                      key={l}
                      type="button"
                      onClick={() => setOrderLots(l)}
                      className={`py-1 text-xs font-mono font-medium rounded-lg border ${
                        orderLots === l
                          ? "bg-slate-900 text-white border-slate-900"
                          : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                      }`}
                    >
                      {l} lot
                    </button>
                  ))}
                </div>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="10.0"
                  value={orderLots}
                  onChange={(e) => setOrderLots(parseFloat(e.target.value) || 0.01)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Take Profit ($)</label>
                  <input
                    type="number"
                    step="0.10"
                    placeholder="Optional TP"
                    value={orderTP}
                    onChange={(e) => setOrderTP(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5 text-xs font-mono text-slate-800"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-slate-600 block mb-1">Stop Loss ($)</label>
                  <input
                    type="number"
                    step="0.10"
                    placeholder="Optional SL"
                    value={orderSL}
                    onChange={(e) => setOrderSL(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5 text-xs font-mono text-slate-800"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmittingOrder}
                className={`w-full py-2.5 rounded-xl text-white font-bold text-xs shadow-sm transition mt-2 ${
                  orderSide === "BUY" ? "bg-emerald-600 hover:bg-emerald-700" : "bg-rose-600 hover:bg-rose-700"
                }`}
              >
                {isSubmittingOrder ? "Executing..." : `Place ${orderSide} Order (${orderLots} Lots)`}
              </button>
            </form>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-400">
            Gold contract: 1.00 lot = 100 oz. Mini: 0.10 lot = 10 oz. Margin requirement calculated dynamically at 1:{account?.leverage || 50}.
          </div>
        </div>
      </div>

      {/* ── Tabs for Positions, Optimizer, and Alerts ─────────── */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="border-b border-slate-200 px-6 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <button
              onClick={() => setActiveTab("positions")}
              className={`py-4 text-xs font-bold border-b-2 transition ${
                activeTab === "positions"
                  ? "border-emerald-600 text-emerald-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              Active Positions ({openPositions.length})
            </button>
            <button
              onClick={() => setActiveTab("optimizer")}
              className={`py-4 text-xs font-bold border-b-2 transition flex items-center gap-1.5 ${
                activeTab === "optimizer"
                  ? "border-emerald-600 text-emerald-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              <span>Max Profit Optimizer Results</span>
            </button>
            <button
              onClick={() => setActiveTab("alerts")}
              className={`py-4 text-xs font-bold border-b-2 transition ${
                activeTab === "alerts"
                  ? "border-emerald-600 text-emerald-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              TradingView Webhook Logs ({alerts.length})
            </button>
          </div>

          <button
            onClick={() => {
              refreshPositions();
              refreshAlerts();
              refreshOverview();
            }}
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 py-2 font-medium"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>

        {/* Tab 1: Positions */}
        {activeTab === "positions" && (
          <div className="p-6">
            {openPositions.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-xs">
                No active 24/7 positions currently open. Use the Quick Order panel or send a TradingView webhook alert to open trades.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3">Position ID</th>
                      <th className="py-2.5 px-3">Symbol</th>
                      <th className="py-2.5 px-3">Side</th>
                      <th className="py-2.5 px-3">Lots</th>
                      <th className="py-2.5 px-3">Entry Price</th>
                      <th className="py-2.5 px-3">Current</th>
                      <th className="py-2.5 px-3">TP / SL</th>
                      <th className="py-2.5 px-3">Pip Gain</th>
                      <th className="py-2.5 px-3">Unrealized P&L</th>
                      <th className="py-2.5 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {openPositions.map((p) => (
                      <tr key={p.id} className="hover:bg-slate-50/60">
                        <td className="py-3 px-3 font-semibold text-slate-800">{p.id}</td>
                        <td className="py-3 px-3 font-bold text-slate-900">{p.symbol}</td>
                        <td className="py-3 px-3">
                          <span
                            className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                              p.side === "BUY"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-rose-100 text-rose-800"
                            }`}
                          >
                            {p.side}
                          </span>
                        </td>
                        <td className="py-3 px-3">{p.lots.toFixed(2)}</td>
                        <td className="py-3 px-3">${p.entry_price.toFixed(2)}</td>
                        <td className="py-3 px-3">${p.current_price.toFixed(2)}</td>
                        <td className="py-3 px-3 text-[11px] text-slate-500">
                          {p.tp ? `TP: $${p.tp}` : "--"} / {p.sl ? `SL: $${p.sl}` : "--"}
                        </td>
                        <td className="py-3 px-3">
                          <span className={p.pip_gain >= 0 ? "text-emerald-600" : "text-rose-600"}>
                            {p.pip_gain >= 0 ? `+${p.pip_gain}` : p.pip_gain} pips
                          </span>
                        </td>
                        <td className="py-3 px-3 font-bold text-sm">
                          <span className={p.unrealized_pnl >= 0 ? "text-emerald-600" : "text-rose-600"}>
                            {p.unrealized_pnl >= 0 ? `+$${p.unrealized_pnl.toFixed(2)}` : `-$${Math.abs(p.unrealized_pnl).toFixed(2)}`}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => handleClosePosition(p.id)}
                            className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg text-[11px] border border-slate-300 transition"
                          >
                            Close
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Max Profit Optimizer Results */}
        {activeTab === "optimizer" && (
          <div className="p-6 space-y-6">
            {!optimizationResult ? (
              <div className="text-center py-12">
                <Zap className="w-8 h-8 text-amber-500 mx-auto mb-2" />
                <h4 className="text-sm font-bold text-slate-800">Max Profit Optimization Engine</h4>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">
                  Run multi-strategy historical simulation across XAU/USD data to find the highest-profit configuration, win rate, and optimal leverage.
                </p>
                <button
                  onClick={handleRunOptimizer}
                  disabled={isOptimizing}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-xl shadow-xs transition"
                >
                  {isOptimizing ? "Running Optimization..." : "Execute Strategy Optimizer Now"}
                </button>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Result Highlight Banner */}
                <div className="p-5 rounded-2xl bg-amber-50 border border-amber-200">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-900 uppercase tracking-wider mb-1">
                    <Zap className="w-4 h-4 text-amber-600" />
                    Optimal Configuration Discovered
                  </div>
                  <div className="text-sm text-amber-950 font-medium leading-relaxed">
                    {optimizationResult.recommendation_summary}
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-amber-200/80 font-mono">
                    <div>
                      <div className="text-[11px] text-amber-800">Best Strategy</div>
                      <div className="text-base font-bold text-slate-900">{optimizationResult.best_strategy}</div>
                    </div>
                    <div>
                      <div className="text-[11px] text-amber-800">Max Net Profit</div>
                      <div className="text-base font-bold text-emerald-700">+${optimizationResult.max_profit.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-[11px] text-amber-800">Optimal TP/SL</div>
                      <div className="text-base font-bold text-slate-900">1:{optimizationResult.optimal_tp_sl_ratio} RR</div>
                    </div>
                    <div>
                      <div className="text-[11px] text-amber-800">Recommended Lot</div>
                      <div className="text-base font-bold text-slate-900">{optimizationResult.recommended_lot_size} lots</div>
                    </div>
                  </div>
                </div>

                {/* Comparative Table */}
                <div>
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-3">
                    Comparative Strategy Profit Breakdown
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-2.5 px-3">Strategy</th>
                          <th className="py-2.5 px-3">Trades</th>
                          <th className="py-2.5 px-3">Win Rate</th>
                          <th className="py-2.5 px-3">Net Profit ($)</th>
                          <th className="py-2.5 px-3">Return %</th>
                          <th className="py-2.5 px-3">Profit Factor</th>
                          <th className="py-2.5 px-3">Sharpe</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono">
                        {optimizationResult.strategies_compared.map((s, idx) => (
                          <tr key={idx} className={s.name.includes("MAX PROFIT") ? "bg-emerald-50/50 font-bold" : "hover:bg-slate-50"}>
                            <td className="py-3 px-3 text-slate-900">{s.name}</td>
                            <td className="py-3 px-3">{s.total_trades}</td>
                            <td className="py-3 px-3 text-emerald-700">{s.win_rate_pct.toFixed(1)}%</td>
                            <td className="py-3 px-3 text-emerald-700 font-bold">+${s.net_profit.toFixed(2)}</td>
                            <td className="py-3 px-3 text-emerald-700">+{s.return_pct.toFixed(1)}%</td>
                            <td className="py-3 px-3">{s.profit_factor.toFixed(2)}</td>
                            <td className="py-3 px-3">{s.sharpe_ratio.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: TradingView Alert Webhook Logs */}
        {activeTab === "alerts" && (
          <div className="p-6">
            {alerts.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-xs">
                No alerts received yet. Test by clicking &ldquo;Test Alert Trigger&rdquo; above or setting up alerts in TradingView.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3">Time</th>
                      <th className="py-2.5 px-3">Alert ID</th>
                      <th className="py-2.5 px-3">Ticker</th>
                      <th className="py-2.5 px-3">Action</th>
                      <th className="py-2.5 px-3">Quantity</th>
                      <th className="py-2.5 px-3">Price</th>
                      <th className="py-2.5 px-3">Strategy</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Execution Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                    {alerts.map((a) => (
                      <tr key={a.id} className="hover:bg-slate-50">
                        <td className="py-2.5 px-3 text-slate-400">
                          {new Date(a.received_at).toLocaleTimeString()}
                        </td>
                        <td className="py-2.5 px-3 font-semibold text-slate-700">{a.id}</td>
                        <td className="py-2.5 px-3 font-bold text-slate-900">{a.ticker}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${
                              a.action === "BUY"
                                ? "bg-emerald-100 text-emerald-800"
                                : a.action === "SELL"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {a.action}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">{a.quantity}</td>
                        <td className="py-2.5 px-3">${a.price}</td>
                        <td className="py-2.5 px-3 text-slate-600">{a.strategy}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                              a.status === "EXECUTED"
                                ? "bg-emerald-100 text-emerald-800"
                                : a.status === "REJECTED"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {a.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-500 max-w-xs truncate">{a.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Pine Script Preview Modal ───────────────────────── */}
      {showPineModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full border border-slate-200 shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Code2 className="w-5 h-5 text-emerald-600" />
                  TradingView Pine Script v5 Strategy
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Paste this code directly into TradingView Pine Editor to send automated alerts to this engine.
                </p>
              </div>
              <button onClick={() => setShowPineModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 bg-slate-950 font-mono text-xs text-emerald-400">
              <pre className="whitespace-pre-wrap">{pineScriptData?.pinescript || "// Loading Pine Script..."}</pre>
            </div>

            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                Webhook URL: <code className="bg-slate-200 px-1.5 py-0.5 rounded text-slate-800">{webhookUrl}</code>
              </span>
              <button
                onClick={handleCopyPineScript}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-xs transition flex items-center gap-1.5"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>{copiedScript ? "Copied to Clipboard!" : "Copy Full Pine Script"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
