"""Postgres (Neon) storage for price history.

The app reads the whole dataset once per process (it is small) and keeps it in
memory, so there is no connection pool: one short connection per load. Data is
written only by scripts/upload_neon.py from a locally fetched prices.json.

Rows are (kind, symbol, day, value): kind is "metal" (USD per troy ounce) or
"fx" (USD per 1 unit of the currency). Display in-app only; never export.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_points (
    kind   text NOT NULL CHECK (kind IN ('metal', 'fx')),
    symbol text NOT NULL,
    day    date NOT NULL,
    value  double precision NOT NULL CHECK (value > 0),
    PRIMARY KEY (kind, symbol, day)
);
CREATE TABLE IF NOT EXISTS dataset_info (
    id          int PRIMARY KEY CHECK (id = 1),
    source      text NOT NULL,
    synthetic   boolean NOT NULL,
    uploaded_at timestamptz NOT NULL DEFAULT now()
);
"""

KINDS = {"metals": "metal", "fx": "fx"}

Row = tuple[str, str, date, float]


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or None


def to_rows(raw: dict) -> list[Row]:
    """prices.json dict -> rows. Rejects zero/negative prices with a plain message."""
    rows: list[Row] = []
    for group, kind in KINDS.items():
        for symbol, series in raw.get(group, {}).items():
            for day, value in series.items():
                v = float(value)
                if v <= 0:
                    raise ValueError(f"{kind} {symbol} on {day}: price must be positive, got {v}")
                rows.append((kind, symbol, date.fromisoformat(day), v))
    return rows


def from_rows(rows: Iterable[Row], source: str, synthetic: bool) -> dict:
    """Rows -> the same dict shape as prices.json."""
    raw: dict = {"metals": {}, "fx": {}, "source": source, "synthetic": synthetic}
    group = {kind: g for g, kind in KINDS.items()}
    for kind, symbol, day, value in rows:
        raw[group[kind]].setdefault(symbol, {})[day.isoformat()] = float(value)
    return raw


def connect(url: str | None = None):
    import psycopg  # imported lazily so file-only setups need no driver

    url = url or database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # prepare_threshold=None: safe behind Neon's pooled (PgBouncer) endpoint.
    return psycopg.connect(url, prepare_threshold=None, connect_timeout=15)


def load_raw(url: str | None = None) -> dict:
    with connect(url) as conn:
        info = conn.execute("SELECT source, synthetic FROM dataset_info WHERE id = 1").fetchone()
        if info is None:
            raise FileNotFoundError("Database has no price data. Run scripts/upload_neon.py")
        rows = conn.execute("SELECT kind, symbol, day, value FROM price_points").fetchall()
    return from_rows(rows, source=info[0], synthetic=info[1])


def upload(raw: dict, url: str | None = None, replace: bool = False) -> int:
    """Upsert every row in one transaction. replace=True first deletes all rows."""
    rows = to_rows(raw)
    if not rows:
        raise ValueError("nothing to upload: the file has no prices")
    with connect(url) as conn, conn.transaction():
        conn.execute(SCHEMA)
        if replace:
            conn.execute("DELETE FROM price_points")
        conn.execute(
            "CREATE TEMP TABLE incoming (LIKE price_points INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        with conn.cursor().copy("COPY incoming (kind, symbol, day, value) FROM STDIN") as cp:
            for row in rows:
                cp.write_row(row)
        conn.execute(
            "INSERT INTO price_points SELECT * FROM incoming "
            "ON CONFLICT (kind, symbol, day) DO UPDATE SET value = EXCLUDED.value"
        )
        conn.execute(
            "INSERT INTO dataset_info (id, source, synthetic) VALUES (1, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET source = EXCLUDED.source, "
            "synthetic = EXCLUDED.synthetic, uploaded_at = now()",
            (raw.get("source", "unknown"), bool(raw.get("synthetic", False))),
        )
    return len(rows)
