"""Price conversion: plain, deterministic code. No AI, no network.

Inputs follow the metals.dev conventions:
  - metals are quoted in USD per troy ounce
  - currencies are quoted as USD per 1 unit of the currency (INR ~ 0.012)

per_gram = (usd_per_toz / TROY_OZ_GRAMS) / usd_per_unit * purity
then x (1 + duty%), plus premium per gram, then x (1 + GST%).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

TROY_OZ_GRAMS = 31.1034768

# Purity multipliers. Only gold has the karat variants; silver/platinum use 1.0.
PURITY = {"24k": 1.0, "22k": 0.916}


@dataclass(frozen=True)
class TaxRule:
    """One tax setting, valid from `effective_from` until the next rule starts."""

    effective_from: date
    duty_pct: float = 0.0
    premium_per_gram: float = 0.0  # in the display currency
    gst_pct: float = 0.0  # GST / VAT / sales tax


@dataclass
class TaxProfile:
    """A set of tax rules over time. Tax rates change; history must stay correct."""

    name: str = "default"
    rules: list[TaxRule] = field(default_factory=list)

    def rule_for(self, on: date) -> TaxRule | None:
        applicable = [r for r in self.rules if r.effective_from <= on]
        if not applicable:
            return None
        return max(applicable, key=lambda r: r.effective_from)


def spot_per_gram(usd_per_toz: float, usd_per_unit: float, purity: float = 1.0) -> float:
    """Spot price per gram in the target currency, before any duty or tax."""
    if usd_per_toz <= 0:
        raise ValueError("metal price must be positive")
    if usd_per_unit <= 0:
        raise ValueError("currency rate must be positive")
    return (usd_per_toz / TROY_OZ_GRAMS) / usd_per_unit * purity


def apply_tax(spot: float, rule: TaxRule | None) -> float:
    """Spot -> landed price: x(1+duty), + premium, x(1+GST)."""
    if rule is None:
        return spot
    return ((spot * (1 + rule.duty_pct / 100)) + rule.premium_per_gram) * (1 + rule.gst_pct / 100)


def per_gram(
    usd_per_toz: float,
    usd_per_unit: float,
    purity: float = 1.0,
    on: date | None = None,
    profile: TaxProfile | None = None,
) -> float:
    """Convenience: spot per gram, taxed if a profile applies on that date."""
    spot = spot_per_gram(usd_per_toz, usd_per_unit, purity)
    if profile is None or on is None:
        return spot
    return apply_tax(spot, profile.rule_for(on))


def convert_series(
    metal_usd_toz: Iterable[tuple[date, float]],
    rates_usd_per_unit: dict[date, float],
    purity: float = 1.0,
    profile: TaxProfile | None = None,
) -> list[tuple[date, float]]:
    """Convert a dated metal series into per-gram prices in a currency.

    Days without a currency rate are skipped (the validator flags such gaps).
    """
    out: list[tuple[date, float]] = []
    for d, price in metal_usd_toz:
        rate = rates_usd_per_unit.get(d)
        if rate is None:
            continue
        out.append((d, per_gram(price, rate, purity, d, profile)))
    return out


def pct_move(old: float, new: float) -> float:
    """Percentage change from old to new."""
    return (new / old - 1.0) * 100.0
