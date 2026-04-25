import { useEffect, useMemo, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'
import { createApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

const formatDate = (value) => {
  if (!value) return '-'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString()
}

const csvEscape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`

const exportRowsToCsv = (rows) => {
  const header = ['Job ID', 'VM', 'Status', 'Created', 'Updated', 'Error']
  const lines = rows.map((row) => [
    row.job_id,
    row.vm_name,
    row.status,
    row.created_at,
    row.updated_at,
    row.error || '',
  ].map(csvEscape).join(','))
  return [header.map(csvEscape).join(','), ...lines].join('\n')
}

const MigrationHistoryPage = () => {
  const { token } = useAuth()
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])

  const refresh = async () => {
    setError('')
    setLoading(true)
    try {
      const data = await api.fetchJson('/api/v1/migration/jobs')
      setRows(data || [])
    } catch (err) {
      setError(err.message || 'Failed to load migration history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const filteredRows = useMemo(() => rows.filter((row) => {
    const query = search.trim().toLowerCase()
    const textOk = !query
      || (row.vm_name || '').toLowerCase().includes(query)
      || (row.job_id || '').toLowerCase().includes(query)
    const statusOk = statusFilter === 'All' || (row.status || '').toLowerCase() === statusFilter.toLowerCase()
    return textOk && statusOk
  }), [rows, search, statusFilter])

  const exportCsv = () => {
    const csv = exportRowsToCsv(filteredRows)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'migration-history.csv'
    link.click()
    URL.revokeObjectURL(link.href)
  }

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>Migration History</h1>
          <p>Review backend jobs and export historical reports.</p>
        </div>
      </header>

      <section className="grid">
        <Card
          className="wide"
          title="History Table"
          actions={(
            <>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://10.9.21.90:8000" />
              <Input placeholder="Filter by VM or Job ID" value={search} onChange={(e) => setSearch(e.target.value)} />
              <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option>All</option>
                <option>queued</option>
                <option>running</option>
                <option>completed</option>
                <option>failed</option>
              </select>
              <Button variant="ghost" onClick={exportCsv}>Export CSV</Button>
              <Button onClick={refresh} disabled={loading}>{loading ? 'Refreshing...' : 'Refresh'}</Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>VM</th>
                  <th>Job ID</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan="6">No jobs found.</td>
                  </tr>
                ) : null}
                {filteredRows.map((row) => (
                  <tr key={row.job_id}>
                    <td>{row.vm_name}</td>
                    <td>{row.job_id}</td>
                    <td>{row.status}</td>
                    <td>{formatDate(row.created_at)}</td>
                    <td>{formatDate(row.updated_at)}</td>
                    <td>{row.error || '-'}</td>
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

export default MigrationHistoryPage
