#!/usr/bin/env python3
"""Generate SYNTHETIC price history for development and tests.

This is invented data (seeded random walk), clearly flagged `synthetic: true`.
It exists so the app can be built and demoed without redistributing any
provider data. Replace with real data via fetch_metals.py.
"""

import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "sample_prices.json"

START = date(2021, 10, 18)
END = date(2026, 10, 16)

METALS = {  # start USD/toz, annual drift, daily vol
    "gold": (1770.0, 0.14, 0.0085),
    "silver": (23.5, 0.10, 0.017),
    "platinum": (1030.0, -0.01, 0.014),
}
FX = {  # USD per unit start, annual drift, daily vol
    "INR": (0.01334, -0.03, 0.0021),
    "EUR": (1.16, 0.0, 0.004),
    "GBP": (1.37, 0.0, 0.0045),
    "AED": (0.27225, 0.0, 0.0002),
    "JPY": (0.0088, -0.05, 0.0055),
    "SGD": (0.74, 0.0, 0.003),
    "AUD": (0.74, -0.01, 0.005),
    "CAD": (0.80, 0.0, 0.0035),
    "CHF": (1.09, 0.01, 0.0035),
    "CNY": (0.155, -0.01, 0.002),
    "HKD": (0.1284, 0.0, 0.0003),
    "BRL": (0.18, -0.01, 0.0075),
    "USD": (1.0, 0.0, 0.0),
}


def walk(rng, start, drift, vol, days):
    out, p = [], start
    for _ in days:
        out.append(p)
        p *= math.exp((drift / 252) - 0.5 * vol * vol + vol * rng.gauss(0, 1))
    return out


def build() -> dict:
    rng = random.Random(2026)
    days = []
    d = START
    while d <= END:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    data = {"metals": {}, "fx": {}, "source": "synthetic (seeded random walk)", "synthetic": True}
    for name, (s, drift, vol) in METALS.items():
        data["metals"][name] = {
            day.isoformat(): round(v, 4) for day, v in zip(days, walk(rng, s, drift, vol, days))
        }
    for cur, (s, drift, vol) in FX.items():
        series = walk(rng, s, drift, vol, days) if vol else [s] * len(days)
        data["fx"][cur] = {day.isoformat(): round(v, 8) for day, v in zip(days, series)}
    return data


def main():
    data = build()
    OUT.write_text(json.dumps(data))
    print(f"wrote {OUT} ({len(data['metals']['gold'])} days, synthetic)", file=sys.stderr)


if __name__ == "__main__":
    main()
