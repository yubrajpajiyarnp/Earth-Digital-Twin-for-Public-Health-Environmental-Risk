import { useState } from 'react'
import { api } from '../api'
import StatusPill from './StatusPill'

function ScenarioCard({
  title,
  description,
  sliderLabel,
  min,
  max,
  step = 5,
  unit,
  run,
  metricLabel,
  getCurrent,
  getProjected,
  formatMetric,
}) {
  const [value, setValue] = useState(Math.round((min + max) / 4))
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function handleRun() {
    setLoading(true)
    setError(null)
    run(value)
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  const current = result ? getCurrent(result) : null
  const projected = result ? getProjected(result) : null
  const pctChange = result?.pct_change ?? 0
  const anyChange = result?.outcomes.some((o) => o.risk_before !== o.risk_after)

  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="scenario-desc">{description}</p>

      <div className="field">
        <label>
          <span>{sliderLabel}</span>
          <span>
            {value}
            {unit}
          </span>
        </label>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => setValue(Number(e.target.value))}
        />
        <div className="slider-scale">
          <span>
            {min}
            {unit}
          </span>
          <span>
            {max}
            {unit}
          </span>
        </div>
      </div>

      <button className="run-btn" onClick={handleRun} disabled={loading}>
        {loading ? 'Calculating…' : result ? 'Recalculate' : 'See projected impact'}
      </button>

      {error && (
        <div className="error" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}

      {!result && !loading && !error && (
        <p className="empty-hint">
          Move the slider to the level you want to test, then run it to see the projected
          effect on {metricLabel.toLowerCase()} and linked health risks.
        </p>
      )}

      {result && (
        <div className="scenario-result">
          <div className="metric-compare">
            <div>
              <span className="metric-label">{metricLabel}</span>
              <span className="metric-values">
                {formatMetric(current)} <span className="arrow">→</span> {formatMetric(projected)}
              </span>
            </div>
            <span className={`delta-badge ${pctChange !== 0 ? 'improve' : 'neutral'}`}>
              {pctChange >= 0 ? '+' : ''}
              {pctChange.toFixed(1)}%
            </span>
          </div>

          <div className="outcome-list">
            {result.outcomes.map((o) => (
              <div className="outcome-change" key={o.outcome}>
                <span className="outcome-name">{o.outcome.replace('_', ' ')}</span>
                {o.risk_before === o.risk_after ? (
                  <span className="no-change">
                    no change <StatusPill level={o.risk_after} />
                  </span>
                ) : (
                  <span className="changed">
                    <StatusPill level={o.risk_before} />
                    <span className="arrow">→</span>
                    <StatusPill level={o.risk_after} />
                  </span>
                )}
              </div>
            ))}
          </div>

          {!anyChange && (
            <p className="empty-hint" style={{ marginTop: 8 }}>
              At this level, risk stays in the same category. Try a larger value to see a
              bigger effect.
            </p>
          )}

          <details className="assumption-details">
            <summary>How is this estimated?</summary>
            <p>{result.assumption}</p>
          </details>
        </div>
      )}
    </div>
  )
}

export default function SimulationPanel() {
  return (
    <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
      <ScenarioCard
        title="What if: traffic reduction"
        description="See how cutting vehicle traffic and related emissions would change Vellore's air pollution, and the asthma/respiratory risk linked to it."
        sliderLabel="Cut traffic-related emissions by"
        min={0}
        max={100}
        unit="%"
        run={api.simulateTraffic}
        metricLabel="NO₂ pollution"
        getCurrent={(r) => r.no2_current}
        getProjected={(r) => r.no2_projected}
        formatMetric={(v) => v.toExponential(2)}
      />
      <ScenarioCard
        title="What if: afforestation"
        description="See how reforesting part of the monitored area would change vegetation cover, and the heat/temperature risk linked to vegetation loss."
        sliderLabel="Reforest this much of the buffer area"
        min={0}
        max={100}
        unit="%"
        run={api.simulateAfforestation}
        metricLabel="Vegetation (NDVI)"
        getCurrent={(r) => r.ndvi_current}
        getProjected={(r) => r.ndvi_projected}
        formatMetric={(v) => v.toFixed(3)}
      />
    </div>
  )
}
