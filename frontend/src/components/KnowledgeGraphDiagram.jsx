const NODE_W = 168
const NODE_H = 40
const ROW_H = 60
const TOP_PAD = 24
const LEFT_X = 20
const RIGHT_X = 480

function columnPositions(count, totalHeight) {
  const contentHeight = Math.max(0, (count - 1) * ROW_H)
  const startY = (totalHeight - contentHeight) / 2
  return Array.from({ length: count }, (_, i) => startY + i * ROW_H)
}

function label(id) {
  return id.replace(/_/g, ' ')
}

// Bipartite indicator -> outcome network: nodes with no incoming edge are laid out on the
// left (environmental indicators), everything else on the right (health/environmental
// outcomes). Edge color/dash encodes whether that relationship is backed by a live data
// pipeline or is still a schema placeholder — the one distinction this diagram exists to
// make legible at a glance (the mechanism/citation text for each edge stays as prose below,
// where sentences belong).
export default function KnowledgeGraphDiagram({ nodes, edges }) {
  const sourceIds = new Set(edges.map((e) => e.source))
  const targetIds = new Set(edges.map((e) => e.target))
  const leftNodes = nodes.filter((n) => sourceIds.has(n) && !targetIds.has(n))
  const rightNodes = nodes.filter((n) => targetIds.has(n))

  const height = Math.max(leftNodes.length, rightNodes.length) * ROW_H + TOP_PAD * 2
  const width = RIGHT_X + NODE_W + 20

  const leftY = columnPositions(leftNodes.length, height)
  const rightY = columnPositions(rightNodes.length, height)

  const leftPos = Object.fromEntries(leftNodes.map((n, i) => [n, leftY[i]]))
  const rightPos = Object.fromEntries(rightNodes.map((n, i) => [n, rightY[i]]))

  return (
    <figure style={{ margin: 0 }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label="Diagram of environmental indicators linked to health and environmental outcomes, colored by whether each link is backed by live data or is still a schema placeholder"
      >
        <defs>
          <marker id="kg-arrow-live" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <polygon points="0,0 8,4 0,8" fill="var(--series-1)" />
          </marker>
          <marker id="kg-arrow-pending" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <polygon points="0,0 8,4 0,8" fill="var(--text-muted)" />
          </marker>
        </defs>

        {edges.map((e) => {
          const y1 = leftPos[e.source]
          const y2 = rightPos[e.target]
          if (y1 === undefined || y2 === undefined) return null
          const x1 = LEFT_X + NODE_W
          const x2 = RIGHT_X
          const c = (x2 - x1) / 2
          const live = e.data_connected
          return (
            <path
              key={`${e.source}-${e.target}`}
              d={`M ${x1} ${y1} C ${x1 + c} ${y1}, ${x2 - c} ${y2}, ${x2} ${y2}`}
              fill="none"
              stroke={live ? 'var(--series-1)' : 'var(--text-muted)'}
              strokeWidth={live ? 2 : 1.5}
              strokeDasharray={live ? undefined : '4 4'}
              opacity={live ? 0.9 : 0.55}
              markerEnd={`url(#${live ? 'kg-arrow-live' : 'kg-arrow-pending'})`}
            >
              <title>
                {label(e.source)} → {label(e.target)}: {e.mechanism}
              </title>
            </path>
          )
        })}

        {leftNodes.map((n) => (
          <g key={n} transform={`translate(${LEFT_X}, ${leftPos[n] - NODE_H / 2})`}>
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={8}
              fill="var(--surface-2)"
              stroke="var(--border)"
            />
            <text
              x={NODE_W / 2}
              y={NODE_H / 2 + 4}
              textAnchor="middle"
              fontSize="11.5"
              fontWeight="600"
              fill="var(--text-primary)"
              style={{ textTransform: 'capitalize' }}
            >
              {label(n)}
            </text>
          </g>
        ))}

        {rightNodes.map((n) => (
          <g key={n} transform={`translate(${RIGHT_X}, ${rightPos[n] - NODE_H / 2})`}>
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={8}
              fill="var(--surface-2)"
              stroke="var(--border)"
            />
            <text
              x={NODE_W / 2}
              y={NODE_H / 2 + 4}
              textAnchor="middle"
              fontSize="11.5"
              fontWeight="600"
              fill="var(--text-primary)"
              style={{ textTransform: 'capitalize' }}
            >
              {label(n)}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="caption" style={{ marginTop: 12 }}>
        Environmental indicators (left) linked to health and environmental outcomes (right).{' '}
        <span style={{ color: 'var(--series-1)', fontWeight: 600 }}>Solid blue</span> = live
        data; <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>
        dashed gray</span> = not tracked yet. Hover an arrow to see how it works.
      </figcaption>
    </figure>
  )
}
