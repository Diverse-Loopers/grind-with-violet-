"use client";

import React, { useState } from "react";
import { usePositions, useOrders, useEquityCurve } from "@/hooks/useApi";
import { StatCard } from "@/components/StatCard";
import { WalletCard } from "@/components/WalletCard";
import { StockCandleChartModal } from "@/components/StockCandleChartModal";
import { formatINR, formatPct, formatISTTime } from "@/lib/format";
import { postData } from "@/lib/api";
import { Briefcase, Layers, ArrowUpRight, ArrowDownRight, PlusCircle, X } from "lucide-react";

export default function PortfolioPage() {
  const { data: posData, mutate: refreshPositions } = usePositions();
  const { data: ordersData, mutate: refreshOrders } = useOrders();
  const { data: equityData } = useEquityCurve();

  const [activeTab, setActiveTab] = useState<"POSITIONS" | "ORDERS">("POSITIONS");
  const [selectedChartSymbol, setSelectedChartSymbol] = useState<string | null>(null);

  // Manual Paper Order modal state
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [symbol, setSymbol] = useState("RELIANCE");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [qty, setQty] = useState(10);
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [limitPrice, setLimitPrice] = useState<number | undefined>(undefined);
  const [placing, setPlacing] = useState(false);
  const [orderError, setOrderError] = useState("");

  const summary = posData?.summary || {
    total_positions_value: 0,
    unrealized_pnl: 0,
    realized_pnl: 0,
    total_fees: 0,
    open_count: 0,
  };

  const positions = posData?.positions || [];
  const orders = ordersData?.orders || [];

  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setOrderError("");
    setPlacing(true);
    try {
      await postData("/api/portfolio/orders", {
        trading_symbol: symbol.toUpperCase(),
        transaction_type: side,
        quantity: Number(qty),
        order_type: orderType,
        price: orderType === "LIMIT" ? Number(limitPrice) : undefined,
        product: "CNC",
      });
      setShowOrderModal(false);
      refreshPositions();
      refreshOrders();
    } catch (err: any) {
      setOrderError(err.message || "Failed to submit paper order");
    } finally {
      setPlacing(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Portfolio Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-bold text-slate-900 flex items-center gap-2">
            Simulated Portfolio & Execution Log
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium">
              PAPER TRADING VENUE
            </span>
          </h1>
          <p className="text-xs text-slate-500">
            Real-time mark-to-market positions, trade execution history, and fee breakdown
          </p>
        </div>

        <button
          onClick={() => setShowOrderModal(true)}
          className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-xs"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>New Paper Order</span>
        </button>
      </div>

      {/* Trading Wallet & Capital Allocation Card */}
      <WalletCard />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          label="Holdings Value"
          value={formatINR(summary.total_positions_value)}
          subValue={`${summary.open_count} open positions`}
          icon={<Briefcase className="w-4 h-4" />}
        />
        <StatCard
          label="Unrealized P&L"
          value={formatINR(summary.unrealized_pnl)}
          isPositive={summary.unrealized_pnl > 0}
          isNegative={summary.unrealized_pnl < 0}
          subValue="Mark-to-market"
          icon={<ArrowUpRight className="w-4 h-4" />}
        />
        <StatCard
          label="Realized P&L"
          value={formatINR(summary.realized_pnl)}
          isPositive={summary.realized_pnl > 0}
          isNegative={summary.realized_pnl < 0}
          subValue="Closed trades profit/loss"
          icon={<ArrowDownRight className="w-4 h-4" />}
        />
        <StatCard
          label="Statutory Fees & Brokerage"
          value={formatINR(summary.total_fees)}
          subValue="STT, GST, Stamp, Exch charges"
          icon={<Layers className="w-4 h-4" />}
        />
      </div>

      {/* Navigation tabs */}
      <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200 w-fit">
        <button
          onClick={() => setActiveTab("POSITIONS")}
          className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition ${
            activeTab === "POSITIONS" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Open Positions ({positions.length})
        </button>
        <button
          onClick={() => setActiveTab("ORDERS")}
          className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition ${
            activeTab === "ORDERS" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Order Audit Trail ({orders.length})
        </button>
      </div>

      {/* Tab Tables */}
      {activeTab === "POSITIONS" ? (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
          {positions.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500">
              No open positions. Candidate signals will automatically route to paper broker when market conditions pass risk checks.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-mono uppercase border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-3">Symbol</th>
                    <th className="py-3 px-3 text-right">Quantity</th>
                    <th className="py-3 px-3 text-right">Avg Entry Price</th>
                    <th className="py-3 px-3 text-right">Current LTP</th>
                    <th className="py-3 px-3 text-right">Holding Value</th>
                    <th className="py-3 px-3 text-right">Unrealized P&L</th>
                    <th className="py-3 px-3 text-right">P&L %</th>
                    <th className="py-3 px-3 text-right">Total Fees</th>
                    <th className="py-3 px-3 text-center">Strategy</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {positions.map((p) => {
                    const holdingVal = p.quantity * p.current_price;
                    const pnlPct =
                      p.average_entry_price > 0
                        ? ((p.current_price - p.average_entry_price) / p.average_entry_price) * 100
                        : 0;
                    return (
                      <tr
                        key={p.id}
                        onClick={() => setSelectedChartSymbol(p.trading_symbol)}
                        className="hover:bg-slate-50 transition cursor-pointer"
                      >
                        <td className="py-3 px-3 font-bold text-slate-900 flex items-center gap-1.5">
                          <span className="hover:text-emerald-700 hover:underline">{p.trading_symbol}</span>
                          <span className="text-[10px] text-emerald-600 font-normal">📈 Chart</span>
                        </td>
                        <td className="py-3 px-3 text-right text-slate-700">{p.quantity}</td>
                        <td className="py-3 px-3 text-right text-slate-600">{formatINR(p.average_entry_price)}</td>
                        <td className="py-3 px-3 text-right font-medium text-slate-900">{formatINR(p.current_price)}</td>
                        <td className="py-3 px-3 text-right text-slate-700">{formatINR(holdingVal)}</td>
                        <td
                          className={`py-3 px-3 text-right font-bold ${
                            p.unrealized_pnl > 0 ? "text-emerald-600" : p.unrealized_pnl < 0 ? "text-rose-600" : "text-slate-600"
                          }`}
                        >
                          {formatINR(p.unrealized_pnl)}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-bold ${
                            pnlPct > 0 ? "text-emerald-600" : pnlPct < 0 ? "text-rose-600" : "text-slate-600"
                          }`}
                        >
                          {formatPct(pnlPct)}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-500">{formatINR(p.total_fees)}</td>
                        <td className="py-3 px-3 text-center">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700 border border-slate-200">
                            {p.strategy || "SYSTEM"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        /* Orders tab */
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-mono uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-3">Order Ref</th>
                  <th className="py-3 px-3">Symbol</th>
                  <th className="py-3 px-3">Side</th>
                  <th className="py-3 px-3">Type</th>
                  <th className="py-3 px-3 text-right">Qty</th>
                  <th className="py-3 px-3 text-right">Fill Price</th>
                  <th className="py-3 px-3 text-right">Slippage</th>
                  <th className="py-3 px-3 text-right">Fees</th>
                  <th className="py-3 px-3 text-center">Status</th>
                  <th className="py-3 px-3 text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {orders.map((o) => {
                  const isFilled = o.status === "FILLED";
                  return (
                    <tr key={o.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-3 px-3 text-slate-400 text-[11px] truncate max-w-[140px]">
                        {o.order_reference_id || `#${o.id}`}
                      </td>
                      <td className="py-3 px-3 font-bold text-slate-900">{o.trading_symbol}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            o.transaction_type === "BUY"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}
                        >
                          {o.transaction_type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-600">{o.order_type}</td>
                      <td className="py-3 px-3 text-right text-slate-700">{o.quantity}</td>
                      <td className="py-3 px-3 text-right text-slate-900 font-medium">
                        {o.average_fill_price ? formatINR(o.average_fill_price) : "-"}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-500">
                        {o.simulated_slippage ? formatINR(o.simulated_slippage) : "-"}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-500">{formatINR(o.fees)}</td>
                      <td className="py-3 px-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            isFilled
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {o.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right text-slate-500 text-[11px]">
                        {formatISTTime(o.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Manual Order Modal */}
      {showOrderModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <PlusCircle className="w-4 h-4 text-emerald-600" />
                Place Manual Paper Order
              </h3>
              <button
                onClick={() => setShowOrderModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-500">
              Orders will execute against the simulated book with bid-ask spread and slippage.
            </p>

            {orderError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700">
                {orderError}
              </div>
            )}

            <form onSubmit={handlePlaceOrder} className="space-y-3.5 text-xs font-mono">
              <div>
                <label className="text-slate-600 block mb-1 font-semibold">Trading Symbol</label>
                <input
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-600 block mb-1 font-semibold">Transaction Side</label>
                  <select
                    value={side}
                    onChange={(e) => setSide(e.target.value as any)}
                    className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-600 block mb-1 font-semibold">Quantity</label>
                  <input
                    type="number"
                    value={qty}
                    min={1}
                    onChange={(e) => setQty(Number(e.target.value))}
                    className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-600 block mb-1 font-semibold">Order Type</label>
                  <select
                    value={orderType}
                    onChange={(e) => setOrderType(e.target.value as any)}
                    className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="MARKET">MARKET</option>
                    <option value="LIMIT">LIMIT</option>
                  </select>
                </div>
                {orderType === "LIMIT" && (
                  <div>
                    <label className="text-slate-600 block mb-1 font-semibold">Limit Price (₹)</label>
                    <input
                      type="number"
                      step="0.05"
                      value={limitPrice || ""}
                      onChange={(e) => setLimitPrice(Number(e.target.value))}
                      className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                      required
                    />
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowOrderModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={placing}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition shadow-xs"
                >
                  {placing ? "Executing..." : "Execute Paper Order"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Stock Candlestick & Trades Chart Modal */}
      {selectedChartSymbol && (
        <StockCandleChartModal
          symbol={selectedChartSymbol}
          onClose={() => setSelectedChartSymbol(null)}
          onTradeExecuted={() => {
            refreshPositions();
            refreshOrders();
          }}
        />
      )}
    </div>
  );
}
