import { useMemo, useState } from 'react'

const WIDTH = 640
const PAD = { top: 16, right: 16, bottom: 28, left: 60 }
const GRID_ROWS = 4

// Multi-series line chart in plain SVG (no charting library). Series share an ordinal x
// axis (`labels`, usually ISO dates); `null` values break a line, so history and forecast
// can sit on one timeline. Options:
//   - normalize: scale each series to its own 0–1 range so drivers with different units can
//     be overlaid (the tooltip still shows raw values)
//   - thresholds: horizontal reference lines [{ value, label, color }]
//   - markers: x-indices to highlight with a vertical tick [{ index, label }] (incidents)
//   - splitIndex: draw a "today" divider before this x-index
export default function MultiLineChart({
  labels,
  series,
  normalize = false,
  thresholds = [],
  markers = [],
  splitIndex,
  height = 240,
  formatValue = (v) => v.toFixed(1),
  formatLabel = (l) => l,
}) {
  const [hoverIdx, setHoverIdx] = useState(null)
  const plotW = WIDTH - PAD.left - PAD.right
  const plotH = height - PAD.top - PAD.bottom

  const { scaled, yFor, gridValues } = useMemo(() => {
    const ranges = series.map((s) => {
      const vals = s.values.filter((v) => v != null && Number.isFinite(v))
      return vals.length ? [Math.min(...vals), Math.max(...vals)] : [0, 1]
    })
    const scaled = series.map((s, i) => {
      if (!normalize) return s.values
      const [lo, hi] = ranges[i]
      return s.values.map((v) => (v == null ? null : hi === lo ? 0.5 : (v - lo) / (hi - lo)))
    })
    let lo, hi
    if (normalize) {
      lo = 0
      hi = 1
    } else {
      const all = [...scaled.flat().filter((v) => v != null && Number.isFinite(v)), ...thresholds.map((t) => t.value)]
      lo = all.length ? Math.min(...all) : 0
      hi = all.length ? Math.max(...all) : 1
    }
    const span = hi - lo || Math.abs(hi) * 0.1 || 1
    const minY = normalize ? -0.05 : Math.min(lo - span * 0.08, lo >= 0 ? 0 : lo)
    const maxY = hi + span * 0.08
    const yFor = (v) => PAD.top + plotH - ((v - minY) / (maxY - minY)) * plotH
    const gridValues = Array.from({ length: GRID_ROWS + 1 }, (_, i) => minY + (i / GRID_ROWS) * (maxY - minY))
    return { scaled, yFor, gridValues }
  }, [series, normalize, thresholds, plotH])

  if (!labels?.length) return <div className="empty">No data</div>

  const xFor = (i) => (labels.length === 1 ? PAD.left + plotW / 2 : PAD.left + (i / (labels.length - 1)) * plotW)

  function pathFor(values) {
    let d = ''
    let pen = false
    values.forEach((v, i) => {
      if (v == null || !Number.isFinite(v)) {
        pen = false
        return
      }
      d += `${pen ? 'L' : 'M'} ${xFor(i).toFixed(1)} ${yFor(v).toFixed(1)} `
      pen = true
    })
    return d
  }

  function handleMove(e) {
    const rect = e.currentTarget.getBoundingClientRect()
    const relX = ((e.clientX - rect.left) / rect.width) * WIDTH
    const i = Math.round(((relX - PAD.left) / plotW) * (labels.length - 1))
    setHoverIdx(Math.min(Math.max(i, 0), labels.length - 1))
  }

  const markerAt = Object.fromEntries(markers.map((m) => [m.index, m.label]))

  return (
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        width="100%"
        height={height}
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIdx(null)}
        role="img"
        aria-label={`Line chart of ${series.map((s) => s.label).join(', ')}`}
      >
        {gridValues.map((v, i) => (
          <g key={i}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={yFor(v)} y2={yFor(v)} stroke="var(--gridline)" strokeWidth="1" />
            <text x={PAD.left - 8} y={yFor(v) + 4} fontSize="11" fill="var(--text-muted)" textAnchor="end">
              {normalize ? `${Math.round(v * 100)}%` : formatValue(v)}
            </text>
          </g>
        ))}

        {markers.map((m) => (
          <line
            key={`m-${m.index}`}
            x1={xFor(m.index)}
            x2={xFor(m.index)}
            y1={PAD.top}
            y2={height - PAD.bottom}
            stroke="var(--status-critical)"
            strokeWidth="1.5"
            opacity="0.35"
          />
        ))}

        {splitIndex != null && splitIndex > 0 && splitIndex < labels.length && (
          <g>
            <line
              x1={(xFor(splitIndex - 1) + xFor(splitIndex)) / 2}
              x2={(xFor(splitIndex - 1) + xFor(splitIndex)) / 2}
              y1={PAD.top}
              y2={height - PAD.bottom}
              stroke="var(--axis)"
              strokeWidth="1"
            />
            <text x={(xFor(splitIndex - 1) + xFor(splitIndex)) / 2 + 4} y={PAD.top + 10} fontSize="10.5" fill="var(--text-muted)">
              forecast →
            </text>
          </g>
        )}

        {!normalize &&
          thresholds.map((t) => (
            <g key={t.label}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={yFor(t.value)}
                y2={yFor(t.value)}
                stroke={t.color}
                strokeWidth="1"
                strokeDasharray="5 4"
              />
              <text x={WIDTH - PAD.right - 4} y={yFor(t.value) - 4} fontSize="10.5" fill={t.color} textAnchor="end">
                {t.label}
              </text>
            </g>
          ))}

        {series.map((s, i) => (
          <path
            key={s.id}
            d={pathFor(scaled[i])}
            fill="none"
            stroke={s.color}
            strokeWidth={s.width ?? 2}
            strokeDasharray={s.dashed ? '5 4' : undefined}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {hoverIdx != null && (
          <>
            <line
              x1={xFor(hoverIdx)}
              x2={xFor(hoverIdx)}
              y1={PAD.top}
              y2={height - PAD.bottom}
              stroke="var(--axis)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            {series.map((s, i) =>
              scaled[i][hoverIdx] == null ? null : (
                <circle key={s.id} cx={xFor(hoverIdx)} cy={yFor(scaled[i][hoverIdx])} r="4" fill="var(--surface-1)" stroke={s.color} strokeWidth="2" />
              ),
            )}
          </>
        )}

        <text x={PAD.left} y={height - 8} fontSize="11.5" fill="var(--text-muted)">
          {formatLabel(labels[0])}
        </text>
        <text x={WIDTH - PAD.right} y={height - 8} fontSize="11.5" fill="var(--text-muted)" textAnchor="end">
          {formatLabel(labels[labels.length - 1])}
        </text>
      </svg>

      {hoverIdx != null && (
        <div
          style={{
            position: 'absolute',
            left: `${(xFor(hoverIdx) / WIDTH) * 100}%`,
            top: 4,
            transform: `translateX(${hoverIdx > labels.length / 2 ? '-105%' : '5%'})`,
            background: 'var(--surface-1)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-md)',
            borderRadius: 8,
            padding: '6px 10px',
            fontSize: 12,
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
            zIndex: 2,
          }}
        >
          <div style={{ color: 'var(--text-muted)', marginBottom: 3 }}>{formatLabel(labels[hoverIdx])}</div>
          {series.map((s) =>
            s.values[hoverIdx] == null ? null : (
              <div key={s.id} style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
                <span style={{ color: s.color, fontWeight: 600 }}>{s.label}</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{(s.format || formatValue)(s.values[hoverIdx])}</span>
              </div>
            ),
          )}
          {markerAt[hoverIdx] && <div style={{ color: 'var(--status-critical)', fontWeight: 700, marginTop: 3 }}>{markerAt[hoverIdx]}</div>}
        </div>
      )}
    </div>
  )
}

export function ChartLegend({ items, onToggle, hidden = new Set() }) {
  return (
    <div className="chart-legend">
      {items.map((it) => (
        <span
          key={it.id}
          className={`chart-legend-item ${onToggle ? 'toggle' : ''} ${hidden.has(it.id) ? 'off' : ''}`}
          onClick={onToggle ? () => onToggle(it.id) : undefined}
          role={onToggle ? 'button' : undefined}
          style={{ color: it.color }}
        >
          <span className={`chart-legend-swatch ${it.dashed ? 'dashed' : ''}`} style={{ background: it.color }} />
          <span style={{ color: 'var(--text-secondary)' }}>{it.label}</span>
        </span>
      ))}
    </div>
  )
}
