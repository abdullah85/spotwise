# AGENTS.md: guidance for AI coding agents working on SpotWise

## Layout
- `backend/spotwise/` FastAPI app. `convert.py` price conversion, `backtest.py` engines,
  `ai.py` parser/explainer, `validate.py` data checks, `store.py` data loading, `main.py` API.
- `backend/scripts/` `fetch_metals.py` (resumable, call-counting), `make_sample.py` (synthetic data).
- `frontend/src/` React + Lightweight Charts. `markers.js` snaps trade dates to trading days.

## Commands
- Backend tests: `cd backend && python -m pytest -q` (must stay green)
- Frontend build: `cd frontend && npm run build`

## Hard rules
1. **The model never does arithmetic.** Numbers come from code. Any model-written text must pass
   `numbers_ok()`; otherwise use the template. Never remove that check.
2. **Never commit data or keys.** No metals.dev dataset, no API key, no raw-data export endpoint.
   Data is displayed in-app only and credited "Prices by metals.dev".
3. **Conversion code is plain and tested.** Change `convert.py` only with a test; keep the two
   test vectors (gold/INR ~4854, gold/AED ~227.5).
4. **Tax profiles are effective-dated.** Don't hard-code rates. Defaults are unverified placeholders
   and must stay labelled as such.
5. **Validate model output** with Pydantic bounds; never trust it.
6. Keep the chart attribution logo and `NOTICE`.
7. No real-revenue claims; payments (if added) are test mode only.

## Style
Small pure functions, explicit errors with plain messages, empty/loading/error states in the UI.
