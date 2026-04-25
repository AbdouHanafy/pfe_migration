import { useEffect, useMemo, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'
import { createApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

const doneStates = new Set(['completed', 'done', 'success', 'succeeded'])

const toneFromStatus = (status) => {
  const s = (status || '').toLowerCase()
  if (s.includes('fail') || s.includes('error')) return 'Failed'
  if (doneStates.has(s)) return 'Done'
  if (!s) return 'Pending'
  return 'Running'
}

const MigrationProgressPage = () => {
  const { token } = useAuth()
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000')
  const [jobId, setJobId] = useState('')
  const [jobs, setJobs] = useState([])
  const [statusData, setStatusData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])

  const refreshJobs = async () => {
    const data = await api.fetchJson('/api/v1/migration/jobs')
    setJobs(data || [])
    if (!jobId && data?.[0]?.job_id) setJobId(data[0].job_id)
  }

  const refreshStatus = async (id) => {
    if (!id) return
    const data = await api.fetchJson(`/api/v1/migration/status/${encodeURIComponent(id)}`)
    setStatusData(data)
  }

  const refreshAll = async () => {
    setError('')
    setLoading(true)
    try {
      await refreshJobs()
      await refreshStatus(jobId)
    } catch (err) {
      setError(err.message || 'Failed to refresh migration progress')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshAll()
  }, [])

  useEffect(() => {
    if (!jobId) return
    refreshStatus(jobId).catch((err) => setError(err.message || 'Failed to load status'))
    const timer = window.setInterval(() => {
      refreshStatus(jobId).catch(() => {})
    }, 3000)
    return () => window.clearInterval(timer)
  }, [jobId])

  const steps = Array.isArray(statusData?.steps) ? statusData.steps : []
  const completed = steps.filter((step) => doneStates.has((step.status || '').toLowerCase())).length
  const progress = steps.length ? Math.round((completed / steps.length) * 100) : 0

  const logs = Array.isArray(statusData?.logs) ? statusData.logs.slice(-20) : []

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>Migration Progress</h1>
          <p>Track live job steps and backend logs in real time.</p>
        </div>
      </header>

      <section className="grid">
        <Card
          title="Job Tracker"
          actions={(
            <>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://10.9.21.90:8000" />
              <select className="input" value={jobId} onChange={(e) => setJobId(e.target.value)}>
                <option value="">Select a job</option>
                {jobs.map((job) => (
                  <option key={job.job_id} value={job.job_id}>
                    {job.vm_name} - {job.job_id}
                  </option>
                ))}
              </select>
              <Button onClick={refreshAll} disabled={loading}>{loading ? 'Refreshing...' : 'Refresh'}</Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <div className="progress-track large">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="row-between">
            <p className="micro">Status: {statusData?.status || 'No job selected'}</p>
            <p className="micro">Progress: {progress}%</p>
          </div>
        </Card>

        <Card title="Step Timeline">
          <div className="timeline">
            {steps.length === 0 ? <div className="micro">No step data yet.</div> : null}
            {steps.map((item) => (
              <div key={item.name} className="timeline-row">
                <span>{item.name}</span>
                <span className={`pill pill-${toneFromStatus(item.status).toLowerCase()}`}>{toneFromStatus(item.status)}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="wide" title="Live Logs">
          <div className="log">
            {logs.length === 0 ? <div>Waiting for logs...</div> : null}
            {logs.map((line, idx) => {
              if (typeof line === 'string') return <div key={`${line}-${idx}`}>{line}</div>
              const ts = line?.timestamp ? new Date(line.timestamp).toLocaleTimeString() : '--:--:--'
              const level = (line?.level || 'info').toUpperCase()
              return <div key={`${ts}-${idx}`}>[{ts}] [{level}] {line?.message || ''}</div>
            })}
          </div>
        </Card>
      </section>
    </div>
  )
}

export default MigrationProgressPage
