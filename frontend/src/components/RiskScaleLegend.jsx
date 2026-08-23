const ROWS = [
  { level: 'elevated', label: 'Elevated', meaning: 'Worse than usual for this location' },
  { level: 'typical', label: 'Typical', meaning: 'Within the normal range' },
  { level: 'reduced', label: 'Reduced', meaning: 'Better than usual for this location' },
]

// Reference key for the "elevated / typical / reduced" pills used throughout the
// dashboard. All risk levels here are relative to Vellore's own recent baseline
// (z-score), not an absolute pollution limit — see CLAUDE.md on why there's no
// calibrated AQI threshold to compare against.
export default function RiskScaleLegend() {
  return (
    <div className="card risk-scale">
      <h3>Risk scale</h3>
      <table>
        <tbody>
          {ROWS.map((r) => (
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
        Relative to this location's own recent history — not an absolute pollution limit.
      </p>
    </div>
  )
}
