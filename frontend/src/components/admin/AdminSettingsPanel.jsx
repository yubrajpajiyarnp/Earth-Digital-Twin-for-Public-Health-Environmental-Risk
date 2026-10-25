import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useAdmin } from '../../context/AdminContext'

export default function AdminSettingsPanel() {
  const { email } = useAdmin()
  const [settings, setSettings] = useState(null)
  const [error, setError] = useState(null)
  const [key, setKey] = useState('')
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)

  function load() {
    api
      .adminListSettings(email)
      .then((d) => setSettings(d.settings))
      .catch((err) => setError(err.message))
  }

  useEffect(load, [email])

  function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    api
      .adminSetSetting(email, key.trim(), value)
      .then(() => {
        setKey('')
        setValue('')
        load()
      })
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false))
  }

  function handleDelete(k) {
    api
      .adminDeleteSetting(email, k)
      .then(load)
      .catch((err) => setError(err.message))
  }

  return (
    <div className="card">
      <h2>Config overrides</h2>
      <p className="scenario-desc">
        Override any config value normally set in .env — e.g.{' '}
        <code>weather_api_key</code>, <code>flood_api_key</code>,{' '}
        <code>landslide_api_key</code>, <code>accuweather_api_key</code>. Applies right
        away, no restart needed.
      </p>

      {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}

      <form className="admin-form" onSubmit={handleSave}>
        <div className="admin-form-row">
          <input placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} required />
          <input
            placeholder="value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          />
          <button className="run-btn" type="submit" disabled={saving}>
            Save
          </button>
        </div>
      </form>

      {settings && settings.length === 0 && (
        <p className="empty-hint">
          No overrides set — the app is using whatever's in backend/.env.
        </p>
      )}

      {settings && settings.length > 0 && (
        <div className="admin-table" style={{ marginTop: 12 }}>
          {settings.map((s) => (
            <div className="admin-table-row" key={s.key}>
              <span className="admin-table-cell">
                <strong>{s.key}</strong> = {s.value}
              </span>
              <button className="admin-delete-btn" onClick={() => handleDelete(s.key)}>
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
