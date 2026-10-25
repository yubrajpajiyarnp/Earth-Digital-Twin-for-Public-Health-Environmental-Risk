import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import StatusPill from '../ui/StatusPill'
import MultiLineChart, { ChartLegend } from '../ui/MultiLineChart'
import ModelAttributionCard from '../ui/ModelAttributionCard'
import NextRefreshCard from '../ui/NextRefreshCard'

const REFRESH_INTERVAL_SECONDS = 900
const HISTORY_DAYS_SHOWN = 45

const LEGEND = [
  { id: 'observed', label: 'GloFAS observed', color: 'var(--series-1)' },
  { id: 'ml', label: 'Local ML forecast', color: 'var(--series-2)' },
  { id: 'glofas', label: 'GloFAS forecast', color: 'var(--series-1)', dashed: true },
  { id: 'baseline', label: 'Holt-Winters baseline', color: 'var(--text-muted)', dashed: true },
]

const fmtM3s = (v) => `${v.toFixed(v < 10 ? 2 : 1)} m³/s`
const fmtDate = (d) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

function RiverCard({ river }) {
  const history = river.history.slice(-HISTORY_DAYS_SHOWN)
  const labels = [...history.map((h) => h.date), ...river.forecast.map((f) => f.date)]
  const pad = (n) => Array(n).fill(null)
  // Repeat the last observed value at the start of each forecast line so the lines connect.
  const last = history[history.length - 1]?.m3s ?? null
  const series = [
    { id: 'observed', label: 'Observed', color: 'var(--series-1)', values: [...history.map((h) => h.m3s), ...pad(river.forecast.length)] },
    {
      id: 'glofas',
      label: 'GloFAS fcst',
      color: 'var(--series-1)',
      dashed: true,
      width: 1.5,
      values: [...pad(history.length - 1), last, ...river.forecast.map((f) => f.glofas_m3s)],
    },
    {
      id: 'baseline',
      label: 'HW baseline',
      color: 'var(--text-muted)',
      dashed: true,
      width: 1.5,
      values: [...pad(history.length - 1), last, ...river.forecast.map((f) => f.baseline_m3s)],
    },
    {
      id: 'ml',
      label: 'ML forecast',
      color: 'var(--series-2)',
      width: 2.5,
      values: [...pad(history.length - 1), last, ...river.forecast.map((f) => f.ml_m3s)],
    },
  ]
  const surgeMarkers = river.surges.map((s) => ({
    index: history.length + river.forecast.findIndex((f) => f.date === s.date),
    label: `Surge Δz ${s.delta_z.toFixed(1)}`,
  }))
  const peakIsHigh = river.peak_m3s >= river.thresholds_m3s.p90 * 0.5

  return (
    <div className="card river-card">
      <div className="outcome-card-head">
        <h3 style={{ margin: 0 }}>{river.river}</h3>
        <StatusPill level={river.risk_tier} />
      </div>
      <div className="metric-row">
        <div className="metric">
          <span className="metric-label">Now</span>
          <span className="metric-value">{fmtM3s(river.current_m3s)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Forecast peak</span>
          <span className="metric-value">{fmtM3s(river.peak_m3s)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Peak date</span>
          <span className="metric-value">{fmtDate(river.peak_date)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Max Δz</span>
          <span className="metric-value" style={river.surge_warning ? { color: 'var(--status-critical)' } : undefined}>
            {river.max_delta_z >= 0 ? '+' : ''}
            {river.max_delta_z.toFixed(2)}
          </span>
        </div>
      </div>
      <MultiLineChart
        labels={labels}
        series={series}
        splitIndex={history.length}
        markers={surgeMarkers}
        thresholds={
          peakIsHigh
            ? [
                { value: river.thresholds_m3s.p90, label: 'P90', color: 'var(--status-warning)' },
                { value: river.thresholds_m3s.p99, label: 'P99', color: 'var(--status-critical)' },
              ]
            : []
        }
        height={200}
        formatValue={(v) => v.toFixed(v < 10 ? 1 : 0)}
        formatLabel={fmtDate}
      />
      <div className="caption" style={{ marginTop: 6 }}>
        Historical thresholds: P90 {fmtM3s(river.thresholds_m3s.p90)} · P99 {fmtM3s(river.thresholds_m3s.p99)} · record{' '}
        {fmtM3s(river.thresholds_m3s.max)}
        {!peakIsHigh && ' (off-scale — current flows are far below them)'}
      </div>
    </div>
  )
}

export default function KathmanduFloodPanel() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    setError(null)
    api
      .predictNepal('kathmandu_flood')
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 3fr) minmax(220px, 1fr)' }}>
        <div className="card">
          <div className="region-head">
            <h2 style={{ margin: 0 }}>Kathmandu flood early warning</h2>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {data && <StatusPill level={data.risk_tier} />}
              <button className="run-btn" onClick={load} disabled={loading} style={{ padding: '6px 14px' }}>
                {loading ? 'Forecasting…' : 'Refresh'}
              </button>
            </div>
          </div>
          <p className="scenario-desc" style={{ marginTop: 8, marginBottom: 8 }}>
            14-day discharge forecast for the Bagmati, Bishnumati and Dhobi Khola from locally trained
            gradient-boosting models driven by ECMWF weather, checked against a Holt-Winters baseline to flag
            unexpected surges.
          </p>
          {error && <div className="error">{error}</div>}
          {loading && !data && (
            <div className="loading">
              <span className="spinner" />
              Running the local flood models on the latest forecast…
            </div>
          )}
          {data && <p style={{ fontSize: 14, lineHeight: 1.55, margin: 0 }}>{data.narrative}</p>}
        </div>
        <NextRefreshCard intervalSeconds={REFRESH_INTERVAL_SECONDS} onRefresh={load} />
      </div>

      {data && (
        <>
          {data.surge_warning && (
            <div className="surge-banner">
              ⚠ Unexpected future surge: the ML forecast exceeds the recent-trend baseline by Δz ≥ 1 on{' '}
              {data.rivers
                .filter((r) => r.surge_warning)
                .map((r) => `${r.river} (${r.surges.map((s) => fmtDate(s.date)).join(', ')})`)
                .join('; ')}
              .
            </div>
          )}

          <ChartLegend items={LEGEND} />
          <div className="river-grid">
            {data.rivers.map((r) => (
              <RiverCard key={r.river_id} river={r} />
            ))}
          </div>

          <div className="two-col" style={{ marginTop: 16 }}>
            <div className="card">
              <h3>Forecast weather drivers (Kathmandu)</h3>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Rain mm</th>
                      <th>Peak mm/h</th>
                      <th>API mm</th>
                      <th>Soil 28–100</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.drivers_forecast.map((d) => (
                      <tr key={d.date}>
                        <td>{fmtDate(d.date)}</td>
                        <td>{d.precip_sum_mm.toFixed(1)}</td>
                        <td>{d.precip_max_hourly_mm.toFixed(1)}</td>
                        <td>{d.api_mm.toFixed(1)}</td>
                        <td>{d.sm_28_100.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.linked_outcomes.length > 0 && (
                <p className="citation" style={{ marginTop: 10 }}>
                  Linked outcomes: {data.linked_outcomes.map((o) => o.outcome.replace(/_/g, ' ')).join(', ')}
                </p>
              )}
            </div>
            <ModelAttributionCard attribution={data.rivers[0].attribution} />
          </div>

          <details className="assumption-details">
            <summary>How is this estimated?</summary>
            <p style={{ marginTop: 8 }}>{data.assumption}</p>
          </details>
        </>
      )}
    </div>
  )
}
