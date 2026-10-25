import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api/client'

const AdminContext = createContext(null)

function readStoredEmail() {
  try {
    return localStorage.getItem('adminEmail')
  } catch {
    return null
  }
}

export function AdminProvider({ children }) {
  const [email, setEmail] = useState(readStoredEmail)
  const [verified, setVerified] = useState(false)
  const [checking, setChecking] = useState(Boolean(readStoredEmail()))

  useEffect(() => {
    if (!email) {
      setChecking(false)
      return
    }
    setChecking(true)
    api
      .adminWhoami(email)
      .then(() => setVerified(true))
      .catch(() => {
        setVerified(false)
        try {
          localStorage.removeItem('adminEmail')
        } catch {
          /* ignore */
        }
        setEmail(null)
      })
      .finally(() => setChecking(false))
  }, [email])

  async function login(inputEmail) {
    await api.adminWhoami(inputEmail) // throws if not recognized
    try {
      localStorage.setItem('adminEmail', inputEmail)
    } catch {
      /* ignore */
    }
    setEmail(inputEmail)
    setVerified(true)
  }

  function logout() {
    try {
      localStorage.removeItem('adminEmail')
    } catch {
      /* ignore */
    }
    setEmail(null)
    setVerified(false)
  }

  return (
    <AdminContext.Provider value={{ email, verified, checking, login, logout }}>
      {children}
    </AdminContext.Provider>
  )
}

export function useAdmin() {
  return useContext(AdminContext)
}
