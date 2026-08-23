import { useEffect, useState } from 'react'
import { api } from '../api'
import StatTile from './StatTile'
import StatusPill from './StatusPill'
import LineChart from './LineChart'

export default function VegetationPanel() {
  const [ndvi, setNdvi] = useState(null)
  const [risk, setRisk] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Both endpoints re-scan ~150-200 Sentinel-2 scenes server-side (30-90s+, see
    // CLAUDE.md) — this panel loads independently of the faster NO2 panel so one slow
    // pipeline never blocks the other from rendering.
    Promise.all([api.ndvi(), api.riskVegetation()])
      .then(([n, r]) => {
        setNdvi(n)
        setRisk(r)
      })
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="card error">Vegetation pipeline failed to load: {error}</div>
  if (!ndvi || !risk) {
    return (
      <div className="card loading">
        <span className="spinner" />
        Loading vegetation data — this scans ~150-200 satellite scenes and can take up to a
        minute…
      </div>
    )
  }

  const current = ndvi.series[ndvi.series.length - 1]

  return (
    <>
      <div className="grid">
        <StatTile
          label="NDVI (latest scene)"
          value={current.value.toFixed(3)}
          caption={`${current.date} · ${ndvi.scene_count} usable scenes over the trailing year`}
          accent="var(--series-3)"
        />
        <StatTile
          label={`Recent avg (last ${risk.recent_window_days}d)`}
          value={risk.recent_mean.toFixed(3)}
          caption={`${risk.pct_change_vs_baseline >= 0 ? '+' : ''}${risk.pct_change_vs_baseline.toFixed(1)}% vs 365-day baseline`}
          accent="var(--series-3)"
        />
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-critical)' }}>
          <div className="label">Deforestation risk</div>
          <StatusPill level={risk.risk_level} />
        </div>
      </div>

      <div className="card">
        <h2>NDVI over the trailing year</h2>
        <LineChart
          points={ndvi.series.map((p) => ({ x: p.date, y: p.value }))}
          color="var(--series-3)"
          formatValue={(v) => v.toFixed(3)}
          formatLabel={(d) => d.slice(0, 7)}
        />
        <div className="caption">
          Cloud-masked Sentinel-2 scenes only — gaps (e.g. monsoon months) are real missing
          data, not interpolated.
        </div>
      </div>

      <div className="card">
        <h2>Outcomes linked to vegetation loss</h2>
        {risk.outcomes.map((o) => (
          <div className="outcome-row" key={o.outcome}>
            <div style={{ flex: 1 }}>
              <div className="name">{o.outcome.replace('_', ' ')}</div>
              <div className="mechanism">{o.explanation}</div>
              <div className="citation">{o.citation}</div>
            </div>
            <StatusPill level={o.risk_level} />
          </div>
        ))}
      </div>
    </>
  )
}
