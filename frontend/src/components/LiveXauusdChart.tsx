"use client";

import React, { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";
import { useGlobalCandles, useGlobalPositions } from "@/hooks/useApi";
import { BarChart2, Zap } from "lucide-react";

export const LiveXauusdChart: React.FC<{ symbol?: string; height?: number }> = ({
  symbol = "XAUUSD",
  height = 320,
}) => {
  const { data: candles } = useGlobalCandles(symbol);
  const { data: posData } = useGlobalPositions();

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

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

  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !candles || candles.length === 0) return;

    const sortedCandles = [...candles].sort((a, b) => a.time - b.time);
    const uniqueCandles: typeof candles = [];
    let lastTime = -1;

    for (const c of sortedCandles) {
      if (c.time > lastTime) {
        uniqueCandles.push(c);
        lastTime = c.time;
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

    // Apply markers for XAUUSD positions
    const openPos = posData?.open_positions?.filter((p) => p.symbol === symbol) || [];
    const closedPos = posData?.closed_positions?.filter((p) => p.symbol === symbol) || [];
    const allPos = [...openPos, ...closedPos];

    if (allPos.length > 0 && uniqueCandles.length > 0) {
      const markers = allPos.map((p) => {
        const timeSec = Math.floor(new Date(p.opened_at).getTime() / 1000);
        let closestTime = uniqueCandles[0].time;
        let minDiff = Math.abs(timeSec - closestTime);
        for (const c of uniqueCandles) {
          const diff = Math.abs(timeSec - c.time);
          if (diff < minDiff) {
            minDiff = diff;
            closestTime = c.time;
          }
        }
        return {
          time: closestTime as any,
          position: (p.side === "BUY" ? "belowBar" : "aboveBar") as any,
          color: p.side === "BUY" ? "#10b981" : "#f43f5e",
          shape: (p.side === "BUY" ? "arrowUp" : "arrowDown") as any,
          text: `${p.side} ${p.lots}L @ $${p.entry_price.toFixed(1)}`,
        };
      }).sort((a, b) => (a.time as number) - (b.time as number));
      try {
        candleSeriesRef.current.setMarkers(markers);
      } catch (e) {
        // Fallback gracefully
      }
    }

    chartRef.current?.timeScale().fitContent();
  }, [candles, posData, symbol]);

  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-600 font-bold">
            <BarChart2 className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              XAU/USD Gold Spot Live Candlestick Feed (15M)
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </h3>
            <p className="text-[11px] text-slate-500">Continuous 24/7 market pricing with trade execution overlay</p>
          </div>
        </div>
        <div className="text-xs font-mono text-amber-800 bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-200 font-semibold flex items-center gap-1">
          <Zap className="w-3.5 h-3.5 text-amber-600" />
          <span>Real-time Ticks</span>
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
};
