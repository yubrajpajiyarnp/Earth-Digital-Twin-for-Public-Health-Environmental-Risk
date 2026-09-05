import { vegetationLevelBoundaries } from '../vegetationLevels'

// Reference key for the Good/Mid/Bad labels shown on the NDVI stat tiles. The cutoffs are
// computed live from this location's own current baseline (mean ± std-dev multiples), not
// a universal "healthy NDVI" threshold — there isn't one that means anything without
// knowing the specific land-cover type being observed.
export default function VegetationScaleLegend({ baselineMean, baselineStd }) {
  const rows = vegetationLevelBoundaries(baselineMean, baselineStd)
  if (!rows.length) return null

  return (
    <div className="card risk-scale">
      <h3>NDVI level scale</h3>
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
        Boundaries are set from this location's own recent NDVI readings, not a fixed global
        vegetation-health scale.
      </p>
    </div>
  )
}
