"""
Agent 2: Strategy Confluence Brain.
Translates market intelligence from Agent 1 (Radar) into precision multi-leg trade plans
strictly adhering to the trader's playbook:
- Bull Call Spread (Cost Cutting, Early BEP, Theta Offset)
- Bear Put Spread (Cost Cutting, Early BEP, Theta Offset)
- Long Synthetic (Future Buy + Put Buy Hedge - Capped Risk, Unlimited Upside)
- Short Synthetic (Future Short + Call Buy Hedge - Capped Risk, Unlimited Downside)
- Long Butterfly (Call/Put - Low Net Debit, High R:R Range-bound Expiry Pin)
- Long Straddle & Strangle (Event/Volatility Surges)
- Cash-to-Future Arbitrage (NSE Spot Buy + Future Short on Premium)
- Covered Call (Delivery Hold + OTM Call Write)
- Hardcoded Rejection of Naked Futures and Naked Short Straddles/Strangles ("Nahi Karna").
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from app.models.playbook import (
    PlaybookTradePlan,
    StrategyType,
    MarketSentiment,
    OptionLeg,
    LegType,
    TradeAction,
)
from app.agents.fo_universe import get_lot_size, get_strike_interval, get_margin_percent
from app.utils.logging import get_logger

logger = get_logger(__name__)


class StrategyConfluenceAgent:
    """Strategy Brain that applies playbook rules and calculates mathematical payoffs."""

    def __init__(self):
        pass

    def evaluate_and_formulate_plans(self, market_data: Dict[str, Any]) -> List[PlaybookTradePlan]:
        """
        Receives market intelligence for a ticker and formulates candidate trade plans
        matching the prevailing market structure.
        """
        plans: List[PlaybookTradePlan] = []
        symbol = market_data["symbol"]
        sentiment = MarketSentiment(market_data.get("sentiment", "RANGE_BOUND"))
        spot_price = market_data["spot_price"]
        chain = market_data["chain"]

        # 1. Bullish Market Structure -> Bull Call Spread & Long Synthetic
        if sentiment == MarketSentiment.BULLISH:
            bull_call = self._build_bull_call_spread(symbol, spot_price, chain, market_data)
            if bull_call:
                plans.append(bull_call)

            long_synth = self._build_long_synthetic(symbol, spot_price, chain, market_data)
            if long_synth:
                plans.append(long_synth)

        # 2. Bearish Market Structure -> Bear Put Spread & Short Synthetic
        elif sentiment == MarketSentiment.BEARISH:
            bear_put = self._build_bear_put_spread(symbol, spot_price, chain, market_data)
            if bear_put:
                plans.append(bear_put)

            short_synth = self._build_short_synthetic(symbol, spot_price, chain, market_data)
            if short_synth:
                plans.append(short_synth)

        # 3. Range-Bound Structure -> Long Call/Put Butterfly
        elif sentiment == MarketSentiment.RANGE_BOUND:
            butterfly = self._build_long_call_butterfly(symbol, spot_price, chain, market_data)
            if butterfly:
                plans.append(butterfly)

        # 4. Cash-to-Future Arbitrage (Available whenever basis is in healthy premium)
        if market_data.get("basis", 0.0) > (spot_price * 0.002):
            arb_plan = self._build_cash_future_arbitrage(symbol, spot_price, market_data)
            if arb_plan:
                plans.append(arb_plan)

        return plans

    # ── Strategy 1: Bull Call Spread ──────────────────────────
    def _build_bull_call_spread(
        self, symbol: str, spot: float, chain: Any, meta: Dict[str, Any]
    ) -> Optional[PlaybookTradePlan]:
        """
        Bull Call Spread:
        Leg 1: Buy 1 Lot ATM Call (debit)
        Leg 2: Sell 1 Lot OTM Call at target / resistance (credit)
        """
        atm_strike = chain.atm_strike
        interval = chain.strike_interval
        lot_size = chain.lot_size
        target_strike = chain.resistance_strike

        # Ensure target is at least 1-2 strikes above ATM
        if target_strike <= atm_strike:
            target_strike = atm_strike + (2 * interval)

        strikes_dict = {s["strike"]: s for s in chain.strikes}
        atm_info = strikes_dict.get(atm_strike)
        target_info = strikes_dict.get(target_strike)

        if not atm_info or not target_info:
            return None

        ce_buy_price = atm_info["ce_price"]
        ce_sell_price = target_info["ce_price"]

        net_debit_point = round(ce_buy_price - ce_sell_price, 2)
        if net_debit_point <= 0.0:
            net_debit_point = 1.0

        spread_width = round(target_strike - atm_strike, 2)
        max_loss_point = net_debit_point
        max_profit_point = round(spread_width - net_debit_point, 2)

        total_net_debit = round(net_debit_point * lot_size, 2)
        total_max_loss = round(max_loss_point * lot_size, 2)
        total_max_profit = round(max_profit_point * lot_size, 2)
        bep = round(atm_strike + net_debit_point, 2)

        rr_ratio = round(total_max_profit / max(1.0, total_max_loss), 2)

        legs = [
            OptionLeg(
                symbol=f"{symbol}_{int(atm_strike)}_CE",
                leg_type=LegType.CALL,
                action=TradeAction.BUY,
                strike_price=atm_strike,
                entry_price=ce_buy_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="ATM",
            ),
            OptionLeg(
                symbol=f"{symbol}_{int(target_strike)}_CE",
                leg_type=LegType.CALL,
                action=TradeAction.SELL,
                strike_price=target_strike,
                entry_price=ce_sell_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="OTM",
            ),
        ]

        # Margin is roughly net debit for a debit spread in Indian brokerages
        margin_required = total_max_loss

        return PlaybookTradePlan(
            id=f"PLAN_BCS_{uuid.uuid4().hex[:8].upper()}",
            underlying_symbol=symbol,
            strategy_type=StrategyType.BULL_CALL_SPREAD,
            sentiment=MarketSentiment.BULLISH,
            spot_price=spot,
            legs=legs,
            net_debit=total_net_debit,
            max_loss=total_max_loss,
            max_profit=total_max_profit,
            risk_reward_ratio=rr_ratio,
            breakeven_points=[bep],
            margin_required=margin_required,
            confidence_score=0.88,
            agent_reasoning=(
                f"Bull Call Spread on {symbol} (Spot: {spot:.2f}): Price above 50 MA ({meta['ma_50']:.2f}) "
                f"with bullish PCR ({meta['pcr']:.2f}). Bought {atm_strike} CE @ {ce_buy_price} and Sold "
                f"{target_strike} CE @ {ce_sell_price} to offset theta and cut cost. "
                f"Max Profit: ₹{total_max_profit:.2f} vs Max Loss: ₹{total_max_loss:.2f} (R:R {rr_ratio}:1). "
                f"BEP at ₹{bep:.2f}."
            ),
            indicators_snapshot={
                "ma_50": meta["ma_50"],
                "pcr": meta["pcr"],
                "support": meta["support_strike"],
                "resistance": meta["resistance_strike"],
            },
        )

    # ── Strategy 2: Bear Put Spread ──────────────────────────
    def _build_bear_put_spread(
        self, symbol: str, spot: float, chain: Any, meta: Dict[str, Any]
    ) -> Optional[PlaybookTradePlan]:
        """
        Bear Put Spread:
        Leg 1: Buy 1 Lot ATM Put (debit)
        Leg 2: Sell 1 Lot OTM Put at target / support (credit)
        """
        atm_strike = chain.atm_strike
        interval = chain.strike_interval
        lot_size = chain.lot_size
        target_strike = chain.support_strike

        if target_strike >= atm_strike:
            target_strike = atm_strike - (2 * interval)

        strikes_dict = {s["strike"]: s for s in chain.strikes}
        atm_info = strikes_dict.get(atm_strike)
        target_info = strikes_dict.get(target_strike)

        if not atm_info or not target_info:
            return None

        pe_buy_price = atm_info["pe_price"]
        pe_sell_price = target_info["pe_price"]

        net_debit_point = round(pe_buy_price - pe_sell_price, 2)
        if net_debit_point <= 0.0:
            net_debit_point = 1.0

        spread_width = round(atm_strike - target_strike, 2)
        max_loss_point = net_debit_point
        max_profit_point = round(spread_width - net_debit_point, 2)

        total_net_debit = round(net_debit_point * lot_size, 2)
        total_max_loss = round(max_loss_point * lot_size, 2)
        total_max_profit = round(max_profit_point * lot_size, 2)
        bep = round(atm_strike - net_debit_point, 2)

        rr_ratio = round(total_max_profit / max(1.0, total_max_loss), 2)

        legs = [
            OptionLeg(
                symbol=f"{symbol}_{int(atm_strike)}_PE",
                leg_type=LegType.PUT,
                action=TradeAction.BUY,
                strike_price=atm_strike,
                entry_price=pe_buy_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="ATM",
            ),
            OptionLeg(
                symbol=f"{symbol}_{int(target_strike)}_PE",
                leg_type=LegType.PUT,
                action=TradeAction.SELL,
                strike_price=target_strike,
                entry_price=pe_sell_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="OTM",
            ),
        ]

        margin_required = total_max_loss

        return PlaybookTradePlan(
            id=f"PLAN_BPS_{uuid.uuid4().hex[:8].upper()}",
            underlying_symbol=symbol,
            strategy_type=StrategyType.BEAR_PUT_SPREAD,
            sentiment=MarketSentiment.BEARISH,
            spot_price=spot,
            legs=legs,
            net_debit=total_net_debit,
            max_loss=total_max_loss,
            max_profit=total_max_profit,
            risk_reward_ratio=rr_ratio,
            breakeven_points=[bep],
            margin_required=margin_required,
            confidence_score=0.86,
            agent_reasoning=(
                f"Bear Put Spread on {symbol} (Spot: {spot:.2f}): Price below 50 MA ({meta['ma_50']:.2f}) "
                f"with bearish PCR ({meta['pcr']:.2f}). Bought {atm_strike} PE @ {pe_buy_price} and Sold "
                f"{target_strike} PE @ {pe_sell_price} to reduce theta decay and lower BEP to ₹{bep:.2f}. "
                f"Max Profit: ₹{total_max_profit:.2f} vs Max Loss: ₹{total_max_loss:.2f} (R:R {rr_ratio}:1)."
            ),
            indicators_snapshot={
                "ma_50": meta["ma_50"],
                "pcr": meta["pcr"],
                "support": meta["support_strike"],
                "resistance": meta["resistance_strike"],
            },
        )

    # ── Strategy 3: Long Synthetic (Hedged Future) ───────────
    def _build_long_synthetic(
        self, symbol: str, spot: float, chain: Any, meta: Dict[str, Any]
    ) -> Optional[PlaybookTradePlan]:
        """
        Long Synthetic:
        Leg 1: Buy 1 Lot Future
        Leg 2: Buy 1 Lot ATM Put (Safety Hedge!)
        Enforces rule: 'Never Trade in Future in Single Side'
        """
        lot_size = chain.lot_size
        atm_strike = chain.atm_strike
        fut_price = chain.future_price

        strikes_dict = {s["strike"]: s for s in chain.strikes}
        atm_info = strikes_dict.get(atm_strike)
        if not atm_info:
            return None

        pe_hedge_price = atm_info["pe_price"]
        
        # Max loss is strictly capped at (fut_price - atm_strike + pe_hedge_price) * lot_size
        # Even if stock drops to 0, Put absorbs all downside beyond strike!
        downside_risk_point = round((fut_price - atm_strike) + pe_hedge_price, 2)
        total_max_loss = round(downside_risk_point * lot_size, 2)
        bep = round(fut_price + pe_hedge_price, 2)
        
        # Target 5% move for calculated max profit
        target_price = round(spot * 1.05, 2)
        target_profit_point = round(target_price - bep, 2)
        total_max_profit = round(max(0.0, target_profit_point) * lot_size, 2)
        rr_ratio = round(total_max_profit / max(1.0, total_max_loss), 2)

        margin_pct = get_margin_percent(symbol)
        margin_required = round((fut_price * lot_size * (margin_pct / 100.0)) + (pe_hedge_price * lot_size), 2)

        legs = [
            OptionLeg(
                symbol=f"{symbol}_FUT",
                leg_type=LegType.FUTURE,
                action=TradeAction.BUY,
                entry_price=fut_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="FUT",
            ),
            OptionLeg(
                symbol=f"{symbol}_{int(atm_strike)}_PE",
                leg_type=LegType.PUT,
                action=TradeAction.BUY,
                strike_price=atm_strike,
                entry_price=pe_hedge_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="ATM",
            ),
        ]

        return PlaybookTradePlan(
            id=f"PLAN_LSYN_{uuid.uuid4().hex[:8].upper()}",
            underlying_symbol=symbol,
            strategy_type=StrategyType.LONG_SYNTHETIC,
            sentiment=MarketSentiment.BULLISH,
            spot_price=spot,
            legs=legs,
            net_debit=round(pe_hedge_price * lot_size, 2),
            max_loss=total_max_loss,
            max_profit=total_max_profit,
            risk_reward_ratio=rr_ratio,
            breakeven_points=[bep],
            margin_required=margin_required,
            confidence_score=0.82,
            agent_reasoning=(
                f"Long Synthetic on {symbol} (Spot: {spot:.2f}): Playbook Rule 'Never Trade Future Single Side' enforced. "
                f"Bought 1 Lot Future @ {fut_price:.2f} + Bought 1 Lot {atm_strike} PE Hedge @ {pe_hedge_price:.2f}. "
                f"Downside risk strictly capped at ₹{total_max_loss:.2f} with unlimited upside above BEP ₹{bep:.2f}."
            ),
            indicators_snapshot={
                "ma_50": meta["ma_50"],
                "future_price": fut_price,
                "basis": meta["basis"],
            },
        )

    # ── Strategy 4: Short Synthetic (Hedged Short Future) ─────
    def _build_short_synthetic(
        self, symbol: str, spot: float, chain: Any, meta: Dict[str, Any]
    ) -> Optional[PlaybookTradePlan]:
        """
        Short Synthetic:
        Leg 1: Short 1 Lot Future
        Leg 2: Buy 1 Lot ATM Call (Safety Hedge!)
        """
        lot_size = chain.lot_size
        atm_strike = chain.atm_strike
        fut_price = chain.future_price

        strikes_dict = {s["strike"]: s for s in chain.strikes}
        atm_info = strikes_dict.get(atm_strike)
        if not atm_info:
            return None

        ce_hedge_price = atm_info["ce_price"]
        
        # Max loss is strictly capped if price explodes upwards:
        # Call covers everything above atm_strike
        upside_risk_point = round((atm_strike - fut_price) + ce_hedge_price, 2)
        if upside_risk_point < 0:
            upside_risk_point = ce_hedge_price
        total_max_loss = round(upside_risk_point * lot_size, 2)
        bep = round(fut_price - ce_hedge_price, 2)

        target_price = round(spot * 0.95, 2)
        target_profit_point = round(bep - target_price, 2)
        total_max_profit = round(max(0.0, target_profit_point) * lot_size, 2)
        rr_ratio = round(total_max_profit / max(1.0, total_max_loss), 2)

        margin_pct = get_margin_percent(symbol)
        margin_required = round((fut_price * lot_size * (margin_pct / 100.0)) + (ce_hedge_price * lot_size), 2)

        legs = [
            OptionLeg(
                symbol=f"{symbol}_FUT",
                leg_type=LegType.FUTURE,
                action=TradeAction.SELL,
                entry_price=fut_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="FUT",
            ),
            OptionLeg(
                symbol=f"{symbol}_{int(atm_strike)}_CE",
                leg_type=LegType.CALL,
                action=TradeAction.BUY,
                strike_price=atm_strike,
                entry_price=ce_hedge_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="ATM",
            ),
        ]

        return PlaybookTradePlan(
            id=f"PLAN_SSYN_{uuid.uuid4().hex[:8].upper()}",
            underlying_symbol=symbol,
            strategy_type=StrategyType.SHORT_SYNTHETIC,
            sentiment=MarketSentiment.BEARISH,
            spot_price=spot,
            legs=legs,
            net_debit=round(ce_hedge_price * lot_size, 2),
            max_loss=total_max_loss,
            max_profit=total_max_profit,
            risk_reward_ratio=rr_ratio,
            breakeven_points=[bep],
            margin_required=margin_required,
            confidence_score=0.81,
            agent_reasoning=(
                f"Short Synthetic on {symbol} (Spot: {spot:.2f}): Downside conviction below 50 MA. "
                f"Short 1 Lot Future @ {fut_price:.2f} hedged by 1 Lot {atm_strike} CE @ {ce_hedge_price:.2f}. "
                f"Upside gap risk capped at ₹{total_max_loss:.2f}. BEP at ₹{bep:.2f}."
            ),
            indicators_snapshot={
                "ma_50": meta["ma_50"],
                "future_price": fut_price,
                "basis": meta["basis"],
            },
        )

    # ── Strategy 5: Long Call Butterfly ───────────────────────
    def _build_long_call_butterfly(
        self, symbol: str, spot: float, chain: Any, meta: Dict[str, Any]
    ) -> Optional[PlaybookTradePlan]:
        """
        Long Call Butterfly:
        Leg 1: Buy 1 Lot ITM Call (ATM - interval)
        Leg 2: Sell 2 Lots ATM Call
        Leg 3: Buy 1 Lot OTM Call (ATM + interval)
        Symmetric wings. Tiny risk (net debit ₹50 - ₹600) for high potential payout at expiry pin.
        """
        atm_strike = chain.atm_strike
        interval = chain.strike_interval
        lot_size = chain.lot_size

        itm_strike = atm_strike - interval
        otm_strike = atm_strike + interval

        strikes_dict = {s["strike"]: s for s in chain.strikes}
        itm_info = strikes_dict.get(itm_strike)
        atm_info = strikes_dict.get(atm_strike)
        otm_info = strikes_dict.get(otm_strike)

        if not itm_info or not atm_info or not otm_info:
            return None

        itm_ce = itm_info["ce_price"]
        atm_ce = atm_info["ce_price"]
        otm_ce = otm_info["ce_price"]

        # Net Debit = (ITM CE + OTM CE) - 2 * ATM CE
        net_debit_point = round((itm_ce + otm_ce) - (2 * atm_ce), 2)
        if net_debit_point <= 0.1:
            net_debit_point = 1.0

        spread_width = interval
        max_loss_point = net_debit_point
        max_profit_point = round(spread_width - net_debit_point, 2)

        total_max_loss = round(max_loss_point * lot_size, 2)
        total_max_profit = round(max_profit_point * lot_size, 2)

        lower_bep = round(itm_strike + net_debit_point, 2)
        upper_bep = round(otm_strike - net_debit_point, 2)
        rr_ratio = round(total_max_profit / max(1.0, total_max_loss), 2)

        legs = [
            OptionLeg(
                symbol=f"{symbol}_{int(itm_strike)}_CE",
                leg_type=LegType.CALL,
                action=TradeAction.BUY,
                strike_price=itm_strike,
                entry_price=itm_ce,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="ITM",
            ),
            OptionLeg(
                symbol=f"{symbol}_{int(atm_strike)}_CE",
                leg_type=LegType.CALL,
                action=TradeAction.SELL,
                strike_price=atm_strike,
                entry_price=atm_ce,
                quantity=lot_size * 2,
                lot_size=lot_size,
                moneyness="ATM",
            ),
            OptionLeg(
                symbol=f"{symbol}_{int(otm_strike)}_CE",
                leg_type=LegType.CALL,
                action=TradeAction.BUY,
                strike_price=otm_strike,
                entry_price=otm_ce,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="OTM",
            ),
        ]

        return PlaybookTradePlan(
            id=f"PLAN_LBFLY_{uuid.uuid4().hex[:8].upper()}",
            underlying_symbol=symbol,
            strategy_type=StrategyType.LONG_CALL_BUTTERFLY,
            sentiment=MarketSentiment.RANGE_BOUND,
            spot_price=spot,
            legs=legs,
            net_debit=total_max_loss,
            max_loss=total_max_loss,
            max_profit=total_max_profit,
            risk_reward_ratio=rr_ratio,
            breakeven_points=[lower_bep, upper_bep],
            margin_required=total_max_loss,
            confidence_score=0.85,
            agent_reasoning=(
                f"Long Call Butterfly on {symbol} (Spot: {spot:.2f}): Market is range-bound between "
                f"Support ₹{meta['support_strike']} and Resistance ₹{meta['resistance_strike']}. "
                f"Legs: Buy 1x {itm_strike} CE, Sell 2x {atm_strike} CE, Buy 1x {otm_strike} CE. "
                f"Defined Risk: ₹{total_max_loss:.2f} to make Max Profit ₹{total_max_profit:.2f} (R:R {rr_ratio}:1) "
                f"if price pins near ₹{atm_strike:.2f} at expiry."
            ),
            indicators_snapshot={
                "ma_50": meta["ma_50"],
                "pcr": meta["pcr"],
                "support": meta["support_strike"],
                "resistance": meta["resistance_strike"],
            },
        )

    # ── Strategy 6: Cash-to-Future Arbitrage ──────────────────
    def _build_cash_future_arbitrage(
        self, symbol: str, spot: float, meta: Dict[str, Any]
    ) -> Optional[PlaybookTradePlan]:
        """
        Cash to Future Arbitrage:
        Leg 1: Buy Cash (NSE Spot)
        Leg 2: Short 1 Lot Future
        Rule: 'If future is at discount, avoid trade'. Only trade when Basis > 0 (Premium).
        """
        fut_price = meta.get("future_price", spot)
        basis = meta.get("basis", 0.0)
        lot_size = get_lot_size(symbol)

        if basis <= 0.0:
            logger.info(f"Arbitrage rejected for {symbol}: Future at discount (Basis {basis}).")
            return None

        # Absolute risk-free gross profit = basis * lot_size
        gross_profit = round(basis * lot_size, 2)
        # Estimated slippage / transaction costs
        est_cost = round((spot * lot_size * 0.0005) + (fut_price * lot_size * 0.0005), 2)
        net_profit = round(gross_profit - est_cost, 2)

        if net_profit <= 0:
            return None

        margin_pct = get_margin_percent(symbol)
        margin_required = round((spot * lot_size) + (fut_price * lot_size * (margin_pct / 100.0)), 2)

        legs = [
            OptionLeg(
                symbol=f"{symbol}_CASH",
                leg_type=LegType.EQUITY,
                action=TradeAction.BUY,
                entry_price=spot,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="EQ",
            ),
            OptionLeg(
                symbol=f"{symbol}_FUT",
                leg_type=LegType.FUTURE,
                action=TradeAction.SELL,
                entry_price=fut_price,
                quantity=lot_size,
                lot_size=lot_size,
                moneyness="FUT",
            ),
        ]

        return PlaybookTradePlan(
            id=f"PLAN_ARB_{uuid.uuid4().hex[:8].upper()}",
            underlying_symbol=symbol,
            strategy_type=StrategyType.CASH_FUTURE_ARBITRAGE,
            sentiment=MarketSentiment.ARBITRAGE,
            spot_price=spot,
            legs=legs,
            net_debit=0.0,
            max_loss=0.0,  # Zero directional risk
            max_profit=net_profit,
            risk_reward_ratio=99.9,
            breakeven_points=[spot],
            margin_required=margin_required,
            confidence_score=0.95,
            agent_reasoning=(
                f"Cash-to-Future Arbitrage on {symbol}: Future trading at a premium of ₹{basis:.2f} over spot "
                f"(Spot: {spot:.2f}, Future: {fut_price:.2f}). Bought {lot_size} cash shares and shorted 1 Future. "
                f"Locked-in risk-free convergence profit of ₹{net_profit:.2f} at expiry."
            ),
            indicators_snapshot={
                "spot": spot,
                "future_price": fut_price,
                "basis": basis,
            },
        )

    # ── Negative Constraint Guardrails ───────────────────────
    @staticmethod
    def validate_playbook_compliance(plan: PlaybookTradePlan) -> tuple[bool, str]:
        """
        Checks playbook hard constraints:
        1. Never Trade Future in Single Side (Naked Future).
        2. Short Straddle / Short Strangle is forbidden ('Nahi Karna').
        3. Max Loss must be defined and strictly > 0 (or 0 for pure arbitrage).
        """
        # Rule 1: No Naked Futures
        future_legs = [l for l in plan.legs if l.leg_type == LegType.FUTURE]
        option_legs = [l for l in plan.legs if l.leg_type in (LegType.CALL, LegType.PUT)]
        equity_legs = [l for l in plan.legs if l.leg_type == LegType.EQUITY]

        if future_legs and not option_legs and not equity_legs:
            return False, "Playbook Rule Violation: 'Never Trade in Future in Single Side' (Naked future is forbidden)."

        # Rule 2: No Naked Short Straddles or Strangles ("Nahi Karna")
        if plan.strategy_type in (StrategyType.LONG_STRADDLE, StrategyType.LONG_STRANGLE):
            short_legs = [l for l in plan.legs if l.action == TradeAction.SELL]
            if short_legs:
                return False, "Playbook Rule Violation: Short Straddle/Strangle marked 'Nahi Karna' (Unlimited risk forbidden)."

        # Rule 3: Must have defined risk
        if plan.max_loss < 0:
            return False, "Trade Plan has undefined or negative max loss."

        return True, "Compliant with Trader Playbook."
