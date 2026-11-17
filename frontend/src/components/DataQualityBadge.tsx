import React from "react";
import { DataQuality } from "@/types";

interface Props {
  quality: DataQuality;
}

export const DataQualityBadge: React.FC<Props> = ({ quality }) => {
  const styles: Record<DataQuality, string> = {
    LIVE: "bg-emerald-50 text-emerald-700 border-emerald-200",
    REAL: "bg-emerald-50 text-emerald-700 border-emerald-200",
    DELAYED: "bg-amber-50 text-amber-700 border-amber-200",
    CACHED: "bg-orange-50 text-orange-700 border-orange-200",
    DEMO: "bg-slate-100 text-slate-600 border-slate-200",
  };

  const style = styles[quality] || styles.DEMO;

  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium border ${style}`}>
      {quality}
    </span>
  );
};
