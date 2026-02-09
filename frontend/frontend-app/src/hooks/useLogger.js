import { useCallback, useState } from 'react'
import { nowIso } from '../utils/time'

export const useLogger = () => {
  const [logs, setLogs] = useState([])

  const pushLog = useCallback((msg) => {
    setLogs((prev) => [`[${nowIso()}] ${msg}`, ...prev].slice(0, 200))
  }, [])

  return { logs, pushLog }
}
