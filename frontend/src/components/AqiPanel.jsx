import { useEffect, useState } from 'react'
import { api } from '../api'
import StatTile from './StatTile'
import StatusPill from './StatusPill'
import LineChart from './LineChart'
import OutcomeCard from './OutcomeCard'

function fmtNo2(v) {
  return `${v.toExponential(2)}`
}

export default function AqiPanel() {
  const [proxy, setProxy] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [risk, setRisk] = useState(null)
  const [explain, setExplain] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.aqiProxy(), api.forecastAqi(7), api.riskAqi(7), api.explainAqi()])
      .then(([p, f, r, e]) => {
        setProxy(p)
        setForecast(f)
        setRisk(r)
        setExplain(e)
      })
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="card error">AQI pipeline failed to load: {error}</div>
  if (!proxy || !forecast || !risk || !explain) {
    return (
      <div className="card loading">
        <span className="spinner" />
        Loading air quality data…
      </div>
    )
  }

  const maxAbsContribution = Math.max(...explain.contributions.map((c) => Math.abs(c.contribution)))

  return (
    <>
      <div className="grid">
        <StatTile
          label="NO₂ proxy (current)"
          value={proxy.value.toExponential(2)}
          caption={`mol/m² · ${proxy.scene_count} recent Sentinel-5P scenes`}
          accent="var(--series-1)"
        />
        <StatTile
          label="7-day forecast avg"
          value={(
            forecast.forecast.reduce((s, p) => s + p.value, 0) / forecast.forecast.length
          ).toExponential(2)}
          caption={`${risk.pct_change_vs_baseline >= 0 ? '+' : ''}${risk.pct_change_vs_baseline.toFixed(1)}% vs ${risk.baseline_mean.toExponential(2)} baseline`}
          accent="var(--series-1)"
        />
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-critical)' }}>
          <div className="label">Pollution risk</div>
          <StatusPill level={risk.risk_level} />
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr' }}>
        <div className="card">
          <h2>NO₂ forecast (next {forecast.horizon_days} days)</h2>
          <LineChart
            points={forecast.forecast.map((p) => ({ x: p.date, y: p.value }))}
            color="var(--series-1)"
            formatValue={fmtNo2}
            formatLabel={(d) => d.slice(5)}
          />
          <div className="caption">
            Holt-Winters forecast over {forecast.history_points} days of history (
            {forecast.history_start} → {forecast.history_end}) · values in mol/m²
          </div>
        </div>

        <div className="card">
          <h2>What's driving it</h2>
          <p style={{ fontSize: 13, marginBottom: 14 }}>{explain.summary}</p>
          {explain.contributions.map((c) => {
            const widthPct = (Math.abs(c.contribution) / maxAbsContribution) * 100
            const positive = c.contribution > 0
            return (
              <div className="shap-row" key={c.feature}>
                <div className="shap-label-row">
                  <span className="name">{c.label}</span>
                  <span className="value">{c.contribution.toExponential(1)}</span>
                </div>
                <div className="shap-track">
                  <div
                    className="shap-fill"
                    style={{
                      width: `${widthPct}%`,
                      background: positive ? 'var(--diverging-pos)' : 'var(--diverging-neg)',
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="card">
        <h2>Health outcomes linked to NO₂</h2>
        <div className="outcome-grid">
          {risk.outcomes.map((o) => (
            <OutcomeCard key={o.outcome} outcome={o} />
          ))}
        </div>
      </div>
    </>
  )
}
