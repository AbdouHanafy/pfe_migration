const VMWARE_OS_MAP = {
  ubuntu: ['ubuntu', 'x86'],
  'ubuntu-64': ['Ubuntu', 'x86_64'],
  debian: ['debian', 'x86'],
  'debian-64': ['Debian', 'x86_64'],
  rhel: ['rhel', 'x86'],
  'rhel-64': ['RHEL', 'x86_64'],
  centos: ['centos', 'x86'],
  'centos-64': ['CentOS', 'x86_64'],
  fedora: ['fedora', 'x86'],
  'fedora-64': ['Fedora', 'x86_64'],
  sles: ['sles', 'x86'],
  'sles-64': ['SLES', 'x86_64'],
  otherlinux: ['other-linux', 'x86'],
  'otherlinux-64': ['other-linux', 'x86_64'],
  'other-64': ['linux', 'x86_64'],
  windows9: ['Windows 10', 'x86'],
  'windows9-64': ['Windows 10', 'x86_64'],
  winxphome: ['Windows XP', 'x86'],
  winxppro: ['Windows XP', 'x86'],
  'winxphome-64': ['Windows XP', 'x86_64'],
  'winxppro-64': ['Windows XP', 'x86_64'],
  'windows7-64': ['Windows 7', 'x86_64'],
  'windows8-64': ['Windows 8', 'x86_64'],
  'windows8server-64': ['Windows Server 2012', 'x86_64'],
  win11: ['Windows 11', 'x86_64'],
  'win11srv-64': ['Windows Server 2022', 'x86_64'],
  other: ['unknown', 'unknown'],
}

const SUPPORTED_ARCHES = new Set(['x86_64', 'amd64'])
const SUPPORTED_DISK_FORMATS = new Set(['raw', 'qcow2'])
const SUPPORTED_DISK_BUSES = new Set(['virtio', 'scsi', 'sata'])
const SUPPORTED_NET_MODELS = new Set(['virtio', 'e1000'])
const fileStem = (filename) => (filename || '').replace(/\.[^.]+$/, '')

const parseGuestOs = (guestOsCode) => VMWARE_OS_MAP[(guestOsCode || 'other').toLowerCase().trim()] || ['unknown', 'unknown']

const normalizeBus = (value) => (value || 'unknown').toLowerCase().replace(/[0-9:]+$/g, '')

const parseVmx = (text) => {
  const data = {}
  text.split(/\r?\n/).forEach((line) => {
    if (!line || line.trim().startsWith('#') || !line.includes('=')) return
    const [rawKey, ...rest] = line.split('=')
    const key = rawKey.trim()
    const value = rest.join('=').trim().replace(/^"|"$/g, '')
    if (key) data[key] = value
  })
  return data
}

const extractSpecs = (vmxData) => {
  const memoryMb = Number.parseInt(vmxData.memsize || '0', 10) || 0
  const cpus = Number.parseInt(vmxData.numvcpus || '1', 10) || 1
  const [osType, osArch] = parseGuestOs(vmxData.guestOS)
  return {
    memory_mb: memoryMb,
    cpus,
    os_type: osType,
    os_arch: osArch,
    guestOS: vmxData.guestOS || 'unknown',
  }
}

const extractDisks = (vmxData, filesByName) => {
  const disks = []
  Object.entries(vmxData).forEach(([key, value]) => {
    if (!key.endsWith('.fileName') || !value.toLowerCase().endsWith('.vmdk')) return
    const busType = normalizeBus(key.split('.')[0])
    const matchingFile = filesByName.get(value.split(/[\\/]/).pop()) || null
    disks.push({
      type: 'file',
      device: 'disk',
      path: matchingFile?.name || value,
      format: 'vmdk',
      bus: busType || 'scsi',
      driver: 'vmware',
      size_bytes: matchingFile?.size || 0,
    })
  })
  return disks
}

const extractNetwork = (vmxData) => {
  const networks = []
  Object.keys(vmxData).forEach((key) => {
    if (!key.startsWith('ethernet') || !key.endsWith('.present')) return
    if ((vmxData[key] || '').toLowerCase() !== 'true') return
    const idx = key.split('.')[0]
    const addressType = (vmxData[`${idx}.addressType`] || '').toLowerCase()
    let mac = ''
    if (addressType === 'static') mac = vmxData[`${idx}.address`] || ''
    if (addressType === 'generated') mac = vmxData[`${idx}.generatedAddress`] || ''
    networks.push({
      type: 'network',
      mac_address: mac,
      network: vmxData[`${idx}.connectionType`] || vmxData[`${idx}.networkName`] || '',
      model: vmxData[`${idx}.virtualDev`] || 'e1000',
    })
  })
  return networks
}

export const analyzeVmDetails = (vmDetails) => {
  const specs = vmDetails.specs || {}
  const disks = vmDetails.disks || []
  const networks = vmDetails.network || []
  const issues = []
  const recommendations = []
  const blockers = []
  let score = 100

  const osArch = (specs.os_arch || 'unknown').toLowerCase()
  if (!SUPPORTED_ARCHES.has(osArch)) {
    blockers.push(`Architecture non supportee: ${osArch}`)
    issues.push({ code: 'arch_unsupported', severity: 'blocker', message: `Architecture non supportee: ${osArch}` })
    score -= 40
  }

  const memoryMb = specs.memory_mb || 0
  if (memoryMb < 512) {
    issues.push({ code: 'memory_low', severity: 'warning', message: `RAM faible: ${memoryMb} MB` })
    recommendations.push('Augmenter la RAM a au moins 1 GB.')
    score -= 10
  }

  const cpuCount = specs.cpus || 1
  if (cpuCount < 1) {
    issues.push({ code: 'cpu_invalid', severity: 'warning', message: 'Nombre de CPU invalide' })
    score -= 10
  }

  if (disks.length === 0) {
    blockers.push('Aucun disque detecte')
    issues.push({ code: 'no_disk', severity: 'blocker', message: 'Aucun disque detecte' })
    score -= 40
  }

  disks.forEach((disk) => {
    const fmt = (disk.format || 'unknown').toLowerCase()
    const bus = normalizeBus(disk.bus)
    if (!SUPPORTED_DISK_FORMATS.has(fmt)) {
      issues.push({ code: 'disk_format', severity: 'warning', message: `Format disque non optimal: ${fmt}` })
      recommendations.push(`Convertir le disque en format raw (actuel: ${fmt}).`)
      score -= 10
    }
    if (!SUPPORTED_DISK_BUSES.has(bus)) {
      issues.push({ code: 'disk_bus', severity: 'warning', message: `Bus disque non supporte: ${bus}` })
      recommendations.push('Changer le bus disque vers virtio ou scsi.')
      score -= 10
    }
  })

  networks.forEach((nic) => {
    const model = (nic.model || 'unknown').toLowerCase()
    if (!SUPPORTED_NET_MODELS.has(model)) {
      issues.push({ code: 'net_model', severity: 'warning', message: `Modele reseau non optimal: ${model}` })
      recommendations.push('Utiliser une carte reseau virtio.')
      score -= 10
    }
  })

  return {
    compatibility: blockers.length > 0 ? 'non_compatible' : issues.length > 0 ? 'partiellement_compatible' : 'compatible',
    score: Math.max(0, Math.min(100, score)),
    issues,
    recommendations,
    detected: {
      os_arch: osArch,
      memory_mb: memoryMb,
      cpu_count: cpuCount,
      disks_count: disks.length,
      network_count: networks.length,
    },
  }
}

export const buildConversionPlan = (vmDetails, analysis) => {
  const actions = []
  const warnings = []

  if (analysis.compatibility === 'non_compatible') {
    return {
      can_convert: false,
      actions,
      warnings: ['VM non compatible, conversion automatique refusee.'],
    }
  }

  ;(vmDetails.disks || []).forEach((disk) => {
    const fmt = (disk.format || 'unknown').toLowerCase()
    const bus = normalizeBus(disk.bus)
    if (!SUPPORTED_DISK_FORMATS.has(fmt)) {
      actions.push({ type: 'disk_format_conversion', disk_path: disk.path || '', from: fmt, to: 'raw' })
    }
    if (!SUPPORTED_DISK_BUSES.has(bus)) {
      actions.push({ type: 'disk_bus_change', disk_path: disk.path || '', from: bus, to: 'virtio' })
    }
  })

  ;(vmDetails.network || []).forEach((nic) => {
    const model = (nic.model || 'unknown').toLowerCase()
    if (!SUPPORTED_NET_MODELS.has(model)) {
      actions.push({ type: 'network_model_change', mac_address: nic.mac_address || '', from: model, to: 'virtio' })
    }
  })

  if (actions.length === 0) warnings.push('Aucune conversion requise.')
  return { can_convert: true, actions, warnings }
}

export const chooseLocalStrategy = (analysis, conversionPlan) => {
  let strategy = 'direct'
  if (analysis.compatibility === 'non_compatible') strategy = 'alternative'
  else if ((conversionPlan.actions || []).length > 0) strategy = 'conversion'

  const probs = {
    direct: strategy === 'direct' ? 0.8 : 0.1,
    conversion: strategy === 'conversion' ? 0.8 : 0.1,
    alternative: strategy === 'alternative' ? 0.8 : 0.1,
  }

  let reason = `VM ${analysis.compatibility} (score: ${analysis.score}/100).`
  if (strategy === 'conversion') reason += ` ${(conversionPlan.actions || []).length} action(s) de conversion requises.`
  if (strategy === 'alternative') reason += ' Migration alternative recommandee.'
  if (strategy === 'direct') reason += ' Aucune conversion majeure requise.'

  return {
    strategy,
    confidence: 0.8,
    model_available: false,
    method: 'local-heuristic',
    probabilities: probs,
    reason,
  }
}

export const analyzeLocalVmwareBundle = async (files, fallbackName = 'vmware-local') => {
  const vmxFile = files.find((file) => file.name.toLowerCase().endsWith('.vmx'))
  if (!vmxFile) {
    throw new Error('Select the .vmx file together with the VMware disk files.')
  }

  const vmxText = await vmxFile.text()
  const vmxData = parseVmx(vmxText)
  const filesByName = new Map(files.map((file) => [file.name, file]))
  const vmName = vmxData.displayName || fileStem(vmxFile.name) || fallbackName

  const details = {
    name: vmName,
    uuid: vmxData['uuid.bios'] || vmxData['uuid.location'] || '',
    state: 'local-browser',
    hypervisor: 'vmware-workstation',
    specs: extractSpecs(vmxData),
    disks: extractDisks(vmxData, filesByName),
    network: extractNetwork(vmxData),
    vmx_path: vmxFile.name,
    selected_files: files.map((file) => ({ name: file.name, size_bytes: file.size })),
  }

  const analysis = analyzeVmDetails(details)
  const conversionPlan = buildConversionPlan(details, analysis)
  const strategy = chooseLocalStrategy(analysis, conversionPlan)

  return {
    vm_name: vmName,
    source: 'local-browser-vmware',
    details,
    analysis,
    conversion_plan: conversionPlan,
    strategy,
  }
}
