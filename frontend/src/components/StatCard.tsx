import React from "react";

interface Props {
  label: string;
  value: string | number;
  subValue?: string;
  isPositive?: boolean;
  isNegative?: boolean;
  icon?: React.ReactNode;
}

export const StatCard: React.FC<Props> = ({
  label,
  value,
  subValue,
  isPositive,
  isNegative,
  icon,
}) => {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:border-slate-300 transition">
      <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider mb-2">
        <span>{label}</span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <div className="flex items-baseline gap-2">
        <span
          className={`text-2xl font-bold font-mono ${
            isPositive
              ? "text-emerald-600"
              : isNegative
              ? "text-rose-600"
              : "text-slate-900"
          }`}
        >
          {value}
        </span>
      </div>
      {subValue && <div className="text-xs text-slate-500 mt-1 font-mono">{subValue}</div>}
    </div>
  );
};
