"use client";

import React, { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";
import { useStockCandles } from "@/hooks/useApi";
import { formatINR, formatPct } from "@/lib/format";
import { postData } from "@/lib/api";
import {
  X,
  TrendingUp,
  TrendingDown,
  BarChart2,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Play,
  ShoppingCart,
  RefreshCw,
} from "lucide-react";

interface Props {
  symbol: string | null;
  onClose: () => void;
  onTradeExecuted?: () => void;
}

export const StockCandleChartModal: React.FC<Props> = ({
  symbol,
  onClose,
  onTradeExecuted,
}) => {
  const [intervalMins, setIntervalMins] = useState<number>(5);
  const { data: chartData, mutate: refreshCandles, isLoading } = useStockCandles(symbol, intervalMins);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const [tradeQuantity, setTradeQuantity] = useState<number>(10);
  const [executingSide, setExecutingSide] = useState<"BUY" | "SELL" | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const quote = chartData?.quote;
  const trades = chartData?.trades || [];
  const candles = chartData?.candles || [];

  // Setup lightweight-charts instance
  useEffect(() => {
    if (!chartContainerRef.current || !symbol) return;

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
      height: 380,
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
        top: 0.82,
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
  }, [symbol, intervalMins]);

  // Update chart data whenever candles or trades arrive
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || candles.length === 0) return;

    // Deduplicate and sort by time
    const sortedCandles = [...candles].sort((a, b) => a.time - b.time);
    const uniqueCandles: typeof candles = [];
    let lastTime = -1;

    for (const c of sortedCandles) {
      if (c.time > lastTime) {
        uniqueCandles.push(c);
        lastTime = c.time;
      }
    }

    const IST_OFFSET = 19800; // 5 hours 30 mins to align chart axis with Indian Standard Time (IST)

    candleSeriesRef.current.setData(
      uniqueCandles.map((c) => ({
        time: (c.time + IST_OFFSET) as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    volumeSeriesRef.current.setData(
      uniqueCandles.map((c) => ({
        time: (c.time + IST_OFFSET) as any,
        value: c.volume,
        color: c.close >= c.open ? "rgba(16, 185, 129, 0.3)" : "rgba(244, 63, 94, 0.3)",
      }))
    );

    // Apply Buy and Sell trade execution markers to candles
    if (trades && trades.length > 0 && uniqueCandles.length > 0) {
      const markers = trades.map((t) => {
        // Find closest candle time so lightweight-charts snaps marker to valid bar
        let closestTime = uniqueCandles[0].time;
        let minDiff = Math.abs(t.time - closestTime);
        for (const c of uniqueCandles) {
          const diff = Math.abs(t.time - c.time);
          if (diff < minDiff) {
            minDiff = diff;
            closestTime = c.time;
          }
        }
        return {
          time: (closestTime + IST_OFFSET) as any,
          position: (t.side === "BUY" ? "belowBar" : "aboveBar") as any,
          color: t.side === "BUY" ? "#10b981" : "#f43f5e",
          shape: (t.side === "BUY" ? "arrowUp" : "arrowDown") as any,
          text: `${t.side} ${t.quantity}x @ ₹${t.price.toFixed(1)}`,
        };
      }).sort((a, b) => (a.time as number) - (b.time as number));

      try {
        candleSeriesRef.current.setMarkers(markers);
      } catch (e) {
        // Fallback gracefully if timestamps fall outside candle ranges
      }
    }

    chartRef.current?.timeScale().fitContent();
  }, [candles, trades]);

  if (!symbol) return null;

  const ltp = quote?.ltp ?? 1000.0;
  const changePct = quote?.change_pct ?? 0.0;
  const isPos = changePct >= 0;

  // Manual fast execution
  const handleExecuteTrade = async (side: "BUY" | "SELL") => {
    try {
      setExecutingSide(side);
      setFeedback(null);
      await postData("/api/portfolio/orders", {
        trading_symbol: symbol,
        transaction_type: side,
        quantity: Number(tradeQuantity),
        order_type: "MARKET",
        product: "CNC",
      });
      setFeedback(`✓ ${side} order filled for ${tradeQuantity} qty ${symbol} @ ₹${ltp.toFixed(2)}!`);
      await refreshCandles();
      if (onTradeExecuted) onTradeExecuted();
    } catch (err: any) {
      setFeedback(`❌ Error: ${err.message}`);
    } finally {
      setExecutingSide(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6">
      <div className="bg-white rounded-2xl max-w-4xl w-full border border-slate-200 shadow-2xl flex flex-col overflow-hidden max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-600 font-bold text-sm">
              <BarChart2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-black text-slate-900 tracking-tight">{symbol}</h3>
                <span className="text-[10px] font-mono text-slate-500 bg-slate-200/80 px-2 py-0.5 rounded font-semibold">
                  NSE • EQUITY
                </span>
                <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded font-semibold">
                  {trades.length} Trade(s) on Chart
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono mt-0.5">
                <span className="text-slate-900 font-bold text-sm">{formatINR(ltp)}</span>
                <span
                  className={`flex items-center font-semibold text-xs ${
                    isPos ? "text-emerald-600" : "text-rose-600"
                  }`}
                >
                  {isPos ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                  {formatPct(changePct)}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Timeframe Selectors */}
            <div className="flex items-center p-0.5 bg-slate-200/70 rounded-xl text-xs font-mono">
              {[1, 5, 15, 60].map((mins) => (
                <button
                  key={mins}
                  onClick={() => setIntervalMins(mins)}
                  className={`px-2.5 py-1 rounded-lg font-bold transition ${
                    intervalMins === mins
                      ? "bg-white text-slate-900 shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {mins === 60 ? "1H" : `${mins}M`}
                </button>
              ))}
            </div>

            <button
              onClick={() => refreshCandles()}
              className="p-1.5 rounded-xl border border-slate-200 text-slate-500 hover:bg-slate-100 transition"
              title="Refresh Candles"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            <button
              onClick={onClose}
              className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {feedback && (
          <div className="px-6 py-2 bg-emerald-50 border-b border-emerald-200 text-xs font-semibold text-emerald-800 flex items-center justify-between">
            <span>{feedback}</span>
            <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-slate-600">
              ×
            </button>
          </div>
        )}

        {/* Chart View Container */}
        <div className="relative p-4 flex-1 min-h-[380px] bg-white">
          {isLoading && (
            <div className="absolute inset-0 z-10 bg-white/70 flex items-center justify-center">
              <div className="text-xs font-semibold text-slate-500 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                Loading Candlestick Data...
              </div>
            </div>
          )}
          <div ref={chartContainerRef} className="w-full h-[380px]" />
        </div>

        {/* Trade Execution Footer */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-slate-700">Quick Trade on {symbol}:</span>
            <div className="flex items-center gap-1.5">
              {[5, 10, 25, 50].map((qty) => (
                <button
                  key={qty}
                  onClick={() => setTradeQuantity(qty)}
                  className={`px-2 py-1 rounded-lg border text-xs font-mono font-bold transition ${
                    tradeQuantity === qty
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {qty} qty
                </button>
              ))}
            </div>
            <span className="text-slate-400 text-[11px] font-mono">
              Total: {formatINR(ltp * tradeQuantity)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleExecuteTrade("BUY")}
              disabled={executingSide !== null}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs transition disabled:opacity-50 flex items-center gap-1.5"
            >
              <ShoppingCart className="w-3.5 h-3.5" />
              <span>{executingSide === "BUY" ? "Buying..." : `BUY ${tradeQuantity} QTY`}</span>
            </button>
            <button
              onClick={() => handleExecuteTrade("SELL")}
              disabled={executingSide !== null}
              className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs shadow-xs transition disabled:opacity-50 flex items-center gap-1.5"
            >
              <span>{executingSide === "SELL" ? "Selling..." : `SELL ${tradeQuantity} QTY`}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
