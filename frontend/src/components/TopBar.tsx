"use client";

import React, { useState } from "react";
import { ModeBadge } from "./ModeBadge";
import { GrowwConnectModal } from "./GrowwConnectModal";
import { useDashboardOverview } from "@/hooks/useApi";
import { Clock, Activity, Link2, Zap } from "lucide-react";
import Link from "next/link";

export const TopBar: React.FC = () => {
  const { data: overview, mutate: refreshOverview } = useDashboardOverview();
  const [showConnectModal, setShowConnectModal] = useState(false);

  const mode = overview?.mode || "DEMO";
  const isOpen = overview?.market_status?.is_open ?? false;
  const sessionName = overview?.market_status?.session || "CLOSED";
  const istTime = overview?.market_status?.market_time_ist || "--:-- IST";
  const isLiveGroww = mode === "PAPER" || mode === "LIVE";

  return (
    <>
      <header className="h-16 bg-white/95 backdrop-blur-xs border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-20 shadow-xs">
        <div className="flex items-center gap-4">
          <ModeBadge mode={mode} />
          <span className="text-xs text-slate-500 font-mono hidden md:inline">
            {overview?.data_source || "Connecting to feed..."}
          </span>
        </div>

        <div className="flex items-center gap-4">
          {/* 24/7 Global Switcher Button */}
          <Link
            href="/tradingview"
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300 hover:bg-amber-100 transition shadow-xs"
          >
            <Zap className="w-3.5 h-3.5 text-amber-600 fill-amber-500" />
            <span>24/7 Gold &amp; TradingView</span>
          </Link>

          {/* Connect Groww API Action */}
          <button
            onClick={() => setShowConnectModal(true)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition border shadow-xs ${
              isLiveGroww
                ? "bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100"
                : "bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-200"
            }`}
          >
            <Link2 className="w-3.5 h-3.5" />
            <span>{isLiveGroww ? "Groww API Active" : "Connect Real Groww"}</span>
          </button>

          {/* Market Status */}
          <div className="flex items-center gap-2 text-xs font-mono bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
            <span
              className={`w-2 h-2 rounded-full ${
                isOpen ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
              }`}
            />
            <span className="text-slate-700 font-semibold">{sessionName}</span>
            <span className="text-slate-300">•</span>
            <span className="text-slate-500 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              {istTime}
            </span>
          </div>

          {/* System Health */}
          <div className="hidden lg:flex items-center gap-1.5 text-xs font-mono text-emerald-700 bg-emerald-50 px-2.5 py-1.5 rounded-xl border border-emerald-200">
            <Activity className="w-3.5 h-3.5 text-emerald-600" />
            <span>Engine OK</span>
          </div>
        </div>
      </header>

      {/* Groww Connection Modal */}
      <GrowwConnectModal
        isOpen={showConnectModal}
        onClose={() => setShowConnectModal(false)}
        onConnected={() => refreshOverview()}
      />
    </>
  );
};
