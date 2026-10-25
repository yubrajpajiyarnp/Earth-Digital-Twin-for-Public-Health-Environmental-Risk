import { Fragment, useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import MultiLineChart, { ChartLegend } from '../ui/MultiLineChart'

const DRIVER_COLORS = ['var(--series-1)', 'var(--series-4)', 'var(--series-3)', 'var(--series-5)', 'var(--text-secondary)']
const TARGET_COLOR = 'var(--series-2)'
const VIEWS = [
  { id: 'last1', label: 'Last 12 months', days: 365 },
  { id: 'last2', label: 'Last 2 years', days: 730 },
  { id: 'last5', label: 'Last 5 years', days: 1825 },
  { id: 'all', label: 'All time (2011 →)', days: 6000 },
  { id: 'year', label: 'By year' },
  { id: 'month', label: 'By month' },
]
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const fmtDate = (d) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' })
const fmtDay = (d) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
const fmtMonth = (d) => new Date(d).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
const RESOLUTION_LABEL = { D: 'daily', W: 'weekly', M: 'monthly' }
const pad2 = (n) => String(n).padStart(2, '0')

// Inclusive YYYY-MM-DD bounds for a calendar year or month (month is 0-based). Built from
// numbers rather than Date→ISO so the browser's time zone can't shift the day.
function windowFor(view, year, month) {
  if (view === 'year') return { start: `${year}-01-01`, end: `${year}-12-31` }
  const lastDay = new Date(year, month + 1, 0).getDate()
  return { start: `${year}-${pad2(month + 1)}-01`, end: `${year}-${pad2(month + 1)}-${pad2(lastDay)}` }
}

// Every (year, month) pair the stored history covers, oldest first.
function monthsInRange(available) {
  if (!available) return []
  const [sy, sm] = available.start.split('-').map(Number)
  const [ey, em] = available.end.split('-').map(Number)
  const out = []
  for (let y = sy, m = sm - 1; y < ey || (y === ey && m <= em - 1); m === 11 ? (y++, (m = 0)) : m++) {
    out.push({ year: y, month: m })
  }
  return out
}

function fmtP(p) {
  if (p == null) return '—'
  return p < 0.001 ? '<0.001' : p.toFixed(3)
}

function CorrCell({ r }) {
  if (r == null) return <span>—</span>
  const pct = Math.abs(r) * 50
  return (
    <span>
      <span className="corr-bar">
        <span
          className="corr-bar-fill"
          style={{
            left: r >= 0 ? '50%' : `${50 - pct}%`,
            width: `${pct}%`,
            background: r >= 0 ? 'var(--diverging-pos)' : 'var(--diverging-neg)',
          }}
        />
      </span>
      {r.toFixed(2)}
    </span>
  )
}

function heatColor(r) {
  const c = r >= 0 ? 'var(--diverging-pos)' : 'var(--diverging-neg)'
  return `color-mix(in srgb, ${c} ${Math.round(Math.abs(r) * 70)}%, var(--surface-2))`
}

// Backtest: how past weather trigger curves lined up with actual disaster spikes. Every
// series is min-max scaled to 0–100% so drivers with different units can share one axis;
// red ticks mark periods with reported incidents. Computed by the backend from the data
// stored in the local model bundle.
export default function CollinearityPanel({ region }) {
  const [view, setView] = useState('last2')
  const [year, setYear] = useState(null)
  const [month, setMonth] = useState(null)
  const [available, setAvailable] = useState(null)
  const [resample, setResample] = useState(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [hidden, setHidden] = useState(new Set())

  const calendarView = view === 'year' || view === 'month'
  // A month has too few weeks for meaningful correlations, so it's always daily.
  const effectiveResample = view === 'month' ? 'D' : resample

  useEffect(() => {
    if (calendarView && year == null) return
    let cancelled = false
    setLoading(true)
    setError(null)
    const query = calendarView
      ? { ...windowFor(view, year, month), resample: effectiveResample }
      : { daysBack: VIEWS.find((v) => v.id === view).days, resample: effectiveResample }
    api
      .collinearity(region, query)
      .then((d) => {
        if (cancelled) return
        setData(d)
        setAvailable(d.available)
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [region, view, year, month, effectiveResample, calendarView])

  const allMonths = useMemo(() => monthsInRange(available), [available])
  const years = useMemo(() => [...new Set(allMonths.map((m) => m.year))].reverse(), [allMonths])
  const monthsOfYear = allMonths.filter((m) => m.year === year).map((m) => m.month)

  function changeView(next) {
    setView(next)
    if ((next === 'year' || next === 'month') && year == null && allMonths.length) {
      // Default to the most recent complete month/year that history covers.
      const latest = allMonths[allMonths.length - 1]
      setYear(next === 'year' && latest.month < 11 && years.length > 1 ? latest.year - 1 : latest.year)
      setMonth(latest.month)
    }
  }

  function changeYear(y) {
    setYear(y)
    const valid = allMonths.filter((m) => m.year === y).map((m) => m.month)
    if (!valid.includes(month)) setMonth(valid[valid.length - 1])
  }

  // Step one month/year back (-1) or forward (+1) within the available history.
  function step(dir) {
    if (view === 'year') {
      const i = years.indexOf(year) - dir // years are newest-first
      if (i >= 0 && i < years.length) changeYear(years[i])
      return
    }
    const i = allMonths.findIndex((m) => m.year === year && m.month === month) + dir
    if (i >= 0 && i < allMonths.length) {
      setYear(allMonths[i].year)
      setMonth(allMonths[i].month)
    }
  }

  const atStart = view === 'year' ? year === years[years.length - 1] : allMonths[0]?.year === year && allMonths[0]?.month === month
  const atEnd =
    view === 'year'
      ? year === years[0]
      : allMonths[allMonths.length - 1]?.year === year && allMonths[allMonths.length - 1]?.month === month

  const chart = useMemo(() => {
    if (!data) return null
    const labels = data.series.map((p) => p.date)
    const lineTargets = data.targets.filter((t) => t.id !== 'incidents' || data.targets.length === 1)
    const legend = [
      ...lineTargets.map((t) => ({ id: t.id, label: t.label, color: TARGET_COLOR })),
      ...data.drivers.map((d, i) => ({ id: d.id, label: d.label, color: DRIVER_COLORS[i % DRIVER_COLORS.length] })),
    ]
    const series = legend
      .filter((l) => !hidden.has(l.id))
      .map((l) => ({
        id: l.id,
        label: l.label,
        color: l.color,
        width: lineTargets.some((t) => t.id === l.id) ? 2.6 : 1.4,
        values: data.series.map((p) => p[l.id]),
      }))
    const markers = data.series
      .map((p, index) => ({ index, n: p.incidents }))
      .filter((m) => m.n > 0)
      .map((m) => ({ index: m.index, label: `${m.n} reported incident${m.n > 1 ? 's' : ''}` }))
    return { labels, legend, series, markers }
  }, [data, hidden])

  function toggle(id) {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="region-head">
        <h2 style={{ margin: 0 }}>Historical collinearity &amp; incident graph</h2>
        <div className="period-controls">
          <label className="select-field">
            <span>View</span>
            <select value={view} onChange={(e) => changeView(e.target.value)} disabled={!available}>
              {VIEWS.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </select>
          </label>

          {calendarView && year != null && (
            <>
              <button className="step-btn" onClick={() => step(-1)} disabled={atStart} aria-label="Previous period">
                ‹
              </button>
              <label className="select-field">
                <span>Year</span>
                <select value={year} onChange={(e) => changeYear(Number(e.target.value))}>
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
              {view === 'month' && (
                <label className="select-field">
                  <span>Month</span>
                  <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                    {monthsOfYear.map((m) => (
                      <option key={m} value={m}>
                        {MONTHS[m]}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <button className="step-btn" onClick={() => step(1)} disabled={atEnd} aria-label="Next period">
                ›
              </button>
            </>
          )}

          <label className="select-field">
            <span>Resolution</span>
            <select
              value={effectiveResample ?? data?.resample ?? 'D'}
              onChange={(e) => setResample(e.target.value)}
              disabled={view === 'month'}
              title={view === 'month' ? 'A single month is always shown day by day' : undefined}
            >
              <option value="D">Daily</option>
              <option value="W">Weekly</option>
              <option value="M">Monthly</option>
            </select>
          </label>
        </div>
      </div>
      <p className="scenario-desc" style={{ marginTop: 8 }}>
        How past weather triggers tracked actual disaster spikes. Each curve is scaled to its own range;{' '}
        <span style={{ color: 'var(--status-critical)', fontWeight: 600 }}>red ticks</span> mark periods with
        reported incidents (NDRRMA BIPAD). Click a legend item to hide it.
      </p>

      {error && <div className="error">{error}</div>}
      {loading && !data && (
        <div className="loading">
          <span className="spinner" /> Computing correlations…
        </div>
      )}

      {data && chart && (
        <>
          <ChartLegend items={chart.legend} onToggle={toggle} hidden={hidden} />
          <MultiLineChart
            labels={chart.labels}
            series={chart.series}
            markers={chart.markers}
            normalize
            height={280}
            formatValue={(v) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2))}
            formatLabel={view === 'month' ? fmtDay : data.resample === 'M' ? fmtMonth : fmtDate}
          />
          <div className="caption" style={{ marginTop: 4 }}>
            {data.period.start} → {data.period.end} · {RESOLUTION_LABEL[data.resample]} ·{' '}
            {chart.markers.length} period{chart.markers.length === 1 ? '' : 's'} with incidents
            {loading && ' · updating…'}
          </div>

          <div className="two-col" style={{ marginTop: 18 }}>
            <div>
              <h3>Driver → disaster correlation</h3>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Driver</th>
                      <th>Target</th>
                      <th>Pearson r</th>
                      <th>Spearman ρ</th>
                      <th>p (ρ)</th>
                      <th>n</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.correlations.map((c) => (
                      <tr key={`${c.driver}-${c.target}`}>
                        <td>{c.label}</td>
                        <td>{c.target === 'incidents' ? 'incidents' : 'discharge'}</td>
                        <td>
                          <CorrCell r={c.pearson_r} />
                        </td>
                        <td>
                          <CorrCell r={c.spearman_rho} />
                        </td>
                        <td style={c.spearman_p != null && c.spearman_p < 0.05 ? { fontWeight: 700 } : undefined}>
                          {fmtP(c.spearman_p)}
                        </td>
                        <td>{c.n}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3>Collinearity between drivers</h3>
              <div
                className="heatmap"
                style={{ gridTemplateColumns: `110px repeat(${data.driver_correlation_matrix.labels.length}, 1fr)` }}
              >
                <span />
                {data.driver_correlation_matrix.labels.map((l) => (
                  <span key={l} className="heatmap-label" title={l}>
                    {l.replace(/_/g, ' ')}
                  </span>
                ))}
                {data.driver_correlation_matrix.matrix.map((row, i) => (
                  <Fragment key={i}>
                    <span className="heatmap-label" title={data.driver_correlation_matrix.labels[i]}>
                      {data.driver_correlation_matrix.labels[i].replace(/_/g, ' ')}
                    </span>
                    {row.map((r, j) => (
                      <span key={`${i}-${j}`} className="heatmap-cell" style={{ background: heatColor(r) }}>
                        {r.toFixed(2)}
                      </span>
                    ))}
                  </Fragment>
                ))}
              </div>
              <table className="data-table" style={{ marginTop: 14 }}>
                <thead>
                  <tr>
                    <th>Driver</th>
                    <th>VIF</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.vif).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k.replace(/_/g, ' ')}</td>
                      <td
                        style={{
                          fontWeight: 700,
                          color: v > 10 ? 'var(--status-critical)' : v > 5 ? 'var(--status-warning)' : undefined,
                        }}
                      >
                        {v == null ? '∞' : v.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="caption" style={{ marginTop: 6 }}>
                VIF &gt; 5 flags notable and &gt; 10 severe collinearity — those drivers carry overlapping information.
              </p>
            </div>
          </div>

          <details className="assumption-details">
            <summary>Caveats</summary>
            <p style={{ marginTop: 8 }}>{data.assumption}</p>
          </details>
        </>
      )}
    </div>
  )
}
