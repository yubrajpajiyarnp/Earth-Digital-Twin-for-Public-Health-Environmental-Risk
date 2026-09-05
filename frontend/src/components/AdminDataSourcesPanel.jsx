import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAdmin } from '../AdminContext'

const STATUS_STYLE = {
  live: { label: 'Live', color: 'var(--status-good)' },
  configured: { label: 'Configured', color: 'var(--status-good)' },
  'not configured': { label: 'Not configured', color: 'var(--status-warning)' },
  'not yet queried': { label: 'Not yet queried', color: 'var(--text-secondary)' },
  unreachable: { label: 'Unreachable', color: 'var(--status-critical)' },
}

export default function AdminDataSourcesPanel() {
  const { email } = useAdmin()
  const [sources, setSources] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  function load() {
    setLoading(true)
    setError(null)
    api
      .adminDataSources(email)
      .then((d) => setSources(d.sources))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [email])

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h2>Where data is pulled from</h2>
        <button className="run-btn" onClick={load} disabled={loading} style={{ padding: '6px 14px' }}>
          {loading ? 'Checking…' : 'Recheck'}
        </button>
      </div>
      <p className="scenario-desc">
        Every external source feeding this dashboard, and whether it's currently reachable
        or configured. Checked live each time this loads.
      </p>

      {error && <div className="error">{error}</div>}
      {!sources && !error && (
        <div className="loading">
          <span className="spinner" /> Checking sources…
        </div>
      )}

      {sources && (
        <div className="data-source-list">
          {sources.map((s) => {
            const style = STATUS_STYLE[s.status] || { label: s.status, color: 'var(--text-secondary)' }
            return (
              <div className="data-source-row" key={s.indicator}>
                <div className="data-source-row-head">
                  <span className="data-source-indicator">{s.indicator}</span>
                  <span className="data-source-status" style={{ color: style.color }}>
                    <span className="data-source-dot" style={{ background: style.color }} />
                    {style.label}
                  </span>
                </div>
                <div className="data-source-provider">{s.provider}</div>
                <div className="data-source-detail">{s.detail}</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
