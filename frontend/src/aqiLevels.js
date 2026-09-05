// Turns the NO2 proxy's raw scientific-notation value into a simple word, using the same
// baseline z-score the backend already computes (risk.baseline_mean / risk.baseline_std) —
// no new data, no fabricated absolute AQI thresholds, just a friendlier read of the same
// relative-to-this-location comparison used elsewhere in the app.
export const AQI_LEVELS = [
  { key: 'good', label: 'Good', color: 'var(--status-good)', maxZ: -1 },
  { key: 'moderate', label: 'Moderate', color: 'var(--text-secondary)', maxZ: 1 },
  { key: 'bad', label: 'Bad', color: 'var(--status-warning)', maxZ: 2 },
  { key: 'worst', label: 'Worst', color: 'var(--status-critical)', maxZ: Infinity },
]

export function zScore(value, baselineMean, baselineStd) {
  if (value == null || baselineMean == null || !baselineStd) return null
  return (value - baselineMean) / baselineStd
}

export function classifyAqiLevel(z) {
  if (z == null || Number.isNaN(z)) return null
  return AQI_LEVELS.find((level) => z <= level.maxZ) || AQI_LEVELS[AQI_LEVELS.length - 1]
}

// Converts the z-score tier boundaries into actual mol/m² cutoffs for this location's
// current baseline, so the legend shows real numbers rather than abstract std-dev multiples.
export function aqiLevelBoundaries(baselineMean, baselineStd) {
  if (baselineMean == null || !baselineStd) return []
  const cutoff = (z) => baselineMean + z * baselineStd
  return AQI_LEVELS.map((level, i) => {
    const prevMaxZ = i === 0 ? -Infinity : AQI_LEVELS[i - 1].maxZ
    const lowText = prevMaxZ === -Infinity ? null : cutoff(prevMaxZ).toExponential(2)
    const highText = level.maxZ === Infinity ? null : cutoff(level.maxZ).toExponential(2)
    let rangeText
    if (lowText == null) rangeText = `below ${highText} mol/m²`
    else if (highText == null) rangeText = `above ${lowText} mol/m²`
    else rangeText = `${lowText} – ${highText} mol/m²`
    return { ...level, rangeText }
  })
}
