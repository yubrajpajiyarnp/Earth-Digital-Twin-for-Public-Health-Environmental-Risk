export default function StatTile({ label, value, caption, accent, valueColor }) {
  return (
    <div className="card stat-tile" style={accent ? { '--stat-accent': accent } : undefined}>
      <div className="label">{label}</div>
      <div className="value" style={valueColor ? { color: valueColor } : undefined}>
        {value}
      </div>
      {caption && <div className="caption">{caption}</div>}
    </div>
  )
}
