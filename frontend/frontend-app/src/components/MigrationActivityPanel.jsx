import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from './Button'
import { LOGS_CLEAR_EVENT } from '../hooks/useLogger'

const STATE_KEY = 'migration-control-room-state'
const LOGS_KEY = 'migration-control-room-logs'
const CLEAR_EVENT = 'migration-activity-cleared'
const PANEL_HIDDEN_KEY = 'migration-activity-panel-hidden'

const readJson = (key, fallback) => {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.sessionStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

const formatBytes = (value) => {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

const extractProgress = (state) => {
  if (state?.prepareProgress?.percent != null) return state.prepareProgress.percent
  const steps = Array.isArray(state?.migration?.steps) ? state.migration.steps : []
  if (!steps.length) return null
  const completed = steps.filter((step) => ['completed', 'done', 'success', 'succeeded'].includes((step.status || '').toLowerCase())).length
  return Math.round((completed / steps.length) * 100)
}

const MigrationActivityPanel = () => {
  const navigate = useNavigate()
  const [state, setState] = useState(() => readJson(STATE_KEY, null))
  const [logs, setLogs] = useState(() => readJson(LOGS_KEY, []))
  const [collapsed, setCollapsed] = useState(() => readJson(PANEL_HIDDEN_KEY, false))

  useEffect(() => {
    const refresh = () => {
      setState(readJson(STATE_KEY, null))
      setLogs(readJson(LOGS_KEY, []))
    }
    refresh()
    const timer = window.setInterval(refresh, 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      window.sessionStorage.setItem(PANEL_HIDDEN_KEY, JSON.stringify(collapsed))
    } catch {
      // Ignore persistence issues.
    }
  }, [collapsed])

  const hasContent = useMemo(() => {
    return Boolean(
      state?.vmName
      || state?.jobId
      || state?.prepareProgress
      || state?.openShiftResult
      || state?.migrationNotice
      || (Array.isArray(logs) && logs.length > 0)
    )
  }, [logs, state])

  if (!hasContent) return null

  const progress = extractProgress(state)
  const title = state?.targetVmName || state?.vmName || state?.openShiftResult?.target_vm_name || 'Migration activity'
  const latestLogs = Array.isArray(logs) ? logs.slice(0, 5) : []

  const clearState = () => {
    window.sessionStorage.removeItem(STATE_KEY)
    window.sessionStorage.removeItem(LOGS_KEY)
    window.dispatchEvent(new CustomEvent(CLEAR_EVENT))
    setState(null)
    setLogs([])
  }

  const clearOnlyLogs = () => {
    window.sessionStorage.removeItem(LOGS_KEY)
    window.dispatchEvent(new CustomEvent(LOGS_CLEAR_EVENT))
    setLogs([])
  }

  return (
    <aside className="migration-activity-panel">
      <div className="migration-activity-head">
        <div>
          <strong>{title}</strong>
          <div className="migration-activity-sub">
            {state?.jobId ? `Job ${state.jobId}` : 'Unsaved migration context'}
          </div>
        </div>
        <div className="migration-activity-head-actions">
          <Button
            variant="ghost"
            className="activity-icon-btn"
            onClick={() => setCollapsed((value) => !value)}
            title={collapsed ? 'Show panel' : 'Hide panel'}
          >
            {collapsed ? '[+]' : '[-]'}
          </Button>
          <Button
            variant="ghost"
            className="activity-icon-btn"
            onClick={clearOnlyLogs}
            title="Clear logs"
          >
            [x]
          </Button>
          <Button variant="ghost" className="activity-mini-btn" onClick={clearState}>Delete</Button>
        </div>
      </div>

      {collapsed ? null : (
        <>
      {progress != null ? (
        <>
          <div className="migration-activity-progress-head">
            <span>Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="upload-progress-bar" aria-hidden="true">
            <div className={`upload-progress-fill${state?.prepareProgress?.active ? ' active' : ''}`} style={{ width: `${progress}%` }} />
          </div>
        </>
      ) : null}

      {state?.prepareProgress ? (
        <div className="migration-activity-sub">
          {formatBytes(state.prepareProgress.uploadedBytes)} uploaded / {formatBytes(state.prepareProgress.totalBytes)}
        </div>
      ) : null}

      {state?.migrationNotice ? <div className="migration-activity-note">{state.migrationNotice}</div> : null}

      {latestLogs.length ? (
        <div className="migration-activity-log">
          {latestLogs.map((line, index) => (
            <div key={`${index}-${line}`}>{line}</div>
          ))}
        </div>
      ) : null}

      <div className="migration-activity-actions">
        <Button variant="ghost" className="activity-mini-btn" onClick={() => navigate('/migrations/new')}>Open</Button>
        <Button variant="ghost" className="activity-mini-btn" onClick={() => navigate('/migrations/progress')}>Progress</Button>
      </div>
        </>
      )}
    </aside>
  )
}

export default MigrationActivityPanel
