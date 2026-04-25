import { useContext } from 'react'
import { AuthContext } from '../store/auth-context.js'

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
