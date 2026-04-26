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
import {
  analyzeLocalVmwareBundle,
  analyzeVmDetails,
  buildConversionPlan,
  chooseLocalStrategy,
} from '../utils/localVmware'

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

const inferPrimaryKvmDisk = (details) => {
  const disks = Array.isArray(details?.disks) ? details.disks : []
  return disks.find((disk) => (disk.device || 'disk') === 'disk' && disk.path) || null
}

const isLocalAgentSource = (source) => ['local-agent-kvm', 'local-agent-hyperv'].includes(source)

const buildLocalAgentEndpoint = (source, vmName = '') => {
  const encodedVmName = encodeURIComponent(vmName)
  if (source === 'local-agent-kvm') {
    return vmName ? `/api/v1/discovery/kvm/${encodedVmName}` : '/api/v1/discovery/kvm'
  }
  if (source === 'local-agent-hyperv') {
    return vmName ? `/api/v1/discovery/hyperv/${encodedVmName}` : '/api/v1/discovery/hyperv'
  }
  return '/api/v1/discovery/kvm'
}

const buildLocalAgentPlan = (details, source) => {
  const analysis = analyzeVmDetails(details)
  const conversionPlan = buildConversionPlan(details, analysis)
  const strategy = chooseLocalStrategy(analysis, conversionPlan)
  return {
    vm_name: details?.name || '',
    source,
    details,
    analysis,
    conversion_plan: conversionPlan,
    strategy,
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

const BASTION_UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024

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

const STORAGE_KEY = 'migration-control-room-state'
const LOG_STORAGE_KEY = 'migration-control-room-logs'

const HomePage = () => {
  const [apiBase, setApiBase] = useState(
    import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000'
  )
  const [localAgentBase, setLocalAgentBase] = useState(import.meta.env.VITE_LOCAL_AGENT_BASE_URL || 'http://127.0.0.1:8010')
  const [localAgentToken, setLocalAgentToken] = useState(import.meta.env.VITE_LOCAL_AGENT_TOKEN || '')
  const [localAgentHealth, setLocalAgentHealth] = useState(null)
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
    agentHealth: false,
    discover: false,
    analyze: false,
    plan: false,
    prepare: false,
    agentPrepare: false,
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
  const [prepareProgress, setPrepareProgress] = useState(null)
  const [preparedBundle, setPreparedBundle] = useState(null)
  const [localAgentPreparation, setLocalAgentPreparation] = useState(null)

  const { token } = useAuth()
  const api = useMemo(() => createApi(apiBase, token), [apiBase, token])
  const { logs, pushLog } = useLogger(LOG_STORAGE_KEY)
  const migrationGate = useMemo(() => buildMigrationGate(analysis, vmName), [analysis, vmName])
  const trimmedSourceDiskPath = sourceDiskPath.trim()
  const localAgentSourceSelected = isLocalAgentSource(vmSource)
  const migrationUsesBastionPath = Boolean(trimmedSourceDiskPath)
  const inferredKvmDisk = useMemo(() => (
    vmSource === 'kvm' ? inferPrimaryKvmDisk(analysis?.details) : null
  ), [analysis, vmSource])
  const canStartRealMigration = migrationGate.ready
    && Boolean(targetVmName)
    && (migrationUsesBastionPath || diskFiles.length > 0 || Boolean(inferredKvmDisk))
  const lastNotifiedStatusRef = useRef('')

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const saved = JSON.parse(raw)
      if (saved.localAgentBase) setLocalAgentBase(saved.localAgentBase)
      if (saved.localAgentToken) setLocalAgentToken(saved.localAgentToken)
      if (saved.vmName) setVmName(saved.vmName)
      if (saved.vmSource) setVmSource(saved.vmSource)
      if (saved.analysis) setAnalysis(saved.analysis)
      if (saved.migration) setMigration(saved.migration)
      if (saved.jobId) setJobId(saved.jobId)
      if (saved.openShiftResult) setOpenShiftResult(saved.openShiftResult)
      if (saved.sourceDiskPath) setSourceDiskPath(saved.sourceDiskPath)
      if (saved.sourceDiskFormat) setSourceDiskFormat(saved.sourceDiskFormat)
      if (saved.targetVmName) setTargetVmName(saved.targetVmName)
      if (saved.pvcSize) setPvcSize(saved.pvcSize)
      if (saved.memory) setMemory(saved.memory)
      if (saved.cpuCores) setCpuCores(saved.cpuCores)
      if (saved.firmware) setFirmware(saved.firmware)
      if (saved.diskBus) setDiskBus(saved.diskBus)
      if (saved.namespace) setNamespace(saved.namespace)
      if (saved.importMode) setImportMode(saved.importMode)
      if (saved.migrationNotice) setMigrationNotice(saved.migrationNotice)
      if (saved.prepareProgress) setPrepareProgress(saved.prepareProgress)
      if (saved.preparedBundle) setPreparedBundle(saved.preparedBundle)
      if (saved.localAgentPreparation) setLocalAgentPreparation(saved.localAgentPreparation)
    } catch {
      // Ignore invalid persisted UI state.
    }
  }, [])

  useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        vmName,
        vmSource,
        localAgentBase,
        localAgentToken,
        analysis,
        migration,
        jobId,
        openShiftResult,
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
        migrationNotice,
        prepareProgress,
        preparedBundle,
        localAgentPreparation,
      }))
    } catch {
      // Ignore persistence issues.
    }
  }, [
    vmName,
    vmSource,
    localAgentBase,
    localAgentToken,
    analysis,
    migration,
    jobId,
    openShiftResult,
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
    migrationNotice,
    prepareProgress,
    preparedBundle,
    localAgentPreparation,
  ])

  useEffect(() => {
    if (!inferredKvmDisk || vmSource !== 'kvm') return
    if (!trimmedSourceDiskPath) {
      setSourceDiskPath(inferredKvmDisk.path || '')
    }
    if (!sourceDiskFormat || sourceDiskFormat === 'auto' || sourceDiskFormat === 'vmdk') {
      setSourceDiskFormat(inferredKvmDisk.format || 'raw')
    }
    if (!targetVmName) {
      setTargetVmName(vmName)
    }
  }, [inferredKvmDisk, vmSource, trimmedSourceDiskPath, sourceDiskFormat, targetVmName, vmName])

  const setActionLoading = (key, value) => {
    setLoading((prev) => ({ ...prev, [key]: value }))
  }

  const fetchLocalAgentJson = async (path, options = {}) => {
    const headers = { ...(options.headers || {}) }
    if (localAgentToken) {
      headers['X-Agent-Token'] = localAgentToken
    }
    const base = (localAgentBase || '').replace(/\/$/, '')
    const response = await fetch(`${base}${path}`, { ...options, headers })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(`${response.status} ${response.statusText}: ${text}`)
    }
    return response.json()
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

  const onLocalAgentHealth = async () => {
    setError(null)
    setActionLoading('agentHealth', true)
    try {
      const data = await fetchLocalAgentJson('/health')
      setLocalAgentHealth(data)
      pushLog('Local agent health OK')
    } catch (err) {
      handleError('Local agent health', err)
    } finally {
      setActionLoading('agentHealth', false)
    }
  }

  const onDiscover = async () => {
    setError(null)
    setActionLoading('discover', true)
    try {
      let endpoint = '/api/v1/discovery/kvm'
      let data
      if (discoverySource === 'local-agent-kvm' || discoverySource === 'local-agent-hyperv') {
        endpoint = buildLocalAgentEndpoint(discoverySource)
        data = await fetchLocalAgentJson(endpoint)
      } else if (discoverySource === 'vmware-workstation') {
        endpoint = '/api/v1/discovery/vmware-workstation'
        data = await api.fetchJson(endpoint)
      } else if (discoverySource === 'vmware-esxi') {
        endpoint = '/api/v1/discovery/vmware-esxi'
        data = await api.fetchJson(endpoint)
      } else {
        data = await api.fetchJson(endpoint)
      }
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
    if (isLocalAgentSource(vmSource)) {
      setError(null)
      setActionLoading('analyze', true)
      try {
        const details = await fetchLocalAgentJson(buildLocalAgentEndpoint(vmSource, vmName))
        const data = buildLocalAgentPlan(details, vmSource)
        setAnalysis(data)
        const primaryDisk = inferPrimaryKvmDisk(details)
        if (primaryDisk?.path && !trimmedSourceDiskPath) setSourceDiskPath(primaryDisk.path)
        if (primaryDisk?.format) setSourceDiskFormat(primaryDisk.format)
        if (!targetVmName) setTargetVmName(details?.name || vmName)
        pushLog(`Local agent analysis done for ${vmName}`)
      } catch (err) {
        handleError('Analysis', err)
      } finally {
        setActionLoading('analyze', false)
      }
      return
    }
    if (diskFiles.length === 0 && trimmedSourceDiskPath && vmSource === 'kvm') {
      setError('Analysis: use local VM files for Analyze/Plan, or keep the previous plan. Bastion Disk Path is used for migration, not KVM discovery.')
      return pushLog('Analyze blocked: bastion path is for migration. Use local VM files for Analyze/Plan.')
    }
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
    if (isLocalAgentSource(vmSource)) {
      setError(null)
      setActionLoading('plan', true)
      try {
        const details = await fetchLocalAgentJson(buildLocalAgentEndpoint(vmSource, vmName))
        const data = buildLocalAgentPlan(details, vmSource)
        setAnalysis(data)
        const primaryDisk = inferPrimaryKvmDisk(details)
        if (primaryDisk?.path && !trimmedSourceDiskPath) setSourceDiskPath(primaryDisk.path)
        if (primaryDisk?.format) setSourceDiskFormat(primaryDisk.format)
        if (!targetVmName) setTargetVmName(details?.name || vmName)
        pushLog(`Local agent plan generated for ${vmName}`)
      } catch (err) {
        handleError('Plan', err)
      } finally {
        setActionLoading('plan', false)
      }
      return
    }
    if (diskFiles.length === 0 && trimmedSourceDiskPath && vmSource === 'kvm') {
      setError('Plan: use local VM files for Analyze/Plan, or keep the previous plan. Bastion Disk Path is used for migration, not KVM discovery.')
      return pushLog('Plan blocked: bastion path is for migration. Use local VM files for Analyze/Plan.')
    }
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
    if (localAgentSourceSelected) {
      setMigrationNotice('Local agent discovery and planning are ready. The next phase is disk handoff from the user machine to the bastion before a real migration can start.')
      return pushLog('Start blocked: local agent disk handoff to bastion is the next implementation step.')
    }
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

  const onPrepareBastion = async () => {
    if (!vmName) return pushLog('VM name required')
    if (diskFiles.length === 0) return pushLog('Select local VM files first')

    setError(null)
    setActionLoading('prepare', true)
    try {
      const totalBytes = diskFiles.reduce((sum, file) => sum + (file.size || 0), 0)
      const authHeaders = token ? { Authorization: `Bearer ${token}` } : {}
      const reportProgress = (uploadedBytes) => {
        const percent = totalBytes > 0 ? Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)) : 100
        setPrepareProgress({
          uploadedBytes,
          totalBytes,
          percent,
          active: percent < 100,
        })
        setMigrationNotice(`Uploading files to the bastion: ${percent}% (${formatBytes(uploadedBytes)} / ${formatBytes(totalBytes)})`)
      }

      reportProgress(0)
      pushLog('Uploading local VM files to the bastion in chunks so the disk path can be filled automatically.')

      const session = await api.fetchJson(`/api/v1/migration/prepare-upload-session/${vmName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_vm_name: targetVmName || vmName,
          source_disk_format: sourceDiskFormat || 'auto',
          files: diskFiles.map((file) => ({
            name: file.name,
            size: file.size,
          })),
        }),
      })

      let uploadedBytes = 0
      let lastReportedPercent = -10
      for (const file of diskFiles) {
        const totalChunks = Math.max(1, Math.ceil(file.size / BASTION_UPLOAD_CHUNK_SIZE))
        pushLog(`Uploading ${file.name} in ${totalChunks} chunk(s)...`)

        for (let offset = 0; offset < file.size || (file.size === 0 && offset === 0); offset += BASTION_UPLOAD_CHUNK_SIZE) {
          const chunk = file.slice(offset, Math.min(file.size, offset + BASTION_UPLOAD_CHUNK_SIZE))
          const params = new URLSearchParams({
            filename: file.name,
            offset: `${offset}`,
            total_size: `${file.size}`,
          })

          const response = await fetch(`${apiBase}/api/v1/migration/upload-session/${session.session_id}/chunk?${params.toString()}`, {
            method: 'POST',
            headers: {
              ...authHeaders,
              'Content-Type': 'application/octet-stream',
            },
            body: chunk,
          })

          if (!response.ok) {
            const text = await response.text()
            throw new Error(`${response.status} ${response.statusText}: ${text}`)
          }

          uploadedBytes += chunk.size
          reportProgress(uploadedBytes)
          const percent = totalBytes > 0 ? Math.round((uploadedBytes / totalBytes) * 100) : 100
          if (percent >= lastReportedPercent + 10 || percent === 100) {
            pushLog(`Bastion upload progress: ${percent}%`)
            lastReportedPercent = percent
          }

          if (file.size === 0) {
            break
          }
        }
      }

      const data = await api.fetchJson(`/api/v1/migration/upload-session/${session.session_id}/complete`, {
        method: 'POST',
      })

      setPreparedBundle(data)
      setSourceDiskPath(data.source_disk_path || '')
      setSourceDiskFormat(data.source_disk_format || sourceDiskFormat)
      setTargetVmName(data.target_vm_name || targetVmName || vmName)
      setVmName(data.vm_name || vmName)
      setDiskFiles([])
      setPrepareProgress({
        uploadedBytes: totalBytes,
        totalBytes,
        percent: 100,
        active: false,
      })
      setMigrationNotice('Files prepared on the bastion. The bastion disk path was filled automatically.')
      pushLog(`Bastion path ready: ${data.source_disk_path}`)
    } catch (err) {
      setPrepareProgress((current) => current ? { ...current, active: false } : null)
      handleError('Prepare on bastion', err)
    } finally {
      setActionLoading('prepare', false)
    }
  }

  const onPrepareLocalAgent = async () => {
    if (!vmName) return pushLog('VM name required')
    if (!isLocalAgentSource(vmSource)) return pushLog('Select a Local Agent VM first')

    setError(null)
    setActionLoading('agentPrepare', true)
    try {
      const source = vmSource === 'local-agent-hyperv' ? 'hyperv' : 'kvm'
      pushLog(`Reading local VM metadata from agent for ${vmName}...`)
      const localData = await fetchLocalAgentJson(`/api/v1/prepare/${source}/${encodeURIComponent(vmName)}`)
      setLocalAgentPreparation(localData)
      setTargetVmName((current) => current || localData?.vm_name || vmName)
      setSourceDiskFormat(localData?.primary_disk?.format || sourceDiskFormat || 'raw')

      pushLog('Streaming local VM disk from local agent to bastion storage...')
      const bastionData = await api.fetchJson(`/api/v1/migration/prepare-local-agent/${vmName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          local_agent_base_url: localAgentBase,
          local_source: source,
          local_agent_token: localAgentToken,
          target_vm_name: targetVmName || localData?.vm_name || vmName,
          source_disk_format: localData?.primary_disk?.format || sourceDiskFormat || 'auto',
        }),
      })

      setPreparedBundle(bastionData)
      setSourceDiskPath(bastionData?.source_disk_path || '')
      setSourceDiskFormat(bastionData?.source_disk_format || localData?.primary_disk?.format || sourceDiskFormat || 'raw')
      setTargetVmName((current) => bastionData?.target_vm_name || current || localData?.vm_name || vmName)
      setMigrationNotice('Local agent handoff completed. Disk is now on bastion and real migration can start from UI.')
      pushLog(`Local agent handoff done. Bastion path: ${bastionData?.source_disk_path || 'n/a'}`)
    } catch (err) {
      handleError('Local agent prepare', err)
    } finally {
      setActionLoading('agentPrepare', false)
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
    if (diskFiles.length === 0 && !trimmedSourceDiskPath && !inferredKvmDisk) {
      return pushLog('Select a local disk file, enter a bastion disk path, or choose a KVM VM with a detected disk')
    }

    setError(null)
    setActionLoading(loadingKey, true)
    try {
      const waitMessage = estimateMigrationTime(importMode, !migrationUsesBastionPath && diskFiles.length > 0)
      setMigrationNotice(waitMessage)
      pushLog(waitMessage)
      let data

      if (!migrationUsesBastionPath && diskFiles.length > 0) {
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
          sourceDiskPath: trimmedSourceDiskPath || inferredKvmDisk?.path || '',
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

        const migrationSource = ['kvm', 'vmware-esxi', 'vmware-workstation'].includes(vmSource) ? vmSource : 'kvm'
        data = await api.fetchJson(`/api/v1/migration/openshift/${vmName}?source=${migrationSource}`, {
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
      if (migrationUsesBastionPath && diskFiles.length > 0) {
        pushLog('Using bastion path for migration. Local files remain only as analysis context.')
      }

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
    if (localAgentSourceSelected && !canStartRealMigration) return 'Start (Prepare Agent First)'
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
          title="Local Agent"
          hint="Use this when the VM exists only on the user machine, for example local KVM or Hyper-V."
          actions={
            <Button variant="ghost" onClick={onLocalAgentHealth} disabled={loading.agentHealth}>
              {btnLabel('agentHealth') || 'Agent Health'}
            </Button>
          }
        >
          <FieldGrid>
            <label className="field">
              <span className="field-label">Agent URL</span>
              <Input value={localAgentBase} onChange={(e) => setLocalAgentBase(e.target.value)} placeholder="http://127.0.0.1:8010" />
            </label>
            <label className="field">
              <span className="field-label">Agent Token</span>
              <Input value={localAgentToken} onChange={(e) => setLocalAgentToken(e.target.value)} placeholder="optional agent token" />
            </label>
          </FieldGrid>
          <JsonBlock data={localAgentHealth} />
        </Card>

        <Card
          title="Discovery"
          hint="Lists VMs visible from the backend host or from the local agent."
          actions={
            <>
              <select
                className="input"
                value={discoverySource}
                onChange={(e) => setDiscoverySource(e.target.value)}
              >
                <option value="kvm">KVM</option>
                <option value="local-agent-kvm">Local Agent KVM</option>
                <option value="local-agent-hyperv">Local Agent Hyper-V</option>
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
                  setLocalAgentPreparation(null)
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
            <>
              <Button variant="ghost" onClick={onPrepareLocalAgent} disabled={loading.agentPrepare || !isLocalAgentSource(vmSource)}>
                {btnLabel('agentPrepare') || 'Prepare Via Agent'}
              </Button>
              <Button variant="ghost" onClick={onPrepareBastion} disabled={loading.prepare || diskFiles.length === 0}>
                {btnLabel('prepare') || 'Prepare On Bastion'}
              </Button>
              <Button onClick={onOpenShift} disabled={loading.openshift || !canStartRealMigration}>
                {btnLabel('openshift') || 'Migrate to OpenShift'}
              </Button>
            </>
          }
        >
          <p className="hint">
            Precheck: <strong>{migrationGate.message}</strong>
          </p>
          {localAgentSourceSelected ? (
            <p className="hint">
              Local agent source selected. Use <strong>Prepare Via Agent</strong> to copy the disk to bastion, then run real migration from that prepared bastion path.
            </p>
          ) : null}
          {prepareProgress ? (
            <div className="upload-progress-card">
              <div className="upload-progress-head">
                <strong>Prepare Upload Progress</strong>
                <span>{prepareProgress.percent}%</span>
              </div>
              <div className="upload-progress-bar" aria-hidden="true">
                <div
                  className={`upload-progress-fill${prepareProgress.active ? ' active' : ''}`}
                  style={{ width: `${prepareProgress.percent}%` }}
                />
              </div>
              <div className="upload-progress-meta">
                <span>{formatBytes(prepareProgress.uploadedBytes)} uploaded</span>
                <span>{formatBytes(prepareProgress.totalBytes)} total</span>
              </div>
            </div>
          ) : null}
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
                  setVmSource('local-browser-vmware')
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
            Estimated time: <strong>{estimateMigrationTime(importMode, !migrationUsesBastionPath && diskFiles.length > 0)}</strong>
          </p>
          {migrationUsesBastionPath && diskFiles.length > 0 ? (
            <p className="hint">
              Using bastion path for the real migration. Local files stay selected only for analysis and planning.
            </p>
          ) : null}
          {!migrationUsesBastionPath && inferredKvmDisk ? (
            <p className="hint">
              KVM disk detected from libvirt: <strong>{inferredKvmDisk.path}</strong>. The migration can use it automatically.
            </p>
          ) : null}
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
              {localAgentSourceSelected
                ? 'No browser file is needed for local-agent discovery. Use Prepare Via Agent to fetch VM metadata and transfer the primary disk to bastion.'
                : 'No local file selected. The migration will use the bastion disk path field if you submit now.'}
            </p>
          )}
          {preparedBundle?.source_disk_path ? (
            <p className="hint">
              Prepared on bastion: <strong>{preparedBundle.source_disk_path}</strong>
            </p>
          ) : null}
          {localAgentPreparation?.primary_disk?.path ? (
            <p className="hint">
              Prepared via local agent: <strong>{localAgentPreparation.primary_disk.path}</strong>
            </p>
          ) : null}
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
