import { useEffect, useMemo, useState } from 'react'
import PriceChart from './PriceChart.jsx'
import { ask, getMeta, getPosition, getPrices } from './api.js'
import { buildMarkers, snapDate } from './markers.js'

const METAL_COLOR = { gold: '#c9a227', silver: '#8c98a6', platinum: '#5b86b3' }
const RANGES = [
  { key: '1M', days: 30 },
  { key: '6M', days: 182 },
  { key: '1Y', days: 365 },
  { key: '3Y', days: 365 * 3 },
  { key: '5Y', days: 365 * 5 },
  { key: 'All', days: null },
]
const EXAMPLES = [
  'Gold, 10000 a month for the last 5 years. Buy double 5% below average, sell 10% when 10% above.',
  'What if I had put 5000 a month into silver for 3 years?',
  'Platinum 8000 a month last 4 years, sell 20% when 15% above',
]

function useStored(key, initial) {
  const [v, setV] = useState(() => {
    try {
      const s = localStorage.getItem(key)
      return s ? JSON.parse(s) : initial
    } catch {
      return initial
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(v))
    } catch {}
  }, [key, v])
  return [v, setV]
}

const num = (x, d = 2) =>
  Number(x).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: 0 })

export default function App() {
  const [meta, setMeta] = useState(null)
  const [metaErr, setMetaErr] = useState(null)
  const [metal, setMetal] = useStored('sw.metal', 'gold')
  const [currency, setCurrency] = useStored('sw.currency', 'INR')
  const [purity, setPurity] = useStored('sw.purity', '24k')
  const [taxOn, setTaxOn] = useStored('sw.taxOn', false)
  const [taxRules, setTaxRules] = useStored('sw.taxRules', [
    { effective_from: '2000-01-01', duty_pct: 6, premium_per_gram: 0, gst_pct: 3 },
  ])
  const [trades, setTrades] = useStored('sw.trades', [])
  const [range, setRange] = useState(null)
  const [data, setData] = useState({ status: 'loading', points: [] })
  const [position, setPosition] = useState(null)
  const [backtest, setBacktest] = useState(null)
  const [showMonthly, setShowMonthly] = useState(false)

  useEffect(() => {
    getMeta().then(setMeta).catch((e) => setMetaErr(e.message))
  }, [])

  const cleanRules = useMemo(
    () => taxRules.filter((r) => r.effective_from).sort((a, b) => (a.effective_from < b.effective_from ? -1 : 1)),
    [taxRules],
  )

  const [reload, setReload] = useState(0)
  useEffect(() => {
    if (!meta) return
    let live = true
    setData((d) => ({ ...d, status: 'loading' }))
    getPrices({ metal, currency, purity, taxRules: taxOn ? cleanRules : null })
      .then((r) => live && setData({ status: r.points.length ? 'ok' : 'empty', points: r.points, unit: r.unit }))
      .catch((e) => live && setData({ status: 'error', points: [], error: e.message }))
    return () => {
      live = false
    }
  }, [meta, metal, currency, purity, taxOn, cleanRules, reload])

  const mine = useMemo(
    () => trades.filter((t) => t.metal === metal && t.currency === currency && (metal !== 'gold' || t.purity === purity)),
    [trades, metal, currency, purity],
  )
  const hidden = trades.length - mine.length

  useEffect(() => {
    if (!mine.length) return setPosition(null)
    getPosition({
      metal, currency, purity,
      trades: mine.map(({ date, side, grams, price }) => ({ date, side, grams, price })),
    })
      .then(setPosition)
      .catch((e) => setPosition({ error: e.message }))
  }, [mine, metal, currency, purity])

  const times = useMemo(() => data.points.map((p) => p.time), [data.points])
  const markers = useMemo(
    () => buildMarkers({ times, ledger: mine, backtest, showMonthly }),
    [times, mine, backtest, showMonthly],
  )

  if (metaErr)
    return (
      <main className="shell">
        <h1>SpotWise</h1>
        <p className="err" role="alert">{metaErr}</p>
        <button onClick={() => location.reload()}>Retry</button>
      </main>
    )
  if (!meta) return <main className="shell"><h1>SpotWise</h1><p className="muted">Loading…</p></main>

  return (
    <main className="shell">
      <header className="top">
        <div>
          <h1>SpotWise</h1>
          <p className="muted">Research and paper-trade gold, silver and platinum on real price history.</p>
        </div>
        {meta.synthetic && (
          <p className="badge warn" role="status">Demo data is synthetic (not real prices)</p>
        )}
      </header>

      <section className="panel controls" aria-label="Chart controls">
        <Seg label="Metal" value={metal} options={meta.metals} onChange={setMetal} />
        <label>
          Currency
          <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {meta.currencies.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        {metal === 'gold' && <Seg label="Purity" value={purity} options={meta.purities} onChange={setPurity} />}
        <label className="check">
          <input type="checkbox" checked={taxOn} onChange={(e) => setTaxOn(e.target.checked)} />
          Include duty &amp; tax
        </label>
      </section>

      <section className="panel" aria-label="Price chart">
        <div className="range">
          {RANGES.map((r) => (
            <button key={r.key} onClick={() => setRange({ ...r, n: Math.random() })}>{r.key}</button>
          ))}
          <span className="unit">{currency}/g · {metal}{metal === 'gold' ? ` ${purity}` : ''}{taxOn ? ' · with duty & tax' : ' · spot'}</span>
        </div>
        <div className="chart-area">
          <PriceChart
            points={data.points}
            color={METAL_COLOR[metal]}
            unit={`${currency}/g`}
            markers={markers}
            range={range}
          />
          {data.status === 'loading' && <div className="overlay">Loading prices…</div>}
          {data.status === 'empty' && <div className="overlay">No price history for this selection.</div>}
          {data.status === 'error' && (
            <div className="overlay err" role="alert">
              {data.error} <button onClick={() => setReload((n) => n + 1)}>Retry</button>
            </div>
          )}
        </div>
        <Legend backtest={backtest} />
      </section>

      <div className="cols">
        <AskPanel
          metal={metal}
          currency={currency}
          modelConfigured={meta.model_configured}
          backtest={backtest}
          onResult={(r) => { setBacktest(r); if (r) setRange({ key: 'All', days: null, n: Math.random() }) }}
          showMonthly={showMonthly}
          setShowMonthly={setShowMonthly}
          setMetal={setMetal}
          setCurrency={setCurrency}
        />
        <Ledger
          {...{ metal, currency, purity, mine, hidden, position, trades, setTrades, data, times }}
        />
      </div>

      {taxOn && <TaxEditor rules={taxRules} setRules={setTaxRules} currency={currency} />}
      {!taxOn && (
        <button className="link" onClick={() => setTaxOn(true)}>Set up duty &amp; tax profiles…</button>
      )}

      <footer className="muted">
        {meta.attribution}. Display only; data may not be copied or resold. Educational tool, not financial advice.
        Backtests use spot prices and past results do not predict future returns.
      </footer>
    </main>
  )
}

function Seg({ label, value, options, onChange }) {
  return (
    <fieldset className="seg">
      <legend>{label}</legend>
      {options.map((o) => (
        <button key={o} className={o === value ? 'on' : ''} aria-pressed={o === value} onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </fieldset>
  )
}

function Legend({ backtest }) {
  return (
    <p className="legend muted">
      <span className="dot" style={{ background: '#1a9e6b' }} /> Your buy
      <span className="dot" style={{ background: '#d6453d' }} /> Your sell
      {backtest && (
        <>
          <span className="dot" style={{ background: '#2f6fed' }} /> AI backtest trades
        </>
      )}
    </p>
  )
}

function AskPanel({ metal, currency, modelConfigured, backtest, onResult, showMonthly, setShowMonthly, setMetal, setCurrency }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)

  const run = async (q) => {
    const question = (q ?? text).trim()
    if (!question) return
    setBusy(true)
    setErr(null)
    try {
      const r = await ask({ text: question, metal, currency })
      setRes(r)
      onResult(r.result)
      // follow the question: show the metal/currency it was about
      setMetal(r.params.metal)
      setCurrency(r.params.currency)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const clear = () => {
    setRes(null)
    onResult(null)
  }
  const s = res?.result

  return (
    <section className="panel" aria-label="Ask">
      <h2>Ask SpotWise</h2>
      <p className="muted small">
        Describe a plan in plain words. Code runs the numbers; the AI only reads your request and explains the result.
        {!modelConfigured && ' (No model connected: using the built-in parser and template explanation.)'}
      </p>
      <textarea
        rows={3}
        value={text}
        placeholder="e.g. gold, 10000 a month for the last 5 years, buy double 5% below average"
        onChange={(e) => setText(e.target.value)}
      />
      <div className="row">
        <button className="primary" disabled={busy || !text.trim()} onClick={() => run()}>
          {busy ? 'Running…' : 'Run backtest'}
        </button>
        {backtest && <button onClick={clear}>Clear from chart</button>}
      </div>
      <div className="chips">
        {EXAMPLES.map((e) => (
          <button key={e} className="chip" onClick={() => { setText(e); run(e) }}>{e}</button>
        ))}
      </div>
      {err && <p className="err" role="alert">{err}</p>}
      {res && (
        <div className="answer">
          <p>{res.answer}</p>
          <table>
            <thead>
              <tr><th></th><th>Monthly buying</th><th>Dip strategy</th></tr>
            </thead>
            <tbody>
              <Row l="Invested" a={s.monthly.summary.total_bought} b={s.dip.summary.total_bought} />
              <Row l="Grams held" a={s.monthly.summary.grams_held} b={s.dip.summary.grams_held} d={2} />
              <Row l="Sold for" a={s.monthly.summary.total_sold} b={s.dip.summary.total_sold} />
              <Row l="Value now" a={s.monthly.summary.value_now} b={s.dip.summary.value_now} />
              <Row l="Profit / loss" a={s.monthly.summary.profit_loss} b={s.dip.summary.profit_loss} />
              <Row l="Return %" a={s.monthly.summary.profit_loss_pct} b={s.dip.summary.profit_loss_pct} d={1} suffix="%" />
            </tbody>
          </table>
          <label className="check small">
            <input type="checkbox" checked={showMonthly} onChange={(e) => setShowMonthly(e.target.checked)} />
            Also show plain monthly buys on the chart
          </label>
          <p className="muted small">
            Parsed by {res.parsed_by}, explained by {res.explained_by}. {res.note}
          </p>
        </div>
      )}
    </section>
  )
}

const Row = ({ l, a, b, d = 0, suffix = '' }) => (
  <tr><th>{l}</th><td>{num(a, d)}{suffix}</td><td>{num(b, d)}{suffix}</td></tr>
)

function Ledger({ metal, currency, purity, mine, hidden, position, trades, setTrades, data, times }) {
  const lastDate = times[times.length - 1] || ''
  const [date, setDate] = useState('')
  const [side, setSide] = useState('buy')
  const [grams, setGrams] = useState('')
  const [price, setPrice] = useState('')
  const [err, setErr] = useState(null)
  const d = date || lastDate

  const priceAt = (day) => {
    const t = snapDate(day, times)
    const p = data.points.find((x) => x.time === t)
    return p ? p.value : null
  }
  const fill = () => {
    const p = priceAt(d)
    if (p != null) setPrice(String(Math.round(p * 100) / 100))
  }

  const add = () => {
    const g = parseFloat(grams)
    const p = parseFloat(price)
    if (!d || !(g > 0) || !(p > 0)) return setErr('Enter a date, grams and price above zero.')
    if (times.length && (d < times[0] || d > times[times.length - 1]))
      return setErr(`Date must be within ${times[0]} to ${times[times.length - 1]}.`)
    if (side === 'sell') {
      const held = mine.reduce((h, t) => h + (t.side === 'buy' ? t.grams : -t.grams), 0)
      if (g > held + 1e-9) return setErr(`You only hold ${num(held, 2)} g.`)
    }
    setErr(null)
    setTrades([...trades, { id: Date.now(), date: d, side, grams: g, price: p, metal, currency, purity }])
    setGrams('')
  }

  return (
    <section className="panel" aria-label="Your paper trades">
      <h2>Your paper trades</h2>
      <p className="muted small">Saved in this browser only. Showing {metal}{metal === 'gold' ? ` ${purity}` : ''} in {currency}.</p>
      <div className="form">
        <label>Date<input type="date" value={d} min={times[0]} max={lastDate} onChange={(e) => setDate(e.target.value)} /></label>
        <label>Side
          <select value={side} onChange={(e) => setSide(e.target.value)}>
            <option value="buy">Buy</option><option value="sell">Sell</option>
          </select>
        </label>
        <label>Grams<input inputMode="decimal" value={grams} onChange={(e) => setGrams(e.target.value)} /></label>
        <label>Price / g
          <span className="inline">
            <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
            <button type="button" title="Use the chart price on that date" onClick={fill}>Use chart</button>
          </span>
        </label>
        <button className="primary" onClick={add}>Add trade</button>
      </div>
      {err && <p className="err" role="alert">{err}</p>}
      {position && !position.error && (
        <dl className="stats">
          <div><dt>Held</dt><dd>{num(position.grams_held, 2)} g</dd></div>
          <div><dt>Avg cost</dt><dd>{num(position.avg_cost)}</dd></div>
          <div><dt>Value now</dt><dd>{num(position.value_now)}</dd></div>
          <div><dt>Unrealised</dt><dd className={position.unrealised >= 0 ? 'pos' : 'neg'}>{num(position.unrealised)}</dd></div>
          <div><dt>Realised</dt><dd className={position.realised >= 0 ? 'pos' : 'neg'}>{num(position.realised)}</dd></div>
          <div><dt>Total P&amp;L</dt><dd className={position.total_pnl >= 0 ? 'pos' : 'neg'}>{num(position.total_pnl)}</dd></div>
        </dl>
      )}
      {position?.error && <p className="err" role="alert">{position.error}</p>}
      {mine.length === 0 ? (
        <p className="muted">No trades yet for this selection. Add one above and it appears on the chart.</p>
      ) : (
        <ul className="trades">
          {[...mine].sort((a, b) => (a.date < b.date ? 1 : -1)).map((t) => (
            <li key={t.id}>
              <span className={t.side === 'buy' ? 'pos' : 'neg'}>{t.side}</span> {num(t.grams, 2)} g @ {num(t.price)} on {t.date}
              <button className="x" aria-label="Delete trade" onClick={() => setTrades(trades.filter((x) => x.id !== t.id))}>×</button>
            </li>
          ))}
        </ul>
      )}
      {hidden > 0 && <p className="muted small">{hidden} trade{hidden > 1 ? 's' : ''} in other metals or currencies hidden.</p>}
    </section>
  )
}

function TaxEditor({ rules, setRules, currency }) {
  const set = (i, k, v) => setRules(rules.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  const n = (v) => (v === '' ? '' : parseFloat(v))
  return (
    <section className="panel" aria-label="Duty and tax profile">
      <h2>Duty &amp; tax profile</h2>
      <p className="warn small">
        Placeholder rates (6% duty, 3% GST). They are not verified. Enter your own, with the date each takes effect.
        Price = (spot × (1 + duty%) + premium) × (1 + tax%).
      </p>
      <div className="taxrows">
        {rules.map((r, i) => (
          <div className="taxrow" key={i}>
            <label>Effective from<input type="date" value={r.effective_from} onChange={(e) => set(i, 'effective_from', e.target.value)} /></label>
            <label>Duty %<input inputMode="decimal" value={r.duty_pct} onChange={(e) => set(i, 'duty_pct', n(e.target.value))} /></label>
            <label>Premium ({currency}/g)<input inputMode="decimal" value={r.premium_per_gram} onChange={(e) => set(i, 'premium_per_gram', n(e.target.value))} /></label>
            <label>GST / VAT %<input inputMode="decimal" value={r.gst_pct} onChange={(e) => set(i, 'gst_pct', n(e.target.value))} /></label>
            {rules.length > 1 && <button className="x" aria-label="Remove rule" onClick={() => setRules(rules.filter((_, j) => j !== i))}>×</button>}
          </div>
        ))}
      </div>
      <button onClick={() => setRules([...rules, { effective_from: new Date().toISOString().slice(0, 10), duty_pct: 0, premium_per_gram: 0, gst_pct: 0 }])}>
        Add a rule
      </button>
    </section>
  )
}
