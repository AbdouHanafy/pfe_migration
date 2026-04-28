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
  const [namespace, setNamespace] = useState('vm-migration')
  const [discoveredVms, setDiscoveredVms] = useState([])
  const [openshiftVms, setOpenshiftVms] = useState([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState({})
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

      setDiscoveredVms([
        ...kvm.map((vm) => normalizeSource(vm, 'kvm')),
        ...ws.map((vm) => normalizeSource(vm, 'vmware-workstation')),
        ...esxi.map((vm) => normalizeSource(vm, 'vmware-esxi')),
      ])

      const openshift = await api.fetchJson(`/api/v1/openshift/vms?namespace=${encodeURIComponent(namespace || 'vm-migration')}`).catch(() => ({ items: [] }))
      setOpenshiftVms(Array.isArray(openshift.items) ? openshift.items : [])
    } catch (err) {
      setError(err.message || 'Failed to discover VMs')
    } finally {
      setLoading(false)
    }
  }

  const controlVm = async (vmName, action) => {
    const actionKey = `${action}-${vmName}`
    setError('')
    setActionLoading((current) => ({ ...current, [actionKey]: true }))
    try {
      await api.fetchJson(`/api/v1/openshift/vms/${encodeURIComponent(vmName)}/${action}?namespace=${encodeURIComponent(namespace || 'vm-migration')}`, {
        method: 'POST',
      })
      await refresh()
    } catch (err) {
      setError(err.message || `Failed to ${action} VM`)
    } finally {
      setActionLoading((current) => ({ ...current, [actionKey]: false }))
    }
  }

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>VM Management</h1>
          <p>Source discovery plus OpenShift Virtualization VMs in your target namespace.</p>
        </div>
      </header>

      <section className="grid">
        <Card
          className="wide"
          title="OpenShift VMs"
          actions={(
            <>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://10.9.21.90:8000" />
              <Input value={namespace} onChange={(e) => setNamespace(e.target.value)} placeholder="vm-migration" />
              <Button onClick={refresh} disabled={loading}>
                {loading ? 'Refreshing...' : 'Refresh'}
              </Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <div className="list vm-list">
            {openshiftVms.length === 0 ? <p className="empty">No OpenShift VMs found in this namespace yet.</p> : null}
            {openshiftVms.map((vm) => (
              <div key={`openshift-${vm.namespace}-${vm.name}`} className="item item-stack">
                <div className="row-between">
                  <div>
                    <strong>{vm.name}</strong>
                    <p className="micro">{vm.namespace}</p>
                  </div>
                  <span className="pill">{vm.status || 'Unknown'}</span>
                </div>
                <div className="row">
                  <span className="micro">CPU: {vm.cpu_cores || 0}</span>
                  <span className="micro">RAM: {vm.memory || 'n/a'}</span>
                  <span className="micro">Disks: {vm.disks_count || 0}</span>
                </div>
                <div className="row-between">
                  <span className="micro">Ready: {vm.ready ? 'Yes' : 'No'}</span>
                </div>
                <div className="row">
                  {vm.console_url ? (
                    <Button
                      variant="ghost"
                      onClick={() => window.open(vm.console_url, '_blank', 'noopener,noreferrer')}
                    >
                      Console
                    </Button>
                  ) : null}
                  <Button
                    variant="ghost"
                    onClick={() => controlVm(vm.name, 'start')}
                    disabled={loading || actionLoading[`start-${vm.name}`] || vm.status === 'Running'}
                  >
                    {actionLoading[`start-${vm.name}`] ? 'Starting...' : 'Start'}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => controlVm(vm.name, 'stop')}
                    disabled={loading || actionLoading[`stop-${vm.name}`] || vm.status !== 'Running'}
                  >
                    {actionLoading[`stop-${vm.name}`] ? 'Stopping...' : 'Stop'}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card
          className="wide"
          title="Discovered VMs"
          actions={(
            <>
              <Button onClick={refresh} disabled={loading}>
                {loading ? 'Refreshing...' : 'Refresh'}
              </Button>
            </>
          )}
        >
          {error ? <p className="error">{error}</p> : null}
          <div className="list vm-list">
            {discoveredVms.length === 0 ? <p className="empty">No VMs discovered yet.</p> : null}
            {discoveredVms.map((vm) => (
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
