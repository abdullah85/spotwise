"""AI layer. The model only (1) turns text into a structured request and
(2) explains a result computed by code. It never does arithmetic, and every
number it writes must appear in the facts we supplied; otherwise we fall back
to template text. With no model configured, the app still works end to end.

Model server (optional): any OpenAI-compatible /v1/chat/completions endpoint
(llama.cpp server, vLLM, Ollama...). Configure with:
    SPOTWISE_LLM_URL=http://localhost:8080/v1   SPOTWISE_LLM_MODEL=<name>
    SPOTWISE_LLM_API_KEY=<key>   (optional; sent as a Bearer token for hosted servers)
Constrained JSON output is requested via `response_format` (json_schema).
Support varies by server and version - verify against yours.
Instructions go in the user message, not a system message: some models
(e.g. Gemma) have no system role and some hosts reject one for them.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta

import httpx

from .backtest import BacktestParams

LLM_URL = os.environ.get("SPOTWISE_LLM_URL", "").rstrip("/")
LLM_MODEL = os.environ.get("SPOTWISE_LLM_MODEL", "")
LLM_API_KEY = os.environ.get("SPOTWISE_LLM_API_KEY", "")

CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED", "AUD", "BRL", "CAD", "CHF", "CNY", "HKD", "JPY", "SGD"]


# ---------- model server helpers ----------

def auth_headers(api_key: str) -> dict:
    """Bearer header for hosted servers; none for a local server without a key."""
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def user_messages(instructions: str, content: str) -> list[dict]:
    """One user message carrying the instructions, so models without a system role work."""
    return [{"role": "user", "content": f"{instructions}\n\n{content}"}]


# ---------- 1. text -> structured request ----------

def rule_parse(text: str, last_date: date) -> BacktestParams:
    """Deterministic fallback parser for simple phrasing. Never raises on odd text."""
    t = text.lower()
    f: dict = {}
    for m in ("gold", "silver", "platinum"):
        if m in t:
            f["metal"] = m
            break
    for c in CURRENCIES:
        if re.search(rf"\b{c.lower()}\b", t) or c in text:
            f["currency"] = c
            break
    if "22k" in t or "916" in t:
        f["purity"] = "22k"
    amt = re.search(r"(?:₹|rs\.?|inr|\$|usd|eur|€|£)?\s*(\d[\d,]*)\s*(k|lakh)?\s*(?:/|per|a|each)?\s*month", t)
    if amt:
        v = float(amt.group(1).replace(",", ""))
        if amt.group(2) == "k":
            v *= 1000
        elif amt.group(2) == "lakh":
            v *= 100000
        f["monthly_amount"] = v
    yrs = re.search(r"(?:last|past)\s+(\d+)\s*(?:year|yr)", t)
    if yrs:
        f["start"] = last_date - timedelta(days=365 * int(yrs.group(1)))
        f["end"] = last_date
    dip = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:below|dip|drop|down)", t)
    if dip:
        f["dip_pct"] = float(dip.group(1))
    rise = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:above|rise|up|spike)", t)
    if rise:
        f["rise_pct"] = float(rise.group(1))
    sell = re.search(r"sell\s+(\d+(?:\.\d+)?)\s*%", t)
    if sell:
        f["sell_fraction"] = float(sell.group(1)) / 100
    return BacktestParams(**f)


def llm_parse(text: str, last_date: date) -> BacktestParams | None:
    """Ask the model for JSON matching the schema. None on any failure."""
    if not LLM_URL:
        return None
    schema = BacktestParams.model_json_schema()
    body = {
        "model": LLM_MODEL or "default",
        "temperature": 0,
        "messages": user_messages(
            "Convert the user's request into JSON for a gold/silver/platinum backtest. "
            f"Today's latest data date is {last_date.isoformat()}. "
            "Output only JSON. Omit fields the user did not mention. Do no arithmetic.",
            f"Request: {text}",
        ),
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "backtest_request", "schema": schema},
        },
    }
    try:
        r = httpx.post(
            f"{LLM_URL}/chat/completions", json=body, headers=auth_headers(LLM_API_KEY), timeout=60
        )
        r.raise_for_status()
        raw = json.loads(r.json()["choices"][0]["message"]["content"])
        return BacktestParams(**raw)  # pydantic enforces bounds: never trust the model
    except Exception:
        return None


def parse_request(text: str, last_date: date) -> tuple[BacktestParams, str]:
    p = llm_parse(text, last_date)
    if p is not None:
        return p, "model"
    return rule_parse(text, last_date), "rules"


# ---------- 2. result -> facts -> explanation ----------

def fmt(x: float, d: int = 0) -> str:
    return f"{x:,.{d}f}"


def build_facts(p: BacktestParams, res: dict) -> dict:
    m, s = res["monthly"]["summary"], res["dip"]["summary"]
    cmp_ = res["comparison"]
    return {
        "metal": p.metal,
        "currency": p.currency,
        "start": res["range"]["start"],
        "end": res["range"]["end"],
        "monthly_amount": fmt(p.monthly_amount),
        "monthly_buys": str(m["n_buys"]),
        "monthly_invested": fmt(m["total_bought"]),
        "monthly_value": fmt(m["value_now"]),
        "monthly_pnl_pct": fmt(m["profit_loss_pct"], 1),
        "dip_invested": fmt(s["total_bought"]),
        "dip_value": fmt(s["value_now"] + s["total_sold"]),
        "dip_pnl_pct": fmt(s["profit_loss_pct"], 1),
        "dip_sells": str(s["n_sells"]),
        "dip_pct": fmt(p.dip_pct, 1).rstrip("0").rstrip("."),
        "rise_pct": fmt(p.rise_pct, 1).rstrip("0").rstrip("."),
        "pnl_pct_gap": fmt(abs(cmp_["pnl_pct_diff"]), 1),
        "winner": cmp_["winner"],
    }


def template_text(f: dict) -> str:
    lead = (
        "buying more on dips (and trimming on spikes)"
        if f["winner"] == "dip"
        else "plain monthly buying"
    )
    return (
        f"Backtest of {f['metal']} in {f['currency']}, {f['start']} to {f['end']}, "
        f"with {f['monthly_amount']} {f['currency']} a month. "
        f"Plain monthly buying made {f['monthly_buys']} purchases totalling "
        f"{f['monthly_invested']} and is now worth {f['monthly_value']}, "
        f"a {f['monthly_pnl_pct']}% return. "
        f"The dip strategy (double up when {f['dip_pct']}% below the recent average, "
        f"sell a slice when {f['rise_pct']}% above) invested {f['dip_invested']}, "
        f"made {f['dip_sells']} sales, and ended at {f['dip_value']} including sale proceeds: "
        f"a {f['dip_pnl_pct']}% return. "
        f"Over this period {lead} came out ahead by {f['pnl_pct_gap']} percentage points. "
        "Past results on historical prices do not predict future returns."
    )


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def numbers_ok(text: str, facts: dict) -> bool:
    """True if every number in `text` appears in the supplied facts."""
    allowed = set()
    for v in facts.values():
        for n in _NUM.findall(str(v)):
            allowed.add(n.replace(",", ""))
    cleaned = _ISO.sub("", text)
    for n in _NUM.findall(cleaned):
        if n.replace(",", "").rstrip(".") not in allowed:
            return False
    return True


def llm_explain(facts: dict) -> str | None:
    if not LLM_URL:
        return None
    body = {
        "model": LLM_MODEL or "default",
        "temperature": 0.2,
        "messages": user_messages(
            "Explain this backtest result in 3-4 plain sentences to a long-term saver. "
            "Use ONLY the numbers in the facts, copied exactly. Do not calculate, "
            "round, or invent any figure. Do not give financial advice.",
            f"Facts: {json.dumps(facts)}",
        ),
    }
    try:
        r = httpx.post(
            f"{LLM_URL}/chat/completions", json=body, headers=auth_headers(LLM_API_KEY), timeout=60
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def explain(facts: dict) -> tuple[str, str]:
    """-> (text, source) where source is 'model' or 'template'."""
    text = llm_explain(facts)
    if text and numbers_ok(text, facts):
        return text, "model"
    return template_text(facts), "template"
