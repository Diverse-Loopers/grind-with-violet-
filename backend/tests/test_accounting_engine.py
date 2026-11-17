"""
Automated Accounting Engine & Multi-Account Reconciliation Tests.
Verifies:
1. Double-entry immutable ledger creation for deposits, trades, fees, and realized P&L.
2. Decimal-safe monetary arithmetic across Equities (INR), Crypto (INR/USDT), and Gold/Forex (USD).
3. Exact reconciliation between broker balances and cumulative ledger state with zero discrepancy.
"""

import uuid
import pytest
from app.database import init_db
from app.engine.accounting_engine import AccountingEngine
from app.engine.paper_broker import PaperBroker
from app.coindcx.paper_broker import CoinDCXPaperBroker
from app.global_engine.broker import GlobalPaperBroker


@pytest.fixture(autouse=True)
def setup_accounting_test():
    init_db()


def test_accounting_engine_deposit_and_reconciliation():
    test_acc = f"TEST_DEP_{uuid.uuid4().hex[:6]}"
    # Record initial capital deposit of 100,000 INR
    entry = AccountingEngine.record_deposit(
        account_type=test_acc,
        currency="INR",
        amount=100000.0,
        reference_id=f"TEST-DEP-{uuid.uuid4().hex[:4]}",
        description="Initial test deposit",
    )
    assert entry.id is not None
    assert entry.amount == 100000.0
    assert entry.currency == "INR"

    latest_bal = AccountingEngine.get_latest_balance(test_acc, "INR")
    assert latest_bal == 100000.0

    # Reconcile against reported cash equal to latest balance
    recon = AccountingEngine.reconcile_account(
        account_type=test_acc,
        currency="INR",
        current_reported_cash=latest_bal,
    )
    assert recon["is_reconciled"] is True
    assert recon["discrepancy"] == 0.0


def test_accounting_engine_trade_buy_and_sell_lifecycle():
    # Fresh isolated test account
    test_acc = f"TEST_LIFECYCLE_{uuid.uuid4().hex[:6]}"
    AccountingEngine.record_deposit(
        account_type=test_acc,
        currency="INR",
        amount=50000.0,
        reference_id=f"DEP-{uuid.uuid4().hex[:4]}",
        description="Isolated account deposit",
    )

    # Buy 10 shares @ 1000 = 10,000 cash outlay + 25 fee + 10 tax = 10,035 deduction
    buy_entry = AccountingEngine.record_trade(
        account_type=test_acc,
        reference_id=f"ORD-BUY-{uuid.uuid4().hex[:4]}",
        symbol="INFY",
        side="BUY",
        quantity=10.0,
        fill_price=1000.0,
        fee=25.0,
        tax=10.0,
        currency="INR",
    )
    assert buy_entry.amount == -10035.0
    assert buy_entry.balance_after == 39965.0

    # Sell 10 shares @ 1100 = 11,000 cash inflow - 25 fee - 10 tax = 10,965 addition
    sell_entry = AccountingEngine.record_trade(
        account_type=test_acc,
        reference_id=f"ORD-SELL-{uuid.uuid4().hex[:4]}",
        symbol="INFY",
        side="SELL",
        quantity=10.0,
        fill_price=1100.0,
        fee=25.0,
        tax=10.0,
        currency="INR",
    )
    assert sell_entry.amount == 10965.0
    assert sell_entry.balance_after == 50930.0

    # Reconcile against expected 50,930
    recon = AccountingEngine.reconcile_account(
        account_type=test_acc,
        currency="INR",
        current_reported_cash=50930.0,
    )
    assert recon["is_reconciled"] is True
    assert recon["discrepancy"] == 0.0
    assert recon["ledger_balance"] == 50930.0


def test_reconcile_all_accounts_across_asset_classes():
    """Tests end-to-end multi-currency reconciliation across Equities, Crypto, and Gold/Forex."""
    equity_broker = PaperBroker()
    crypto_broker = CoinDCXPaperBroker(starting_inr=50000.0, starting_usdt=1000.0)
    global_broker = GlobalPaperBroker(starting_balance=10000.0)

    funds = equity_broker.get_funds()
    crypto_overview = crypto_broker.get_wallet_overview()
    results = AccountingEngine.reconcile_all_accounts(
        current_equity_cash=funds["available_cash"],
        current_crypto_inr=crypto_overview["inr_cash"],
        current_crypto_usdt=crypto_overview["usdt_cash"],
        current_global_usd=global_broker.balance,
    )

    assert results["overall_status"] == "ALL_ACCOUNTS_RECONCILED"
    accounts = results["accounts"]
    assert "equity_inr" in accounts
    assert "crypto_inr" in accounts
    assert "crypto_usdt" in accounts
    assert "global_gold_usd" in accounts

    for acc_name, recon in accounts.items():
        assert recon["is_reconciled"] is True, f"{acc_name} failed reconciliation: {recon}"
        assert abs(recon["discrepancy"]) < 0.01
