export type OperatingMode = "DEMO" | "PAPER" | "LIVE";
export type DataQuality = "LIVE" | "REAL" | "DELAYED" | "CACHED" | "DEMO";
export type SignalStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "EXPIRED";
export type StrategyType = "SPREAD" | "GAP" | "PAIRS";

export interface DashboardOverview {
  mode: OperatingMode;
  market_status: {
    is_open: boolean;
    session: string;
    market_time_ist: string;
  };
  data_source: string;
  data_freshness: string;
  cash_balance: number;
  portfolio_equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  active_positions: number;
  signals_detected: number;
  signals_rejected: number;
  system_health: {
    api: boolean;
    database: boolean;
    scanner: boolean;
    risk_engine: boolean;
  };
}

export interface ScannerInstrument {
  trading_symbol: string;
  exchange: string;
  name: string;
  ltp: number;
  bid: number;
  ask: number;
  spread_pct: number;
  change_pct: number;
  volume: number;
  relative_volume: number;
  high: number;
  low: number;
  volatility: number;
  deviation_from_ma: number;
  gap_pct: number;
  net_edge_pct: number;
  data_quality: DataQuality;
  quote_timestamp: string | null;
  data_freshness_ms: number;
}

export interface SignalItem {
  id: number;
  instrument_id?: number;
  trading_symbol: string;
  strategy: StrategyType;
  signal_type: "BUY" | "SELL";
  entry_price: number;
  reference_price?: number;
  expected_edge_pct?: number;
  estimated_cost_pct?: number;
  net_edge_pct?: number;
  confidence_score?: number;
  reason?: string;
  data_quality: DataQuality;
  quote_timestamp?: string;
  bid_price?: number;
  ask_price?: number;
  spread_pct?: number;
  volume?: number;
  relative_volume?: number;
  volatility?: number;
  status: SignalStatus;
  rejection_reason?: string;
  created_at?: string;
}

export interface PositionItem {
  id: number;
  trading_symbol: string;
  exchange: string;
  quantity: number;
  average_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_fees: number;
  strategy?: string;
  mode: string;
  opened_at?: string;
}

export interface OrderItem {
  id: number;
  trading_symbol: string;
  exchange: string;
  order_type: string;
  transaction_type: "BUY" | "SELL";
  product: string;
  quantity: number;
  price?: number;
  status: string;
  filled_quantity: number;
  average_fill_price?: number;
  simulated_slippage?: number;
  fees: number;
  paper_or_live: string;
  order_reference_id?: string;
  created_at?: string;
}

export interface EquityPoint {
  timestamp: string;
  cash_balance: number;
  positions_value: number;
  total_equity: number;
  daily_pnl: number;
  cumulative_pnl: number;
  drawdown_pct: number;
}

export interface RiskSettingsData {
  max_position_pct: number;
  max_daily_loss: number;
  max_open_positions: number;
  max_single_order_value: number;
  quote_max_age_seconds: number;
  min_net_edge_pct: number;
  kill_switch_active: boolean;
  strategy_spread_enabled: boolean;
  strategy_gap_enabled: boolean;
  strategy_pairs_enabled: boolean;
}

export interface RiskStatusData {
  kill_switch_active: boolean;
  current_exposure: {
    total_equity: number;
    max_single_position_value: number;
    max_single_position_pct: number;
    max_single_position_pct_limit: number;
    open_positions_count: number;
    open_positions_limit: number;
    daily_loss: number;
    daily_loss_limit: number;
  };
  alerts: Array<{ level: "INFO" | "WARNING" | "CRITICAL"; message: string }>;
}

export interface AuditLogItem {
  id: number;
  timestamp: string;
  event_type: string;
  component: string;
  trading_symbol?: string;
  action: string;
  details?: string;
  outcome: string;
}

export interface BacktestRunItem {
  id: number;
  strategy: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital?: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate?: number;
  max_drawdown_pct?: number;
  net_return_pct?: number;
  profit_factor?: number;
  avg_profit?: number;
  avg_loss?: number;
  sharpe_ratio?: number;
  total_fees: number;
  status: string;
  created_at?: string;
}

// ── 24/7 Global Engine & TradingView Types ────────────────────

export interface GlobalQuote {
  symbol: string;
  name: string;
  bid: number;
  ask: number;
  ltp: number;
  spread: number;
  spread_pips: number;
  change_24h: number;
  change_24h_pct: number;
  high_24h: number;
  low_24h: number;
  open_24h: number;
  volume: number;
  timestamp: string;
  session: string;
  is_open_24_7: boolean;
}

export interface GlobalAccount {
  currency: string;
  balance: number;
  equity: number;
  margin_used: number;
  free_margin: number;
  margin_level_pct: number;
  leverage: number;
  daily_pnl: number;
  total_pnl: number;
  open_positions_count: number;
  win_rate: number;
}

export interface GlobalPosition {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  lots: number;
  entry_price: number;
  current_price: number;
  sl?: number;
  tp?: number;
  unrealized_pnl: number;
  realized_pnl: number;
  margin_used: number;
  pip_gain: number;
  strategy: string;
  status: "OPEN" | "CLOSED";
  opened_at: string;
  closed_at?: string;
  close_price?: number;
  close_reason?: string;
}

export interface StrategySignalItem {
  strategy_id: string;
  strategy_name: string;
  symbol: string;
  action: "BUY" | "SELL" | "CLOSE" | "HOLD";
  confidence: number;
  price: number;
  sl: number;
  tp: number;
  risk_reward: number;
  reason: string;
  timestamp: string;
}

export interface OptimizationMetricItem {
  strategy_id: string;
  name: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  net_profit: number;
  return_pct: number;
  profit_factor: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
}

export interface MaxProfitResult {
  timestamp: string;
  best_strategy: string;
  max_profit: number;
  max_return_pct: number;
  optimal_confluence_threshold: number;
  optimal_tp_sl_ratio: number;
  optimal_leverage: number;
  recommended_lot_size: number;
  strategies_compared: OptimizationMetricItem[];
  ensemble_profit: number;
  ensemble_win_rate: number;
  ensemble_profit_factor: number;
  confluence_score: number;
  market_sentiment: "STRONG_BUY" | "BUY" | "NEUTRAL" | "SELL" | "STRONG_SELL";
  recommendation_summary: string;
}

export interface TradingViewAlertItem {
  id: string;
  ticker: string;
  action: string;
  price: number;
  quantity: number;
  strategy: string;
  timeframe: string;
  tp?: number;
  sl?: number;
  status: string;
  message: string;
  received_at: string;
  raw_payload?: Record<string, any>;
}

export interface GlobalOverviewResponse {
  market: string;
  primary_asset: string;
  quote: GlobalQuote;
  account: GlobalAccount;
  session: string;
  is_open_24_7: boolean;
  confluence_score: number;
  market_sentiment: string;
  auto_trade_enabled: boolean;
  auto_confluence_trading: boolean;
  active_signals_count: number;
  indicators: Record<string, number>;
}

// ── Wallet & Bot Activity Types ───────────────────────────────

export interface WalletData {
  currency: string;
  cash_balance: number;
  invested_amount: number;
  total_equity: number;
  daily_pnl: number;
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions_count: number;
  total_filled_orders: number;
  allocation: {
    cash_pct: number;
    invested_pct: number;
  };
  starting_balance: number;
}

export interface ActivityEventItem {
  id: string;
  timestamp: string;
  event_type: "SCAN" | "SIGNAL" | "RISK_PASS" | "RISK_REJECT" | "ORDER_FILLED" | "ORDER_CLOSED" | "INFO";
  symbol?: string;
  side?: string;
  price?: number;
  quantity?: number;
  message: string;
  details?: Record<string, any>;
}

export interface CandleItem {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeMarkerItem {
  id: number;
  time: number;
  side: "BUY" | "SELL";
  price: number;
  quantity: number;
  fees: number;
}

export interface SymbolCandlesResponse {
  symbol: string;
  quote: {
    symbol: string;
    ltp: number;
    change_pct: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    bid: number;
    ask: number;
  };
  count: number;
  candles: CandleItem[];
  trades: TradeMarkerItem[];
}

