const ROWS = {
  all: [
    { level: 'severe', label: 'Severe', meaning: 'Beyond the 99th percentile / slope near failure' },
    { level: 'elevated', label: 'Elevated', meaning: 'Beyond the 90th percentile / z ≥ 1' },
    { level: 'typical', label: 'Typical', meaning: 'Within the normal range for this place' },
  ],
  flood: [
    { level: 'severe', label: 'Severe', meaning: 'Forecast peak above the river’s 99th-percentile flow' },
    { level: 'elevated', label: 'Elevated', meaning: 'Forecast peak above its 90th-percentile flow' },
    { level: 'typical', label: 'Typical', meaning: 'Within the river’s normal range' },
  ],
  landslide: [
    { level: 'severe', label: 'Severe', meaning: 'Failure z ≥ 2, or stability index below 1.0' },
    { level: 'elevated', label: 'Elevated', meaning: 'Failure z ≥ 1, or stability index below 1.3' },
    { level: 'typical', label: 'Typical', meaning: 'Normal for the corridor' },
  ],
}

// Reference key for the "typical / elevated / severe" pills. Flood tiers compare forecast
// discharge with each river's own 2011–present record; landslide tiers combine the model's
// failure z-score with the slope stability index — see CLAUDE.md.
export default function RiskScaleLegend({ hazard = 'all' }) {
  return (
    <div className="card risk-scale">
      <h3>Risk scale</h3>
      <table>
        <tbody>
          {ROWS[hazard].map((r) => (
            <tr key={r.level}>
              <td>
                <span className={`risk-dot risk-dot-${r.level}`} />
              </td>
              <td className="risk-scale-label">{r.label}</td>
              <td className="risk-scale-meaning">{r.meaning}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="risk-scale-note">
        Relative to each location's own 2011–present history — not an official warning level.
      </p>
    </div>
  )
}
