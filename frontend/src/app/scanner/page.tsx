"use client";

import React, { useState, useMemo, useEffect } from "react";
import { useScannerInstruments, useSignals } from "@/hooks/useApi";
import { useScannerWebSocket } from "@/hooks/useWebSocket";
import { DataQualityBadge } from "@/components/DataQualityBadge";
import { StockCandleChartModal } from "@/components/StockCandleChartModal";
import { formatINR, formatPct } from "@/lib/format";
import {
  Search,
  RefreshCw,
  Plus,
  Check,
  BarChart2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { postData } from "@/lib/api";

export default function ScannerPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search.trim());
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  const { data: apiData, mutate: refreshInstruments } = useScannerInstruments(debouncedSearch);
  const { instruments: wsInstruments, isConnected: wsConnected } = useScannerWebSocket();
  const { data: signalsData, mutate: refreshSignals } = useSignals();

  // If user has a search term, display the server-side results from all 2,619 stocks.
  // Otherwise display the streaming active watchlist.
  const rawInstruments = debouncedSearch.length > 0
    ? (apiData?.instruments || [])
    : (wsInstruments.length > 0 ? wsInstruments : apiData?.instruments || []);

  const [minEdge, setMinEdge] = useState<number>(0);
  const [minVolume, setMinVolume] = useState<number>(0);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"WATCHLIST" | "SIGNALS">("WATCHLIST");
  const [scanning, setScanning] = useState(false);
  const [addingSymbol, setAddingSymbol] = useState<string | null>(null);

  // Sorting
  const [sortField, setSortField] = useState<string>("net_edge_pct");
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  // Pagination for high-performance rendering (prevents browser lockup)
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const filteredInstruments = useMemo(() => {
    return rawInstruments
      .filter((inst) => {
        const matchesEdge = inst.net_edge_pct >= minEdge;
        const matchesVol = inst.volume >= minVolume;
        return matchesEdge && matchesVol;
      })
      .sort((a, b) => {
        let valA = (a as any)[sortField] ?? 0;
        let valB = (b as any)[sortField] ?? 0;
        if (typeof valA === "string") {
          return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return sortAsc ? valA - valB : valB - valA;
      });
  }, [rawInstruments, minEdge, minVolume, sortField, sortAsc]);

  // Reset pagination when search or filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearch, minEdge, minVolume, sortField, sortAsc]);

  const totalPages = Math.ceil(filteredInstruments.length / pageSize) || 1;
  const paginatedInstruments = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredInstruments.slice(start, start + pageSize);
  }, [filteredInstruments, currentPage, pageSize]);

  const handleAddToWatchlist = async (symbol: string, name: string) => {
    try {
      setAddingSymbol(symbol);
      await postData("/api/scanner/instruments", {
        trading_symbol: symbol,
        name: name || symbol,
        exchange: "NSE",
      });
      refreshInstruments();
    } catch (e) {
      console.error(e);
    } finally {
      setAddingSymbol(null);
    }
  };

  const handleManualScan = async () => {
    try {
      setScanning(true);
      await postData("/api/scanner/scan-now");
      refreshInstruments();
      refreshSignals();
    } catch (e) {
      console.error(e);
    } finally {
      setScanning(false);
    }
  };

  const signals = signalsData?.signals || [];
  const totalStocks = apiData?.total_available_stocks || 2619;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Controls Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white border border-slate-200 p-5 rounded-2xl shadow-xs">
        <div>
          <h1 className="text-base font-bold text-slate-900 flex items-center gap-2">
            Market Opportunity Scanner
            <span
              className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-medium ${
                wsConnected
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-blue-50 text-blue-700 border border-blue-200"
              }`}
            >
              {wsConnected ? "STREAMING (WS)" : "POLLING (REST)"}
            </span>
          </h1>
          <p className="text-xs text-slate-500">
            Real-time bid-ask spread calculation, moving average deviations, and net opportunity modeling
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleManualScan}
            disabled={scanning}
            className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} />
            <span>{scanning ? "Scanning..." : "Scan Watchlist"}</span>
          </button>
        </div>
      </div>

      {/* View Switcher & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              onClick={() => setActiveTab("WATCHLIST")}
              className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === "WATCHLIST"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Watchlist ({debouncedSearch ? `${filteredInstruments.length} found` : `${rawInstruments.length} active`})
            </button>
            <button
              onClick={() => setActiveTab("SIGNALS")}
              className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === "SIGNALS"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Signals Feed ({signals.length})
            </button>
          </div>
          <span className="text-[11px] bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-1 rounded-lg font-medium">
            {totalStocks.toLocaleString()} NSE Equities
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search 2,619 stocks (e.g. ZOMATO, PAYTM)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-white border border-slate-300 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 w-72 font-mono shadow-xs"
            />
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-600 font-medium">
            <span>Min Edge:</span>
            <select
              value={minEdge}
              onChange={(e) => setMinEdge(Number(e.target.value))}
              className="bg-white border border-slate-300 rounded-xl px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-emerald-500 font-mono shadow-xs"
            >
              <option value={0}>All</option>
              <option value={0.1}>&gt; 0.10%</option>
              <option value={0.25}>&gt; 0.25%</option>
              <option value={0.5}>&gt; 0.50%</option>
              <option value={1.0}>&gt; 1.00%</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Table Content */}
      {activeTab === "WATCHLIST" ? (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-mono uppercase border-b border-slate-200">
                <tr>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800"
                    onClick={() => handleSort("trading_symbol")}
                  >
                    Symbol {sortField === "trading_symbol" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("ltp")}
                  >
                    LTP {sortField === "ltp" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th className="py-3 px-3 text-right">Bid</th>
                  <th className="py-3 px-3 text-right">Ask</th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("spread_pct")}
                  >
                    Spread % {sortField === "spread_pct" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("change_pct")}
                  >
                    Change % {sortField === "change_pct" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("volume")}
                  >
                    Volume {sortField === "volume" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("relative_volume")}
                  >
                    Rel Vol {sortField === "relative_volume" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("volatility")}
                  >
                    Volat % {sortField === "volatility" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("deviation_from_ma")}
                  >
                    MA Dev % {sortField === "deviation_from_ma" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th
                    className="py-3 px-3 cursor-pointer hover:text-slate-800 text-right"
                    onClick={() => handleSort("net_edge_pct")}
                  >
                    Net Edge % {sortField === "net_edge_pct" ? (sortAsc ? "▲" : "▼") : ""}
                  </th>
                  <th className="py-3 px-3 text-center">Quality</th>
                  <th className="py-3 px-3 text-right">Freshness</th>
                  <th className="py-3 px-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {paginatedInstruments.map((row) => {
                  const isPosChange = row.change_pct > 0;
                  const isNegChange = row.change_pct < 0;
                  return (
                    <tr
                      key={row.trading_symbol}
                      onClick={() => setSelectedSymbol(row.trading_symbol)}
                      className={`hover:bg-slate-50/80 cursor-pointer transition ${
                        selectedSymbol === row.trading_symbol ? "bg-slate-100/80" : ""
                      }`}
                    >
                      <td className="py-3 px-3">
                        <div className="font-bold text-slate-900 flex items-center gap-1.5">
                          <span className="hover:text-emerald-700">{row.trading_symbol}</span>
                          <BarChart2 className="w-3.5 h-3.5 text-slate-400 hover:text-emerald-600" />
                        </div>
                        <div className="text-[10px] text-slate-500 font-sans truncate max-w-[140px]">
                          {row.name}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right font-bold text-slate-900">
                        {formatINR(row.ltp)}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600">
                        {row.bid > 0 ? formatINR(row.bid) : "-"}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600">
                        {row.ask > 0 ? formatINR(row.ask) : "-"}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600 font-medium">
                        {row.spread_pct > 0 ? `${row.spread_pct.toFixed(2)}%` : "-"}
                      </td>
                      <td
                        className={`py-3 px-3 text-right font-semibold ${
                          isPosChange ? "text-emerald-600" : isNegChange ? "text-rose-600" : "text-slate-600"
                        }`}
                      >
                        {formatPct(row.change_pct)}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600">
                        {row.volume.toLocaleString("en-IN")}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`font-semibold ${
                            row.relative_volume >= 2.0 ? "text-emerald-600" : "text-slate-600"
                          }`}
                        >
                          {row.relative_volume.toFixed(1)}x
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600">
                        {row.volatility.toFixed(2)}%
                      </td>
                      <td
                        className={`py-3 px-3 text-right ${
                          row.deviation_from_ma > 0
                            ? "text-emerald-600"
                            : row.deviation_from_ma < 0
                            ? "text-rose-600"
                            : "text-slate-600"
                        }`}
                      >
                        {formatPct(row.deviation_from_ma)}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`font-bold px-1.5 py-0.5 rounded ${
                            row.net_edge_pct >= 0.2
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "text-slate-500"
                          }`}
                        >
                          {formatPct(row.net_edge_pct)}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <DataQualityBadge quality={row.data_quality} />
                      </td>
                      <td className="py-3 px-3 text-right text-slate-500">
                        {row.data_freshness_ms}ms
                      </td>
                      <td className="py-3 px-3 text-center" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleAddToWatchlist(row.trading_symbol, row.name)}
                          disabled={addingSymbol === row.trading_symbol}
                          className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-semibold transition flex items-center gap-1 mx-auto"
                        >
                          <Plus className="w-3 h-3" />
                          <span>Watch</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Clean Pagination Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-600 font-sans">
            <div>
              Showing <span className="font-semibold text-slate-900">{filteredInstruments.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}</span> to{" "}
              <span className="font-semibold text-slate-900">{Math.min(currentPage * pageSize, filteredInstruments.length)}</span> of{" "}
              <span className="font-semibold text-slate-900">{filteredInstruments.length.toLocaleString()}</span> stocks
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <span>Rows:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="bg-white border border-slate-300 rounded-lg px-2 py-1 text-xs text-slate-800 font-mono focus:outline-none"
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>

              <div className="flex items-center gap-1 font-mono">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  className="p-1 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="px-2.5 py-0.5 text-xs font-semibold text-slate-900">
                  {currentPage} / {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="p-1 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Signals Tab */
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-mono uppercase border-b border-slate-200">
                <tr>
                  <th className="py-3 px-3">Symbol</th>
                  <th className="py-3 px-3">Strategy</th>
                  <th className="py-3 px-3">Direction</th>
                  <th className="py-3 px-3 text-right">Entry Price</th>
                  <th className="py-3 px-3 text-right">Reference Price</th>
                  <th className="py-3 px-3 text-right">Gross Edge</th>
                  <th className="py-3 px-3 text-right">Est. Cost</th>
                  <th className="py-3 px-3 text-right">Net Edge</th>
                  <th className="py-3 px-3 text-center">Status</th>
                  <th className="py-3 px-3">Explanation / Decision Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {signals.map((sig) => {
                  const isAccepted = sig.status === "ACCEPTED";
                  return (
                    <tr
                      key={sig.id}
                      onClick={() => setSelectedSymbol(sig.trading_symbol)}
                      className="hover:bg-slate-50/80 transition cursor-pointer"
                    >
                      <td className="py-3 px-3 font-bold text-slate-900 flex items-center gap-1.5">
                        <span className="hover:text-emerald-700 hover:underline">{sig.trading_symbol}</span>
                        <span className="text-[10px] text-emerald-600 font-normal">📈 Chart</span>
                      </td>
                      <td className="py-3 px-3 text-slate-600">{sig.strategy}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            sig.signal_type === "BUY"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}
                        >
                          {sig.signal_type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right text-slate-800">
                        {formatINR(sig.entry_price)}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600">
                        {sig.reference_price ? formatINR(sig.reference_price) : "-"}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-600">
                        {formatPct(sig.expected_edge_pct)}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-500">
                        {formatPct(sig.estimated_cost_pct, false)}
                      </td>
                      <td className="py-3 px-3 text-right font-bold text-emerald-700">
                        {formatPct(sig.net_edge_pct)}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                            isAccepted
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-amber-50 text-amber-700 border border-amber-200"
                          }`}
                        >
                          {isAccepted ? "ACCEPTED" : "REJECTED"}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-[11px] text-slate-600 font-sans max-w-sm truncate">
                        {isAccepted ? sig.reason : sig.rejection_reason || sig.reason}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Exactly ONE Stock Candlestick & Trades Chart Modal rendered when selected */}
      {selectedSymbol && (
        <StockCandleChartModal
          symbol={selectedSymbol}
          onClose={() => setSelectedSymbol(null)}
          onTradeExecuted={() => {
            refreshInstruments();
            refreshSignals();
          }}
        />
      )}
    </div>
  );
}
