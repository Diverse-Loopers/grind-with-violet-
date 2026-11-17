"use client";

import React, { useState, useEffect } from "react";
import {
  Coins,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Wallet,
  ArrowRightLeft,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Sliders,
  DollarSign,
  Info,
} from "lucide-react";
import { API_BASE } from "@/lib/constants";
import { LiveCoinDCXChart } from "@/components/LiveCoinDCXChart";

interface TickerData {
  market: string;
  last_price: number;
  bid: number;
  ask: number;
  high: number;
  low: number;
  volume: number;
  change_24_hour: number;
  timestamp: number;
  spread: number;
  spread_pct: number;
  data_freshness_seconds: number;
  is_stale: boolean;
}

interface ArbitrageOpp {
  target_asset: string;
  inr_market: string;
  usdt_market: string;
  fx_market: string;
  inr_price: number;
  usdt_price: number;
  usdt_inr_rate: number;
  synthetic_inr_price: number;
  price_discrepancy_inr: number;
  price_discrepancy_pct: number;
  direction: string;
  estimated_trading_fees_pct: number;
  estimated_slippage_pct: number;
  estimated_statutory_tds_pct: number;
  total_execution_cost_pct: number;
  net_profit_pct: number;
  is_executable: boolean;
  status: "EXECUTABLE" | "DETECTED_ONLY";
  execution_reason: string;
  timestamp: string;
}

interface WalletHolding {
  id: number;
  market: string;
  target_currency: string;
  base_currency: string;
  quantity: number;
  average_entry_price: number;
  current_price: number;
  market_value_base: number;
  market_value_inr: number;
  unrealized_pnl_base: number;
  unrealized_pnl_inr: number;
  unrealized_pnl_pct: number;
  total_fees: number;
}

interface WalletOverview {
  currency: string;
  inr_cash: number;
  usdt_cash: number;
  usdt_inr_rate: number;
  total_crypto_value_inr: number;
  total_equity_inr: number;
  realized_pnl_inr: number;
  unrealized_pnl_inr: number;
  cumulative_pnl_inr: number;
  holdings_count: number;
  holdings: WalletHolding[];
  starting_balance_inr: number;
  starting_balance_usdt: number;
}

interface OrderAudit {
  id: number;
  order_id: string;
  market: string;
  pair: string;
  side: "BUY" | "SELL";
  order_type: string;
  quantity: number;
  price: number;
  fill_price: number;
  total_value: number;
  fee: number;
  tds: number;
  slippage: number;
  status: "FILLED" | "REJECTED";
  rejection_reason?: string;
  mode: string;
  created_at: string;
}

interface MarketDetail {
  coindcx_name: string;
  symbol: string;
  pair: string;
  base_currency_short_name: string;
  target_currency_short_name: string;
  base_currency_precision: number;
  target_currency_precision: number;
  min_quantity: number;
  max_quantity: number;
  min_price: number;
  max_price: number;
  min_notional: number;
  step: number;
  status: string;
}

export default function CoinDCXPage() {
  const [selectedMarket, setSelectedMarket] = useState<string>("BTCINR");
  const [tickers, setTickers] = useState<TickerData[]>([]);
  const [wallet, setWallet] = useState<WalletOverview | null>(null);
  const [arbitrageOpps, setArbitrageOpps] = useState<ArbitrageOpp[]>([]);
  const [orders, setOrders] = useState<OrderAudit[]>([]);
  const [marketDetail, setMarketDetail] = useState<MarketDetail | null>(null);

  // Paper order form state
  const [orderSide, setOrderSide] = useState<"BUY" | "SELL">("BUY");
  const [orderQty, setOrderQty] = useState<string>("0.001");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [orderResult, setOrderResult] = useState<{ success: boolean; message: string } | null>(null);

  // Reset wallet modal state
  const [showResetModal, setShowResetModal] = useState<boolean>(false);
  const [resetInr, setResetInr] = useState<string>("1000000");
  const [resetUsdt, setResetUsdt] = useState<string>("10000");
  const [isResetting, setIsResetting] = useState<boolean>(false);

  // Status & freshness
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Fetch all live data
  const fetchData = async () => {
    try {
      setIsRefreshing(true);
      const [statusRes, tickersRes, walletRes, arbRes, ordersRes, detailRes] = await Promise.all([
        fetch(`${API_BASE}/api/coindcx/status`),
        fetch(`${API_BASE}/api/coindcx/tickers`),
        fetch(`${API_BASE}/api/coindcx/paper/wallet`),
        fetch(`${API_BASE}/api/coindcx/scanner/arbitrage`),
        fetch(`${API_BASE}/api/coindcx/paper/orders?limit=30`),
        fetch(`${API_BASE}/api/coindcx/markets/${selectedMarket}`),
      ]);

      if (statusRes.ok) setSystemStatus(await statusRes.json());
      if (tickersRes.ok) setTickers(await tickersRes.json());
      if (walletRes.ok) setWallet(await walletRes.json());
      if (arbRes.ok) setArbitrageOpps(await arbRes.json());
      if (ordersRes.ok) setOrders(await ordersRes.json());
      if (detailRes.ok) setMarketDetail(await detailRes.json());

      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("Failed fetching CoinDCX data:", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 8000);
    return () => clearInterval(timer);
  }, [selectedMarket]);

  // Selected ticker
  const activeTicker = tickers.find((t) => t.market === selectedMarket);
  const estimatedPrice = activeTicker
    ? orderSide === "BUY"
      ? activeTicker.ask || activeTicker.last_price
      : activeTicker.bid || activeTicker.last_price
    : 0;

  const numQty = parseFloat(orderQty) || 0;
  const turnover = numQty * estimatedPrice;
  const estimatedFee = turnover * 0.002; // 0.20% CoinDCX taker fee
  const isINRBase = marketDetail?.base_currency_short_name?.toUpperCase() === "INR";
  const estimatedTds = (orderSide === "SELL" && isINRBase) ? turnover * 0.01 : 0.0; // 1% Indian Section 194S TDS
  const netOrderCost = orderSide === "BUY" ? turnover + estimatedFee : turnover - estimatedFee - estimatedTds;

  // Handle order placement
  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (numQty <= 0) return;

    try {
      setIsSubmitting(true);
      setOrderResult(null);
      const res = await fetch(`${API_BASE}/api/coindcx/paper/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          market: selectedMarket,
          side: orderSide,
          quantity: numQty,
          order_type: "MARKET",
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setOrderResult({ success: true, message: data.message });
        fetchData();
      } else {
        const errMsg = data?.detail?.error || data?.detail?.message || data?.message || "Order rejected by CoinDCX rules";
        setOrderResult({ success: false, message: errMsg });
      }
    } catch (err: any) {
      setOrderResult({ success: false, message: err?.message || "Failed placing paper order" });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle reset wallet
  const handleResetWallet = async () => {
    try {
      setIsResetting(true);
      const res = await fetch(`${API_BASE}/api/coindcx/paper/wallet/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          starting_inr: parseFloat(resetInr) || 1000000,
          starting_usdt: parseFloat(resetUsdt) || 10000,
        }),
      });
      if (res.ok) {
        setShowResetModal(false);
        fetchData();
      }
    } catch (err) {
      console.error("Failed resetting wallet:", err);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* ── Top Header & Security Bar ── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-orange-500/10 border border-orange-500/30 flex items-center justify-center text-orange-600 shadow-xs">
              <Coins className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
                CoinDCX Crypto Engine & Paper Trading
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                  OFFICIAL API
                </span>
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                  STRICT PAPER MODE
                </span>
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Public market data, multi-currency accounting, and cross-market arbitrage scanner
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="text-xs font-medium text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-xs flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Updated: <strong className="font-mono text-slate-800">{lastRefreshed || "Syncing..."}</strong></span>
          </div>

          <button
            onClick={fetchData}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-xs transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            <span>Refresh Feed</span>
          </button>

          <button
            onClick={() => setShowResetModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-orange-50 hover:bg-orange-100 text-orange-700 border border-orange-200 shadow-xs transition"
          >
            <RotateCcw className="w-3.5 h-3.5 text-orange-600" />
            <span>Reset Wallet</span>
          </button>
        </div>
      </div>

      {/* ── Safety Guard Banner ── */}
      <div className="bg-emerald-50/60 border border-emerald-200 rounded-2xl p-4 flex items-start gap-3 text-xs text-emerald-900">
        <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <div className="font-bold flex items-center gap-2">
            Safety Barrier Active • Live Execution Locked
            <span className="text-[10px] bg-emerald-200 text-emerald-900 px-1.5 py-0.2 rounded font-mono">
              992 Markets Indexed
            </span>
          </div>
          <div className="text-emerald-700 leading-relaxed">
            All trades execute in an isolated virtual paper broker. Real-time market data is verified for freshness (rejects data older than 30s). Minimum order quantities, step increments, CoinDCX 0.20% taker fees, and Indian Section 194S 1.0% crypto TDS are strictly enforced. Live order submission is permanently disabled.
          </div>
        </div>
      </div>

      {/* ── Tickers Highlight Ribbon ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {tickers.slice(0, 6).map((t) => {
          const isSelected = selectedMarket === t.market;
          const isPos = t.change_24_hour >= 0;
          return (
            <div
              key={t.market}
              onClick={() => setSelectedMarket(t.market)}
              className={`p-3.5 rounded-2xl border transition cursor-pointer shadow-xs ${
                isSelected
                  ? "bg-orange-500/5 border-orange-500 ring-2 ring-orange-500/20"
                  : "bg-white border-slate-200 hover:border-slate-300"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-xs text-slate-800">{t.market}</span>
                <span
                  className={`text-[11px] font-mono font-semibold flex items-center ${
                    isPos ? "text-emerald-600" : "text-rose-600"
                  }`}
                >
                  {isPos ? "+" : ""}
                  {t.change_24_hour.toFixed(2)}%
                </span>
              </div>
              <div className="text-base font-bold text-slate-900 font-mono tracking-tight">
                {t.market.endsWith("INR") ? "₹" : "$"}
                {t.last_price >= 1000
                  ? t.last_price.toLocaleString(undefined, { maximumFractionDigits: 1 })
                  : t.last_price.toFixed(4)}
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 font-mono">
                <span>Spread: {t.spread_pct.toFixed(2)}%</span>
                <span className={t.is_stale ? "text-rose-500 font-bold" : "text-slate-400"}>
                  {t.data_freshness_seconds}s
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Virtual Multi-Currency Wallet Card ── */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-600">
              <Wallet className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Multi-Currency Paper Wallet</h2>
              <p className="text-[11px] text-slate-500">Virtual balance mark-to-market against live CoinDCX exchange tickers</p>
            </div>
          </div>
          <div className="text-xs font-mono bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200 text-slate-600">
            Live FX Rate: <strong className="text-slate-900">1 USDT = ₹{wallet?.usdt_inr_rate?.toFixed(2) || "101.50"} INR</strong>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Total Equity (INR)</div>
            <div className="text-xl font-bold font-mono text-slate-900">
              ₹{wallet?.total_equity_inr?.toLocaleString() || "0"}
            </div>
            <div className="text-[10px] text-slate-400 mt-1">Cash + Crypto Holdings</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Virtual Cash Balances</div>
            <div className="space-y-0.5">
              <div className="text-sm font-bold font-mono text-slate-800">
                ₹{wallet?.inr_cash?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || "0"} <span className="text-[10px] text-slate-400 font-sans">INR</span>
              </div>
              <div className="text-sm font-bold font-mono text-slate-800">
                ${wallet?.usdt_cash?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || "0"} <span className="text-[10px] text-slate-400 font-sans">USDT</span>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Crypto Holdings Value</div>
            <div className="text-xl font-bold font-mono text-slate-900">
              ₹{wallet?.total_crypto_value_inr?.toLocaleString() || "0"}
            </div>
            <div className="text-[10px] text-slate-400 mt-1">{wallet?.holdings_count || 0} active position(s)</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Realized / Unrealized P&L</div>
            <div className="flex items-center gap-3">
              <div>
                <span className="text-[10px] text-slate-400 block">Realized</span>
                <span className={`text-sm font-mono font-bold ${(wallet?.realized_pnl_inr || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                  ₹{wallet?.realized_pnl_inr?.toLocaleString() || "0"}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">Unrealized</span>
                <span className={`text-sm font-mono font-bold ${(wallet?.unrealized_pnl_inr || 0) >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                  ₹{wallet?.unrealized_pnl_inr?.toLocaleString() || "0"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Holdings Table */}
        {wallet && wallet.holdings.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Asset</th>
                  <th className="py-2.5 px-3">Market</th>
                  <th className="py-2.5 px-3 text-right">Quantity</th>
                  <th className="py-2.5 px-3 text-right">Avg Price</th>
                  <th className="py-2.5 px-3 text-right">Current Price</th>
                  <th className="py-2.5 px-3 text-right">Valuation (INR)</th>
                  <th className="py-2.5 px-3 text-right">Unrealized P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {wallet.holdings.map((h) => {
                  const isPos = h.unrealized_pnl_inr >= 0;
                  return (
                    <tr key={h.id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-sans font-bold text-slate-800">{h.target_currency}</td>
                      <td className="py-2.5 px-3 text-slate-600">{h.market}</td>
                      <td className="py-2.5 px-3 text-right text-slate-900 font-bold">{h.quantity}</td>
                      <td className="py-2.5 px-3 text-right text-slate-600">₹{h.average_entry_price.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-right text-slate-900 font-bold">₹{h.current_price.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-right font-bold text-slate-900">₹{h.market_value_inr.toLocaleString()}</td>
                      <td className={`py-2.5 px-3 text-right font-bold ${isPos ? "text-emerald-600" : "text-rose-600"}`}>
                        {isPos ? "+" : ""}₹{h.unrealized_pnl_inr.toLocaleString()} ({h.unrealized_pnl_pct.toFixed(2)}%)
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-5 bg-slate-50 rounded-xl border border-dashed border-slate-200 text-xs text-slate-500">
            No open crypto holdings. Place a paper trade below to test simulated execution.
          </div>
        )}
      </div>

      {/* ── Live Candlestick & Quick Trade Section ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Chart */}
        <div className="lg:col-span-2">
          <LiveCoinDCXChart market={selectedMarket} height={380} />
        </div>

        {/* Right: Quick Paper Trade Form */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-orange-600" />
                Paper Order Simulator
              </h3>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-orange-100 text-orange-800 border border-orange-200">
                {selectedMarket}
              </span>
            </div>

            {/* Buy / Sell Buttons */}
            <div className="grid grid-cols-2 gap-2 mb-4">
              <button
                type="button"
                onClick={() => setOrderSide("BUY")}
                className={`py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                  orderSide === "BUY"
                    ? "bg-emerald-600 text-white shadow-xs"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                BUY (Long)
              </button>
              <button
                type="button"
                onClick={() => setOrderSide("SELL")}
                className={`py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                  orderSide === "SELL"
                    ? "bg-rose-600 text-white shadow-xs"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                <TrendingDown className="w-3.5 h-3.5" />
                SELL (Short/Close)
              </button>
            </div>

            {/* Market Constraints Box */}
            {marketDetail && (
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-[11px] space-y-1 mb-4">
                <div className="font-semibold text-slate-700 flex items-center justify-between">
                  <span>CoinDCX Market Rules</span>
                  <span className="text-emerald-700 font-bold uppercase">{marketDetail.status}</span>
                </div>
                <div className="grid grid-cols-2 gap-x-2 text-slate-500 font-mono">
                  <div>Min Qty: <strong>{marketDetail.min_quantity}</strong></div>
                  <div>Step Size: <strong>{marketDetail.step}</strong></div>
                  <div>Min Notional: <strong>{marketDetail.min_notional} {marketDetail.base_currency_short_name}</strong></div>
                  <div>Precision: <strong>{marketDetail.target_currency_precision} dec</strong></div>
                </div>
              </div>
            )}

            {/* Quantity Input */}
            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Quantity ({marketDetail?.target_currency_short_name || "Crypto"})
                </label>
                <input
                  type="number"
                  step={marketDetail?.step || "0.0001"}
                  min={marketDetail?.min_quantity || "0.0001"}
                  value={orderQty}
                  onChange={(e) => setOrderQty(e.target.value)}
                  className="w-full px-3 py-2 text-sm font-mono font-semibold bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500"
                  placeholder="0.001"
                />
              </div>

              {/* Order Cost & Fees Breakdown */}
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5 text-xs font-mono">
                <div className="flex justify-between text-slate-500">
                  <span>Top of Book Fill:</span>
                  <span className="text-slate-800 font-bold">
                    {marketDetail?.base_currency_short_name === "USDT" ? "$" : "₹"}
                    {estimatedPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Turnover:</span>
                  <span className="text-slate-800">
                    {marketDetail?.base_currency_short_name === "USDT" ? "$" : "₹"}
                    {turnover.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Taker Fee (0.20%):</span>
                  <span className="text-slate-800">
                    {marketDetail?.base_currency_short_name === "USDT" ? "$" : "₹"}
                    {estimatedFee.toFixed(2)}
                  </span>
                </div>
                {orderSide === "SELL" && isINRBase && (
                  <div className="flex justify-between text-amber-700">
                    <span>Indian TDS (1.0%):</span>
                    <span className="font-bold">₹{estimatedTds.toFixed(2)}</span>
                  </div>
                )}
                <div className="pt-1.5 border-t border-slate-200 flex justify-between font-bold text-slate-900">
                  <span>Net Required:</span>
                  <span className="text-orange-600">
                    {marketDetail?.base_currency_short_name === "USDT" ? "$" : "₹"}
                    {netOrderCost.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            </div>

            {/* Notification Result */}
            {orderResult && (
              <div
                className={`p-3 rounded-xl text-xs mb-3 flex items-start gap-2 ${
                  orderResult.success
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "bg-rose-50 text-rose-800 border border-rose-200"
                }`}
              >
                {orderResult.success ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                )}
                <div className="leading-relaxed">{orderResult.message}</div>
              </div>
            )}
          </div>

          <form onSubmit={handlePlaceOrder}>
            <button
              type="submit"
              disabled={isSubmitting || numQty <= 0}
              className={`w-full py-2.5 rounded-xl text-xs font-bold transition shadow-xs flex items-center justify-center gap-2 ${
                orderSide === "BUY"
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-rose-600 hover:bg-rose-700 text-white"
              } disabled:opacity-50`}
            >
              {isSubmitting ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <span>Place Simulated {orderSide} Order</span>
              )}
            </button>
            <div className="text-[10px] text-slate-400 text-center mt-2">
              Virtual paper execution • Real market depth verified
            </div>
          </form>
        </div>
      </div>

      {/* ── Cross-Market Arbitrage & Momentum Scanner Table ── */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-orange-500/10 border border-orange-500/30 flex items-center justify-center text-orange-600">
              <ArrowRightLeft className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Cross-Market Arbitrage & Friction Scanner</h2>
              <p className="text-[11px] text-slate-500">
                Direct INR Price vs Synthetic (USDT * USDT/INR) • Evaluates net edge after 0.40% fees, 1.0% TDS, and slippage
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 font-mono">
            Tracking {arbitrageOpps.length} Major Pairs
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3">Asset</th>
                <th className="py-2.5 px-3 text-right">Direct INR</th>
                <th className="py-2.5 px-3 text-right">Synthetic INR</th>
                <th className="py-2.5 px-3 text-right">Gross Edge</th>
                <th className="py-2.5 px-3 text-right">Trading Fees</th>
                <th className="py-2.5 px-3 text-right">Statutory TDS</th>
                <th className="py-2.5 px-3 text-right">Slippage</th>
                <th className="py-2.5 px-3 text-right">Net Profit</th>
                <th className="py-2.5 px-3 text-center">Status</th>
                <th className="py-2.5 px-3">Execution Evaluation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {arbitrageOpps.map((opp) => {
                const isExecutable = opp.status === "EXECUTABLE";
                const isPosGross = opp.price_discrepancy_pct >= 0;
                return (
                  <tr key={opp.target_asset} className="hover:bg-slate-50">
                    <td className="py-3 px-3 font-sans font-bold text-slate-900 flex items-center gap-1.5">
                      <span>{opp.target_asset}</span>
                      <span className="text-[10px] text-slate-400 font-mono font-normal">
                        ({opp.inr_market})
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-slate-900">
                      ₹{opp.inr_price >= 1000 ? opp.inr_price.toLocaleString(undefined, { maximumFractionDigits: 1 }) : opp.inr_price.toFixed(4)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-600">
                      ₹{opp.synthetic_inr_price >= 1000 ? opp.synthetic_inr_price.toLocaleString(undefined, { maximumFractionDigits: 1 }) : opp.synthetic_inr_price.toFixed(4)}
                    </td>
                    <td className={`py-3 px-3 text-right font-bold ${isPosGross ? "text-emerald-600" : "text-rose-600"}`}>
                      {isPosGross ? "+" : ""}{opp.price_discrepancy_pct.toFixed(2)}%
                    </td>
                    <td className="py-3 px-3 text-right text-slate-500">
                      {opp.estimated_trading_fees_pct.toFixed(2)}%
                    </td>
                    <td className="py-3 px-3 text-right text-amber-700">
                      {opp.estimated_statutory_tds_pct.toFixed(2)}%
                    </td>
                    <td className="py-3 px-3 text-right text-slate-500">
                      {opp.estimated_slippage_pct.toFixed(2)}%
                    </td>
                    <td className={`py-3 px-3 text-right font-bold ${opp.net_profit_pct > 0 ? "text-emerald-600" : "text-slate-500"}`}>
                      {opp.net_profit_pct > 0 ? "+" : ""}{opp.net_profit_pct.toFixed(2)}%
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                          isExecutable
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : "bg-slate-100 text-slate-600 border border-slate-200"
                        }`}
                      >
                        {opp.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-[11px] font-sans text-slate-500 max-w-xs">
                      {opp.execution_reason}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Order Audit Log Table ── */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-900">Simulated Orders & Fills Audit</h2>
            <span className="text-xs text-slate-400 font-mono">({orders.length} orders recorded)</span>
          </div>
          <span className="text-[11px] text-slate-500">Persisted in SQLite database</span>
        </div>

        {orders.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 font-sans">
                <tr>
                  <th className="py-2.5 px-3">Order Ref</th>
                  <th className="py-2.5 px-3">Market</th>
                  <th className="py-2.5 px-3">Side</th>
                  <th className="py-2.5 px-3 text-right">Quantity</th>
                  <th className="py-2.5 px-3 text-right">Fill Price</th>
                  <th className="py-2.5 px-3 text-right">Turnover</th>
                  <th className="py-2.5 px-3 text-right">Fee (0.2%)</th>
                  <th className="py-2.5 px-3 text-right">TDS (1%)</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                  <th className="py-2.5 px-3">Rejection / Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-3 text-[11px] text-slate-500 font-bold">{o.order_id}</td>
                    <td className="py-2.5 px-3 font-bold text-slate-800">{o.market}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          o.side === "BUY"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-rose-100 text-rose-800"
                        }`}
                      >
                        {o.side}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-900 font-semibold">{o.quantity}</td>
                    <td className="py-2.5 px-3 text-right text-slate-800">
                      {o.fill_price > 0 ? o.fill_price.toLocaleString() : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-900 font-bold">
                      {o.total_value > 0 ? o.total_value.toLocaleString() : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-500">{o.fee.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right text-amber-700">{o.tds.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          o.status === "FILLED"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-rose-100 text-rose-800"
                        }`}
                      >
                        {o.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-[11px] font-sans text-slate-500 max-w-xs truncate">
                      {o.rejection_reason || "Filled at top-of-book"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6 bg-slate-50 rounded-xl text-xs text-slate-500">
            No simulated orders executed yet.
          </div>
        )}
      </div>

      {/* ── Reset Wallet Modal ── */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
              <RotateCcw className="w-4 h-4 text-orange-600" />
              Reset Virtual CoinDCX Balance
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Clears all simulated crypto holdings and resets virtual wallet balances.
            </p>

            <div className="space-y-3 mb-5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Starting INR Balance (₹)
                </label>
                <input
                  type="number"
                  value={resetInr}
                  onChange={(e) => setResetInr(e.target.value)}
                  className="w-full px-3 py-2 text-sm font-mono bg-slate-50 border border-slate-200 rounded-xl"
                  placeholder="1000000"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Starting USDT Balance ($)
                </label>
                <input
                  type="number"
                  value={resetUsdt}
                  onChange={(e) => setResetUsdt(e.target.value)}
                  className="w-full px-3 py-2 text-sm font-mono bg-slate-50 border border-slate-200 rounded-xl"
                  placeholder="10000"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isResetting}
                onClick={handleResetWallet}
                className="px-4 py-2 text-xs font-bold text-white bg-orange-600 hover:bg-orange-700 rounded-xl shadow-xs transition"
              >
                {isResetting ? "Resetting..." : "Confirm Reset"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
