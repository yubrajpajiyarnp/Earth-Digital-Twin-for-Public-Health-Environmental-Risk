import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import StatusPill from '../ui/StatusPill'

export default function DashboardSummaryCard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  function load() {
    setLoading(true)
    setError(null)
    api
      .summary()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const paragraphs = data?.summary ? data.summary.split(/\n\s*\n/).filter(Boolean) : []

  return (
    <div className="card summary-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h2>AI summary &amp; outlook</h2>
        <button
          className="run-btn"
          onClick={load}
          disabled={loading}
          style={{ padding: '6px 14px' }}
        >
          {loading ? 'Thinking…' : data ? 'Refresh' : 'Generate'}
        </button>
      </div>
      <p className="scenario-desc">
        A Mistral-written synthesis of the Kathmandu flood and Mugling landslide outlooks for
        the next two weeks. Every number is computed by the local models — the language model
        only phrases them, it never invents figures.
      </p>

      {error && <div className="error">{error}</div>}

      {loading && !data && (
        <div className="loading">
          <span className="spinner" />
          Running both regional forecasts and writing the summary — this can take up to a
          minute.
        </div>
      )}

      {data && (
        <>
          <div className="summary-indicator-row">
            {data.indicators.map((i) => (
              <div className="summary-indicator" key={i.name}>
                <StatusPill level={i.risk_level} />
                <span className="summary-indicator-name">{i.name}</span>
                <span className="summary-indicator-pct">{i.headline}</span>
              </div>
            ))}
          </div>

          {data.unavailable.length > 0 && (
            <p className="empty-hint">Not available this run: {data.unavailable.join('; ')}</p>
          )}

          <div className="summary-text">
            {paragraphs.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
