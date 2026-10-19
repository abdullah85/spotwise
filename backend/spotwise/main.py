"""SpotWise API. Serves converted prices to this app only: there is deliberately
no endpoint that exports raw provider data (see README, data licence)."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, store
from .backtest import BacktestParams, ledger_position, run_backtest
from .convert import PURITY, TaxProfile, TaxRule, convert_series

app = FastAPI(title="SpotWise", docs_url="/api/docs", openapi_url="/api/openapi.json")
CORS_ORIGINS = os.environ.get("SPOTWISE_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

ATTRIBUTION = "Prices by metals.dev"


def _profile(tax_json: str | None) -> TaxProfile | None:
    if not tax_json:
        return None
    try:
        rules = [
            TaxRule(
                effective_from=date.fromisoformat(r["effective_from"]),
                duty_pct=float(r.get("duty_pct", 0)),
                premium_per_gram=float(r.get("premium_per_gram", 0)),
                gst_pct=float(r.get("gst_pct", 0)),
            )
            for r in json.loads(tax_json)
        ]
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, f"bad tax profile: {e}")
    return TaxProfile(rules=rules)


def _series(metal: str, currency: str, purity: str, profile: TaxProfile | None):
    data = store.load()
    if metal not in data["metals"]:
        raise HTTPException(404, f"no data for metal '{metal}'")
    if currency not in data["fx"]:
        raise HTTPException(404, f"no data for currency '{currency}'")
    if purity not in PURITY:
        raise HTTPException(400, "purity must be 24k or 22k")
    p = PURITY[purity] if metal == "gold" else 1.0
    metal_pts = sorted(data["metals"][metal].items())
    return convert_series(metal_pts, data["fx"][currency], p, profile)


@app.get("/api/health")
def health():
    """For Render's health check. Data is cached, so this rarely touches the database."""
    try:
        data = store.load()
    except Exception as e:  # report, don't crash: Render shows this in the deploy log
        raise HTTPException(503, f"price data unavailable: {e}")
    return {"ok": True, "source": data["source"], "synthetic": data["synthetic"]}


@app.get("/api/meta")
def meta():
    data = store.load()
    all_days = sorted({d for s in data["metals"].values() for d in s})
    return {
        "metals": sorted(data["metals"]),
        "currencies": sorted(data["fx"]),
        "purities": list(PURITY),
        "start": all_days[0].isoformat(),
        "end": all_days[-1].isoformat(),
        "synthetic": data["synthetic"],
        "attribution": ATTRIBUTION,
        "model_configured": bool(ai.LLM_URL),
    }


@app.get("/api/prices")
def prices(
    metal: str = "gold",
    currency: str = "INR",
    purity: str = "24k",
    tax: str | None = Query(None, description="JSON list of tax rules; omit for spot"),
):
    series = _series(metal, currency, purity, _profile(tax))
    return {
        "metal": metal,
        "currency": currency,
        "purity": purity if metal == "gold" else "n/a",
        "unit": f"{currency}/g",
        "taxed": bool(tax),
        "points": [{"time": d.isoformat(), "value": round(v, 4)} for d, v in series],
        "attribution": ATTRIBUTION,
    }


class Trade(BaseModel):
    date: date
    side: str
    grams: float
    price: float


class PositionReq(BaseModel):
    metal: str = "gold"
    currency: str = "INR"
    purity: str = "24k"
    trades: list[Trade]


@app.post("/api/position")
def position(req: PositionReq):
    series = _series(req.metal, req.currency, req.purity, None)
    if not series:
        raise HTTPException(404, "no price data")
    try:
        pos = ledger_position(
            [{**t.model_dump(mode="json")} for t in req.trades], last_price=series[-1][1]
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"as_of": series[-1][0].isoformat(), "last_price": series[-1][1], **pos}


@app.post("/api/backtest")
def backtest(p: BacktestParams):
    series = _series(p.metal, p.currency, p.purity, None)
    try:
        return run_backtest(series, p)
    except ValueError as e:
        raise HTTPException(400, str(e))


class AskReq(BaseModel):
    text: str
    metal: str | None = None
    currency: str | None = None


@app.post("/api/ask")
def ask(req: AskReq):
    data = store.load()
    last = max(d for s in data["metals"].values() for d in s)
    params, parsed_by = ai.parse_request(req.text[:500], last)
    # Chart context fills in anything the question left out.
    explicit = ai.rule_parse(req.text, last)
    if req.metal and explicit.metal == "gold" and "gold" not in req.text.lower():
        params.metal = req.metal
    if req.currency and not any(c in req.text.upper() for c in ai.CURRENCIES):
        params.currency = req.currency
    series = _series(params.metal, params.currency, params.purity, None)
    try:
        result = run_backtest(series, params)
    except ValueError as e:
        raise HTTPException(400, str(e))
    facts = ai.build_facts(params, result)
    text, explained_by = ai.explain(facts)
    return {
        "params": params.model_dump(mode="json"),
        "parsed_by": parsed_by,
        "explained_by": explained_by,
        "answer": text,
        "result": result,
        "note": "Backtests use spot prices (no duty or tax).",
    }


_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
