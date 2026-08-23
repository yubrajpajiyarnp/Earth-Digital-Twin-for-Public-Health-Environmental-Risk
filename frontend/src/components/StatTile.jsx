export default function StatTile({ label, value, caption, accent }) {
  return (
    <div className="card stat-tile" style={accent ? { '--stat-accent': accent } : undefined}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {caption && <div className="caption">{caption}</div>}
    </div>
  )
}
