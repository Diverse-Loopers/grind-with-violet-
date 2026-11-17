"use client";

import React, { useState } from "react";
import { useRiskSettings, useRiskStatus, useAuditLogs } from "@/hooks/useApi";
import { KillSwitch } from "@/components/KillSwitch";
import { formatINR, formatPct, formatISTTime } from "@/lib/format";
import { putData } from "@/lib/api";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Sliders,
  History,
  CheckCircle2,
} from "lucide-react";

export default function RiskConsolePage() {
  const { data: settings, mutate: refreshSettings } = useRiskSettings();
  const { data: status, mutate: refreshStatus } = useRiskStatus();
  const { data: auditData } = useAuditLogs();

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form states
  const [maxPosPct, setMaxPosPct] = useState<number | undefined>(undefined);
  const [maxDailyLoss, setMaxDailyLoss] = useState<number | undefined>(undefined);
  const [maxOpenPos, setMaxOpenPos] = useState<number | undefined>(undefined);
  const [maxOrderVal, setMaxOrderVal] = useState<number | undefined>(undefined);
  const [quoteAge, setQuoteAge] = useState<number | undefined>(undefined);
  const [minEdge, setMinEdge] = useState<number | undefined>(undefined);
  const [spreadEnabled, setSpreadEnabled] = useState<boolean | undefined>(undefined);
  const [gapEnabled, setGapEnabled] = useState<boolean | undefined>(undefined);
  const [pairsEnabled, setPairsEnabled] = useState<boolean | undefined>(undefined);

  React.useEffect(() => {
    if (settings) {
      if (maxPosPct === undefined) setMaxPosPct(settings.max_position_pct);
      if (maxDailyLoss === undefined) setMaxDailyLoss(settings.max_daily_loss);
      if (maxOpenPos === undefined) setMaxOpenPos(settings.max_open_positions);
      if (maxOrderVal === undefined) setMaxOrderVal(settings.max_single_order_value);
      if (quoteAge === undefined) setQuoteAge(settings.quote_max_age_seconds);
      if (minEdge === undefined) setMinEdge(settings.min_net_edge_pct);
      if (spreadEnabled === undefined) setSpreadEnabled(settings.strategy_spread_enabled);
      if (gapEnabled === undefined) setGapEnabled(settings.strategy_gap_enabled);
      if (pairsEnabled === undefined) setPairsEnabled(settings.strategy_pairs_enabled);
    }
  }, [settings]);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      await putData("/api/risk/settings", {
        max_position_pct: Number(maxPosPct),
        max_daily_loss: Number(maxDailyLoss),
        max_open_positions: Number(maxOpenPos),
        max_single_order_value: Number(maxOrderVal),
        quote_max_age_seconds: Number(quoteAge),
        min_net_edge_pct: Number(minEdge),
        strategy_spread_enabled: Boolean(spreadEnabled),
        strategy_gap_enabled: Boolean(gapEnabled),
        strategy_pairs_enabled: Boolean(pairsEnabled),
      });
      refreshSettings();
      refreshStatus();
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert(`Error saving settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const exposure = status?.current_exposure;
  const isKillSwitchActive = status?.kill_switch_active ?? false;
  const alerts = status?.alerts || [];
  const logs = auditData?.logs || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header and Emergency Kill Switch */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white border border-slate-200 p-5 rounded-2xl shadow-xs">
        <div className="flex items-center gap-3.5">
          <div
            className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ${
              isKillSwitchActive
                ? "bg-rose-50 text-rose-600 border border-rose-200"
                : "bg-emerald-50 text-emerald-600 border border-emerald-200"
            }`}
          >
            {isKillSwitchActive ? <ShieldAlert className="w-6 h-6" /> : <ShieldCheck className="w-6 h-6" />}
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 flex items-center gap-2">
              Autonomous Risk Control Console
              <span
                className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-semibold ${
                  isKillSwitchActive
                    ? "bg-rose-50 text-rose-700 border border-rose-200"
                    : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                }`}
              >
                {isKillSwitchActive ? "EMERGENCY HALT ACTIVE" : "PROTECTIONS ARMED"}
              </span>
            </h1>
            <p className="text-xs text-slate-500">
              Deterministic pre-trade verification enforcing position concentration, daily drawdown, and quote freshness caps
            </p>
          </div>
        </div>

        <KillSwitch
          isActive={isKillSwitchActive}
          onToggled={() => {
            refreshStatus();
            refreshSettings();
          }}
        />
      </div>

      {/* Exposure Limits Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Concentration Gauge */}
        <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-600">
            <span className="font-semibold">Single Position Concentration</span>
            <span className="font-mono font-bold text-slate-900">
              {exposure?.max_single_position_pct ?? 0}% / {exposure?.max_single_position_pct_limit ?? 10}%
            </span>
          </div>
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                (exposure?.max_single_position_pct ?? 0) > (exposure?.max_single_position_pct_limit ?? 10) * 0.8
                  ? "bg-amber-500"
                  : "bg-emerald-500"
              }`}
              style={{
                width: `${Math.min(
                  100,
                  ((exposure?.max_single_position_pct ?? 0) / (exposure?.max_single_position_pct_limit ?? 10)) * 100
                )}%`,
              }}
            />
          </div>
          <div className="text-[11px] text-slate-500 font-mono">
            Max Single Pos Value: {formatINR(exposure?.max_single_position_value ?? 0)}
          </div>
        </div>

        {/* Daily Drawdown Gauge */}
        <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-600">
            <span className="font-semibold">Daily Realized Loss Cap</span>
            <span className="font-mono font-bold text-slate-900">
              {formatINR(exposure?.daily_loss ?? 0)} / {formatINR(exposure?.daily_loss_limit ?? 50000)}
            </span>
          </div>
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 transition-all"
              style={{
                width: `${Math.min(
                  100,
                  ((exposure?.daily_loss ?? 0) / (exposure?.daily_loss_limit ?? 50000)) * 100
                )}%`,
              }}
            />
          </div>
          <div className="text-[11px] text-slate-500 font-mono">
            Halt threshold: {formatINR(exposure?.daily_loss_limit ?? 50000)}
          </div>
        </div>

        {/* Open Positions Count */}
        <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-600">
            <span className="font-semibold">Open Positions Limit</span>
            <span className="font-mono font-bold text-slate-900">
              {exposure?.open_positions_count ?? 0} / {exposure?.open_positions_limit ?? 10}
            </span>
          </div>
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all"
              style={{
                width: `${Math.min(
                  100,
                  ((exposure?.open_positions_count ?? 0) / (exposure?.open_positions_limit ?? 10)) * 100
                )}%`,
              }}
            />
          </div>
          <div className="text-[11px] text-slate-500 font-mono">
            Slots available: {(exposure?.open_positions_limit ?? 10) - (exposure?.open_positions_count ?? 0)}
          </div>
        </div>
      </div>

      {/* Alerts banner if any */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alt, idx) => (
            <div
              key={idx}
              className={`p-3.5 rounded-xl border flex items-center gap-3 text-xs font-mono ${
                alt.level === "CRITICAL"
                  ? "bg-rose-50 border-rose-200 text-rose-700"
                  : "bg-amber-50 border-amber-200 text-amber-700"
              }`}
            >
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{alt.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Main Form and Audit Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Limits Form */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-emerald-600" />
              Configurable Risk Parameters
            </h2>
            {saveSuccess && (
              <span className="text-xs text-emerald-700 flex items-center gap-1 font-mono font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" /> Saved
              </span>
            )}
          </div>

          <form onSubmit={handleSaveSettings} className="space-y-4 text-xs font-mono">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-slate-600 block mb-1 font-semibold">Max Position % of Equity</label>
                <input
                  type="number"
                  step="0.5"
                  value={maxPosPct ?? 10}
                  onChange={(e) => setMaxPosPct(Number(e.target.value))}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="text-slate-600 block mb-1 font-semibold">Max Daily Loss (₹)</label>
                <input
                  type="number"
                  value={maxDailyLoss ?? 50000}
                  onChange={(e) => setMaxDailyLoss(Number(e.target.value))}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-slate-600 block mb-1 font-semibold">Max Open Positions</label>
                <input
                  type="number"
                  value={maxOpenPos ?? 10}
                  onChange={(e) => setMaxOpenPos(Number(e.target.value))}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="text-slate-600 block mb-1 font-semibold">Max Single Order Value (₹)</label>
                <input
                  type="number"
                  value={maxOrderVal ?? 100000}
                  onChange={(e) => setMaxOrderVal(Number(e.target.value))}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-slate-600 block mb-1 font-semibold">Quote Max Age (Seconds)</label>
                <input
                  type="number"
                  value={quoteAge ?? 30}
                  onChange={(e) => setQuoteAge(Number(e.target.value))}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="text-slate-600 block mb-1 font-semibold">Min Net Edge % After Cost</label>
                <input
                  type="number"
                  step="0.05"
                  value={minEdge ?? 0.1}
                  onChange={(e) => setMinEdge(Number(e.target.value))}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            {/* Strategy Toggles */}
            <div className="pt-2 border-t border-slate-100 space-y-2">
              <span className="text-slate-700 font-bold block mb-1">Strategy Activation Switches</span>
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-slate-700">Strategy A: Executable Spread Scanner</span>
                <input
                  type="checkbox"
                  checked={spreadEnabled ?? true}
                  onChange={(e) => setSpreadEnabled(e.target.checked)}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-slate-700">Strategy B: Intraday Price-Gap Detector</span>
                <input
                  type="checkbox"
                  checked={gapEnabled ?? true}
                  onChange={(e) => setGapEnabled(e.target.checked)}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-slate-700">Strategy C: Statistical Pairs Research</span>
                <input
                  type="checkbox"
                  checked={pairsEnabled ?? true}
                  onChange={(e) => setPairsEnabled(e.target.checked)}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition text-xs font-mono shadow-xs"
            >
              {saving ? "Saving Changes..." : "Apply & Persist Risk Settings"}
            </button>
          </form>
        </div>

        {/* Audit Log Panel */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <History className="w-4 h-4 text-emerald-600" />
              Pre-Trade Intercept Audit Trail
            </h2>
            <span className="text-xs text-slate-500 font-mono">Latest decisions</span>
          </div>

          <div className="overflow-y-auto max-h-[420px] space-y-2 pr-1">
            {logs.length === 0 ? (
              <div className="text-center py-10 text-xs text-slate-500">No risk events logged yet.</div>
            ) : (
              logs.map((log) => {
                const isApproved = log.outcome === "APPROVED";
                return (
                  <div
                    key={log.id}
                    className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">
                        {log.trading_symbol ? `${log.trading_symbol} • ` : ""}
                        {log.action}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          isApproved
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {log.outcome}
                      </span>
                    </div>
                    <div className="text-slate-600 text-[11px] font-sans truncate">{log.details}</div>
                    <div className="text-slate-400 text-[10px]">{formatISTTime(log.timestamp)}</div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
