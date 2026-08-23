import { useEffect, useState } from 'react'
import { api } from '../api'
import StatTile from './StatTile'
import StatusPill from './StatusPill'
import LineChart from './LineChart'
import OutcomeCard from './OutcomeCard'

export default function FaunaPanel() {
  const [fauna, setFauna] = useState(null)
  const [risk, setRisk] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.fauna(), api.riskFauna()])
      .then(([f, k]) => {
        setFauna(f)
        setRisk(k)
      })
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="card error">Fauna pipeline failed to load: {error}</div>
  if (!fauna || !risk) {
    return (
      <div className="card loading">
        <span className="spinner" />
        Loading wildlife-observation data (GBIF, ~13 monthly queries)…
      </div>
    )
  }

  return (
    <>
      <div className="info-banner" style={{ marginTop: 0, marginBottom: 16 }}>
        <strong>Read this before trusting the numbers below.</strong> This tracks GBIF
        species-observation counts (citizen-science platforms like iNaturalist) near
        Vellore — a real but noisy signal, confounded by how many people were out
        reporting, not just what's actually there. The most recent month in particular
        often reads low simply because of GBIF's publishing lag, not a real activity drop.
      </div>

      <div className="grid">
        <StatTile
          label="Observations (last 30 days)"
          value={risk.recent_count}
          caption={`vs ${risk.baseline_mean.toFixed(0)} typical, over the prior ${fauna.months_series.length - 1} months`}
          accent="var(--series-3)"
        />
        <StatTile
          label="Change vs baseline"
          value={`${risk.pct_change_vs_baseline >= 0 ? '+' : ''}${risk.pct_change_vs_baseline.toFixed(1)}%`}
          accent="var(--series-3)"
        />
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-critical)' }}>
          <div className="label">Fauna disruption risk</div>
          <StatusPill level={risk.risk_level} />
        </div>
      </div>

      <div className="card">
        <h2>Monthly wildlife observations (GBIF)</h2>
        <LineChart
          points={fauna.months_series.map((m) => ({ x: m.end, y: m.count }))}
          color="var(--series-3)"
          formatValue={(v) => `${Math.round(v)} obs.`}
          formatLabel={(d) => d.slice(0, 7)}
        />
        <div className="caption">
          Total species occurrence records within ~50km of Vellore, per trailing 30-day
          window (all taxa, all data providers feeding GBIF).
        </div>
      </div>

      <div className="card">
        <h2>Outcomes linked to wildlife activity</h2>
        <div className="outcome-grid">
          {risk.outcomes.map((o) => (
            <OutcomeCard key={o.outcome} outcome={o} />
          ))}
        </div>
      </div>
    </>
  )
}
