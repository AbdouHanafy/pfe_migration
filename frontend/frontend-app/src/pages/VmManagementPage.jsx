import { useMemo, useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'
import { createApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

const normalizeSource = (vm, source) => ({
  ...vm,
  source,
  cpu_count: vm.cpu_count || vm.specs?.cpus || 0,
  memory_mb: vm.memory_mb || vm.specs?.memory_mb || 0,
  disks_count: Array.isArray(vm.disks) ? vm.disks.length : 0,
})

const VmManagementPage = () => {
  const { token } = useAuth()
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000')
  const [vms, setVms] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])

  const refresh = async () => {
    setError('')
    setLoading(true)
    try {
      const [kvm, ws, esxi] = await Promise.all([
        api.fetchJson('/api/v1/discovery/kvm').catch(() => []),
        api.fetchJson('/api/v1/discovery/vmware-workstation').catch(() => []),
        api.fetchJson('/api/v1/discovery/vmware-esxi').catch(() => []),
      ])

      setVms([
        ...kvm.map((vm) => normalizeSource(vm, 'kvm')),
        ...ws.map((vm) => normalizeSource(vm, 'vmware-workstation')),
        ...esxi.map((vm) => normalizeSource(vm, 'vmware-esxi')),
      ])
    } catch (err) {
      setError(err.message || 'Failed to discover VMs')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>VM Management</h1>
          <p>Live discovery view across KVM, VMware Workstation, and VMware ESXi.</p>
        </div>
      </header>

      <section className="grid">
        <Card
          className="wide"
          title="Discovered VMs"
          actions={(
            <>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://10.9.21.90:8000" />
              <Button onClick={refresh} disabled={loading}>
                {loading ? 'Refreshing...' : 'Refresh'}
              </Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <div className="list vm-list">
            {vms.length === 0 ? <p className="empty">No VMs discovered yet.</p> : null}
            {vms.map((vm) => (
              <div key={`${vm.source}-${vm.uuid || vm.name}`} className="item item-stack">
                <div className="row-between">
                  <div>
                    <strong>{vm.name}</strong>
                    <p className="micro">{vm.source}</p>
                  </div>
                  <span className="pill">{vm.state || 'unknown'}</span>
                </div>
                <div className="row">
                  <span className="micro">CPU: {vm.cpu_count || 0}</span>
                  <span className="micro">RAM: {vm.memory_mb || 0} MB</span>
                  <span className="micro">Disks: {vm.disks_count || 0}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </div>
  )
}

export default VmManagementPage
