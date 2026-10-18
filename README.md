# SpotWise

Research and paper-trade gold, silver and platinum on real price history, in your own
currency and tax terms. Chart your purchases and sales, test strategies on five years of
data, and ask an AI to run the research, backtests and what-if scenarios for you.

> Built for the [Hacktoberfest Open-Source AI Challenge: Week 2 (Side Hustle)](https://dev.to/challenges/hacktoberfest-week2-2026-10-12).
> Started 18 October 2026 as a new project.

## Features
- **Charts** for gold, silver and platinum, with zoom, pan and range buttons (1M to Max)
- **Five years or more** of daily history
- **Multiple currencies**, with prices converted per gram or per troy ounce
- **Tax details:** your own duty, premium and GST or VAT, with effective dates
- **Trade overlay:** buys and sells marked on the chart, with position and profit and loss
- **AI assistant:** research questions, backtests and what-if scenarios in plain language,
  with results drawn on the chart

All calculations are plain, tested code. The AI turns your request into a structured query,
code runs it, and the AI explains the result. It never does the arithmetic.

## Tech stack
- Frontend: React
- Backend: FastAPI
- AI: an open-weight model served by the backend, with template text as a fallback
- Prices: [metals.dev](https://metals.dev)

## Quick start
> These steps will be filled in as the code lands.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your own metals.dev API key
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Data
Prices by [metals.dev](https://metals.dev). The price data is not part of this repository and
is not covered by the MIT licence. You need your own API key. The data is displayed in the app
only; this project does not resell it or claim ownership of it.

API keys live in `.env`, which is git-ignored. Never commit keys.

## Important
SpotWise is a research and planning tool. It is **not financial advice**. Rates are derived
from spot prices and tax settings you enter, so they will differ from a jeweller's or dealer's quote.

## Open-source credits
- This repository is new and was started during the challenge window.
- List the libraries and models you use here, with their licences.

## Commits after the deadline
Commits made after the submission deadline (19 October 2026, 12:29 PM IST) will be listed here.

## Licence
Code is released under the [MIT Licence](LICENSE).
