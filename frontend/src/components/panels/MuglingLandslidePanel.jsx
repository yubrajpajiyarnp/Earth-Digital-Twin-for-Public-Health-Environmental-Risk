import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import StatusPill from '../ui/StatusPill'
import MultiLineChart, { ChartLegend } from '../ui/MultiLineChart'
import ModelAttributionCard from '../ui/ModelAttributionCard'

const fmtPct = (v) => `${(v * 100).toFixed(v < 0.01 ? 2 : 1)}%`
const fmtDate = (d) => new Date(d).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

export default function MuglingLandslidePanel() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    setError(null)
    api
      .predictNepal('mugling_landslide')
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const today = data?.today
  return (
    <div>
      <div className="card">
        <div className="region-head">
          <h2 style={{ margin: 0 }}>Mugling–Narayangadh landslide risk</h2>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {data && <StatusPill level={data.risk_tier} />}
            <button className="run-btn" onClick={load} disabled={loading} style={{ padding: '6px 14px' }}>
              {loading ? 'Assessing…' : 'Refresh'}
            </button>
          </div>
        </div>
        <p className="scenario-desc" style={{ marginTop: 8, marginBottom: 8 }}>
          Daily slope-failure probability for the Trishuli gorge corridor from a classifier trained on reported
          landslides, cross-checked with a physical slope stability index from deep soil wetness and DEM slope.
        </p>
        {error && <div className="error">{error}</div>}
        {loading && !data && (
          <div className="loading">
            <span className="spinner" />
            Running the local landslide model on the latest forecast…
          </div>
        )}
        {data && (
          <>
            <div className="river-card">
              <div className="metric-row">
                <div className="metric">
                  <span className="metric-label">Failure probability today</span>
                  <span className="metric-value">{fmtPct(today.failure_probability)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">z-score</span>
                  <span className="metric-value">
                    {today.failure_z >= 0 ? '+' : ''}
                    {today.failure_z.toFixed(2)}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric-label">Slope stability index</span>
                  <span className="metric-value">{today.slope_stability_index.toFixed(2)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Deep-soil wetness</span>
                  <span className="metric-value">{Math.round(today.wetness * 100)}%</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Corridor slope</span>
                  <span className="metric-value">
                    {data.slope_deg.toFixed(1)}° <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>×{data.slope_multiplier.toFixed(2)}</span>
                  </span>
                </div>
              </div>
            </div>
            <p style={{ fontSize: 14, lineHeight: 1.55, margin: '6px 0 0' }}>{data.narrative}</p>
          </>
        )}
      </div>

      {data && (
        <>
          <div className="two-col" style={{ marginTop: 16 }}>
            <div className="card">
              <h3>14-day failure probability</h3>
              <ChartLegend items={[{ id: 'p', label: 'Failure probability', color: 'var(--series-2)' }]} />
              <MultiLineChart
                labels={data.daily.map((d) => d.date)}
                series={[
                  { id: 'p', label: 'Failure probability', color: 'var(--series-2)', width: 2.5, values: data.daily.map((d) => d.failure_probability), format: fmtPct },
                ]}
                thresholds={[
                  { value: data.probability_thresholds.elevated, label: 'elevated (z=1)', color: 'var(--status-warning)' },
                  { value: data.probability_thresholds.severe, label: 'severe (z=2)', color: 'var(--status-critical)' },
                ]}
                height={210}
                formatValue={(v) => `${(v * 100).toFixed(0)}%`}
                formatLabel={fmtDate}
              />
            </div>
            <div className="card">
              <h3>14-day slope stability index</h3>
              <ChartLegend items={[{ id: 'fos', label: 'Factor of safety (FoS)', color: 'var(--series-3)' }]} />
              <MultiLineChart
                labels={data.daily.map((d) => d.date)}
                series={[
                  { id: 'fos', label: 'FoS', color: 'var(--series-3)', width: 2.5, values: data.daily.map((d) => d.slope_stability_index) },
                ]}
                thresholds={[
                  { value: data.fos_thresholds.elevated, label: 'elevated (<1.3)', color: 'var(--status-warning)' },
                  { value: data.fos_thresholds.severe, label: 'failure (<1.0)', color: 'var(--status-critical)' },
                ]}
                height={210}
                formatValue={(v) => v.toFixed(2)}
                formatLabel={fmtDate}
              />
            </div>
          </div>

          <div className="two-col" style={{ marginTop: 16 }}>
            <div className="card">
              <h3>Daily outlook</h3>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Rain mm</th>
                      <th>Peak mm/h</th>
                      <th>API mm</th>
                      <th>P(fail)</th>
                      <th>FoS</th>
                      <th>Tier</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.daily.map((d) => (
                      <tr key={d.date}>
                        <td>{fmtDate(d.date)}</td>
                        <td>{d.precip_sum_mm.toFixed(1)}</td>
                        <td>{d.precip_max_hourly_mm.toFixed(1)}</td>
                        <td>{d.api_mm.toFixed(1)}</td>
                        <td>{fmtPct(d.failure_probability)}</td>
                        <td>{d.slope_stability_index.toFixed(2)}</td>
                        <td>
                          <StatusPill level={d.risk_tier} />
                        </td>
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
            <ModelAttributionCard attribution={data.attribution} />
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
