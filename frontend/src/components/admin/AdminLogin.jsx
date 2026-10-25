import { useState } from 'react'
import { useAdmin } from '../../context/AdminContext'

export default function AdminLogin() {
  const { email, verified, checking, login, logout } = useAdmin()
  const [input, setInput] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    login(input.trim())
      .then(() => setInput(''))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  if (checking) return null

  if (verified && email) {
    return (
      <div className="admin-badge" title={email}>
        <span className="admin-badge-dot" />
        Admin
        <button type="button" className="admin-logout" onClick={logout}>
          log out
        </button>
      </div>
    )
  }

  return (
    <form className="admin-login" onSubmit={handleSubmit}>
      <input
        type="email"
        placeholder="admin email"
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />
      <button type="submit" disabled={loading || !input}>
        {loading ? '…' : 'Admin'}
      </button>
      {error && <span className="admin-login-error">{error}</span>}
    </form>
  )
}
