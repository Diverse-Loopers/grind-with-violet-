"""
Unit tests for Paper Broker fill modeling and portfolio accounting.
"""

from app.database import init_db, get_db_context
from app.models.portfolio import PortfolioSnapshot
from app.models.position import Position
from app.engine.paper_broker import PaperBroker
from app.adapters.base import Quote


def setup_module():
    init_db()
    with get_db_context() as db:
        initial_snap = PortfolioSnapshot(
            cash_balance=500_000.0,
            positions_value=0.0,
            total_equity=500_000.0,
            daily_pnl=0.0,
            cumulative_pnl=0.0,
            drawdown_pct=0.0,
            mode="PAPER",
        )
        db.add(initial_snap)
        db.commit()


def test_paper_broker_place_market_order():
    broker = PaperBroker(starting_cash=500_000.0, slippage_pct=0.05)
    initial_funds = broker.get_funds()
    assert initial_funds["available_cash"] > 0

    quote = Quote(
        trading_symbol="INFY",
        exchange="NSE",
        segment="CASH",
        ltp=1800.0,
        bid_price=1799.0,
        ask_price=1801.0,
        volume=100000,
        data_quality="DEMO",
    )

    # Place Buy order for 10 shares
    res = broker.place_paper_order(
        trading_symbol="INFY",
        transaction_type="BUY",
        quantity=10,
        order_type="MARKET",
        quote=quote,
    )

    assert res.success is True
    assert res.status == "FILLED"

    updated_funds = broker.get_funds()
    # Cash should decrease by (approx 10 * 1801) + fees
    assert updated_funds["available_cash"] < initial_funds["available_cash"]
    assert updated_funds["positions_value"] > 0
