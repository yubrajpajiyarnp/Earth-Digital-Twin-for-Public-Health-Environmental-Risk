// Turns raw NDVI values into a simple word, using the same baseline z-score the backend
// already computes (risk.baseline_mean / risk.baseline_std) — no new data, just a
// friendlier read of the same relative-to-this-location comparison used elsewhere.
// Unlike NO2, higher NDVI is BETTER (more/healthier vegetation), so "good" sits at the
// high end of the z-score, not the low end.
export const VEGETATION_LEVELS = [
  { key: 'bad', label: 'Bad', color: 'var(--status-critical)' },
  { key: 'mid', label: 'Mid', color: 'var(--text-secondary)' },
  { key: 'good', label: 'Good', color: 'var(--status-good)' },
]

export function zScore(value, baselineMean, baselineStd) {
  if (value == null || baselineMean == null || !baselineStd) return null
  return (value - baselineMean) / baselineStd
}

export function classifyVegetationLevel(z) {
  if (z == null || Number.isNaN(z)) return null
  if (z >= 1) return VEGETATION_LEVELS[2]
  if (z <= -1) return VEGETATION_LEVELS[0]
  return VEGETATION_LEVELS[1]
}

// Converts the z-score tier boundaries into actual NDVI cutoffs for this location's
// current baseline, so the legend shows real numbers rather than abstract std-dev multiples.
export function vegetationLevelBoundaries(baselineMean, baselineStd) {
  if (baselineMean == null || !baselineStd) return []
  const cutoff = (z) => (baselineMean + z * baselineStd).toFixed(3)
  const badMax = cutoff(-1)
  const goodMin = cutoff(1)
  return [
    { ...VEGETATION_LEVELS[0], rangeText: `below ${badMax}` },
    { ...VEGETATION_LEVELS[1], rangeText: `${badMax} – ${goodMin}` },
    { ...VEGETATION_LEVELS[2], rangeText: `above ${goodMin}` },
  ]
}
