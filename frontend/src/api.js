async function req(url, opts) {
  let res
  try {
    res = await fetch(url, opts)
  } catch {
    throw new Error('Cannot reach the SpotWise server. Is the backend running?')
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export const getMeta = () => req('/api/meta')

export const getPrices = ({ metal, currency, purity, taxRules }) => {
  const q = new URLSearchParams({ metal, currency, purity })
  if (taxRules) q.set('tax', JSON.stringify(taxRules))
  return req(`/api/prices?${q}`)
}

const post = (url, body) =>
  req(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const getPosition = (body) => post('/api/position', body)
export const ask = (body) => post('/api/ask', body)
