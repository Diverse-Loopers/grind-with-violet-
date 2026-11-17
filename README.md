# Groww Trading Lab

A local-first algorithmic trading research and paper-trading platform for Indian equity markets, built for personal use with the Groww Trading API.

> **⚠️ IMPORTANT DISCLAIMERS**
> - This software does NOT guarantee profits. Algorithmic trading involves significant risk of financial loss.
> - This is a personal research tool, not investment advice or a public trading service.
> - Live order execution is **disabled by default** and requires manual configuration and regulatory compliance.
> - Always verify compliance with SEBI regulations before enabling any automated trading.

## Features

- **Market Scanner** — Real-time monitoring of Indian equities with bid-ask spreads, volatility, and gap detection
- **Price Gap Detection** — Three independent strategies: spread scanning, intraday gap detection, and statistical pairs research
- **Paper Trading** — Full simulated execution with realistic costs, slippage, and position tracking
- **Risk Engine** — Independent validation of every trade with configurable limits and emergency kill switch
- **Backtesting** — Historical strategy evaluation with out-of-sample validation and CSV export
- **24/7 Global Engine (XAU/USD & Forex)** — Round-the-clock trading execution for Gold (XAU/USD) with USD margin accounting, standard/mini/micro lots, and leverage
- **TradingView Webhook Integration** — Direct webhook receiver for TradingView alerts and Pine Script v5 automated execution
- **Max Profit Multi-Strategy Optimizer** — Dynamic confluence scoring across EMA trend momentum, London/NY session breakouts, and RSI mean reversion, auto-tuning for maximum net profit
- **Professional Dashboard** — Dark-themed trading terminal with charts, tables, and real-time updates
- **Demo Mode** — Works immediately with synthetic data, no API credentials required

## Operating Modes

| Mode | Data Source | Execution | Use Case |
|------|-----------|-----------|----------|
| **DEMO** | Synthetic prices | None | Explore the platform |
| **PAPER** | Live Groww data | Simulated fills | Test strategies safely |
| **LIVE** | Live Groww data | Real orders (disabled) | Future use only |

## Quick Start

### Prerequisites
- macOS (tested on Apple Silicon and Intel)
- Python 3.11+
- Node.js 18+
- npm 9+

### Setup & Run
```bash
# Clone or navigate to the project
cd /path/to/Groww

# One-command setup
./start.sh setup

# Start the application
./start.sh dev
```

Then open:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

### Alternative: Using Make
```bash
make setup    # Install everything
make dev      # Start both servers
make test     # Run tests
```

## Configuration

### Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

```env
# App mode: DEMO (default), PAPER, or LIVE
APP_MODE=DEMO

# Groww API (required for PAPER/LIVE mode)
GROWW_API_TOKEN=your_token_here
GROWW_API_BASE_URL=https://api.groww.in/v1

# Paper trading
PAPER_STARTING_BALANCE=1000000

# Database
DB_URL=sqlite:///./groww_trading.db
```

### Groww API Setup

1. Log into your Groww account
2. Navigate to Profile → Trading APIs
3. Generate an API token (note: tokens expire daily at ~6 AM IST)
4. Add the token to `backend/.env`
5. Set `APP_MODE=PAPER` to use live data with simulated execution

> **Never share your API token, commit it to Git, or store it in frontend code.**

## 24/7 Global Engine & TradingView Integration

In addition to the Indian equity engine, Groww Lab includes a dedicated **24/7 Global Engine** engineered for continuous markets:

### Supported Markets
- **XAU/USD (Gold Spot vs US Dollar)**: High-volatility commodity trading with pip/spread accounting.
- **BTC/USD & EUR/USD**: 24/7 continuous crypto and forex pairs.
- **Account Model**: Margin accounting in USD ($10,000 starting equity), configurable leverage (1:20 to 1:100), standard lot (100 oz), mini lot (10 oz), and micro lot (1 oz).

### TradingView Webhook Bridge
1. Set TradingView Alert Webhook URL to:
   ```
   http://localhost:8000/api/tradingview/webhook
   ```
2. Set Alert Message JSON payload:
   ```json
   {
     "ticker": "{{ticker}}",
     "action": "{{strategy.order.action}}",
     "price": {{close}},
     "quantity": 0.10,
     "strategy": "TradingView Pine Strategy",
     "passphrase": "groww_tradeview_key_2026"
   }
   ```
3. Use the built-in **Pine Script Generator** in the UI (`/tradingview`) to copy ready-to-use Pine Script v5 code into TradingView's Pine Editor.

### Max Profit Multi-Strategy System
- **Gold EMA Trend Momentum**: Rides directional runs using 9/21/50 EMAs with dynamic ATR trailing stops.
- **Asian Range Breakout**: Trades explosive London/NY session breakouts beyond the Asian consolidation band.
- **RSI & Bollinger Scalper**: Mean-reversion scalping at Bollinger Band extremes during range-bound hours.
- **Confluence Booster**: Scales trade size when multiple strategies agree for maximum risk-adjusted profit.
- **Auto-Optimizer**: Runs grid search across historical candles to determine the highest-profit configuration.

## Architecture

```
Groww/
├── backend/                 # FastAPI + Python
│   ├── app/
│   │   ├── adapters/       # Broker integrations (Groww, Demo)
│   │   ├── api/            # REST & WebSocket routes
│   │   ├── engine/         # Decision, risk, cost, paper broker
│   │   ├── models/         # Database & validation models
│   │   ├── scanner/        # Market scanner & watchlist
│   │   ├── strategies/     # Gap, spread, pairs strategies
│   │   ├── backtest/       # Historical backtesting
│   │   └── utils/          # Logging, time utilities
│   └── tests/
├── frontend/                # Next.js + React + TypeScript
│   └── src/
│       ├── app/            # Pages (dashboard, scanner, portfolio, risk, backtest)
│       ├── components/     # Reusable UI components
│       ├── hooks/          # Data fetching hooks
│       └── lib/            # Utilities, types, API client
├── start.sh                # Startup script
├── Makefile                # Build targets
└── .gitignore
```

## Indian Equity Transaction Costs

The cost calculator accounts for all standard charges:

| Fee | Rate |
|-----|------|
| Brokerage | ₹20 flat or 0.03% (configurable) |
| STT (Delivery) | 0.1% buy + sell |
| STT (Intraday) | 0.025% sell side |
| Exchange charges | 0.00345% (NSE) |
| GST | 18% on brokerage + exchange |
| SEBI turnover fee | 0.0001% |
| Stamp duty | 0.015% buy side |

## Risk Limits (Defaults)

| Limit | Default | Description |
|-------|---------|-------------|
| Max position % | 10% | Max capital in one position |
| Max daily loss | ₹50,000 | Auto-halt on breach |
| Max open positions | 10 | Concentration limit |
| Max single order | ₹1,00,000 | Per-order cap |
| Max quote age | 30s | Reject stale quotes |
| Min net edge | 0.1% | Reject low-quality signals |

## Testing

```bash
# Run all tests
make test

# Run specific test file
cd backend && ./venv/bin/python -m pytest tests/test_cost_calculator.py -v
```

## Security

- All secrets in `.env` (git-ignored)
- Backend binds to `127.0.0.1` only — not exposed to network
- Tokens never logged or sent to frontend
- All API responses validated
- Rate limits respected with configurable backoff
- Orders require explicit risk engine approval

## Regulatory Notes

Before enabling live trading:
1. Verify SEBI algorithmic trading requirements for retail investors
2. Confirm Groww API terms of service permit your intended use
3. Check exchange requirements (NSE/BSE) for API-based order submission
4. Review static IP, registration, and tagging requirements if applicable
5. Test extensively in PAPER mode first

Live execution remains **disabled** until these checks are completed.

## License

For personal use only. Not for redistribution or commercial use.
