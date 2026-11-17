"use client";

import React, { useState } from "react";
import { postData, fetcher } from "@/lib/api";
import {
  Link2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  PowerOff,
  X,
  KeyRound,
} from "lucide-react";
import useSWR from "swr";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onConnected?: () => void;
}

export const GrowwConnectModal: React.FC<Props> = ({ isOpen, onClose, onConnected }) => {
  const { data: growwStatus, mutate: refreshStatus } = useSWR<{
    is_connected: boolean;
    mode: string;
    adapter_type: string;
    has_token: boolean;
    masked_token: string;
    ucc?: string;
    active_segments?: string[];
    token_expiry_info: string;
  }>("/api/groww/status", fetcher);

  const [token, setToken] = useState("");
  const [targetMode, setTargetMode] = useState<"PAPER" | "LIVE">("PAPER");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  if (!isOpen) return null;

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    setLoading(true);

    try {
      const res: any = await postData("/api/groww/verify-and-connect", {
        token: token.trim(),
        app_mode: targetMode,
      });

      setSuccessMsg(res.message || "Successfully connected to Groww Live API!");
      refreshStatus();
      onConnected?.();
      setTimeout(() => {
        onClose();
      }, 2500);
    } catch (err: any) {
      setError(err.message || "Failed to verify token with Groww API.");
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await postData("/api/groww/disconnect");
      refreshStatus();
      setSuccessMsg("Disconnected from Groww. Switched back to DEMO mode.");
      onConnected?.();
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || "Failed to disconnect");
    } finally {
      setLoading(false);
    }
  };

  const isConnected = growwStatus?.is_connected ?? false;

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 rounded-2xl p-6 max-w-lg w-full space-y-5 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center font-bold">
              <Link2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Connect Official Groww API</h2>
              <p className="text-xs text-slate-500">Live Indian equity quote ingestion & portfolio sync</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Current status pill */}
        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-emerald-500 animate-pulse" : "bg-purple-500"
              }`}
            />
            <span className="font-semibold text-slate-700">
              {isConnected ? `GROWW CONNECTED (UCC: ${growwStatus?.ucc || "ACTIVE"})` : "DEMO SIMULATION ACTIVE"}
            </span>
          </div>
          {growwStatus?.masked_token && (
            <span className="text-slate-500 text-[11px]">Token: {growwStatus.masked_token}</span>
          )}
        </div>

        {/* Step-by-step guidance */}
        <div className="space-y-2 rounded-xl bg-emerald-50/60 border border-emerald-200/80 p-3.5 text-xs text-slate-700">
          <div className="font-bold text-emerald-900 flex items-center gap-1.5">
            <KeyRound className="w-4 h-4 text-emerald-600" />
            How to get your Daily Groww Access Token:
          </div>
          <ol className="list-decimal list-inside space-y-1 text-[11px] text-slate-600 pl-1 leading-relaxed">
            <li>
              Log in to your account at{" "}
              <a
                href="https://groww.in/trade-api/docs"
                target="_blank"
                rel="noreferrer"
                className="text-emerald-700 font-semibold underline inline-flex items-center gap-0.5"
              >
                Groww Trade API <ExternalLink className="w-2.5 h-2.5" />
              </a>
            </li>
            <li>Go to <strong>Profile Settings &gt; Trading APIs</strong></li>
            <li>Generate your <strong>Daily Access Token</strong> (expires daily at ~6:00 AM IST)</li>
            <li>Copy and paste the Bearer token below</li>
          </ol>
        </div>

        {/* Success or Error alert */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2 font-mono">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-700 flex items-center gap-2 font-mono">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Connection Form */}
        <form onSubmit={handleConnect} className="space-y-4 text-xs font-mono">
          <div>
            <label className="text-slate-600 block mb-1 font-semibold">
              Groww API Access Token (Bearer)
            </label>
            <input
              type="password"
              placeholder="Paste your daily token here..."
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-xl px-3.5 py-2.5 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              required={!isConnected}
            />
            <div className="text-[10px] text-slate-500 mt-1">
              Never shared or logged. Saved only in your local, git-ignored <code className="bg-slate-100 px-1 py-0.5 rounded">.env</code>.
            </div>
          </div>

          <div>
            <label className="text-slate-600 block mb-1 font-semibold">Target Operating Mode</label>
            <select
              value={targetMode}
              onChange={(e) => setTargetMode(e.target.value as any)}
              className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:border-emerald-500 font-mono"
            >
              <option value="PAPER">PAPER (Recommended: Live Groww Quotes + Simulated Fills)</option>
              <option value="LIVE" disabled>
                LIVE EXECUTION (Locked: Awaiting regulatory authorization)
              </option>
            </select>
          </div>

          <div className="flex items-center justify-between pt-2">
            {isConnected ? (
              <button
                type="button"
                onClick={handleDisconnect}
                disabled={loading}
                className="px-3.5 py-2 rounded-xl text-rose-600 bg-rose-50 hover:bg-rose-100 font-semibold text-xs flex items-center gap-1.5 transition border border-rose-200"
              >
                <PowerOff className="w-3.5 h-3.5" />
                <span>Disconnect API</span>
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !token.trim()}
                className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>{loading ? "Verifying Token..." : "Verify & Connect"}</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
