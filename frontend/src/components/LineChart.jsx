import { useMemo, useState } from 'react'

const WIDTH = 600
const HEIGHT = 240
const PAD = { top: 16, right: 16, bottom: 28, left: 64 }
const GRID_ROWS = 4

// Single-series line chart with gridlines, y-axis value labels, soft-fill area, and a
// hover crosshair+tooltip. Plain SVG, no charting library — points are laid out ordinally
// (evenly spaced) rather than by true date distance, which is the right tradeoff for the
// small embedded charts here (NDVI in particular has irregular gaps from cloud cover;
// ordinal spacing keeps the line legible instead of bunching points at one end).
export default function LineChart({ points, color, formatValue, formatLabel }) {
  const [hoverIdx, setHoverIdx] = useState(null)

  const { linePath, areaPath, xFor, yFor, gridValues } = useMemo(() => {
    if (!points || points.length === 0) {
      return { linePath: '', areaPath: '', xFor: () => 0, yFor: () => 0, gridValues: [] }
    }
    const values = points.map((p) => p.y)
    const rawMin = Math.min(...values)
    const rawMax = Math.max(...values)
    const span = rawMax - rawMin || Math.abs(rawMax) * 0.1 || 1
    const minY = rawMin - span * 0.15
    const maxY = rawMax + span * 0.15

    const plotW = WIDTH - PAD.left - PAD.right
    const plotH = HEIGHT - PAD.top - PAD.bottom

    const xFor = (i) =>
      points.length === 1 ? PAD.left + plotW / 2 : PAD.left + (i / (points.length - 1)) * plotW
    const yFor = (v) => PAD.top + plotH - ((v - minY) / (maxY - minY)) * plotH

    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xFor(i)} ${yFor(p.y)}`).join(' ')
    const areaPath =
      `M ${xFor(0)} ${yFor(points[0].y)} ` +
      points.map((p, i) => `L ${xFor(i)} ${yFor(p.y)}`).join(' ') +
      ` L ${xFor(points.length - 1)} ${PAD.top + plotH} L ${xFor(0)} ${PAD.top + plotH} Z`

    const gridValues = Array.from(
      { length: GRID_ROWS + 1 },
      (_, i) => minY + (i / GRID_ROWS) * (maxY - minY),
    )

    return { linePath, areaPath, xFor, yFor, gridValues }
  }, [points])

  if (!points || points.length === 0) {
    return <div className="empty">No data</div>
  }

  const gradientId = `area-gradient-${color.replace(/[^a-zA-Z0-9]/g, '')}`

  function handleMove(e) {
    const rect = e.currentTarget.getBoundingClientRect()
    const relX = ((e.clientX - rect.left) / rect.width) * WIDTH
    let closest = 0
    let closestDist = Infinity
    points.forEach((_, i) => {
      const d = Math.abs(xFor(i) - relX)
      if (d < closestDist) {
        closestDist = d
        closest = i
      }
    })
    setHoverIdx(closest)
  }

  const hover = hoverIdx !== null ? points[hoverIdx] : null
  const fmtVal = formatValue || ((v) => v)

  return (
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        height={HEIGHT}
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIdx(null)}
        role="img"
        aria-label="Line chart"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>

        {gridValues.map((v, i) => (
          <g key={i}>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={yFor(v)}
              y2={yFor(v)}
              stroke="var(--gridline)"
              strokeWidth="1"
            />
            <text x={PAD.left - 10} y={yFor(v) + 4} fontSize="11" fill="var(--text-muted)" textAnchor="end">
              {fmtVal(v)}
            </text>
          </g>
        ))}

        <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
        <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />

        {hover && (
          <>
            <line
              x1={xFor(hoverIdx)}
              x2={xFor(hoverIdx)}
              y1={PAD.top}
              y2={HEIGHT - PAD.bottom}
              stroke="var(--axis)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <circle cx={xFor(hoverIdx)} cy={yFor(hover.y)} r="5" fill="var(--surface-1)" stroke={color} strokeWidth="2.5" />
          </>
        )}

        <text x={PAD.left} y={HEIGHT - 8} fontSize="11.5" fill="var(--text-muted)">
          {formatLabel ? formatLabel(points[0].x) : points[0].x}
        </text>
        <text
          x={WIDTH - PAD.right}
          y={HEIGHT - 8}
          fontSize="11.5"
          fill="var(--text-muted)"
          textAnchor="end"
        >
          {formatLabel ? formatLabel(points[points.length - 1].x) : points[points.length - 1].x}
        </text>
      </svg>
      {hover && (
        <div
          style={{
            position: 'absolute',
            left: `${(xFor(hoverIdx) / WIDTH) * 100}%`,
            top: 4,
            transform: `translateX(${hoverIdx > points.length / 2 ? '-105%' : '5%'})`,
            background: 'var(--surface-1)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-md)',
            borderRadius: 8,
            padding: '6px 10px',
            fontSize: 12.5,
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
          }}
        >
          <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>
            {formatLabel ? formatLabel(hover.x) : hover.x}
          </div>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{fmtVal(hover.y)}</div>
        </div>
      )}
    </div>
  )
}
