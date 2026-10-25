import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useAdmin } from '../../context/AdminContext'

const EMPTY_FORM = {
  id: null,
  source: '',
  target: '',
  relation: 'increases_risk',
  mechanism: '',
  citation: '',
  data_connected: false,
}

export default function AdminKnowledgeGraphPanel() {
  const { email } = useAdmin()
  const [edges, setEdges] = useState(null)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  function load() {
    api
      .adminListKgEdges(email)
      .then((d) => setEdges(d.edges))
      .catch((err) => setError(err.message))
  }

  useEffect(load, [email])

  function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    api
      .adminUpsertKgEdge(email, form)
      .then(() => {
        setForm(EMPTY_FORM)
        load()
      })
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false))
  }

  function handleDelete(id) {
    api
      .adminDeleteKgEdge(email, id)
      .then(load)
      .catch((err) => setError(err.message))
  }

  function handleEdit(edge) {
    setForm(edge)
  }

  return (
    <div className="card">
      <h2>Knowledge graph edges</h2>
      <p className="scenario-desc">
        Add, edit, or remove indicator → outcome relationships. Changes apply immediately
        across the whole app — no restart needed.
      </p>

      {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}

      <form className="admin-form" onSubmit={handleSave}>
        <div className="admin-form-row">
          <input
            placeholder="source (e.g. heat)"
            value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
            required
          />
          <input
            placeholder="target (e.g. heatstroke)"
            value={form.target}
            onChange={(e) => setForm({ ...form, target: e.target.value })}
            required
          />
        </div>
        <input
          placeholder="relation (e.g. increases_risk)"
          value={form.relation}
          onChange={(e) => setForm({ ...form, relation: e.target.value })}
          required
        />
        <textarea
          placeholder="mechanism"
          value={form.mechanism}
          onChange={(e) => setForm({ ...form, mechanism: e.target.value })}
          required
        />
        <input
          placeholder="citation"
          value={form.citation}
          onChange={(e) => setForm({ ...form, citation: e.target.value })}
          required
        />
        <label className="admin-checkbox">
          <input
            type="checkbox"
            checked={form.data_connected}
            onChange={(e) => setForm({ ...form, data_connected: e.target.checked })}
          />
          Backed by a live data pipeline
        </label>
        <div className="admin-form-row">
          <button className="run-btn" type="submit" disabled={saving}>
            {form.id ? 'Update edge' : 'Add edge'}
          </button>
          {form.id && (
            <button type="button" className="admin-cancel-btn" onClick={() => setForm(EMPTY_FORM)}>
              Cancel edit
            </button>
          )}
        </div>
      </form>

      {edges && (
        <div className="kg-grid" style={{ marginTop: 20 }}>
          {edges.map((e) => (
            <div
              className="kg-card"
              key={e.id}
              style={{ '--kg-accent': e.data_connected ? 'var(--status-good)' : 'var(--text-muted)' }}
            >
              <div className="kg-card-head">
                <span className="path">
                  {e.source.replace(/_/g, ' ')} → {e.target.replace(/_/g, ' ')}
                </span>
                <span className={`connected ${e.data_connected ? 'yes' : 'no'}`}>
                  {e.data_connected ? 'live data' : 'schema only'}
                </span>
              </div>
              <div className="mechanism">{e.mechanism}</div>
              <div className="citation">{e.citation}</div>
              <div className="admin-form-row" style={{ marginTop: 10 }}>
                <button className="admin-edit-btn" onClick={() => handleEdit(e)}>
                  Edit
                </button>
                <button className="admin-delete-btn" onClick={() => handleDelete(e.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
