export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000";

export const POLLING_INTERVALS = {
  OVERVIEW: 5000,
  SCANNER: 5000,
  PORTFOLIO: 6000,
  RISK: 6000,
};
