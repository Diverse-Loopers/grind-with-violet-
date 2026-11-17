import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { POLLING_INTERVALS } from "@/lib/constants";
import {
  DashboardOverview,
  ScannerInstrument,
  SignalItem,
  PositionItem,
  OrderItem,
  EquityPoint,
  RiskSettingsData,
  RiskStatusData,
  AuditLogItem,
  BacktestRunItem,
  GlobalOverviewResponse,
  GlobalPosition,
  TradingViewAlertItem,
  WalletData,
  ActivityEventItem,
  SymbolCandlesResponse,
} from "@/types";

export function useDashboardOverview() {
  return useSWR<DashboardOverview>("/api/dashboard/overview", fetcher, {
    refreshInterval: POLLING_INTERVALS.OVERVIEW,
    revalidateOnFocus: true,
  });
}

export function useScannerInstruments(search?: string) {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return useSWR<{ count: number; total_available_stocks?: number; instruments: ScannerInstrument[] }>(
    `/api/scanner/instruments${query}`,
    fetcher,
    {
      refreshInterval: search ? 0 : POLLING_INTERVALS.SCANNER,
      revalidateOnFocus: true,
    }
  );
}

export function useSignals(strategy?: string, status?: string) {
  const query = new URLSearchParams();
  if (strategy) query.set("strategy", strategy);
  if (status) query.set("status", status);
  const path = `/api/scanner/signals${query.toString() ? `?${query.toString()}` : ""}`;
  return useSWR<{ count: number; signals: SignalItem[] }>(path, fetcher, {
    refreshInterval: 5000,
  });
}

export function usePositions() {
  return useSWR<{
    summary: {
      total_positions_value: number;
      unrealized_pnl: number;
      realized_pnl: number;
      total_fees: number;
      open_count: number;
    };
    positions: PositionItem[];
  }>("/api/portfolio/positions", fetcher, {
    refreshInterval: POLLING_INTERVALS.PORTFOLIO,
  });
}

export function useOrders() {
  return useSWR<{ count: number; orders: OrderItem[] }>("/api/portfolio/orders", fetcher, {
    refreshInterval: POLLING_INTERVALS.PORTFOLIO,
  });
}

export function useEquityCurve() {
  return useSWR<{ count: number; data: EquityPoint[] }>("/api/portfolio/equity-curve", fetcher, {
    refreshInterval: 5000,
  });
}

export function useRiskSettings() {
  return useSWR<RiskSettingsData>("/api/risk/settings", fetcher);
}

export function useRiskStatus() {
  return useSWR<RiskStatusData>("/api/risk/status", fetcher, {
    refreshInterval: POLLING_INTERVALS.RISK,
  });
}

export function useAuditLogs() {
  return useSWR<{ count: number; logs: AuditLogItem[] }>("/api/risk/audit-log", fetcher, {
    refreshInterval: 5000,
  });
}

export function useBacktests() {
  return useSWR<{ count: number; runs: BacktestRunItem[] }>("/api/backtest/results", fetcher);
}

// ── 24/7 Global Engine & TradingView Hooks ────────────────────

export function useGlobalOverview() {
  return useSWR<GlobalOverviewResponse>("/api/global/overview", fetcher, {
    refreshInterval: 4000,
    revalidateOnFocus: true,
  });
}

export function useGlobalPositions() {
  return useSWR<{ open_positions: GlobalPosition[]; closed_positions: GlobalPosition[] }>(
    "/api/global/positions",
    fetcher,
    {
      refreshInterval: 5000,
      revalidateOnFocus: true,
    }
  );
}

export function useGlobalCandles(symbol: string = "XAUUSD") {
  return useSWR<{ time: number; open: number; high: number; low: number; close: number; volume: number }[]>(
    `/api/global/candles?symbol=${symbol}&count=100`,
    fetcher,
    {
      refreshInterval: 8000,
    }
  );
}

export function useGlobalStrategies() {
  return useSWR<{
    strategies: { id: string; name: string; description: string; enabled: boolean }[];
    active_signals: any[];
    confluence_score: number;
    market_sentiment: string;
    auto_confluence_trade: boolean;
    confluence_threshold: number;
    confluence_lot_size: number;
  }>("/api/global/strategies", fetcher, {
    refreshInterval: 6000,
  });
}

export function useTradingViewAlerts() {
  return useSWR<TradingViewAlertItem[]>("/api/tradingview/alerts", fetcher, {
    refreshInterval: 5000,
  });
}

export function useTradingViewPineScript() {
  return useSWR<{ pinescript: string; webhook_url: string; passphrase: string }>(
    "/api/tradingview/pinescript",
    fetcher
  );
}

export function useWalletOverview() {
  return useSWR<WalletData>("/api/portfolio/wallet", fetcher, {
    refreshInterval: 5000,
    revalidateOnFocus: true,
  });
}

export function useActivityFeed() {
  return useSWR<{ count: number; events: ActivityEventItem[] }>("/api/dashboard/activity-feed", fetcher, {
    refreshInterval: 4000,
    revalidateOnFocus: true,
  });
}

export function useStockCandles(symbol: string | null, intervalMinutes: number = 5) {
  return useSWR<SymbolCandlesResponse>(
    symbol ? `/api/scanner/candles/${encodeURIComponent(symbol)}?interval_minutes=${intervalMinutes}&count=80` : null,
    fetcher,
    {
      refreshInterval: 8000,
    }
  );
}
