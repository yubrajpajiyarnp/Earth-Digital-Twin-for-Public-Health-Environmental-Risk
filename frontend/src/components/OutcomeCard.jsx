import StatusPill from './StatusPill'

const ACCENT_BY_LEVEL = {
  elevated: 'var(--status-critical)',
  typical: 'var(--text-muted)',
  reduced: 'var(--status-good)',
}

export default function OutcomeCard({ outcome }) {
  return (
    <div
      className="outcome-card"
      style={{ '--outcome-accent': ACCENT_BY_LEVEL[outcome.risk_level] || 'var(--text-muted)' }}
    >
      <div className="outcome-card-head">
        <span className="name">{outcome.outcome.replace(/_/g, ' ')}</span>
        <StatusPill level={outcome.risk_level} />
      </div>
      <div className="mechanism">{outcome.explanation}</div>
      <div className="citation">{outcome.citation}</div>
    </div>
  )
}
