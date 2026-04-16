import { useMemo, useState } from 'react'
import { createApi } from '../services/api'
import { useLogger } from '../hooks/useLogger'
import { useAuth } from '../hooks/useAuth'
import Button from '../components/Button'
import Input from '../components/Input'
import Card from '../components/Card'
import JsonBlock from '../components/JsonBlock'
import Pill from '../components/Pill'
import FieldGrid from '../components/FieldGrid'

const HomePage = () => {
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE || 'http://localhost:8000')
  const [vms, setVms] = useState([])
  const [vmName, setVmName] = useState('')
  const [discoverySource, setDiscoverySource] = useState('kvm')
  const [vmSource, setVmSource] = useState('kvm')
  const [analysis, setAnalysis] = useState(null)
  const [migration, setMigration] = useState(null)
  const [jobId, setJobId] = useState('')
  const [openShiftResult, setOpenShiftResult] = useState(null)
  const [error, setError] = useState(null)

  // Loading states for each action
  const [loading, setLoading] = useState({
    health: false,
    discover: false,
    analyze: false,
    plan: false,
    start: false,
    status: false,
    report: false,
    openshift: false,
  })

  const [sourceDiskPath, setSourceDiskPath] = useState('')
  const [sourceDiskFormat, setSourceDiskFormat] = useState('vmdk')
  const [targetVmName, setTargetVmName] = useState('')
  const [pvcSize, setPvcSize] = useState('20Gi')
  const [memory, setMemory] = useState('2Gi')
  const [cpuCores, setCpuCores] = useState(2)
  const [firmware, setFirmware] = useState('bios')
  const [namespace, setNamespace] = useState('vm-migration')

  const { token } = useAuth()
  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])
  const { logs, pushLog } = useLogger()

  const setActionLoading = (key, value) => {
    setLoading((prev) => ({ ...prev, [key]: value }))
  }

  const handleError = (action, err) => {
    const msg = err.message || 'Unknown error'
    setError(`${action}: ${msg}`)
    pushLog(`❌ ${action} failed: ${msg}`)
  }

  const onHealth = async () => {
    setError(null)
    setActionLoading('health', true)
    try {
      const data = await api.fetchJson('/health')
      setAnalysis(data)
      pushLog('✅ Health OK')
    } catch (err) {
      handleError('Health', err)
    } finally {
      setActionLoading('health', false)
    }
  }

  const onDiscover = async () => {
    setError(null)
    setActionLoading('discover', true)
    try {
      const endpoint =
        discoverySource === 'vmware-workstation'
          ? '/api/v1/discovery/vmware-workstation'
          : '/api/v1/discovery/kvm'
      const data = await api.fetchJson(endpoint)
      setVms(data)
      setVmSource(discoverySource)
      pushLog(`✅ Discovered ${data.length} VMs (${discoverySource})`)
    } catch (err) {
      handleError('Discovery', err)
    } finally {
      setActionLoading('discover', false)
    }
  }

  const onAnalyze = async () => {
    if (!vmName) return pushLog('⚠️ VM name required')
    setError(null)
    setActionLoading('analyze', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/analyze/${vmName}?source=${vmSource}`, {
        method: 'POST',
      })
      setAnalysis(data)
      pushLog(`✅ Analysis done for ${vmName}`)
    } catch (err) {
      handleError('Analysis', err)
    } finally {
      setActionLoading('analyze', false)
    }
  }

  const onPlan = async () => {
    if (!vmName) return pushLog('⚠️ VM name required')
    setError(null)
    setActionLoading('plan', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/plan/${vmName}?source=${vmSource}`, {
        method: 'POST',
      })
      setAnalysis(data)
      pushLog(`✅ Plan generated for ${vmName}`)
    } catch (err) {
      handleError('Plan', err)
    } finally {
      setActionLoading('plan', false)
    }
  }

  const onStart = async () => {
    if (!vmName) return pushLog('⚠️ VM name required')
    setError(null)
    setActionLoading('start', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/start/${vmName}?source=${vmSource}`, {
        method: 'POST',
      })
      setMigration(data)
      setJobId(data.job_id || '')
      pushLog(`✅ Migration started for ${vmName} (job: ${data.job_id})`)
    } catch (err) {
      handleError('Start', err)
    } finally {
      setActionLoading('start', false)
    }
  }

  const onStatus = async () => {
    if (!jobId) return pushLog('⚠️ Job ID required')
    setError(null)
    setActionLoading('status', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/status/${jobId}`)
      setMigration(data)
      pushLog(`✅ Status: ${data.status} (${jobId})`)
    } catch (err) {
      handleError('Status', err)
    } finally {
      setActionLoading('status', false)
    }
  }

  const onReport = async () => {
    if (!jobId) return pushLog('⚠️ Job ID required')
    setError(null)
    setActionLoading('report', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/report/${jobId}`)
      setMigration(data)
      pushLog(`✅ Report fetched for ${jobId}`)
    } catch (err) {
      handleError('Report', err)
    } finally {
      setActionLoading('report', false)
    }
  }

  const onOpenShift = async () => {
    if (!vmName) return pushLog('⚠️ VM name required (source label)')
    if (!sourceDiskPath || !targetVmName) {
      return pushLog('⚠️ source_disk_path and target_vm_name are required')
    }

    const payload = {
      source_disk_path: sourceDiskPath,
      source_disk_format: sourceDiskFormat || 'vmdk',
      target_vm_name: targetVmName,
      pvc_size: pvcSize || '20Gi',
      memory: memory || '2Gi',
      cpu_cores: parseInt(cpuCores, 10) || 2,
      firmware: firmware || 'bios',
      namespace: namespace || 'vm-migration',
    }

    setError(null)
    setActionLoading('openshift', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/openshift/${vmName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      setOpenShiftResult(data)
      pushLog(`✅ OpenShift migration submitted for ${targetVmName}`)
    } catch (err) {
      handleError('OpenShift migration', err)
    } finally {
      setActionLoading('openshift', false)
    }
  }

  const btnLabel = (action) => {
    if (loading[action]) return '⏳ Loading...'
    return null
  }

  return (
    <div className="app">
      <div className="bg" />
      <header className="topbar">
        <div className="brand">
          <div className="logo">VM</div>
          <div className="title">
            <h1>Migration Control Room</h1>
            <p>Smart VM migration to OpenShift Virtualization</p>
          </div>
        </div>
        <div className="actions">
          <Input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
          />
          <Button variant="ghost" onClick={onHealth} disabled={loading.health}>
            {btnLabel('health') || 'Health'}
          </Button>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <strong>⚠️ Error:</strong> {error}
          <button className="dismiss" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <main className="grid">
        <Card
          title="Discovery"
          hint="List VMs from source hypervisor."
          actions={
            <>
              <select
                className="input"
                value={discoverySource}
                onChange={(e) => setDiscoverySource(e.target.value)}
              >
                <option value="kvm">KVM</option>
                <option value="vmware-workstation">VMware Workstation</option>
              </select>
              <Button onClick={onDiscover} disabled={loading.discover}>
                {btnLabel('discover') || 'Discover VMs'}
              </Button>
            </>
          }
        >
          <div className="list">
            {vms.length === 0 && <p className="empty">No VMs discovered yet.</p>}
            {vms.map((vm) => (
              <div
                key={vm.uuid || vm.name}
                className="item"
                onClick={() => {
                  setVmName(vm.name)
                  setVmSource(discoverySource)
                  pushLog(`Selected VM: ${vm.name}`)
                }}
              >
                <div className="name">{vm.name}</div>
                <Pill>{vm.state}</Pill>
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="Analyze & Plan"
          actions={
            <>
              <Input
                placeholder="vm name (e.g., devops)"
                value={vmName}
                onChange={(e) => setVmName(e.target.value)}
              />
              <Button onClick={onAnalyze} disabled={loading.analyze}>
                {btnLabel('analyze') || 'Analyze'}
              </Button>
              <Button variant="ghost" onClick={onPlan} disabled={loading.plan}>
                {btnLabel('plan') || 'Plan'}
              </Button>
            </>
          }
        >
          <JsonBlock data={analysis} />
        </Card>

        <Card
          title="Migration"
          actions={
            <>
              <Button onClick={onStart} disabled={loading.start}>
                {btnLabel('start') || 'Start (Simulated)'}
              </Button>
              <Input
                placeholder="job id"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
              />
              <Button variant="ghost" onClick={onStatus} disabled={loading.status}>
                {btnLabel('status') || 'Status'}
              </Button>
              <Button variant="ghost" onClick={onReport} disabled={loading.report}>
                {btnLabel('report') || 'Report'}
              </Button>
            </>
          }
        >
          <JsonBlock data={migration} />
        </Card>

        <Card
          className="wide"
          title="OpenShift Real Migration"
          hint="Uploads disk, creates VM, and starts it in OpenShift."
          actions={
            <Button onClick={onOpenShift} disabled={loading.openshift}>
              {btnLabel('openshift') || 'Migrate to OpenShift'}
            </Button>
          }
        >
          <FieldGrid>
            <Input placeholder="/path/to/source.vmdk" value={sourceDiskPath} onChange={(e) => setSourceDiskPath(e.target.value)} />
            <Input placeholder="vmdk" value={sourceDiskFormat} onChange={(e) => setSourceDiskFormat(e.target.value)} />
            <Input placeholder="target vm name" value={targetVmName} onChange={(e) => setTargetVmName(e.target.value)} />
            <Input placeholder="20Gi" value={pvcSize} onChange={(e) => setPvcSize(e.target.value)} />
            <Input placeholder="2Gi" value={memory} onChange={(e) => setMemory(e.target.value)} />
            <Input type="number" placeholder="2" value={cpuCores} onChange={(e) => setCpuCores(e.target.value)} />
            <Input placeholder="bios" value={firmware} onChange={(e) => setFirmware(e.target.value)} />
            <Input placeholder="vm-migration" value={namespace} onChange={(e) => setNamespace(e.target.value)} />
          </FieldGrid>
          <JsonBlock data={openShiftResult} />
        </Card>

        <Card className="wide" title="Activity Log">
          <div className="log">
            {logs.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        </Card>
      </main>
    </div>
  )
}

export default HomePage
