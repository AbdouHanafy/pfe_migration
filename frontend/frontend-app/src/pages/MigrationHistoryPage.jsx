import { useMemo, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'

const seedHistory = [
  { id: 'mig-1001', vm: 'erp-vm', os: 'Ubuntu 22.04', date: '2026-04-22', duration: '27m', status: 'Success' },
  { id: 'mig-1002', vm: 'legacy-payroll', os: 'Windows Server 2016', date: '2026-04-21', duration: '41m', status: 'Failed' },
  { id: 'mig-1003', vm: 'analytics-node', os: 'RHEL 9', date: '2026-04-20', duration: '19m', status: 'Success' },
  { id: 'mig-1004', vm: 'ops-tools', os: 'Debian 12', date: '2026-04-19', duration: 'In progress', status: 'In Progress' },
]

const toCsv = (rows) => {
  const header = ['ID', 'VM', 'OS', 'Date', 'Duration', 'Status']
  const lines = rows.map((r) => [r.id, r.vm, r.os, r.date, r.duration, r.status].join(','))
  return [header.join(','), ...lines].join('\n')
}

const MigrationHistoryPage = () => {
  const [dateFilter, setDateFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [osFilter, setOsFilter] = useState('')

  const filteredRows = useMemo(() => seedHistory.filter((row) => {
    const passDate = !dateFilter || row.date === dateFilter
    const passStatus = statusFilter === 'All' || row.status === statusFilter
    const passOs = !osFilter || row.os.toLowerCase().includes(osFilter.toLowerCase())
    return passDate && passStatus && passOs
  }), [dateFilter, statusFilter, osFilter])

  const exportCsv = () => {
    const csv = toCsv(filteredRows)
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
          <p>Review completed jobs, inspect failures, and export execution reports.</p>
        </div>
      </header>

      <section className="grid">
        <Card
          className="wide"
          title="History Table"
          actions={(
            <>
              <Input type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} />
              <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option>All</option>
                <option>Success</option>
                <option>Failed</option>
                <option>In Progress</option>
              </select>
              <Input placeholder="Filter by OS" value={osFilter} onChange={(e) => setOsFilter(e.target.value)} />
              <Button variant="ghost" onClick={exportCsv}>Export CSV</Button>
              <Button onClick={() => window.print()}>Export PDF</Button>
            </>
          )}
        >
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>VM</th>
                  <th>OS</th>
                  <th>Date</th>
                  <th>Duration</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.vm}</td>
                    <td>{row.os}</td>
                    <td>{row.date}</td>
                    <td>{row.duration}</td>
                    <td>{row.status}</td>
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
