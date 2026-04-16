import { useEffect, useMemo, useState } from 'react'
import { createApi } from '../services/api'
import { useLogger } from '../hooks/useLogger'
import { useAuth } from '../hooks/useAuth'
import Button from '../components/Button'
import Input from '../components/Input'
import Card from '../components/Card'
import JsonBlock from '../components/JsonBlock'
import Pill from '../components/Pill'
import FieldGrid from '../components/FieldGrid'

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

const fileStem = (filename) => (filename || '').replace(/\.[^.]+$/, '')

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
  const [diskFile, setDiskFile] = useState(null)

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

  useEffect(() => {
    if (!jobId || !migration) return undefined
    if (migration.status === 'completed' || migration.status === 'failed') return undefined

    const interval = setInterval(async () => {
      try {
        const data = await api.fetchJson(`/api/v1/migration/status/${jobId}`)
        setMigration(data)

        if (data.status === 'completed' || data.status === 'failed') {
          pushLog(`Job ${jobId} finished: ${data.status}`)
        }
      } catch (err) {
        const msg = err.message || 'Unknown error'
        setError(`Auto status refresh: ${msg}`)
        pushLog(`Auto status refresh failed: ${msg}`)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [api, jobId, migration, pushLog])

  const handleError = (action, err) => {
    const msg = err.message || 'Unknown error'
    setError(`${action}: ${msg}`)
    pushLog(`X ${action} failed: ${msg}`)
  }

  const onHealth = async () => {
    setError(null)
    setActionLoading('health', true)
    try {
      const data = await api.fetchJson('/health')
      setAnalysis(data)
      pushLog('Health OK')
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
      pushLog(`Discovered ${data.length} VMs (${discoverySource})`)
    } catch (err) {
      handleError('Discovery', err)
    } finally {
      setActionLoading('discover', false)
    }
  }

  const onAnalyze = async () => {
    if (!vmName) return pushLog('VM name required')
    setError(null)
    setActionLoading('analyze', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/analyze/${vmName}?source=${vmSource}`, {
        method: 'POST',
      })
      setAnalysis(data)
      pushLog(`Analysis done for ${vmName}`)
    } catch (err) {
      handleError('Analysis', err)
    } finally {
      setActionLoading('analyze', false)
    }
  }

  const onPlan = async () => {
    if (!vmName) return pushLog('VM name required')
    setError(null)
    setActionLoading('plan', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/plan/${vmName}?source=${vmSource}`, {
        method: 'POST',
      })
      setAnalysis(data)
      pushLog(`Plan generated for ${vmName}`)
    } catch (err) {
      handleError('Plan', err)
    } finally {
      setActionLoading('plan', false)
    }
  }

  const onStart = async () => {
    if (!vmName) return pushLog('VM name required')
    setError(null)
    setActionLoading('start', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/start/${vmName}?source=${vmSource}`, {
        method: 'POST',
      })
      setMigration(data)
      setJobId(data.job_id || '')
      pushLog(`Migration started for ${vmName} (job: ${data.job_id})`)
    } catch (err) {
      handleError('Start', err)
    } finally {
      setActionLoading('start', false)
    }
  }

  const onStatus = async () => {
    if (!jobId) return pushLog('Job ID required')
    setError(null)
    setActionLoading('status', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/status/${jobId}`)
      setMigration(data)
      pushLog(`Status: ${data.status} (${jobId})`)
    } catch (err) {
      handleError('Status', err)
    } finally {
      setActionLoading('status', false)
    }
  }

  const onReport = async () => {
    if (!jobId) return pushLog('Job ID required')
    setError(null)
    setActionLoading('report', true)
    try {
      const data = await api.fetchJson(`/api/v1/migration/report/${jobId}`)
      setMigration(data)
      pushLog(`Report fetched for ${jobId}`)
    } catch (err) {
      handleError('Report', err)
    } finally {
      setActionLoading('report', false)
    }
  }

  const onOpenShift = async () => {
    if (!vmName) return pushLog('VM name required (source label)')
    if (!targetVmName) return pushLog('Target VM name is required')
    if (!diskFile && !sourceDiskPath) {
      return pushLog('Select a local disk file or enter a bastion disk path')
    }

    setError(null)
    setActionLoading('openshift', true)
    try {
      let data

      if (diskFile) {
        const formData = new FormData()
        formData.append('disk_file', diskFile)
        formData.append('source_disk_format', sourceDiskFormat || 'vmdk')
        formData.append('target_vm_name', targetVmName)
        formData.append('pvc_size', pvcSize || '20Gi')
        formData.append('memory', memory || '2Gi')
        formData.append('cpu_cores', `${parseInt(cpuCores, 10) || 2}`)
        formData.append('firmware', firmware || 'bios')
        formData.append('namespace', namespace || 'vm-migration')

        data = await api.fetchJson(`/api/v1/migration/openshift-upload/${vmName}`, {
          method: 'POST',
          body: formData,
        })
      } else {
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

        data = await api.fetchJson(`/api/v1/migration/openshift/${vmName}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      }

      setOpenShiftResult(data)
      setJobId(data.job_id || '')
      setMigration(data.job_id ? { job_id: data.job_id, status: data.status } : null)
      pushLog(`OpenShift migration submitted for ${targetVmName}`)
    } catch (err) {
      handleError('OpenShift migration', err)
    } finally {
      setActionLoading('openshift', false)
    }
  }

  const btnLabel = (action) => {
    if (loading[action]) return 'Loading...'
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
          <strong>Error:</strong> {error}
          <button className="dismiss" onClick={() => setError(null)}>x</button>
        </div>
      )}

      <main className="grid">
        <Card
          title="Discovery"
          hint="Lists VMs visible from the backend host."
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
                  setTargetVmName((current) => current || vm.name)
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
          title="Analyze And Plan"
          actions={
            <>
              <Input
                placeholder="vm name (for example: devops)"
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
          hint="Upload a local disk from your browser or use a disk path that already exists on the bastion."
          actions={
            <Button onClick={onOpenShift} disabled={loading.openshift}>
              {btnLabel('openshift') || 'Migrate to OpenShift'}
            </Button>
          }
        >
          <FieldGrid>
            <Input
              type="file"
              accept=".vmdk,.qcow2,.img,.raw"
              onChange={(e) => {
                const file = e.target.files?.[0] || null
                setDiskFile(file)

                if (!file) return

                const inferredName = fileStem(file.name)
                const inferredFormat = file.name.split('.').pop()?.toLowerCase() || 'vmdk'

                setVmName((current) => current || inferredName)
                setTargetVmName((current) => current || inferredName)
                setSourceDiskFormat(inferredFormat)
              }}
            />
            <Input
              placeholder="/path/on/bastion/source.vmdk"
              value={sourceDiskPath}
              onChange={(e) => setSourceDiskPath(e.target.value)}
            />
            <Input placeholder="vmdk" value={sourceDiskFormat} onChange={(e) => setSourceDiskFormat(e.target.value)} />
            <Input placeholder="target vm name" value={targetVmName} onChange={(e) => setTargetVmName(e.target.value)} />
            <Input placeholder="20Gi" value={pvcSize} onChange={(e) => setPvcSize(e.target.value)} />
            <Input placeholder="2Gi" value={memory} onChange={(e) => setMemory(e.target.value)} />
            <Input type="number" placeholder="2" value={cpuCores} onChange={(e) => setCpuCores(e.target.value)} />
            <Input placeholder="bios" value={firmware} onChange={(e) => setFirmware(e.target.value)} />
            <Input placeholder="vm-migration" value={namespace} onChange={(e) => setNamespace(e.target.value)} />
          </FieldGrid>
          {diskFile ? (
            <p className="hint">
              Local file selected: <strong>{diskFile.name}</strong> ({formatBytes(diskFile.size)})
            </p>
          ) : (
            <p className="hint">
              No local file selected. The migration will use the bastion disk path field if you submit now.
            </p>
          )}
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
