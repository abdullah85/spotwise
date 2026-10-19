from datetime import date, timedelta

import pytest

from spotwise.backtest import BacktestParams, ledger_position, run_backtest


def make_series(n=400, start=date(2024, 1, 1), f=lambda i: 100.0):
    out, d, i = [], start, 0
    while len(out) < n:
        if d.weekday() < 5:
            out.append((d, f(i)))
            i += 1
        d += timedelta(days=1)
    return out


def test_flat_prices_give_zero_pnl():
    res = run_backtest(make_series(), BacktestParams(monthly_amount=1000))
    assert res["monthly"]["summary"]["profit_loss"] == pytest.approx(0, abs=1e-6)
    assert res["monthly"]["summary"]["n_buys"] >= 12


def test_rising_prices_make_money():
    res = run_backtest(make_series(f=lambda i: 100 + i * 0.2), BacktestParams(monthly_amount=1000))
    assert res["monthly"]["summary"]["profit_loss"] > 0


def test_dip_buys_more_after_a_drop():
    # 120 days flat at 100, then a sharp drop to 80 for the rest
    s = make_series(n=300, f=lambda i: 100 if i < 120 else 80)
    res = run_backtest(s, BacktestParams(monthly_amount=1000, dip_pct=5, buy_multiplier=2))
    amounts = [t["amount"] for t in res["dip"]["trades"] if t["side"] == "buy"]
    assert max(amounts) == 2000


def test_dip_sells_after_a_spike():
    s = make_series(n=300, f=lambda i: 100 if i < 120 else 130)
    res = run_backtest(s, BacktestParams(monthly_amount=1000, rise_pct=10, sell_fraction=0.2))
    assert res["dip"]["summary"]["n_sells"] >= 1


def test_too_little_history_raises():
    with pytest.raises(ValueError):
        run_backtest(make_series(n=50), BacktestParams())


def test_ledger_pnl():
    trades = [
        {"date": "2025-01-01", "side": "buy", "grams": 10, "price": 100},
        {"date": "2025-02-01", "side": "buy", "grams": 10, "price": 120},
        {"date": "2025-03-01", "side": "sell", "grams": 5, "price": 130},
    ]
    pos = ledger_position(trades, last_price=140)
    assert pos["grams_held"] == pytest.approx(15)
    assert pos["avg_cost"] == pytest.approx(110)
    assert pos["realised"] == pytest.approx(5 * (130 - 110))
    assert pos["unrealised"] == pytest.approx(15 * 140 - 15 * 110)


def test_ledger_rejects_overselling():
    with pytest.raises(ValueError):
        ledger_position(
            [{"date": "2025-01-01", "side": "sell", "grams": 1, "price": 100}], last_price=100
        )
