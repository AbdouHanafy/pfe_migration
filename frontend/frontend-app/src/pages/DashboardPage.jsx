import { useEffect, useMemo, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'
import { createApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

const formatSigned = (value) => {
  const num = Number(value || 0)
  if (num > 0) return `+${num}`
  return `${num}`
}

const DashboardPage = () => {
  const { token } = useAuth()
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000')
  const [health, setHealth] = useState(null)
  const [overview, setOverview] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])

  const onRefresh = async () => {
    setError('')
    setLoading(true)
    try {
      const [healthData, overviewData] = await Promise.all([
        api.fetchJson('/health'),
        api.fetchJson('/api/v1/dashboard/overview'),
      ])
      setHealth(healthData)
      setOverview(overviewData)
    } catch (err) {
      setError(err.message || 'Failed to refresh dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    onRefresh()
  }, [])

  const stats = overview?.stats || {}
  const activeMigrations = Array.isArray(overview?.active_migrations) ? overview.active_migrations : []
  const alerts = Array.isArray(overview?.alerts) ? overview.alerts : []

  const statCards = [
    {
      title: 'VMs Migrated',
      value: `${stats.vms_migrated_total ?? 0}`,
      delta: `${formatSigned(stats.vms_migrated_weekly_delta ?? 0)} weekly (last 7d: ${stats.vms_migrated_last_7d ?? 0})`,
    },
    {
      title: 'Success Rate',
      value: `${stats.success_rate_percent ?? 0}%`,
      delta: `${stats.failed_jobs ?? 0} failed / ${stats.running_jobs ?? 0} running`,
    },
    {
      title: 'Avg Migration Time',
      value: `${stats.avg_migration_time_minutes ?? 0}m`,
      delta: 'Computed from completed jobs timestamps',
    },
    {
      title: 'Active Operators',
      value: `${stats.active_operators_ok ?? 0}/${stats.active_operators_total ?? 0}`,
      delta: 'Backend tool availability',
    },
  ]

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Cluster health, migration pulse, and operational alerts in one place.</p>
        </div>
      </header>

      <section className="stats-grid">
        {statCards.map((stat) => (
          <Card key={stat.title} className="stat-card">
            <p className="stat-label">{stat.title}</p>
            <p className="stat-value">{stat.value}</p>
            <p className="stat-delta">{stat.delta}</p>
          </Card>
        ))}
      </section>

      <section className="grid">
        <Card
          title="Cluster Health Overview"
          hint="Backend health and tool checks from live API."
          actions={(
            <>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} />
              <Button onClick={onRefresh} disabled={loading}>
                {loading ? 'Refreshing...' : 'Refresh'}
              </Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <pre className="code">{health ? JSON.stringify(health, null, 2) : 'No health data yet.'}</pre>
        </Card>

        <Card title="Active Migrations" hint="Real-time jobs currently in progress.">
          <div className="list">
            {activeMigrations.length === 0 ? <p className="micro">No active migrations right now.</p> : null}
            {activeMigrations.map((job) => (
              <div key={job.job_id} className="item item-stack">
                <div className="row-between">
                  <strong>{job.vm_name}</strong>
                  <span className="pill">{job.status}</span>
                </div>
                <p className="micro">{job.job_id}</p>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, Number(job.progress || 0)))}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="wide" title="Alerts And Warnings" hint="Generated from backend health checks and failed jobs.">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Level</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 ? (
                  <tr>
                    <td>info</td>
                    <td>No active alerts from backend.</td>
                  </tr>
                ) : null}
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>{alert.level}</td>
                    <td>{alert.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>
    </div>
  )
}

export default DashboardPage
