import { useEffect, useRef } from 'react'
import { createChart, LineSeries, createSeriesMarkers, CrosshairMode } from 'lightweight-charts'

const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()

function themeOptions() {
  return {
    layout: { background: { color: cssVar('--panel') }, textColor: cssVar('--muted'), attributionLogo: true },
    grid: { vertLines: { color: cssVar('--grid') }, horzLines: { color: cssVar('--grid') } },
    rightPriceScale: { borderColor: cssVar('--line') },
    timeScale: { borderColor: cssVar('--line') },
  }
}

// range: { key, days } where days === null means "all"
export default function PriceChart({ points, color, unit, markers, range }) {
  const host = useRef(null)
  const tip = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const markersRef = useRef(null)
  const hadData = useRef(false)

  useEffect(() => {
    const chart = createChart(host.current, {
      autoSize: true,
      localization: { locale: 'en-US' },
      crosshair: { mode: CrosshairMode.Normal },
      ...themeOptions(),
    })
    const series = chart.addSeries(LineSeries, { lineWidth: 2, priceLineVisible: true })
    markersRef.current = createSeriesMarkers(series, [])
    chartRef.current = chart
    seriesRef.current = series

    chart.subscribeCrosshairMove((p) => {
      const el = tip.current
      if (!el) return
      const v = p.seriesData.get(series)
      if (!p.point || !v || p.point.x < 0 || p.point.y < 0) {
        el.style.display = 'none'
        return
      }
      el.style.display = 'block'
      el.innerHTML = `<b>${p.time}</b><br>${v.value.toLocaleString('en-US', { maximumFractionDigits: 2 })} ${el.dataset.unit}`
      const w = host.current.clientWidth
      el.style.left = `${Math.min(p.point.x + 14, w - 150)}px`
      el.style.top = `${Math.max(p.point.y - 50, 4)}px`
    })

    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onTheme = () => chart.applyOptions(themeOptions())
    mq.addEventListener('change', onTheme)
    return () => {
      mq.removeEventListener('change', onTheme)
      chart.remove()
    }
  }, [])

  // New data: keep the user's zoom range across currency/metal/tax switches.
  useEffect(() => {
    const chart = chartRef.current
    const series = seriesRef.current
    if (!chart || !series) return
    const prev = hadData.current ? chart.timeScale().getVisibleRange() : null
    series.applyOptions({ color })
    series.setData(points)
    if (tip.current) tip.current.dataset.unit = unit
    if (points.length) {
      if (prev) {
        try {
          chart.timeScale().setVisibleRange(prev)
        } catch {
          chart.timeScale().fitContent()
        }
      } else {
        applyRange(chart, points, { key: '1Y', days: 365 })
      }
      hadData.current = true
    }
  }, [points, color, unit])

  useEffect(() => {
    markersRef.current?.setMarkers(markers)
  }, [markers, points])

  useEffect(() => {
    if (range && chartRef.current && points.length) applyRange(chartRef.current, points, range)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range])

  return (
    <div className="chart-wrap">
      <div ref={host} className="chart" role="img" aria-label={`Price chart in ${unit}`} />
      <div ref={tip} className="tip" style={{ display: 'none' }} />
    </div>
  )
}

function applyRange(chart, points, range) {
  if (range.days == null) {
    chart.timeScale().fitContent()
    return
  }
  const last = points[points.length - 1].time
  const d = new Date(last + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() - range.days)
  const from = d.toISOString().slice(0, 10)
  chart.timeScale().setVisibleRange({ from: from < points[0].time ? points[0].time : from, to: last })
}
