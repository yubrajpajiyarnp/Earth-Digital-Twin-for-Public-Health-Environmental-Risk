import { useState } from 'react'
import { api } from '../../api/client'
import StatusPill from '../ui/StatusPill'

const PRESETS = [
  { label: 'Dry season day', rain: 5, burst: 2, sat: 20 },
  { label: 'Typical monsoon day', rain: 40, burst: 12, sat: 65 },
  { label: 'Cloudburst on wet soil', rain: 180, burst: 60, sat: 95 },
  { label: 'Sept 2024-scale storm', rain: 300, burst: 45, sat: 100 },
]

function Slider({ label, value, min, max, step, unit, onChange, scale }) {
  return (
    <div className="field">
      <label>
        <span>{label}</span>
        <span>
          {value}
          {unit}
        </span>
      </label>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <div className="slider-scale">
        {scale.map((s) => (
          <span key={s}>{s}</span>
        ))}
      </div>
    </div>
  )
}

const DESCRIPTION = {
  flood:
    "Set a hypothetical day's rainfall, its peak cloudburst intensity and deep-soil saturation, then run the same local models used for the live forecast to see each Kathmandu river's discharge.",
  landslide:
    "Set a hypothetical day's rainfall, its peak cloudburst intensity and deep-soil saturation, then run the same local model used for the live forecast to see the corridor's slope-failure risk.",
}

// Runs the trained local models on a hypothetical day. Results update only when "Run" is
// pressed so dragging a slider doesn't fire a request per pixel. `focus` ('flood' or
// 'landslide') shows only that hazard's result; the backend computes both either way.
export default function InteractiveSimulator({ focus }) {
  const [rain, setRain] = useState(150)
  const [burst, setBurst] = useState(40)
  const [sat, setSat] = useState(90)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  function run(r = rain, b = burst, s = sat) {
    setLoading(true)
    setError(null)
    api
      .simulateInteractive({ rain_volume_mm: r, cloudburst_mm_per_hr: b, soil_saturation_pct: s })
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  function applyPreset(p) {
    setRain(p.rain)
    setBurst(p.burst)
    setSat(p.sat)
    run(p.rain, p.burst, p.sat)
  }

  const slide = result?.landslide
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h2>{focus === 'flood' ? 'Flood scenario simulator' : focus === 'landslide' ? 'Landslide scenario simulator' : 'Interactive disaster simulator'}</h2>
      <p className="scenario-desc">
        {DESCRIPTION[focus] ||
          "Set a hypothetical day's rainfall, its peak cloudburst intensity and deep-soil saturation, then run the same local models used for the live forecast — flood discharge for Kathmandu's rivers and slope failure for the Mugling corridor."}
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        {PRESETS.map((p) => (
          <button key={p.label} className="tab-btn" onClick={() => applyPreset(p)}>
            {p.label}
          </button>
        ))}
      </div>

      <div className="two-col">
        <div>
          <Slider label="Rain volume (24 h)" value={rain} min={0} max={400} step={5} unit=" mm" onChange={setRain} scale={['0', '100', '200', '300', '400 mm']} />
          <Slider label="Cloudburst intensity (peak 1 h)" value={burst} min={0} max={120} step={1} unit=" mm/h" onChange={setBurst} scale={['0', '30', '60', '90', '120 mm/h']} />
          <Slider label="Deep-soil saturation" value={sat} min={0} max={100} step={1} unit="%" onChange={setSat} scale={['driest', '', 'typical', '', 'saturated']} />
          <button className="run-btn" onClick={() => run()} disabled={loading}>
            {loading ? 'Running models…' : 'Run simulation'}
          </button>
          {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
        </div>

        <div>
          {!result && !loading && <p className="empty-hint">Pick a preset or set the sliders and run the simulation.</p>}
          {result && (
            <>
              {focus !== 'landslide' && (
              <>
              <div className="outcome-card-head" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Kathmandu rivers</h3>
                <StatusPill level={result.flood.risk_tier} />
              </div>
              <table className="data-table" style={{ marginBottom: 18 }}>
                <thead>
                  <tr>
                    <th>River</th>
                    <th>Discharge</th>
                    <th>% of P99</th>
                    <th>Tier</th>
                  </tr>
                </thead>
                <tbody>
                  {result.flood.rivers.map((r) => (
                    <tr key={r.river_id}>
                      <td>{r.river}</td>
                      <td>{r.discharge_m3s.toFixed(1)} m³/s</td>
                      <td>{r.pct_of_p99.toFixed(0)}%</td>
                      <td>
                        <StatusPill level={r.risk_tier} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </>
              )}

              {focus !== 'flood' && (
              <>
              <div className="outcome-card-head" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Mugling corridor</h3>
                <StatusPill level={slide.risk_tier} />
              </div>
              <div className="metric-row" style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
                <div className="metric">
                  <span className="metric-label">Failure probability</span>
                  <span className="metric-value">{(slide.failure_probability * 100).toFixed(1)}%</span>
                </div>
                <div className="metric">
                  <span className="metric-label">z-score</span>
                  <span className="metric-value">{slide.failure_z.toFixed(2)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Stability index</span>
                  <span className="metric-value">{slide.slope_stability_index.toFixed(2)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Wetness</span>
                  <span className="metric-value">{Math.round(slide.wetness * 100)}%</span>
                </div>
              </div>
              </>
              )}
            </>
          )}
        </div>
      </div>

      {result && (
        <details className="assumption-details">
          <summary>How is this simulated?</summary>
          <p style={{ marginTop: 8 }}>{result.assumption}</p>
        </details>
      )}
    </div>
  )
}
