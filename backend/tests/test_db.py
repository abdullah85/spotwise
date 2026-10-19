from datetime import date

import pytest

from spotwise import db

RAW = {
    "metals": {"gold": {"2025-01-02": 2650.5, "2025-01-03": 2660.0}},
    "fx": {"INR": {"2025-01-02": 0.01167}},
    "source": "metals.dev",
    "synthetic": False,
}


def test_rows_round_trip():
    rows = db.to_rows(RAW)
    assert ("metal", "gold", date(2025, 1, 2), 2650.5) in rows and len(rows) == 3
    assert db.from_rows(rows, "metals.dev", False) == RAW


def test_rejects_non_positive_price():
    bad = {"metals": {"gold": {"2025-01-02": 0}}, "fx": {}}
    with pytest.raises(ValueError, match="must be positive"):
        db.to_rows(bad)


def test_no_url_means_file_mode(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db.database_url() is None
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db.connect()
