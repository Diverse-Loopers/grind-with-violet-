"use client";

import React, { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";
import { BarChart2, Layers, RefreshCw, Zap } from "lucide-react";
import { API_BASE } from "@/lib/constants";

interface CandleItem {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface OrderBookLevel {
  price: number;
  quantity: number;
}

interface OrderBookData {
  pair: string;
  timestamp: number;
  bids: [number, number][];
  asks: [number, number][];
  best_bid: number;
  best_ask: number;
  spread: number;
  spread_pct: number;
  bid_depth_value: number;
  ask_depth_value: number;
}

interface LiveCoinDCXChartProps {
  market: string;
  height?: number;
}

export const LiveCoinDCXChart: React.FC<LiveCoinDCXChartProps> = ({
  market = "BTCINR",
  height = 360,
}) => {
  const [interval, setInterval] = useState<string>("15m");
  const [candles, setCandles] = useState<CandleItem[]>([]);
  const [orderbook, setOrderbook] = useState<OrderBookData | null>(null);
  const [activeView, setActiveView] = useState<"chart" | "orderbook">("chart");
  const [loading, setLoading] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Fetch Candles
  const fetchCandles = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/coindcx/candles/${market}?interval=${interval}&limit=100`);
      if (res.ok) {
        const data: CandleItem[] = await res.json();
        setCandles(data);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error("Failed fetching CoinDCX candles:", err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch Order Book
  const fetchOrderBook = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/coindcx/orderbook/${market}`);
      if (res.ok) {
        const data: OrderBookData = await res.json();
        setOrderbook(data);
      }
    } catch (err) {
      console.error("Failed fetching CoinDCX orderbook:", err);
    }
  };

  useEffect(() => {
    fetchCandles();
    fetchOrderBook();
    const intervalTimer = window.setInterval(() => {
      fetchCandles();
      fetchOrderBook();
    }, 10000);
    return () => clearInterval(intervalTimer);
  }, [market, interval]);

  // Setup lightweight-chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    chartContainerRef.current.innerHTML = "";

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#64748b",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#f8fafc" },
        horzLines: { color: "#f8fafc" },
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#e2e8f0",
      },
      rightPriceScale: {
        borderColor: "#e2e8f0",
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#f43f5e",
      borderUpColor: "#10b981",
      borderDownColor: "#f43f5e",
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
    });

    const volumeSeries = chart.addHistogramSeries({
      color: "#e2e8f0",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.85,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [height]);

  // Update chart data
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !candles || candles.length === 0) return;

    const sortedCandles = [...candles].sort((a, b) => a.time - b.time);
    const uniqueCandles: CandleItem[] = [];
    let lastTime = -1;

    for (const c of sortedCandles) {
      // CoinDCX API candle timestamps in ms or s
      const timeInSec = c.time > 1e11 ? Math.floor(c.time / 1000) : c.time;
      if (timeInSec > lastTime) {
        uniqueCandles.push({ ...c, time: timeInSec });
        lastTime = timeInSec;
      }
    }

    candleSeriesRef.current.setData(
      uniqueCandles.map((c) => ({
        time: c.time as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    volumeSeriesRef.current.setData(
      uniqueCandles.map((c) => ({
        time: c.time as any,
        value: c.volume,
        color: c.close >= c.open ? "rgba(16, 185, 129, 0.3)" : "rgba(244, 63, 94, 0.3)",
      }))
    );

    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  const intervals = ["1m", "15m", "1h", "1d"];

  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-orange-500/10 border border-orange-500/30 flex items-center justify-center text-orange-600 font-bold">
            <BarChart2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              CoinDCX Live Chart: {market}
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            </h3>
            <p className="text-[11px] text-slate-500">
              Official public candle & order book feed • Updated {lastUpdated || "just now"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs">
            <button
              onClick={() => setActiveView("chart")}
              className={`px-3 py-1 rounded-lg font-medium transition ${
                activeView === "chart" ? "bg-white text-slate-900 shadow-xs font-semibold" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Candlesticks
            </button>
            <button
              onClick={() => setActiveView("orderbook")}
              className={`px-3 py-1 rounded-lg font-medium transition flex items-center gap-1 ${
                activeView === "orderbook" ? "bg-white text-slate-900 shadow-xs font-semibold" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Order Book
            </button>
          </div>

          {/* Interval tabs */}
          {activeView === "chart" && (
            <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-mono">
              {intervals.map((int) => (
                <button
                  key={int}
                  onClick={() => setInterval(int)}
                  className={`px-2.5 py-1 rounded-lg font-medium transition ${
                    interval === int ? "bg-orange-500 text-white font-bold shadow-xs" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {int.toUpperCase()}
                </button>
              ))}
            </div>
          )}

          <button
            onClick={() => {
              fetchCandles();
              fetchOrderBook();
            }}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-200 transition"
            title="Refresh feed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Chart Canvas View */}
      <div className={activeView === "chart" ? "block" : "hidden"}>
        <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
      </div>

      {/* Level 2 Order Book View */}
      {activeView === "orderbook" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" style={{ minHeight: `${height}px` }}>
          {/* Bids */}
          <div className="border border-slate-200 rounded-xl p-3 bg-slate-50/50">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200 mb-2 text-xs font-bold text-emerald-700">
              <span>Bids (Buyers)</span>
              <span>Best: ₹{orderbook?.best_bid?.toLocaleString() || "0"}</span>
            </div>
            <div className="space-y-1 font-mono text-xs max-h-72 overflow-y-auto">
              <div className="flex justify-between text-[11px] text-slate-400 font-semibold px-1 pb-1">
                <span>Price</span>
                <span>Quantity</span>
                <span>Depth</span>
              </div>
              {orderbook?.bids?.slice(0, 15).map(([p, q], idx) => {
                const depthPct = Math.min(100, Math.round((q / (orderbook.bids[0][1] * 2)) * 100));
                return (
                  <div key={idx} className="relative flex justify-between px-2 py-1 rounded bg-white border border-slate-100 overflow-hidden">
                    <div
                      className="absolute inset-y-0 right-0 bg-emerald-500/10 pointer-events-none"
                      style={{ width: `${depthPct}%` }}
                    />
                    <span className="text-emerald-600 font-semibold relative z-10">₹{p.toLocaleString()}</span>
                    <span className="text-slate-700 relative z-10">{q.toFixed(4)}</span>
                    <span className="text-slate-400 text-[10px] relative z-10">₹{(p * q).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Asks */}
          <div className="border border-slate-200 rounded-xl p-3 bg-slate-50/50">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200 mb-2 text-xs font-bold text-rose-700">
              <span>Asks (Sellers)</span>
              <span>Best: ₹{orderbook?.best_ask?.toLocaleString() || "0"}</span>
            </div>
            <div className="space-y-1 font-mono text-xs max-h-72 overflow-y-auto">
              <div className="flex justify-between text-[11px] text-slate-400 font-semibold px-1 pb-1">
                <span>Price</span>
                <span>Quantity</span>
                <span>Depth</span>
              </div>
              {orderbook?.asks?.slice(0, 15).map(([p, q], idx) => {
                const depthPct = Math.min(100, Math.round((q / (orderbook.asks[0][1] * 2)) * 100));
                return (
                  <div key={idx} className="relative flex justify-between px-2 py-1 rounded bg-white border border-slate-100 overflow-hidden">
                    <div
                      className="absolute inset-y-0 right-0 bg-rose-500/10 pointer-events-none"
                      style={{ width: `${depthPct}%` }}
                    />
                    <span className="text-rose-600 font-semibold relative z-10">₹{p.toLocaleString()}</span>
                    <span className="text-slate-700 relative z-10">{q.toFixed(4)}</span>
                    <span className="text-slate-400 text-[10px] relative z-10">₹{(p * q).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
