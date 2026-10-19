// Snap a date to the nearest trading day at or before it, so markers always
// land on a real data point (weekends, holidays and gaps have no bar).
export function snapDate(date, times) {
  if (!times.length) return null
  let lo = 0
  let hi = times.length - 1
  if (date < times[0]) return times[0]
  if (date >= times[hi]) return times[hi]
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (times[mid] <= date) lo = mid
    else hi = mid - 1
  }
  return times[lo]
}

const COLORS = { buy: '#1a9e6b', sell: '#d6453d', dip: '#2f6fed', monthly: '#8a8f98' }

// Build the combined, time-sorted marker list for the chart.
export function buildMarkers({ times, ledger, backtest, showMonthly }) {
  const out = []
  if (backtest) {
    const add = (trades, kind, small) =>
      trades.forEach((t) => {
        const time = snapDate(t.date, times)
        if (!time) return
        const buy = t.side === 'buy'
        out.push({
          time,
          position: buy ? 'belowBar' : 'aboveBar',
          color: COLORS[kind],
          shape: small ? 'circle' : buy ? 'arrowUp' : 'arrowDown',
          size: small ? 0.6 : 1,
          text: small ? '' : buy ? 'AI buy' : 'AI sell',
        })
      })
    add(backtest.dip.trades, 'dip', false)
    if (showMonthly) add(backtest.monthly.trades, 'monthly', true)
  }
  ledger.forEach((t) => {
    const time = snapDate(t.date, times)
    if (!time) return
    const buy = t.side === 'buy'
    out.push({
      time,
      position: buy ? 'belowBar' : 'aboveBar',
      color: COLORS[t.side],
      shape: buy ? 'arrowUp' : 'arrowDown',
      size: 1.3,
      text: buy ? 'Buy' : 'Sell',
    })
  })
  // lightweight-charts requires ascending time order
  return out.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
}
