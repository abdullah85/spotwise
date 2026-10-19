"""Data validation for price history. Pure functions, easy to test."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Mapping

# Weekends are expected gaps in metal quotes; anything longer is flagged.
MAX_EXPECTED_GAP_DAYS = 4
# Daily moves beyond these are flagged for review (not rejected).
JUMP_PCT = {"metal": 12.0, "fx": 5.0}


def validate_series(
    series: Mapping[date, float],
    kind: str = "metal",
    max_gap_days: int = MAX_EXPECTED_GAP_DAYS,
) -> dict:
    """Return a report: gaps, zero/negative prices, large jumps."""
    report = {"count": len(series), "zero_or_negative": [], "gaps": [], "jumps": []}
    days = sorted(series)
    for d in days:
        if not series[d] or series[d] <= 0:
            report["zero_or_negative"].append(d.isoformat())
    prev = None
    for d in days:
        if prev is not None:
            gap = (d - prev).days
            if gap > max_gap_days:
                report["gaps"].append({"from": prev.isoformat(), "to": d.isoformat(), "days": gap})
            a, b = series[prev], series[d]
            if a and b and a > 0 and b > 0:
                move = (b / a - 1) * 100
                if abs(move) > JUMP_PCT.get(kind, 12.0):
                    report["jumps"].append(
                        {"date": d.isoformat(), "pct": round(move, 2)}
                    )
        prev = d
    report["ok"] = not (report["zero_or_negative"] or report["gaps"])
    return report


def coverage(series: Mapping[date, float], start: date, end: date) -> float:
    """Fraction of weekdays in [start, end] that have a price."""
    wanted, have = 0, 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            wanted += 1
            if d in series:
                have += 1
        d += timedelta(days=1)
    return have / wanted if wanted else 0.0
