import { useMemo, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'
import { createApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

const demoAlerts = [
  { id: 'a1', level: 'warning', message: 'Node worker-2 reports high disk pressure.' },
  { id: 'a2', level: 'info', message: 'CDI importer pod restarted successfully.' },
  { id: 'a3', level: 'critical', message: 'One migration job failed conversion step.' },
]

const demoMigrations = [
  { id: 'mig-1021', vm: 'finance-vm', status: 'Running', progress: 62 },
  { id: 'mig-1020', vm: 'legacy-crm', status: 'Running', progress: 28 },
]

const statCards = [
  { title: 'VMs Migrated', value: '147', delta: '+12 this week' },
  { title: 'Success Rate', value: '94.6%', delta: '+1.1% this month' },
  { title: 'Avg Migration Time', value: '23m', delta: '-4m vs last month' },
  { title: 'Active Operators', value: '6/7', delta: '1 operator degraded' },
]

const DashboardPage = () => {
  const { token } = useAuth()
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])

  const onRefreshHealth = async () => {
    setError('')
    setLoading(true)
    try {
      const data = await api.fetchJson('/health')
      setHealth(data)
    } catch (err) {
      setError(err.message || 'Failed to refresh cluster health')
    } finally {
      setLoading(false)
    }
  }

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
          hint="Use your API endpoint to pull backend and operator status."
          actions={(
            <>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} />
              <Button onClick={onRefreshHealth} disabled={loading}>
                {loading ? 'Refreshing...' : 'Refresh'}
              </Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <pre className="code">{JSON.stringify(health, null, 2) || 'No health data yet.'}</pre>
        </Card>

        <Card title="Active Migrations" hint="Real-time jobs currently in progress.">
          <div className="list">
            {demoMigrations.map((job) => (
              <div key={job.id} className="item item-stack">
                <div className="row-between">
                  <strong>{job.vm}</strong>
                  <span className="pill">{job.status}</span>
                </div>
                <p className="micro">{job.id}</p>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${job.progress}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="wide" title="Alerts And Warnings" hint="Prioritized events needing attention.">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Level</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {demoAlerts.map((alert) => (
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
