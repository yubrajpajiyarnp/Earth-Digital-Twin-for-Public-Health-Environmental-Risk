import { useEffect, useState } from 'react'
import { api } from '../api'
import StatTile from './StatTile'
import StatusPill from './StatusPill'
import LineChart from './LineChart'
import OutcomeCard from './OutcomeCard'
import VegetationScaleLegend from './VegetationScaleLegend'
import { classifyVegetationLevel, zScore } from '../vegetationLevels'

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
  const currentZ = zScore(current.value, risk.baseline_mean, risk.baseline_std)
  const currentLevel = classifyVegetationLevel(currentZ)
  const recentZ = zScore(risk.recent_mean, risk.baseline_mean, risk.baseline_std)
  const recentLevel = classifyVegetationLevel(recentZ)

  return (
    <>
      <div className="grid">
        <StatTile
          label="NDVI (latest scene)"
          value={currentLevel?.label ?? '—'}
          valueColor={currentLevel?.color}
          caption={`${current.value.toFixed(3)} · ${current.date} · ${ndvi.scene_count} usable scenes over the trailing year`}
          accent="var(--series-3)"
        />
        <StatTile
          label={`Recent avg (last ${risk.recent_window_days}d)`}
          value={recentLevel?.label ?? '—'}
          valueColor={recentLevel?.color}
          caption={`${risk.recent_mean.toFixed(3)} · ${risk.pct_change_vs_baseline >= 0 ? '+' : ''}${risk.pct_change_vs_baseline.toFixed(1)}% vs 365-day baseline`}
          accent="var(--series-3)"
        />
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-critical)' }}>
          <div className="label">Deforestation risk</div>
          <StatusPill level={risk.risk_level} />
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <VegetationScaleLegend baselineMean={risk.baseline_mean} baselineStd={risk.baseline_std} />
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
          Cloud-masked Sentinel-2 data. Gaps like monsoon months are real — not filled in.
        </div>
      </div>

      <div className="card">
        <h2>Outcomes linked to vegetation loss</h2>
        <div className="outcome-grid">
          {risk.outcomes.map((o) => (
            <OutcomeCard key={o.outcome} outcome={o} />
          ))}
        </div>
      </div>
    </>
  )
}
