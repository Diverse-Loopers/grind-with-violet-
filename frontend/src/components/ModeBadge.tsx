import React from "react";
import { OperatingMode } from "@/types";

interface Props {
  mode: OperatingMode;
  className?: string;
}

export const ModeBadge: React.FC<Props> = ({ mode, className = "" }) => {
  const configs: Record<OperatingMode, { label: string; bg: string; text: string; border: string }> = {
    DEMO: {
      label: "DEMO MODE (SYNTHETIC DATA)",
      bg: "bg-purple-50",
      text: "text-purple-700",
      border: "border-purple-200",
    },
    PAPER: {
      label: "PAPER TRADING (GROWW LIVE FEED)",
      bg: "bg-blue-50",
      text: "text-blue-700",
      border: "border-blue-200",
    },
    LIVE: {
      label: "LIVE EXECUTION (SAFETY LOCKED)",
      bg: "bg-rose-50",
      text: "text-rose-700",
      border: "border-rose-200",
    },
  };

  const c = configs[mode] || configs.DEMO;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${c.bg} ${c.text} ${c.border} ${className}`}
    >
      <span className="w-2 h-2 rounded-full animate-pulse bg-current" />
      {c.label}
    </span>
  );
};
