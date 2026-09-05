import { aqiLevelBoundaries } from '../aqiLevels'

// Reference key for the Good/Moderate/Bad/Worst labels shown on the AQI stat tiles. The
// mol/m² cutoffs are computed live from this location's own current baseline (mean ±
// std-dev multiples), not a universal WHO/EPA AQI scale — see RiskScaleLegend for why NO2
// column density can't be compared to an absolute threshold.
export default function AqiScaleLegend({ baselineMean, baselineStd }) {
  const rows = aqiLevelBoundaries(baselineMean, baselineStd)
  if (!rows.length) return null

  return (
    <div className="card risk-scale">
      <h3>NO₂ level scale</h3>
      <table>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td>
                <span className="risk-dot" style={{ background: r.color }} />
              </td>
              <td className="risk-scale-label">{r.label}</td>
              <td className="risk-scale-meaning">{r.rangeText}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="risk-scale-note">
        Boundaries are set from this location's own recent NO₂ readings, not a fixed global
        AQI scale.
      </p>
    </div>
  )
}
