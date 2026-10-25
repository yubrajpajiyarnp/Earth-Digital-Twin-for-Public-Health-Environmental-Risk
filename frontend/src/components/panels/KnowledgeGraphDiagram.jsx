const NODE_W = 150
const NODE_H = 40
const ROW_H = 60
const TOP_PAD = 24
const COL_GAP = 70

function label(id) {
  return id.replace(/_/g, ' ')
}

// Longest-path layering: roots (no incoming edge) in column 0, every other node one column
// right of its deepest parent. Chains like rainfall → discharge → inundation read left to
// right; cycles (an admin could add one) are cut by capping depth at the node count.
function layerNodes(nodes, edges) {
  const depth = Object.fromEntries(nodes.map((n) => [n, 0]))
  for (let pass = 0; pass < nodes.length; pass++) {
    let changed = false
    for (const e of edges) {
      if (depth[e.target] < depth[e.source] + 1 && depth[e.source] + 1 < nodes.length) {
        depth[e.target] = depth[e.source] + 1
        changed = true
      }
    }
    if (!changed) break
  }
  const columns = []
  for (const n of nodes) {
    ;(columns[depth[n]] ||= []).push(n)
  }
  return columns.filter(Boolean)
}

// Layered driver -> outcome network. Edge color/dash encodes whether that relationship is
// backed by a live data pipeline or is still a schema placeholder — the one distinction this
// diagram exists to make legible at a glance (the mechanism/citation text for each edge
// stays as prose below, where sentences belong).
export default function KnowledgeGraphDiagram({ nodes, edges }) {
  const columns = layerNodes(nodes, edges)
  const height = Math.max(...columns.map((c) => c.length)) * ROW_H + TOP_PAD * 2
  const width = columns.length * NODE_W + (columns.length - 1) * COL_GAP + 40

  const pos = {}
  columns.forEach((col, ci) => {
    const startY = (height - (col.length - 1) * ROW_H) / 2
    col.forEach((n, ri) => {
      pos[n] = { x: 20 + ci * (NODE_W + COL_GAP), y: startY + ri * ROW_H }
    })
  })

  return (
    <figure style={{ margin: 0 }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label="Diagram of hydro-geological drivers linked to hazard and health outcomes, colored by whether each link is backed by live data or is still a schema placeholder"
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
          const a = pos[e.source]
          const b = pos[e.target]
          if (!a || !b) return null
          const x1 = a.x + NODE_W
          const x2 = b.x
          const c = Math.max((x2 - x1) / 2, 30)
          const live = e.data_connected
          return (
            <path
              key={`${e.source}-${e.target}`}
              d={`M ${x1} ${a.y} C ${x1 + c} ${a.y}, ${x2 - c} ${b.y}, ${x2} ${b.y}`}
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

        {nodes.map((n) => (
          <g key={n} transform={`translate(${pos[n].x}, ${pos[n].y - NODE_H / 2})`}>
            <rect width={NODE_W} height={NODE_H} rx={8} fill="var(--surface-2)" stroke="var(--border)" />
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
        Drivers (left) flow through intermediate hazards to outcomes (right).{' '}
        <span style={{ color: 'var(--series-1)', fontWeight: 600 }}>Solid blue</span> = live
        data; <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>
        dashed gray</span> = not tracked yet. Hover an arrow to see how it works.
      </figcaption>
    </figure>
  )
}
