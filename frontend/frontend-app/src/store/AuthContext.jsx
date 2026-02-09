import { createContext, useMemo, useState } from 'react'

export const AuthContext = createContext(null)

const tokenKey = 'vm_migration_token'

export const AuthProvider = ({ children }) => {
  const [token, setTokenState] = useState(localStorage.getItem(tokenKey) || '')

  const setToken = (value) => {
    const next = value || ''
    setTokenState(next)
    if (next) {
      localStorage.setItem(tokenKey, next)
    } else {
      localStorage.removeItem(tokenKey)
    }
  }

  const value = useMemo(() => ({ token, setToken }), [token])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
