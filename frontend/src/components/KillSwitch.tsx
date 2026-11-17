"use client";

import React, { useState } from "react";
import { postData } from "@/lib/api";
import { AlertOctagon, Power } from "lucide-react";

interface Props {
  isActive: boolean;
  onToggled?: () => void;
}

export const KillSwitch: React.FC<Props> = ({ isActive, onToggled }) => {
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleToggle = async () => {
    try {
      setLoading(true);
      await postData("/api/risk/kill-switch", {
        enabled: !isActive,
        reason: !isActive
          ? "Manual emergency halt triggered by operator"
          : "Operator resumed trading operations",
      });
      setShowConfirm(false);
      onToggled?.();
    } catch (err) {
      alert(`Failed to toggle kill switch: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setShowConfirm(true)}
        disabled={loading}
        className={`px-4 py-2.5 rounded-xl font-bold flex items-center gap-2.5 transition text-sm shadow-lg ${
          isActive
            ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/50"
            : "bg-red-600 hover:bg-red-500 text-white shadow-red-950/50 animate-pulse"
        }`}
      >
        <Power className="w-4 h-4" />
        <span>{isActive ? "RESUME TRADING" : "EMERGENCY KILL SWITCH"}</span>
      </button>

      {showConfirm && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600">
              <AlertOctagon className="w-6 h-6 shrink-0" />
              <h3 className="text-lg font-bold text-slate-900">
                {isActive ? "Confirm Trading Resume" : "Confirm Emergency Kill Switch"}
              </h3>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              {isActive
                ? "Resuming will allow the decision engine to approve new paper orders and continue strategy execution."
                : "Activating the Emergency Kill Switch will immediately block all incoming trading orders, cancel pending executions, and halt automated strategies."}
            </p>
            <div className="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleToggle}
                disabled={loading}
                className={`px-4 py-2 rounded-xl text-sm font-bold text-white shadow-xs ${
                  isActive ? "bg-emerald-600 hover:bg-emerald-500" : "bg-rose-600 hover:bg-rose-500"
                }`}
              >
                {loading ? "Processing..." : isActive ? "Yes, Resume" : "Yes, HALT NOW"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
