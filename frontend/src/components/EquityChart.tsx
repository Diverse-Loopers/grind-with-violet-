"use client";

import React, { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";
import { EquityPoint } from "@/types";

interface Props {
  data: EquityPoint[];
  height?: number;
}

export const EquityChart: React.FC<Props> = ({ data, height = 300 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#64748b",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#f1f5f9" },
        horzLines: { color: "#f1f5f9" },
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

    const areaSeries = chart.addAreaSeries({
      topColor: "rgba(0, 208, 156, 0.25)",
      bottomColor: "rgba(0, 208, 156, 0.0)",
      lineColor: "#00d09c",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = areaSeries;

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
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || !data || data.length === 0) return;

    const formattedData = data.map((d, index) => {
      const ts = Math.floor(new Date(d.timestamp).getTime() / 1000) || (1700000000 + index * 60);
      return {
        time: ts as any,
        value: d.total_equity,
      };
    });

    formattedData.sort((a, b) => (a.time as number) - (b.time as number));
    const uniqueData = formattedData.filter(
      (item, index, self) => index === 0 || item.time > (self[index - 1].time as number)
    );

    if (uniqueData.length > 0) {
      seriesRef.current.setData(uniqueData);
      chartRef.current?.timeScale().fitContent();
    }
  }, [data]);

  return <div ref={chartContainerRef} className="w-full relative" />;
};
