"""Backtest engine: plain code, deterministic. The AI never does this arithmetic.

Compares two strategies on one per-gram price series:
  * "monthly": buy a fixed amount on the first trading day of each month
  * "dip":     same base purchase, but buy `buy_multiplier` x when the price is
               `dip_pct`% below its trailing average, and sell `sell_fraction`
               of grams held when it is `rise_pct`% above it.
Prices are whatever series is passed in (spot or tax-inclusive). Selling is
valued at the same series, so a tax-inclusive series overstates sell proceeds;
the app uses spot for backtests and says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from pydantic import BaseModel, Field, model_validator


class BacktestParams(BaseModel):
    metal: str = "gold"
    currency: str = "INR"
    purity: str = "24k"
    start: date | None = None
    end: date | None = None
    monthly_amount: float = Field(10000.0, gt=0, le=1e9)
    dip_pct: float = Field(5.0, gt=0, le=50)
    rise_pct: float = Field(10.0, gt=0, le=100)
    lookback_days: int = Field(90, ge=10, le=730)
    buy_multiplier: float = Field(2.0, ge=1, le=10)
    sell_fraction: float = Field(0.1, ge=0, le=1)

    @model_validator(mode="after")
    def _order(self):
        if self.start and self.end and self.start >= self.end:
            raise ValueError("start must be before end")
        return self


@dataclass
class Trade:
    date: date
    side: str  # "buy" | "sell"
    grams: float
    price: float
    amount: float


def _first_of_month_indices(days: Sequence[date]) -> set[int]:
    seen, idx = set(), set()
    for i, d in enumerate(days):
        key = (d.year, d.month)
        if key not in seen:
            seen.add(key)
            idx.add(i)
    return idx


def _summary(trades: list[Trade], last_price: float) -> dict:
    bought = sum(t.amount for t in trades if t.side == "buy")
    sold = sum(t.amount for t in trades if t.side == "sell")
    grams = sum(t.grams if t.side == "buy" else -t.grams for t in trades)
    value = grams * last_price
    invested_net = bought - sold
    pnl = value + sold - bought
    return {
        "total_bought": bought,
        "total_sold": sold,
        "grams_held": grams,
        "value_now": value,
        "profit_loss": pnl,
        "profit_loss_pct": (pnl / bought * 100) if bought else 0.0,
        "avg_buy_price": (bought / sum(t.grams for t in trades if t.side == "buy"))
        if any(t.side == "buy" for t in trades)
        else 0.0,
        "n_buys": sum(1 for t in trades if t.side == "buy"),
        "n_sells": sum(1 for t in trades if t.side == "sell"),
        "net_cash_in": invested_net,
    }


def run_backtest(series: list[tuple[date, float]], p: BacktestParams) -> dict:
    """series: ascending (date, per_gram_price)."""
    pts = [
        (d, v)
        for d, v in series
        if (p.start is None or d >= p.start) and (p.end is None or d <= p.end)
    ]
    if len(pts) < p.lookback_days + 30:
        raise ValueError("not enough price history for this range")
    days = [d for d, _ in pts]
    prices = [v for _, v in pts]
    firsts = _first_of_month_indices(days)

    monthly: list[Trade] = []
    dip: list[Trade] = []
    held = 0.0
    for i, (d, px) in enumerate(pts):
        if i not in firsts:
            continue
        # plain monthly buying
        monthly.append(Trade(d, "buy", p.monthly_amount / px, px, p.monthly_amount))
        # dip strategy: needs lookback history to compare against
        if i >= p.lookback_days:
            avg = sum(prices[i - p.lookback_days : i]) / p.lookback_days
            vs = (px / avg - 1) * 100
        else:
            vs = 0.0
        amount = p.monthly_amount * (p.buy_multiplier if vs <= -p.dip_pct else 1.0)
        g = amount / px
        dip.append(Trade(d, "buy", g, px, amount))
        held += g
        if vs >= p.rise_pct and held > 0 and p.sell_fraction > 0:
            sg = held * p.sell_fraction
            dip.append(Trade(d, "sell", sg, px, sg * px))
            held -= sg

    last = prices[-1]
    out = {
        "range": {"start": days[0].isoformat(), "end": days[-1].isoformat()},
        "last_price": last,
        "monthly": {"summary": _summary(monthly, last), "trades": [_t(t) for t in monthly]},
        "dip": {"summary": _summary(dip, last), "trades": [_t(t) for t in dip]},
    }
    m, s = out["monthly"]["summary"], out["dip"]["summary"]
    out["comparison"] = {
        "pnl_diff": s["profit_loss"] - m["profit_loss"],
        "pnl_pct_diff": s["profit_loss_pct"] - m["profit_loss_pct"],
        "winner": "dip" if s["profit_loss_pct"] > m["profit_loss_pct"] else "monthly",
    }
    return out


def _t(t: Trade) -> dict:
    return {
        "date": t.date.isoformat(),
        "side": t.side,
        "grams": t.grams,
        "price": t.price,
        "amount": t.amount,
    }


def ledger_position(trades: list[dict], last_price: float) -> dict:
    """Position and P&L for a user's own trades: [{date, side, grams, price}]."""
    held, cost, realised = 0.0, 0.0, 0.0
    for t in sorted(trades, key=lambda x: x["date"]):
        g, px = float(t["grams"]), float(t["price"])
        if t["side"] == "buy":
            held += g
            cost += g * px
        else:
            if g > held + 1e-9:
                raise ValueError("cannot sell more grams than held")
            avg = cost / held if held else 0.0
            realised += g * (px - avg)
            cost -= g * avg
            held -= g
    unrealised = held * last_price - cost
    return {
        "grams_held": held,
        "avg_cost": cost / held if held else 0.0,
        "cost_basis": cost,
        "value_now": held * last_price,
        "unrealised": unrealised,
        "realised": realised,
        "total_pnl": unrealised + realised,
    }
