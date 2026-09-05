import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import StatTile from './StatTile'
import StatusPill from './StatusPill'
import LineChart from './LineChart'
import OutcomeCard from './OutcomeCard'
import AqiScaleLegend from './AqiScaleLegend'
import NextRefreshCard from './NextRefreshCard'
import { classifyAqiLevel, zScore } from '../aqiLevels'

const REFRESH_INTERVAL_SECONDS = 300

function fmtNo2(v) {
  return `${v.toExponential(2)}`
}

export default function AqiPanel() {
  const [proxy, setProxy] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [risk, setRisk] = useState(null)
  const [explain, setExplain] = useState(null)
  const [error, setError] = useState(null)

  const loadData = useCallback(() => {
    Promise.all([api.aqiProxy(), api.forecastAqi(7), api.riskAqi(7), api.explainAqi()])
      .then(([p, f, r, e]) => {
        setProxy(p)
        setForecast(f)
        setRisk(r)
        setExplain(e)
        setError(null)
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

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

  const currentZ = zScore(proxy.value, risk.baseline_mean, risk.baseline_std)
  const currentLevel = classifyAqiLevel(currentZ)
  const forecastZ = zScore(risk.forecast_mean, risk.baseline_mean, risk.baseline_std)
  const forecastLevel = classifyAqiLevel(forecastZ)

  return (
    <>
      <div className="grid">
        <NextRefreshCard intervalSeconds={REFRESH_INTERVAL_SECONDS} onRefresh={loadData} />
        <StatTile
          label="NO₂ proxy (current)"
          value={proxy.value == null ? 'No data' : currentLevel?.label ?? '—'}
          valueColor={proxy.value == null ? undefined : currentLevel?.color}
          caption={
            proxy.value == null
              ? `No cloud-free Sentinel-5P pixels in the last ${proxy.scene_count} scenes`
              : `${proxy.value.toExponential(2)} mol/m² · ${proxy.scene_count} recent Sentinel-5P scenes`
          }
          accent="var(--series-1)"
        />
        <StatTile
          label="7-day forecast avg"
          value={forecastLevel?.label ?? '—'}
          valueColor={forecastLevel?.color}
          caption={`${risk.forecast_mean.toExponential(2)} mol/m² · ${risk.pct_change_vs_baseline >= 0 ? '+' : ''}${risk.pct_change_vs_baseline.toFixed(1)}% vs ${risk.baseline_mean.toExponential(2)} baseline`}
          accent="var(--series-1)"
        />
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-critical)' }}>
          <div className="label">Pollution risk</div>
          <StatusPill level={risk.risk_level} />
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <AqiScaleLegend baselineMean={risk.baseline_mean} baselineStd={risk.baseline_std} />
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
