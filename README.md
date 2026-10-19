# SpotWise

Research and paper-trade gold, silver and platinum on real price history.
Built for the DEV Hacktoberfest Open-Source AI Challenge (Week 2, "Side Hustle").

SpotWise is for a long-term saver who buys gold monthly, buys more when prices are low and
sells a little when they are high, and is tired of ad-filled price sites and doing the sums by hand.

## What it does

- **Charts** for gold, silver and platinum in many currencies, with 1M/6M/1Y/3Y/5Y/All ranges,
  tooltips, and metal / currency / purity (24k, 22k) switching that keeps your zoom.
- **Price conversion** to per-gram prices in your currency, with optional duty, premium and GST/VAT
  using **effective-dated tax profiles** (rates change; history stays correct).
- **Paper trades** you add yourself, drawn on the chart as buy/sell markers, with position,
  average cost and realised / unrealised profit and loss. Stored in your browser only.
- **Ask SpotWise (AI)**: describe a plan in plain words ("gold, 10000 a month for 5 years, buy double
  when 5% below average"). The model turns text into a structured request, **plain code** runs the
  backtest against ordinary monthly buying, and the result is explained in words. The backtest's
  trades are drawn on the chart next to your own.

## Why the AI is built this way

The model never does arithmetic. It does two jobs only:

1. text -> JSON request (validated by Pydantic bounds; the model's output is never trusted)
2. result -> short explanation

Every number in an explanation must appear in the facts the code supplied; if not, SpotWise falls
back to template text. With no model configured, the app still works end to end (rule-based parser
plus templates). This is also what makes small, self-hosted open models practical.

## Why open

A site owner who embeds price research should control it: no per-query fees, swappable models, and
no lock-in to one vendor's API. Any OpenAI-compatible server works
(`SPOTWISE_LLM_URL`, `SPOTWISE_LLM_MODEL`, and `SPOTWISE_LLM_API_KEY` for hosted servers that need
one). Model licences are the operator's responsibility to check.

Instructions are sent in the user message rather than a system message, so models without a system
role, such as Gemma, work. For example, a local Gemma via Ollama:

```bash
ollama pull gemma3:4b
export SPOTWISE_LLM_URL=http://localhost:11434/v1 SPOTWISE_LLM_MODEL=gemma3:4b
```

On Render, set the same variables (plus `SPOTWISE_LLM_API_KEY`) in the dashboard, pointing at a
hosted OpenAI-compatible endpoint. `/api/health` reports `model_configured`.

## Run it

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/make_sample.py        # SYNTHETIC demo data (not real prices)
python -m pytest -q
uvicorn spotwise.main:app --port 8000

# frontend
cd ../frontend
npm install
npm run build                        # served by the backend at http://localhost:8000
# or: npm run dev                    # http://localhost:5173, proxies /api
```

### Real data (metals.dev)

```bash
export METALS_DEV_API_KEY=...        # never commit this
python scripts/fetch_metals.py probe # 1 call: shows what the API returns
python scripts/fetch_metals.py fetch --start 2021-10-18 --end 2026-10-16 --chunk-days 30 --max-calls 60
```

The fetcher is resumable, counts every call (Free plan: 100 a month), stops at `--max-calls`, and
validates the result (gaps, zero prices, large jumps). Its API-shape assumptions are marked in the
script and must be confirmed with `probe`.

### Deploy (Render + Neon)

Data is fetched on your machine, then uploaded to a private Neon Postgres database:

```bash
export DATABASE_URL='postgresql://...neon.tech/spotwise?sslmode=require'   # never commit this
python scripts/upload_neon.py            # upserts data/prices.json; refuses synthetic data
python scripts/upload_neon.py --replace  # wipe and reload
```

`render.yaml` defines the web service. In the Render dashboard set `DATABASE_URL` (and
`SPOTWISE_CORS_ORIGINS` if the frontend is hosted elsewhere). With `DATABASE_URL` set the app reads
from Postgres; without it, from `backend/data/`. The dataset is loaded once per process and cached,
so restart the service after an upload. Health check: `/api/health`.

## Data licence

Prices come from [metals.dev](https://metals.dev). Per the site owner, the Free plan may be used
commercially but data may not be resold or claimed as yours. So SpotWise displays data in-app only,
credits "Prices by metals.dev", offers no raw-data download, and the repository contains no dataset
and no API keys (`backend/data/` is git-ignored). Any proxy serves this app only.

## Conversion

```
per_gram = (usd_per_toz / 31.1034768) / usd_per_unit * purity      (24k = 1.0, 22k = 0.916)
price    = (per_gram * (1 + duty%) + premium_per_gram) * (1 + GST%)
```

Metals are USD per troy ounce; currencies are USD per 1 unit. Percent moves equal metal move x
currency move; duty, tax and purity cancel out. Tested against fixed vectors in
`backend/tests/test_convert.py`.

**The default 6% duty / 3% GST are unverified placeholders.** Set your own rates and dates.

## Not financial advice

Educational tool. Backtests use spot prices, ignore making charges, and past results do not predict
the future. Paper trading only; no real money moves.

## Credits

- Prices by metals.dev
- Charts: [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts)
  (Apache-2.0; its attribution logo is left on, see `NOTICE`)

## Challenge timeline

Repository created and built within the challenge window (12-18 Oct 2026; deadline 11:59 PM PDT
18 Oct = 12:29 PM IST 19 Oct).

Commits made after the deadline (19 Oct 2026, after the entry was submitted):

- Optional `SPOTWISE_LLM_API_KEY` for hosted model servers, and model instructions sent in the user
  message so Gemma works. The submitted entry ran without a model on the public demo.
- Log the reason (never the key) when a model call falls back to rules or the template.

## Licence

MIT. See `LICENSE`.
