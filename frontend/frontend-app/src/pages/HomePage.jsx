import { useEffect, useMemo, useRef, useState } from 'react'
import { createApi } from '../services/api'
import { useLogger } from '../hooks/useLogger'
import { useAuth } from '../hooks/useAuth'
import Button from '../components/Button'
import Input from '../components/Input'
import Card from '../components/Card'
import JsonBlock from '../components/JsonBlock'
import Pill from '../components/Pill'
import FieldGrid from '../components/FieldGrid'
import { analyzeLocalVmwareBundle } from '../utils/localVmware'

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

const inferVmwareBundle = (files) => {
  const normalizedFiles = Array.from(files || [])
  const vmxFile = normalizedFiles.find((file) => /\.vmx$/i.test(file.name))
  const descriptor = normalizedFiles.find((file) => /\.vmdk$/i.test(file.name) && !/-s\d+\.vmdk$/i.test(file.name))
  const splitExtents = normalizedFiles.filter((file) => /-s\d+\.vmdk$/i.test(file.name))
  const primaryFile = vmxFile || descriptor || normalizedFiles[0] || null
  const inferredName = primaryFile ? fileStem(primaryFile.name) : ''
  const inferredFormat = descriptor ? 'auto' : (primaryFile?.name.split('.').pop()?.toLowerCase() || 'auto')

  return {
    primaryFile,
    inferredName,
    inferredFormat,
    hasVmx: Boolean(vmxFile),
    splitExtentCount: splitExtents.length,
  }
}

const buildMigrationGate = (planData, vmName) => {
  if (!vmName) {
    return { ready: false, tone: 'neutral', message: 'Select or enter a VM name first.' }
  }

  if (!planData?.analysis || !planData?.conversion_plan || !planData?.strategy) {
    return { ready: false, tone: 'neutral', message: 'Run Plan first to validate the VM before real migration.' }
  }

  const compatibility = planData.analysis?.compatibility
  const strategy = planData.strategy?.strategy

  if (compatibility === 'non_compatible') {
    return { ready: false, tone: 'danger', message: 'Migration blocked: the VM is marked non compatible.' }
  }

  if (strategy === 'alternative') {
    return { ready: false, tone: 'warn', message: 'Migration blocked: IA recommends an alternative strategy instead of direct migration.' }
  }

  return {
    ready: true,
    tone: 'ok',
    message: `Migration allowed after plan check. Compatibility: ${compatibility || 'unknown'}, strategy: ${strategy || 'unknown'}.`
  }
}

const formatJobLogLine = (entry) => {
  if (!entry) return ''
  const timestamp = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '--:--:--'
  const level = (entry.level || 'info').toUpperCase()
  return `${timestamp} [${level}] ${entry.message || ''}`
}

const buildOpenShiftPayload = ({
  sourceDiskPath,
  sourceDiskFormat,
  targetVmName,
  pvcSize,
  memory,
  cpuCores,
  firmware,
  diskBus,
  namespace,
  importMode,
}) => ({
  source_disk_path: sourceDiskPath,
  source_disk_format: sourceDiskFormat || 'vmdk',
  target_vm_name: targetVmName,
  pvc_size: pvcSize || '20Gi',
  memory: memory || '2Gi',
  cpu_cores: parseInt(cpuCores, 10) || 2,
  firmware: firmware || 'auto',
  disk_bus: diskBus || 'auto',
  namespace: namespace || 'vm-migration',
  import_mode: importMode || 'http',
})

const estimateMigrationTime = (importMode, hasLocalFiles) => {
  if (importMode === 'upload') return 'This can take several minutes and may be slower for large disks.'
  if (hasLocalFiles) return 'Please wait a few minutes while the backend converts the disk, imports it, and creates the VM.'
  return 'Please wait a few minutes while the backend imports the disk and creates the VM.'
}

const HomePage = () => {
  const [apiBase, setApiBase] = useState(
    import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000'
  )
  const [vms, setVms] = useState([])
  const [vmName, setVmName] = useState('')
  const [discoverySource, setDiscoverySource] = useState('kvm')
  const [vmSource, setVmSource] = useState('kvm')
  const [analysis, setAnalysis] = useState(null)
  const [migration, setMigration] = useState(null)
  const [jobId, setJobId] = useState('')
  const [openShiftResult, setOpenShiftResult] = useState(null)
  const [error, setError] = useState(null)
  const [diskFiles, setDiskFiles] = useState([])

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
  const [firmware, setFirmware] = useState('auto')
  const [diskBus, setDiskBus] = useState('auto')
  const [namespace, setNamespace] = useState('vm-migration')
  const [importMode, setImportMode] = useState('http')
  const [migrationNotice, setMigrationNotice] = useState('')

  const { token } = useAuth()
  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])
  const { logs, pushLog } = useLogger()
  const migrationGate = useMemo(() => buildMigrationGate(analysis, vmName), [analysis, vmName])
  const canStartRealMigration = migrationGate.ready && Boolean(targetVmName) && (diskFiles.length > 0 || sourceDiskPath)
  const lastNotifiedStatusRef = useRef('')

  const setActionLoading = (key, value) => {
    setLoading((prev) => ({ ...prev, [key]: value }))
  }

  const openVmConsole = (consoleUrl) => {
    if (!consoleUrl) return
    window.open(consoleUrl, '_blank', 'noopener,noreferrer')
  }

  const notifyUser = async (title, body) => {
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (Notification.permission === 'default') {
      try {
        await Notification.requestPermission()
      } catch {
        return
      }
    }
    if (Notification.permission === 'granted') {
      new Notification(title, { body })
    }
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
          setMigrationNotice(
            data.status === 'completed'
              ? `Migration finished for ${data.vm_name || targetVmName}.`
              : `Migration failed for ${data.vm_name || targetVmName}. Check the logs below.`
          )
        }
      } catch (err) {
        const msg = err.message || 'Unknown error'
        setError(`Auto status refresh: ${msg}`)
        pushLog(`Auto status refresh failed: ${msg}`)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [api, jobId, migration, pushLog, targetVmName])

  useEffect(() => {
    if (!jobId || !migration?.status) return
    const key = `${jobId}:${migration.status}`
    if (lastNotifiedStatusRef.current === key) return
    if (migration.status === 'completed') {
      lastNotifiedStatusRef.current = key
      notifyUser('Migration completed', `${migration.vm_name || targetVmName || 'VM'} is ready on OpenShift.`)
    } else if (migration.status === 'failed') {
      lastNotifiedStatusRef.current = key
      notifyUser('Migration failed', `${migration.vm_name || targetVmName || 'VM'} failed. Open the logs for details.`)
    }
  }, [jobId, migration, targetVmName])

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
      let endpoint = '/api/v1/discovery/kvm'
      if (discoverySource === 'vmware-workstation') {
        endpoint = '/api/v1/discovery/vmware-workstation'
      } else if (discoverySource === 'vmware-esxi') {
        endpoint = '/api/v1/discovery/vmware-esxi'
      }
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
      let data
      if (diskFiles.length > 0) {
        const localResult = await analyzeLocalVmwareBundle(diskFiles, vmName)
        data = {
          vm_name: localResult.vm_name,
          source: localResult.source,
          details: localResult.details,
          analysis: localResult.analysis,
        }
        setVmName(localResult.vm_name || vmName)
        setVmSource('local-browser-vmware')
      } else {
        data = await api.fetchJson(`/api/v1/migration/analyze/${vmName}?source=${vmSource}`, {
          method: 'POST',
        })
      }
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
      let data
      if (diskFiles.length > 0) {
        data = await analyzeLocalVmwareBundle(diskFiles, vmName)
        setVmName(data.vm_name || vmName)
        setVmSource('local-browser-vmware')
      } else {
        data = await api.fetchJson(`/api/v1/migration/plan/${vmName}?source=${vmSource}`, {
          method: 'POST',
        })
      }
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
    if (canStartRealMigration) {
      return submitOpenShiftMigration({
        loadingKey: 'start',
        actionLabel: 'Start migration',
        redirectToConsole: true,
      })
    }
    setError(null)
    setActionLoading('start', true)
    try {
      if (diskFiles.length > 0 || vmSource === 'local-browser-vmware') {
        const localJobId = `local-${Date.now()}`
        const localMigration = {
          job_id: localJobId,
          vm_name: vmName,
          status: 'completed',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          plan: {
            analysis: analysis?.analysis || analysis,
            conversion_plan: analysis?.conversion_plan || null,
            strategy: analysis?.strategy || { strategy: 'conversion' },
          },
          steps: [
            {
              name: 'browser-precheck',
              status: 'completed',
              logs: [{ timestamp: new Date().toISOString(), level: 'info', message: 'Local VMware bundle analyzed in the browser.' }],
            },
            {
              name: 'simulated-migration',
              status: 'completed',
              logs: [{ timestamp: new Date().toISOString(), level: 'info', message: 'Simulation completed locally because the backend cannot rediscover browser-only files.' }],
            },
          ],
          logs: [
            { timestamp: new Date().toISOString(), level: 'info', message: `Local simulated migration prepared for ${vmName}.` },
          ],
          error: null,
          note: 'Local VMware bundle: simulated start handled in the frontend because the backend cannot rediscover browser-only files.',
        }
        setMigration(localMigration)
        setJobId(localJobId)
        pushLog(`Local simulated migration prepared for ${vmName} (job: ${localJobId})`)
        return
      }

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

  const submitOpenShiftMigration = async ({
    loadingKey,
    actionLabel,
    redirectToConsole = false,
  }) => {
    if (!vmName) return pushLog('VM name required (source label)')
    if (!migrationGate.ready) return pushLog(migrationGate.message)
    if (!targetVmName) return pushLog('Target VM name is required')
    if (diskFiles.length === 0 && !sourceDiskPath) {
      return pushLog('Select a local disk file or enter a bastion disk path')
    }

    setError(null)
    setActionLoading(loadingKey, true)
    try {
      const waitMessage = estimateMigrationTime(importMode, diskFiles.length > 0)
      setMigrationNotice(waitMessage)
      pushLog(waitMessage)
      let data

      if (diskFiles.length > 0) {
        const formData = new FormData()
        diskFiles.forEach((file) => {
          formData.append('disk_files', file)
        })
        formData.append('source_disk_format', sourceDiskFormat || 'vmdk')
        formData.append('target_vm_name', targetVmName)
        formData.append('pvc_size', pvcSize || '20Gi')
        formData.append('memory', memory || '2Gi')
        formData.append('cpu_cores', `${parseInt(cpuCores, 10) || 2}`)
        formData.append('firmware', firmware || 'auto')
        formData.append('disk_bus', diskBus || 'auto')
        formData.append('namespace', namespace || 'vm-migration')
        formData.append('import_mode', importMode || 'http')

        data = await api.fetchJson(`/api/v1/migration/openshift-upload/${vmName}`, {
          method: 'POST',
          body: formData,
        })
      } else {
        const payload = buildOpenShiftPayload({
          sourceDiskPath,
          sourceDiskFormat,
          targetVmName,
          pvcSize,
          memory,
          cpuCores,
          firmware,
          diskBus,
          namespace,
          importMode,
        })

        data = await api.fetchJson(`/api/v1/migration/openshift/${vmName}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      }

      setOpenShiftResult(data)
      setJobId(data.job_id || '')
      setMigration(data.job_id ? { job_id: data.job_id, status: data.status, vm_console_url: data.vm_console_url } : null)
      pushLog(`${actionLabel} submitted for ${targetVmName}`)
      pushLog(`Job ${data.job_id} queued. You can wait a few minutes and watch the live logs below.`)

      if (redirectToConsole && data.vm_console_url) {
        pushLog(`Opening OpenShift VM page for ${targetVmName}`)
        openVmConsole(data.vm_console_url)
      }
    } catch (err) {
      handleError(actionLabel, err)
    } finally {
      setActionLoading(loadingKey, false)
    }
  }

  const onOpenShift = async () => {
    await submitOpenShiftMigration({
      loadingKey: 'openshift',
      actionLabel: 'OpenShift migration',
      redirectToConsole: false,
    })
  }

  const btnLabel = (action) => {
    if (loading[action]) return 'Loading...'
    return null
  }

  const startButtonLabel = () => {
    if (loading.start) return 'Loading...'
    if (canStartRealMigration) return 'Start And Open VM'
    return 'Start (Simulated)'
  }

  const renderedJobLogs = migration?.logs || []

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
                <option value="vmware-esxi">VMware ESXi / vSphere</option>
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
                  setAnalysis(null)
                  setOpenShiftResult(null)
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
                onChange={(e) => {
                  setVmName(e.target.value)
                  setAnalysis(null)
                  setOpenShiftResult(null)
                }}
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
                {startButtonLabel()}
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
          {openShiftResult?.vm_console_url ? (
            <div className="row">
              <Button variant="ghost" onClick={() => openVmConsole(openShiftResult.vm_console_url)}>
                Open VM In OpenShift
              </Button>
            </div>
          ) : null}
          {migrationNotice ? <p className="status-note">{migrationNotice}</p> : null}
          <div className="step-log">
            {renderedJobLogs.length === 0 ? (
              <div className="step-log-empty">No job logs yet.</div>
            ) : (
              renderedJobLogs.map((entry, index) => (
                <div key={`${entry.timestamp || 'log'}-${index}`} className={`step-log-line level-${entry.level || 'info'}`}>
                  {formatJobLogLine(entry)}
                </div>
              ))
            )}
          </div>
        </Card>

        <Card
          className="wide"
          title="OpenShift Real Migration"
          hint="Upload a local disk from your browser or use a disk path that already exists on the bastion. Real migration unlocks only after a successful Plan."
          actions={
            <Button onClick={onOpenShift} disabled={loading.openshift || !migrationGate.ready}>
              {btnLabel('openshift') || 'Migrate to OpenShift'}
            </Button>
          }
        >
          <p className="hint">
            Precheck: <strong>{migrationGate.message}</strong>
          </p>
          <FieldGrid>
            <label className="field">
              <span className="field-label">Local VM Files</span>
              <Input
                type="file"
                multiple
                accept=".vmx,.vmdk,.qcow2,.img,.raw"
                onChange={(e) => {
                  const files = Array.from(e.target.files || [])
                  setDiskFiles(files)

                  if (files.length === 0) return

                  const bundle = inferVmwareBundle(files)

                  setVmName((current) => current || bundle.inferredName)
                  setTargetVmName((current) => current || bundle.inferredName)
                  setSourceDiskFormat(bundle.inferredFormat)
                  setSourceDiskPath('')
                }}
              />
            </label>
            <label className="field">
              <span className="field-label">Bastion Disk Path</span>
              <Input
                placeholder="/path/on/bastion/source.vmdk"
                value={sourceDiskPath}
                onChange={(e) => setSourceDiskPath(e.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Disk Format</span>
              <Input placeholder="auto | vmdk | qcow2 | raw" value={sourceDiskFormat} onChange={(e) => setSourceDiskFormat(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Target VM Name</span>
              <Input placeholder="abdou-os" value={targetVmName} onChange={(e) => setTargetVmName(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">PVC Size</span>
              <Input placeholder="20Gi" value={pvcSize} onChange={(e) => setPvcSize(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">RAM</span>
              <Input placeholder="2Gi" value={memory} onChange={(e) => setMemory(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">vCPU</span>
              <Input type="number" placeholder="2" value={cpuCores} onChange={(e) => setCpuCores(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Firmware</span>
              <Input placeholder="auto | bios | uefi" value={firmware} onChange={(e) => setFirmware(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Disk Bus</span>
              <Input placeholder="auto | sata | scsi | virtio" value={diskBus} onChange={(e) => setDiskBus(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Namespace</span>
              <Input placeholder="vm-migration" value={namespace} onChange={(e) => setNamespace(e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Import Mode</span>
              <Input placeholder="http | upload" value={importMode} onChange={(e) => setImportMode(e.target.value)} />
            </label>
          </FieldGrid>
          <p className="hint">
            Estimated time: <strong>{estimateMigrationTime(importMode, diskFiles.length > 0)}</strong>
          </p>
          {diskFiles.length > 0 ? (
            (() => {
              const bundle = inferVmwareBundle(diskFiles)
              return (
                <p className="hint">
                  Local files selected: <strong>{diskFiles.length}</strong> ({formatBytes(diskFiles.reduce((total, file) => total + file.size, 0))}).
                  Primary bundle: <strong>{bundle.primaryFile?.name || 'unknown'}</strong>.
                  {bundle.hasVmx ? ' VMX detected.' : ' No VMX detected.'}
                  {bundle.splitExtentCount > 0 ? ` ${bundle.splitExtentCount} split VMDK extent(s) detected.` : ''}
                </p>
              )
            })()
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
