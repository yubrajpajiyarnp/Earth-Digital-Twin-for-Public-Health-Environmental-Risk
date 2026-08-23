import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAdmin } from '../AdminContext'
import TabBar from './TabBar'

const INDICATOR_TABS = [
  { id: 'no2', label: 'NO₂' },
  { id: 'ndvi', label: 'NDVI' },
  { id: 'rainfall', label: 'Rainfall' },
  { id: 'fauna', label: 'Fauna' },
]

const FETCHERS = {
  no2: api.historyNo2,
  ndvi: api.historyNdvi,
  rainfall: api.historyRainfall,
  fauna: api.historyFauna,
}

export default function AdminHistoryPanel() {
  const { email } = useAdmin()
  const [indicator, setIndicator] = useState('no2')
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  function load() {
    setLoading(true)
    setError(null)
    FETCHERS[indicator]()
      .then((d) => setRows(d.readings))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setRows(null)
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indicator])

  function handleDelete(id) {
    api
      .adminDeleteHistory(email, indicator, id)
      .then(load)
      .catch((err) => setError(err.message))
  }

  return (
    <div className="card">
      <h2>Stored history</h2>
      <p className="scenario-desc">
        Rows accumulate automatically every time the corresponding live panel is used
        elsewhere in the dashboard. Delete any bad or unwanted readings here.
      </p>
      <TabBar tabs={INDICATOR_TABS} activeId={indicator} onChange={setIndicator} />

      {loading && (
        <div className="loading">
          <span className="spinner" /> Loading…
        </div>
      )}
      {error && <div className="error">{error}</div>}

      {rows && rows.length === 0 && (
        <p className="empty-hint">
          No stored rows yet for this indicator — visit its live panel elsewhere in the
          dashboard to populate history.
        </p>
      )}

      {rows && rows.length > 0 && (
        <div className="admin-table">
          {rows
            .slice()
            .reverse()
            .map((r) => (
              <div className="admin-table-row" key={r.id}>
                <span className="admin-table-cell">
                  {indicator === 'fauna'
                    ? `${r.window_start} → ${r.window_end}: ${r.count} observations`
                    : `${r.date}: ${r.value}`}
                </span>
                <button className="admin-delete-btn" onClick={() => handleDelete(r.id)}>
                  Delete
                </button>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
