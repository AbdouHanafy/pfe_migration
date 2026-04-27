import { useCallback, useEffect, useState } from 'react'
import { nowIso } from '../utils/time'

export const useLogger = (storageKey = '') => {
  const [logs, setLogs] = useState(() => {
    if (!storageKey || typeof window === 'undefined') return []
    try {
      const raw = window.sessionStorage.getItem(storageKey)
      const parsed = raw ? JSON.parse(raw) : []
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  })

  const pushLog = useCallback((msg) => {
    setLogs((prev) => [`[${nowIso()}] ${msg}`, ...prev].slice(0, 200))
  }, [])

  const clearLogs = useCallback(() => {
    setLogs([])
  }, [])

  useEffect(() => {
    if (!storageKey || typeof window === 'undefined') return
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(logs))
    } catch {
      // Ignore persistence issues.
    }
  }, [logs, storageKey])

  return { logs, pushLog, clearLogs }
}
