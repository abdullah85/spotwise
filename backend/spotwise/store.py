"""Load the local price history. Display in-app only: no raw-data export is
offered anywhere. Data files live in backend/data/ and are git-ignored.

Source: Postgres (Neon) when DATABASE_URL is set, otherwise the local files.

Normalised file format (prices.json):
  {"metals": {"gold": {"YYYY-MM-DD": usd_per_toz, ...}, ...},
   "fx":     {"INR":  {"YYYY-MM-DD": usd_per_unit, ...}, ...},
   "source": "...", "synthetic": bool}
"""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import db

DATA_DIR = Path(os.environ.get("SPOTWISE_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


def _parse(d: dict[str, float]) -> dict[date, float]:
    return {date.fromisoformat(k): float(v) for k, v in d.items()}


def _load_file() -> dict:
    path = DATA_DIR / "prices.json"
    if not path.exists():
        path = DATA_DIR / "sample_prices.json"
    if not path.exists():
        raise FileNotFoundError(
            "No price data found. Run scripts/fetch_metals.py or scripts/make_sample.py"
        )
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def load():
    """Load once per process. After uploading new data, restart the service."""
    raw = db.load_raw() if db.database_url() else _load_file()
    return {
        "metals": {m: _parse(v) for m, v in raw["metals"].items()},
        "fx": {c: _parse(v) for c, v in raw["fx"].items()},
        "source": raw.get("source", "unknown"),
        "synthetic": bool(raw.get("synthetic", False)),
    }


def reset_cache():
    load.cache_clear()
