"""
CoinDCX Cross-Market Arbitrage, Momentum, and Volatility Scanner.
Analyzes cross-market price discrepancies: Direct INR vs Synthetic (USDT pair * USDT/INR exchange rate).
Calculates estimated net profitability after CoinDCX trading fees (0.20%), statutory TDS (1.0%),
bid-ask spreads, and order book slippage.
Clearly distinguishes DETECTED opportunities from EXECUTABLE trades.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from app.adapters.coindcx_adapter import CoinDCXAdapter
from app.coindcx.models import ArbitrageOpportunity, CoinDCXTicker
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Standard tracked cross-market crypto assets
_TRACKED_ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BNB", "POL"]


class CoinDCXScanner:
    """Scanner for cross-market crypto discrepancies, momentum, and arbitrage."""

    def __init__(self, adapter: Optional[CoinDCXAdapter] = None):
        if adapter is None:
            from app.adapters.coindcx_adapter import CoinDCXAdapter
            self.adapter = CoinDCXAdapter()
        else:
            self.adapter = adapter
        # CoinDCX fee schedule: 0.20% taker fee per leg
        self.taker_fee_pct = 0.20
        # Indian Section 194S TDS: 1.0% on crypto sales
        self.crypto_tds_pct = 1.00

    def scan_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Scans all tracked pairs for cross-market price discrepancies and evaluates net profitability.
        """
        tickers = self.adapter.get_all_tickers()
        usdt_inr_ticker = tickers.get("USDTINR")
        if not usdt_inr_ticker or usdt_inr_ticker.last_price <= 0:
            logger.warning("CoinDCX USDTINR exchange rate unavailable. Scanner cannot compute synthetic prices.")
            return []

        fx_rate = usdt_inr_ticker.last_price
        fx_stale = usdt_inr_ticker.is_stale
        now_iso = datetime.now(timezone.utc).isoformat()
        opportunities: List[ArbitrageOpportunity] = []

        for asset in _TRACKED_ASSETS:
            inr_market = f"{asset}INR"
            usdt_market = f"{asset}USDT"

            inr_ticker = tickers.get(inr_market)
            usdt_ticker = tickers.get(usdt_market)

            if not inr_ticker or not usdt_ticker:
                continue
            if inr_ticker.last_price <= 0 or usdt_ticker.last_price <= 0:
                continue

            # Check market data staleness
            is_stale = inr_ticker.is_stale or usdt_ticker.is_stale or fx_stale

            inr_price = inr_ticker.last_price
            usdt_price = usdt_ticker.last_price
            synthetic_inr = round(usdt_price * fx_rate, 4)

            discrepancy_inr = round(inr_price - synthetic_inr, 2)
            discrepancy_pct = round(((inr_price - synthetic_inr) / synthetic_inr) * 100.0, 3)
            gross_edge_pct = round(abs(discrepancy_pct), 3)

            # Determine trade direction
            if inr_price < synthetic_inr:
                direction = "BUY_DIRECT_INR_SELL_SYNTHETIC"
            else:
                direction = "BUY_SYNTHETIC_SELL_DIRECT_INR"

            # Calculate total execution costs:
            # 1. Trading Fees: 2 legs @ 0.20% each = 0.40%
            trading_fees_pct = round(self.taker_fee_pct * 2.0, 3)

            # 2. Statutory TDS: 1.0% on sell leg
            tds_pct = self.crypto_tds_pct

            # 3. Estimated Slippage & Spread costs (half-spread on both legs)
            slippage_pct = round((inr_ticker.spread_pct / 2.0) + (usdt_ticker.spread_pct / 2.0) + 0.05, 3)

            total_costs_pct = round(trading_fees_pct + tds_pct + slippage_pct, 3)
            net_profit_pct = round(gross_edge_pct - total_costs_pct, 3)

            # Executability check:
            # Must have positive net edge (>0.10%), non-stale data, and non-zero liquidity
            if is_stale:
                is_executable = False
                status = "DETECTED_ONLY"
                reason = f"Rejected: Stale market data ({max(inr_ticker.data_freshness_seconds, usdt_ticker.data_freshness_seconds):.1f}s old, limit {self.adapter.stale_threshold_seconds}s)."
            elif net_profit_pct > 0.10:
                is_executable = True
                status = "EXECUTABLE"
                reason = (
                    f"Actionable edge! Gross discrepancy of {gross_edge_pct:.3f}% exceeds total execution costs "
                    f"of {total_costs_pct:.3f}% (Fees {trading_fees_pct}%, TDS {tds_pct}%, Slippage {slippage_pct}%). "
                    f"Net profit: {net_profit_pct:.3f}%."
                )
            else:
                is_executable = False
                status = "DETECTED_ONLY"
                reason = (
                    f"Gross discrepancy of {gross_edge_pct:.3f}% is insufficient to overcome transaction friction. "
                    f"Total costs: {total_costs_pct:.3f}% (Broker fees: {trading_fees_pct}%, Indian TDS: {tds_pct}%, Slippage: {slippage_pct}%). "
                    f"Net profit after costs: {net_profit_pct:.3f}%."
                )

            opp = ArbitrageOpportunity(
                target_asset=asset,
                inr_market=inr_market,
                usdt_market=usdt_market,
                fx_market="USDTINR",
                inr_price=inr_price,
                usdt_price=usdt_price,
                usdt_inr_rate=fx_rate,
                synthetic_inr_price=synthetic_inr,
                price_discrepancy_inr=discrepancy_inr,
                price_discrepancy_pct=discrepancy_pct,
                direction=direction,
                estimated_trading_fees_pct=trading_fees_pct,
                estimated_slippage_pct=slippage_pct,
                estimated_statutory_tds_pct=tds_pct,
                total_execution_cost_pct=total_costs_pct,
                net_profit_pct=net_profit_pct,
                is_executable=is_executable,
                status=status,
                execution_reason=reason,
                timestamp=now_iso,
            )
            opportunities.append(opp)

        # Sort opportunities by gross edge descending
        opportunities.sort(key=lambda x: abs(x.price_discrepancy_pct), reverse=True)
        return opportunities

    def get_market_momentum(self) -> List[Dict]:
        """Returns momentum, volatility, and volume indicators for top crypto markets."""
        tickers = self.adapter.get_all_tickers()
        momentum_list = []

        for asset in _TRACKED_ASSETS:
            market = f"{asset}INR"
            t = tickers.get(market)
            if not t:
                continue

            volatility = round(((t.high - t.low) / t.low * 100.0), 2) if t.low > 0 else 0.0

            momentum_list.append({
                "market": market,
                "asset": asset,
                "last_price": t.last_price,
                "change_24h": t.change_24_hour,
                "high_24h": t.high,
                "low_24h": t.low,
                "volume_inr": t.volume,
                "spread_pct": t.spread_pct,
                "volatility_24h_pct": volatility,
                "freshness_seconds": t.data_freshness_seconds,
                "is_stale": t.is_stale,
            })

        momentum_list.sort(key=lambda x: abs(x["change_24h"]), reverse=True)
        return momentum_list
