#!/usr/bin/env python3
"""Resumable metals.dev history fetcher.

Run this on YOUR machine (the key must never be committed):

    export METALS_DEV_API_KEY=...            # never put the key in the repo
    python scripts/fetch_metals.py probe     # 1 call: saves a raw sample to inspect
    python scripts/fetch_metals.py fetch --start 2021-10-18 --end 2026-10-16 \
        --chunk-days 30 --max-calls 60 --currencies INR,USD,EUR,GBP,AED

ASSUMPTIONS (UNVERIFIED - confirm with `probe` and the metals.dev docs):
  * endpoint  GET {BASE}/timeseries?api_key=..&start_date=..&end_date=..
  * response  {"rates": {"YYYY-MM-DD": {"metals": {"gold": usd_toz, ...},
                                         "currencies": {"INR": usd_per_unit, ...}}}}
  * the maximum date range per call is unknown; --chunk-days sets it.
If the shape differs, edit `parse_chunk()` only; everything else is generic.

Call budget: the Free plan allows 100 calls a month. Every call is counted in
data/fetch_state.json and the script stops at --max-calls. Re-running resumes
from the chunks already saved in data/raw/.

Licence note: data is for in-app display only. Do not publish data/ or keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotwise.validate import validate_series  # noqa: E402

BASE = os.environ.get("METALS_DEV_BASE", "https://api.metals.dev/v1")
DATA = Path(__file__).resolve().parents[1] / "data"
RAW = DATA / "raw"
STATE = DATA / "fetch_state.json"
METALS = ("gold", "silver", "platinum")


def state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"calls": 0}


def save_state(s: dict) -> None:
    DATA.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s))


def api_key() -> str:
    key = os.environ.get("METALS_DEV_API_KEY")
    if not key:
        sys.exit("Set METALS_DEV_API_KEY in your environment (never commit it).")
    return key


def call(start: date, end: date, max_calls: int) -> dict:
    s = state()
    if s["calls"] >= max_calls:
        sys.exit(f"Call limit reached ({s['calls']}/{max_calls}). Stopping.")
    params = {"api_key": api_key(), "start_date": start.isoformat(), "end_date": end.isoformat()}
    r = httpx.get(f"{BASE}/timeseries", params=params, timeout=60)
    s["calls"] += 1  # count even on failure: the provider counts it
    save_state(s)
    r.raise_for_status()
    return r.json()


def parse_chunk(payload: dict, currencies: set[str]):
    """-> (metals{name:{date:price}}, fx{cur:{date:rate}}). Edit if the shape differs."""
    metals: dict[str, dict[str, float]] = {m: {} for m in METALS}
    fx: dict[str, dict[str, float]] = {c: {} for c in currencies}
    for day, row in payload.get("rates", {}).items():
        for m in METALS:
            v = (row.get("metals") or {}).get(m)
            if v:
                metals[m][day] = float(v)
        for c in currencies:
            v = (row.get("currencies") or {}).get(c)
            if v:
                fx[c][day] = float(v)
    return metals, fx


def probe(args) -> None:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days)
    payload = call(start, end, args.max_calls)
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / "probe.json"
    out.write_text(json.dumps(payload)[:200000])
    days = list(payload.get("rates", {}))
    print(f"saved {out}; top-level keys: {list(payload)}; days returned: {len(days)}")
    if days:
        row = payload["rates"][days[0]]
        print(f"first day {days[0]}: metals={list((row.get('metals') or {}))[:8]}")
        print(f"currencies in row: {len(row.get('currencies') or {})}")
    print(f"calls used so far: {state()['calls']}  (check the dashboard too)")


def fetch(args) -> None:
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    currencies = {c.strip().upper() for c in args.currencies.split(",") if c.strip()}
    RAW.mkdir(parents=True, exist_ok=True)
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=args.chunk_days - 1), end)
        f = RAW / f"{cur.isoformat()}_{chunk_end.isoformat()}.json"
        if not f.exists():
            print(f"fetching {cur} .. {chunk_end}")
            f.write_text(json.dumps(call(cur, chunk_end, args.max_calls)))
            time.sleep(1.0)
        cur = chunk_end + timedelta(days=1)
    merge(currencies)


def merge(currencies: set[str]) -> None:
    metals: dict[str, dict[str, float]] = {m: {} for m in METALS}
    fx: dict[str, dict[str, float]] = {c: {} for c in currencies}
    for f in sorted(RAW.glob("2*.json")):
        m, x = parse_chunk(json.loads(f.read_text()), currencies)
        for k in metals:
            metals[k].update(m[k])
        for k in fx:
            fx[k].update(x[k])
    metals = {k: v for k, v in metals.items() if v}
    fx = {k: v for k, v in fx.items() if v}
    problems = 0
    for kind, group in (("metal", metals), ("fx", fx)):
        for name, ser in group.items():
            rep = validate_series({date.fromisoformat(d): p for d, p in ser.items()}, kind)
            flag = "OK " if rep["ok"] else "BAD"
            print(f"[{flag}] {kind} {name}: {rep['count']} days, gaps={len(rep['gaps'])}, "
                  f"zero={len(rep['zero_or_negative'])}, big jumps={len(rep['jumps'])}")
            problems += 0 if rep["ok"] else 1
    out = DATA / "prices.json"
    out.write_text(json.dumps({"metals": metals, "fx": fx, "source": "metals.dev", "synthetic": False}))
    print(f"wrote {out}" + ("  (WITH PROBLEMS - review the BAD lines)" if problems else ""))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("probe")
    a.add_argument("--days", type=int, default=400, help="range to request in the probe call")
    a.add_argument("--max-calls", type=int, default=90)
    b = sub.add_parser("fetch")
    b.add_argument("--start", required=True)
    b.add_argument("--end", required=True)
    b.add_argument("--chunk-days", type=int, default=30)
    b.add_argument("--max-calls", type=int, default=60)
    b.add_argument("--currencies", default="INR,USD,EUR,GBP,AED")
    c = sub.add_parser("merge")
    c.add_argument("--currencies", default="INR,USD,EUR,GBP,AED")
    args = p.parse_args()
    {"probe": probe, "fetch": fetch}.get(args.cmd, lambda a: merge(
        {x.strip().upper() for x in a.currencies.split(",")}))(args)


if __name__ == "__main__":
    main()
