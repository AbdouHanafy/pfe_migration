import { useEffect, useMemo, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'
import { createApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

const steps = ['Upload', 'Convert', 'Import', 'Deploy']

const stepStateFromProgress = (progress) => {
  const completed = Math.floor(progress / 25)
  return steps.map((step, index) => {
    if (index < completed) return { step, state: 'Done' }
    if (index === completed) return { step, state: 'Running' }
    return { step, state: 'Pending' }
  })
}

const MigrationProgressPage = () => {
  const { token } = useAuth()
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
  const [jobId, setJobId] = useState('')
  const [migration, setMigration] = useState(null)
  const [error, setError] = useState('')
  const [liveLogs, setLiveLogs] = useState([])
  const [cancelled, setCancelled] = useState(false)

  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])

  useEffect(() => {
    if (!jobId || cancelled) return undefined
    const tick = setInterval(async () => {
      try {
        const data = await api.fetchJson(`/api/v1/migration/status/${jobId}`)
        setMigration(data)
        setError('')
      } catch (err) {
        setError(err.message || 'Failed to fetch status')
      }
    }, 2500)
    return () => clearInterval(tick)
  }, [api, jobId, cancelled])

  useEffect(() => {
    if (!jobId || cancelled) return undefined
    const logTicker = setInterval(() => {
      setLiveLogs((prev) => {
        const time = new Date().toLocaleTimeString()
        const next = `${time} [INFO] Processing ${jobId}...`
        return [...prev.slice(-11), next]
      })
    }, 2200)
    return () => clearInterval(logTicker)
  }, [jobId, cancelled])

  const progress = migration?.progress ?? (cancelled ? 0 : 35)
  const eta = cancelled ? 'Cancelled' : `${Math.max(2, Math.ceil((100 - progress) / 8))} min`
  const timeline = stepStateFromProgress(progress)

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>Migration Progress</h1>
          <p>Track each pipeline step with live log updates and estimated completion time.</p>
        </div>
      </header>

      <section className="grid">
        <Card
          title="Real-Time Job Tracker"
          actions={(
            <>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://localhost:8000" />
              <Input value={jobId} onChange={(e) => setJobId(e.target.value)} placeholder="job id" />
              <Button variant="ghost" onClick={() => setCancelled(true)} disabled={!jobId || cancelled}>Cancel</Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <div className="progress-track large">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="row-between">
            <p className="micro">Current Status: {cancelled ? 'Cancelled' : (migration?.status || 'In progress')}</p>
            <p className="micro">ETA: {eta}</p>
          </div>
        </Card>

        <Card title="Step Timeline">
          <div className="timeline">
            {timeline.map((item) => (
              <div key={item.step} className="timeline-row">
                <span>{item.step}</span>
                <span className={`pill pill-${item.state.toLowerCase()}`}>{item.state}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="wide" title="Live Logs (WebSocket-ready view)" hint="Hook this panel to your backend WebSocket stream when available.">
          <div className="log">
            {liveLogs.length === 0 ? <div>Waiting for logs...</div> : null}
            {liveLogs.map((line) => <div key={line}>{line}</div>)}
          </div>
        </Card>
      </section>
    </div>
  )
}

export default MigrationProgressPage
