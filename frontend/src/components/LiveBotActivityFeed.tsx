"use client";

import React, { useState } from "react";
import { useActivityFeed, useDashboardOverview } from "@/hooks/useApi";
import { postData } from "@/lib/api";
import {
  Terminal,
  Activity,
  Play,
  CheckCircle2,
  AlertTriangle,
  ShoppingCart,
  Search,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { ActivityEventItem } from "@/types";

export const LiveBotActivityFeed: React.FC<{
  onSelectSymbol?: (symbol: string) => void;
  className?: string;
}> = ({ onSelectSymbol, className = "" }) => {
  const { data: feedData, mutate: refreshFeed } = useActivityFeed();
  const { mutate: refreshOverview } = useDashboardOverview();
  const [triggering, setTriggering] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const events = feedData?.events || [];

  const handleTriggerInstantTrade = async (symbol: string = "INFY", side: string = "BUY") => {
    try {
      setTriggering(true);
      setTestResult(null);
      const res = await postData<any>(`/api/dashboard/trigger-demo-trade?symbol=${symbol}&side=${side}`);
      await refreshFeed();
      await refreshOverview();
      setTestResult(`✓ ${res.message || "Trade executed successfully!"}`);
      setTimeout(() => setTestResult(null), 5000);
    } catch (err: any) {
      setTestResult(`❌ Error: ${err.message}`);
    } finally {
      setTriggering(false);
    }
  };

  const getEventBadge = (type: string) => {
    switch (type) {
      case "ORDER_FILLED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <ShoppingCart className="w-3 h-3 text-emerald-600" />
            ORDER FILLED
          </span>
        );
      case "ORDER_CLOSED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-300">
            <CheckCircle2 className="w-3 h-3 text-purple-600" />
            POSITION CLOSED
          </span>
        );
      case "SIGNAL":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-300">
            <Activity className="w-3 h-3 text-blue-600" />
            SIGNAL
          </span>
        );
      case "RISK_PASS":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            RISK APPROVED
          </span>
        );
      case "RISK_REJECT":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            RISK CHECK
          </span>
        );
      case "SCAN":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <Search className="w-3 h-3 text-slate-500" />
            SCANNER
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            INFO
          </span>
        );
    }
  };

  return (
    <div className={`bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden flex flex-col ${className}`}>
      {/* Feed Header */}
      <div className="p-4 bg-slate-50 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-600">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900 flex items-center gap-2">
              Live Bot Activity &amp; Order Execution Feed
              <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                Engine Active
              </span>
            </div>
            <div className="text-[11px] text-slate-500">
              Real-time stream showing every scan, signal detection, risk decision, and order execution
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick Instant Test Trade Button */}
          <button
            onClick={() => handleTriggerInstantTrade("INFY", "BUY")}
            disabled={triggering}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1.5 transition shadow-xs disabled:opacity-50"
            title="Forces a test signal through the risk engine and paper broker immediately"
          >
            <Sparkles className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
            <span>{triggering ? "Executing..." : "Simulate Live Buy Now"}</span>
          </button>

          <button
            onClick={() => refreshFeed()}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-100 transition"
            title="Refresh feed"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {testResult && (
        <div className="px-4 py-2 bg-emerald-50 border-b border-emerald-200 text-xs font-semibold text-emerald-800 flex items-center justify-between">
          <span>{testResult}</span>
          <button onClick={() => setTestResult(null)} className="text-slate-400 hover:text-slate-600">
            ×
          </button>
        </div>
      )}

      {/* Events Stream Body */}
      <div className="divide-y divide-slate-100 max-h-72 overflow-y-auto font-mono text-xs">
        {events.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            Listening for bot trading events... Click &quot;Simulate Live Buy Now&quot; above to trigger an immediate test trade.
          </div>
        ) : (
          events.map((evt) => (
            <div
              key={evt.id}
              className="p-3 hover:bg-slate-50/70 transition flex items-start justify-between gap-3"
            >
              <div className="flex items-start gap-2.5 flex-1 min-w-0">
                <div className="shrink-0 mt-0.5">{getEventBadge(evt.event_type)}</div>
                <div className="min-w-0 flex-1">
                  <div className="text-slate-800 font-medium text-xs break-words font-sans">
                    {evt.message}
                  </div>
                  {evt.symbol && (
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-500 font-mono">
                      <span className="font-bold text-slate-700">{evt.symbol}</span>
                      {evt.price && <span>@ ₹{evt.price.toFixed(2)}</span>}
                      {onSelectSymbol && (
                        <button
                          onClick={() => onSelectSymbol(evt.symbol!)}
                          className="text-[10px] text-emerald-700 hover:underline font-semibold"
                        >
                          View Candle Chart →
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="text-[10px] text-slate-400 shrink-0 font-mono">
                {new Date(evt.timestamp).toLocaleTimeString()}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
