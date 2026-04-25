import { AnimatePresence, motion } from 'framer-motion'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from 'react'
import { login as loginRequest, register as registerRequest } from './services/authService'

type StatusTone = 'done' | 'running' | 'failed' | 'info'

type NavItem = {
  label: string
  path: string
}

type HealthResponse = {
  status?: string
  timestamp?: string
  services?: {
    kvm_connection?: boolean
    kvm_uri?: string
    kvm_last_error?: string | null
    vmware_esxi_configured?: boolean
    tools?: Record<string, boolean>
  }
}

type MigrationJob = {
  job_id: string
  vm_name: string
  status: string
  created_at?: string
  updated_at?: string
  logs?: string[]
  error?: string | null
}

type VmInfo = {
  name: string
  state?: string
  source: 'kvm' | 'vmware-workstation' | 'vmware-esxi'
  cpu_count?: number
  memory_mb?: number
  disks?: unknown[]
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/' },
  { label: 'New Migration', path: '/new-migration' },
  { label: 'Migration Progress', path: '/progress' },
  { label: 'VM Management', path: '/vms' },
  { label: 'History', path: '/history' },
]

const pageMotion = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -14 },
  transition: { duration: 0.28, ease: 'easeOut' },
}

const AUTH_KEY = 'ocpmigrate-auth'
const TOKEN_KEY = 'ocpmigrate-token'
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8000'

const getToken = () => {
  try {
    return window.localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

const apiJson = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const token = getToken()
  const headers = new Headers(init?.headers || {})
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      if (data?.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const safeApiJson = async <T,>(path: string, fallback: T, init?: RequestInit): Promise<T> => {
  try {
    return await apiJson<T>(path, init)
  } catch {
    return fallback
  }
}

const mapJobTone = (status?: string): StatusTone => {
  const s = (status || '').toLowerCase()
  if (s.includes('fail') || s.includes('error')) return 'failed'
  if (s.includes('done') || s.includes('success') || s.includes('completed')) return 'done'
  if (s.includes('running') || s.includes('progress') || s.includes('queued') || s.includes('pending')) return 'running'
  return 'info'
}

const formatDate = (value?: string) => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

const loadAuthFlag = () => {
  try {
    return window.localStorage.getItem(AUTH_KEY) === 'true' && !!window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return false
  }
}

const persistAuthFlag = (value: boolean) => {
  try {
    if (value) {
      window.localStorage.setItem(AUTH_KEY, 'true')
    } else {
      window.localStorage.removeItem(AUTH_KEY)
    }
  } catch {
    // Ignore storage failures and keep UI usable.
  }
}

const persistToken = (token: string | null) => {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_KEY, token)
    } else {
      window.localStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    // Ignore storage failures and keep UI usable.
  }
}

const App = () => {
  const location = useLocation()
  const [isAuthenticated, setIsAuthenticated] = useState(loadAuthFlag)
  const [health, setHealth] = useState<HealthResponse | null>(null)

  useEffect(() => {
    if (!isAuthenticated) return
    safeApiJson<HealthResponse>('/health', null as unknown as HealthResponse).then((data) => {
      setHealth(data || null)
    })
  }, [isAuthenticated])

  const onLogin = (token: string) => {
    setIsAuthenticated(true)
    persistAuthFlag(true)
    persistToken(token)
  }

  const onLogout = () => {
    setIsAuthenticated(false)
    persistAuthFlag(false)
    persistToken(null)
  }

  if (!isAuthenticated) {
    return <LoginPage onLogin={onLogin} />
  }

  const healthTone: StatusTone = (health?.status || '').toLowerCase() === 'healthy' ? 'done' : 'running'

  return (
    <div className="min-h-screen text-primary">
      <div className="bg-grid" />
      <div className="mx-auto flex min-h-screen max-w-[1600px] gap-6 px-4 py-6 lg:px-8">
        <aside className="hidden w-72 shrink-0 rounded-2xl border border-line bg-surface/95 p-6 shadow-panel lg:block">
          <p className="font-display text-2xl font-extrabold tracking-[-0.02em]">OCPMigrate</p>
          <p className="mt-2 font-mono text-xs text-muted">OpenShift VM Migration Ops Console</p>
          <nav className="mt-8 flex flex-col gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `rounded-lg border px-4 py-3 text-sm font-mono transition ${
                    isActive
                      ? 'border-accent bg-accent/10 text-primary'
                      : 'border-line bg-[#0f1529] text-muted hover:text-primary'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="flex-1">
          <header className="mb-5 rounded-2xl border border-line bg-surface/90 px-5 py-4 shadow-panel">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-info">Mission Control</p>
                <h1 className="font-display text-3xl font-extrabold tracking-[-0.02em]">OCPMigrate Console</h1>
              </div>
              <div className="flex items-center gap-3 font-mono text-xs">
                <span className="rounded-full border border-line bg-[#0f1529] px-3 py-1 text-muted">API: {API_BASE}</span>
                <span className={`rounded-full border px-3 py-1 ${healthTone === 'done' ? 'border-accent bg-accent/10 text-accent' : 'border-running bg-running/10 text-running'}`}>
                  {health?.status || 'connecting'}
                </span>
                <button onClick={onLogout} className="rounded-md border border-line px-3 py-1 text-primary hover:border-info hover:text-info">
                  Logout
                </button>
              </div>
            </div>
          </header>

          <AnimatePresence mode="wait">
            <motion.div key={location.pathname} {...pageMotion}>
              <Routes location={location}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/new-migration" element={<NewMigrationPage />} />
                <Route path="/progress" element={<MigrationProgressPage />} />
                <Route path="/vms" element={<VmManagementPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}

const LoginPage = ({ onLogin }: { onLogin: (token: string) => void }) => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const matricule = username.trim()
    const pwd = password.trim()
    if (!matricule || !pwd) return
    setIsSubmitting(true)
    setError('')
    setSuccess('')
    try {
      if (mode === 'register') {
        await registerRequest({ baseUrl: API_BASE, matricule, password: pwd })
        setSuccess('Account created. You can now login.')
        setMode('login')
      } else {
        const data = await loginRequest({ baseUrl: API_BASE, matricule, password: pwd })
        onLogin(data.access_token)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-base text-primary">
      <div className="bg-grid" />
      <main className="mx-auto grid min-h-screen max-w-md place-items-center px-4">
        <motion.form
          onSubmit={submit}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
          className="w-full rounded-2xl border border-line bg-surface p-6 shadow-panel"
        >
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-info">OCPMigrate Secure Access</p>
          <h1 className="mt-2 font-display text-3xl font-extrabold tracking-[-0.02em]">{mode === 'login' ? 'Login' : 'Register'}</h1>
          <p className="mt-1 font-mono text-xs text-muted">
            {mode === 'login' ? 'Authenticate to access the OpenShift migration control room.' : 'Create your account with matricule and password.'}
          </p>
          <div className="mt-6 space-y-3">
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Matricule"
              className="w-full rounded-md border border-line bg-[#0f1529] px-3 py-2 font-mono text-sm outline-none focus:border-info"
            />
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Password"
              className="w-full rounded-md border border-line bg-[#0f1529] px-3 py-2 font-mono text-sm outline-none focus:border-info"
            />
          </div>
          {error ? <p className="mt-3 font-mono text-xs text-failed">{error}</p> : null}
          {success ? <p className="mt-3 font-mono text-xs text-accent">{success}</p> : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-5 w-full rounded-md bg-accent px-4 py-2 font-mono text-sm font-bold text-[#041109] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? 'Please wait...' : mode === 'login' ? 'Enter Mission Control' : 'Create Account'}
          </button>
          <button
            type="button"
            onClick={() => {
              setMode((prev) => (prev === 'login' ? 'register' : 'login'))
              setError('')
              setSuccess('')
            }}
            className="mt-3 w-full rounded-md border border-line px-4 py-2 font-mono text-xs text-muted hover:text-primary"
          >
            {mode === 'login' ? 'Need an account? Register' : 'Already have an account? Login'}
          </button>
        </motion.form>
      </main>
    </div>
  )
}

const Panel = ({ title, children, tone }: { title: string; children: ReactNode; tone?: StatusTone }) => (
  <section className={`rounded-xl border border-line bg-surface p-4 shadow-panel ${tone ? `status-${tone}` : ''}`}>
    <h2 className="font-display text-xl font-extrabold tracking-[-0.01em]">{title}</h2>
    <div className="mt-4">{children}</div>
  </section>
)

const StatusBadge = ({ tone, children }: { tone: StatusTone; children: ReactNode }) => (
  <span className={`inline-flex items-center rounded-full px-3 py-1 font-mono text-xs badge-${tone}`}>{children}</span>
)

const Progress = ({ value, tone }: { value: number; tone?: StatusTone }) => (
  <div className="h-1.5 w-full overflow-hidden rounded-full border border-line bg-[#0d1324]">
    <motion.div
      initial={{ width: 0 }}
      animate={{ width: `${value}%` }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className={`h-full ${tone === 'failed' ? 'bg-failed' : tone === 'running' ? 'bg-running' : 'bg-accent'} shadow-glow`}
    />
  </div>
)

const DashboardPage = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [jobs, setJobs] = useState<MigrationJob[]>([])
  const [vms, setVms] = useState<VmInfo[]>([])
  const [error, setError] = useState('')

  const load = async () => {
    setError('')
    try {
      const [healthData, jobsData, kvm, ws, esxi] = await Promise.all([
        apiJson<HealthResponse>('/health'),
        safeApiJson<MigrationJob[]>('/api/v1/migration/jobs', []),
        safeApiJson<VmInfo[]>('/api/v1/discovery/kvm', []),
        safeApiJson<VmInfo[]>('/api/v1/discovery/vmware-workstation', []),
        safeApiJson<VmInfo[]>('/api/v1/discovery/vmware-esxi', []),
      ])

      setHealth(healthData)
      setJobs(jobsData)
      setVms([
        ...kvm.map((vm) => ({ ...vm, source: 'kvm' as const })),
        ...ws.map((vm) => ({ ...vm, source: 'vmware-workstation' as const })),
        ...esxi.map((vm) => ({ ...vm, source: 'vmware-esxi' as const })),
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const runningJobs = jobs.filter((j) => mapJobTone(j.status) === 'running')
  const failedJobs = jobs.filter((j) => mapJobTone(j.status) === 'failed')
  const doneJobs = jobs.filter((j) => mapJobTone(j.status) === 'done')
  const successRate = jobs.length ? Math.round((doneJobs.length / jobs.length) * 1000) / 10 : 0

  const toolStatus = health?.services?.tools || {}
  const toolsOk = Object.values(toolStatus).filter(Boolean).length
  const toolsTotal = Object.keys(toolStatus).length

  const stats = [
    { label: 'Discovered VMs', value: String(vms.length), tone: 'done' as StatusTone, progress: Math.min(100, vms.length * 10) },
    { label: 'Backend Tools', value: toolsTotal ? `${toolsOk}/${toolsTotal}` : '-', tone: toolsOk === toolsTotal && toolsTotal > 0 ? 'done' as StatusTone : 'running' as StatusTone, progress: toolsTotal ? Math.round((toolsOk / toolsTotal) * 100) : 0 },
    { label: 'Active Migrations', value: String(runningJobs.length), tone: 'running' as StatusTone, progress: Math.min(100, runningJobs.length * 20) },
    { label: 'Failed Jobs', value: String(failedJobs.length), tone: failedJobs.length ? 'failed' as StatusTone : 'done' as StatusTone, progress: Math.min(100, failedJobs.length * 20) },
  ]

  const logLines = jobs
    .flatMap((j) => (j.logs || []).slice(-2).map((line) => `[${j.vm_name}] ${line}`))
    .slice(-8)

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <section className="xl:col-span-2 grid gap-4 md:grid-cols-2">
        {stats.map((item) => (
          <Panel key={item.label} title={item.label} tone={item.tone}>
            <p className="font-display text-4xl font-extrabold">{item.value}</p>
            <div className="mt-3"><Progress value={item.progress} tone={item.tone} /></div>
          </Panel>
        ))}

        <Panel title="Active Migrations" tone="running">
          <div className="space-y-3 font-mono text-sm">
            {runningJobs.length === 0 ? <p className="text-muted">No active migration jobs.</p> : null}
            {runningJobs.map((job) => (
              <div key={job.job_id} className="rounded-lg border border-line bg-[#0f1529] p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span>{job.vm_name}</span>
                  <StatusBadge tone="running">{job.status}</StatusBadge>
                </div>
                <p className="font-mono text-xs text-muted">{job.job_id}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Success Rate" tone="done">
          <div className="flex items-center gap-6">
            <div className="relative h-28 w-28 rounded-full border border-line">
              <svg className="h-28 w-28 -rotate-90">
                <circle cx="56" cy="56" r="44" className="stroke-line fill-none" strokeWidth="10" />
                <circle cx="56" cy="56" r="44" className="stroke-accent fill-none" strokeWidth="10" strokeDasharray="276" strokeDashoffset={String(276 - (276 * successRate) / 100)} />
              </svg>
              <span className="absolute inset-0 grid place-items-center font-mono text-sm">{successRate}%</span>
            </div>
            <div className="font-mono text-xs text-muted">
              <p>Total jobs</p>
              <p className="mt-2 text-primary">{jobs.length} tracked jobs</p>
              <p className="text-primary">{doneJobs.length} completed successfully</p>
            </div>
          </div>
        </Panel>
      </section>

      <Panel title="Real-Time Log Stream" tone="info">
        {error ? <p className="mb-3 font-mono text-xs text-failed">{error}</p> : null}
        <div className="mb-3">
          <button onClick={load} className="rounded-md border border-line px-3 py-1 font-mono text-xs text-primary">Refresh</button>
        </div>
        <TerminalPanel lines={logLines.length ? logLines : ['No logs yet from backend jobs.']} />
      </Panel>
    </div>
  )
}

const NewMigrationPage = () => {
  const [vmName, setVmName] = useState('')
  const [source, setSource] = useState<'kvm' | 'vmware-workstation' | 'vmware-esxi'>('kvm')
  const [analyzeData, setAnalyzeData] = useState<unknown>(null)
  const [planData, setPlanData] = useState<unknown>(null)
  const [startData, setStartData] = useState<unknown>(null)
  const [error, setError] = useState('')
  const [loadingAction, setLoadingAction] = useState('')

  const runAction = async (kind: 'analyze' | 'plan' | 'start') => {
    if (!vmName.trim()) {
      setError('Enter a VM name first.')
      return
    }
    setLoadingAction(kind)
    setError('')
    try {
      if (kind === 'analyze') {
        const data = await apiJson(`/api/v1/migration/analyze/${encodeURIComponent(vmName.trim())}?source=${encodeURIComponent(source)}`)
        setAnalyzeData(data)
      } else if (kind === 'plan') {
        const data = await apiJson(`/api/v1/migration/plan/${encodeURIComponent(vmName.trim())}?source=${encodeURIComponent(source)}`)
        setPlanData(data)
      } else {
        const data = await apiJson(`/api/v1/migration/start/${encodeURIComponent(vmName.trim())}?source=${encodeURIComponent(source)}`, { method: 'POST' })
        setStartData(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Migration action failed')
    } finally {
      setLoadingAction('')
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <section className="xl:col-span-2 space-y-4">
        <Panel title="Real Migration Actions" tone="info">
          <div className="grid gap-3 md:grid-cols-2">
            <input
              value={vmName}
              onChange={(e) => setVmName(e.target.value)}
              placeholder="VM name"
              className="rounded-md border border-line bg-[#0f1529] px-3 py-2 font-mono text-sm outline-none focus:border-info"
            />
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as 'kvm' | 'vmware-workstation' | 'vmware-esxi')}
              className="rounded-md border border-line bg-[#0f1529] px-3 py-2 font-mono text-sm outline-none focus:border-info"
            >
              <option value="kvm">kvm</option>
              <option value="vmware-workstation">vmware-workstation</option>
              <option value="vmware-esxi">vmware-esxi</option>
            </select>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button onClick={() => runAction('analyze')} className="rounded-md border border-info px-4 py-2 font-mono text-xs text-info" disabled={loadingAction !== ''}>
              {loadingAction === 'analyze' ? 'Analyzing...' : 'Analyze'}
            </button>
            <button onClick={() => runAction('plan')} className="rounded-md border border-running px-4 py-2 font-mono text-xs text-running" disabled={loadingAction !== ''}>
              {loadingAction === 'plan' ? 'Planning...' : 'Plan'}
            </button>
            <button onClick={() => runAction('start')} className="rounded-md bg-accent px-4 py-2 font-mono text-xs text-[#041109]" disabled={loadingAction !== ''}>
              {loadingAction === 'start' ? 'Starting...' : 'Start Migration'}
            </button>
          </div>
          {error ? <p className="mt-3 font-mono text-xs text-failed">{error}</p> : null}
        </Panel>

        <Panel title="Analyze Result" tone="info">
          <pre className="overflow-auto rounded-lg border border-line bg-[#0f1529] p-3 font-mono text-xs text-primary">{JSON.stringify(analyzeData, null, 2) || 'Run Analyze to see backend output.'}</pre>
        </Panel>
      </section>

      <section className="space-y-4">
        <Panel title="Plan Result" tone="running">
          <pre className="overflow-auto rounded-lg border border-line bg-[#0f1529] p-3 font-mono text-xs text-primary">{JSON.stringify(planData, null, 2) || 'Run Plan to see backend output.'}</pre>
        </Panel>
        <Panel title="Start Result" tone="done">
          <pre className="overflow-auto rounded-lg border border-line bg-[#0f1529] p-3 font-mono text-xs text-primary">{JSON.stringify(startData, null, 2) || 'Run Start Migration to create a job.'}</pre>
        </Panel>
      </section>
    </div>
  )
}

const MigrationProgressPage = () => {
  const [jobs, setJobs] = useState<MigrationJob[]>([])
  const [selectedJob, setSelectedJob] = useState('')
  const [statusData, setStatusData] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')

  const refreshJobs = async () => {
    try {
      const data = await apiJson<MigrationJob[]>('/api/v1/migration/jobs')
      setJobs(data)
      if (!selectedJob && data[0]?.job_id) {
        setSelectedJob(data[0].job_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
    }
  }

  const refreshStatus = async (jobId: string) => {
    if (!jobId) return
    try {
      const data = await apiJson<Record<string, unknown>>(`/api/v1/migration/status/${encodeURIComponent(jobId)}`)
      setStatusData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load job status')
    }
  }

  useEffect(() => {
    refreshJobs()
    const id = window.setInterval(refreshJobs, 5000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    if (selectedJob) {
      refreshStatus(selectedJob)
    }
  }, [selectedJob])

  const steps = useMemo(() => {
    const raw = (statusData?.steps as Array<Record<string, unknown>> | undefined) || []
    if (!Array.isArray(raw)) return []
    return raw.map((s) => {
      const name = String(s.name || s.step || 'step')
      const state = String(s.status || s.state || '')
      const done = /done|success|completed/i.test(state)
      return { name, done, state: state || 'running' }
    })
  }, [statusData])

  const progress = steps.length ? Math.round((steps.filter((s) => s.done).length / steps.length) * 100) : 0

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <section className="xl:col-span-2 space-y-4">
        <Panel title="Pipeline Progress" tone="running">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <select
              value={selectedJob}
              onChange={(e) => setSelectedJob(e.target.value)}
              className="rounded-md border border-line bg-[#0f1529] px-3 py-2 font-mono text-xs outline-none"
            >
              <option value="">Select a job</option>
              {jobs.map((j) => (
                <option key={j.job_id} value={j.job_id}>{j.vm_name} - {j.job_id}</option>
              ))}
            </select>
            <button onClick={refreshJobs} className="rounded-md border border-line px-3 py-2 font-mono text-xs">Refresh Jobs</button>
            <button onClick={() => refreshStatus(selectedJob)} className="rounded-md border border-line px-3 py-2 font-mono text-xs" disabled={!selectedJob}>Refresh Status</button>
          </div>
          <div className="space-y-4">
            <Progress value={progress} tone="running" />
            <div className="grid gap-3 md:grid-cols-4">
              {steps.map((step) => (
                <div key={step.name} className="rounded-lg border border-line bg-[#0f1529] p-3">
                  <p className="font-mono text-xs text-muted">{step.name}</p>
                  <div className="mt-2">
                    {step.done ? <StatusBadge tone="done">Done</StatusBadge> : <StatusBadge tone="running">{step.state}</StatusBadge>}
                  </div>
                </div>
              ))}
            </div>
            {steps.length === 0 ? <p className="font-mono text-xs text-muted">No step data yet for this job.</p> : null}
          </div>
          {error ? <p className="mt-3 font-mono text-xs text-failed">{error}</p> : null}
        </Panel>
      </section>
      <Panel title="Latest Logs" tone="info">
        <TerminalPanel lines={((statusData?.logs as string[] | undefined) || []).slice(-12).length ? ((statusData?.logs as string[] | undefined) || []).slice(-12) : ['No logs available for selected job.']} />
      </Panel>
    </div>
  )
}

const VmManagementPage = () => {
  const [vms, setVms] = useState<VmInfo[]>([])
  const [error, setError] = useState('')

  const refresh = async () => {
    setError('')
    try {
      const [kvm, ws, esxi] = await Promise.all([
        safeApiJson<VmInfo[]>('/api/v1/discovery/kvm', []),
        safeApiJson<VmInfo[]>('/api/v1/discovery/vmware-workstation', []),
        safeApiJson<VmInfo[]>('/api/v1/discovery/vmware-esxi', []),
      ])
      setVms([
        ...kvm.map((vm) => ({ ...vm, source: 'kvm' as const })),
        ...ws.map((vm) => ({ ...vm, source: 'vmware-workstation' as const })),
        ...esxi.map((vm) => ({ ...vm, source: 'vmware-esxi' as const })),
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load VMs')
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={refresh} className="rounded-md border border-line px-3 py-1.5 font-mono text-xs">Refresh Discovery</button>
        <span className="font-mono text-xs text-muted">{vms.length} VM(s) discovered</span>
      </div>
      {error ? <p className="font-mono text-xs text-failed">{error}</p> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {vms.map((vm) => {
          const tone = mapJobTone(vm.state)
          const cpu = Math.min(100, Math.max(0, (vm.cpu_count || 0) * 12))
          const ram = Math.min(100, Math.max(0, Math.round((vm.memory_mb || 0) / 128)))
          const disk = Math.min(100, Math.max(0, ((vm.disks?.length || 0) * 25)))
          return (
            <Panel key={`${vm.source}-${vm.name}`} title={vm.name} tone={tone}>
              <div className="mb-3 flex items-center justify-between">
                <StatusBadge tone={tone}>{vm.state || 'unknown'}</StatusBadge>
                <span className="rounded-md border border-line px-2 py-1 font-mono text-[10px] text-muted">{vm.source}</span>
              </div>
              <div className="space-y-3 font-mono text-xs">
                <div><p className="mb-1 text-muted">CPU Cores</p><Progress value={cpu} tone={tone} /></div>
                <div><p className="mb-1 text-muted">Memory MB</p><Progress value={ram} tone={tone} /></div>
                <div><p className="mb-1 text-muted">Disks</p><Progress value={disk} tone={tone} /></div>
              </div>
            </Panel>
          )
        })}
      </div>
    </div>
  )
}

const HistoryPage = () => {
  const [jobs, setJobs] = useState<MigrationJob[]>([])
  const [filter, setFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [error, setError] = useState('')

  const refresh = async () => {
    setError('')
    try {
      const data = await apiJson<MigrationJob[]>('/api/v1/migration/jobs')
      setJobs(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history')
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const filtered = jobs.filter((job) => {
    const textOk = !filter || job.vm_name.toLowerCase().includes(filter.toLowerCase()) || job.job_id.toLowerCase().includes(filter.toLowerCase())
    const tone = mapJobTone(job.status)
    const statusOk = statusFilter === 'all' || tone === statusFilter
    return textOk && statusOk
  })

  return (
    <Panel title="Migration History" tone="info">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-md border border-line bg-[#0f1529] px-3 py-2 font-mono text-xs outline-none"
          placeholder="Filter by VM / job id"
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-md border border-line bg-[#0f1529] px-3 py-2 font-mono text-xs outline-none">
          <option value="all">All Status</option>
          <option value="done">Done</option>
          <option value="running">Running</option>
          <option value="failed">Failed</option>
          <option value="info">Info</option>
        </select>
        <button onClick={refresh} className="rounded-md border border-info px-3 py-2 font-mono text-xs text-info">Refresh</button>
      </div>
      {error ? <p className="mb-3 font-mono text-xs text-failed">{error}</p> : null}
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[760px] text-left font-mono text-xs">
          <thead className="text-muted">
            <tr>
              <th className="border-b border-line px-3 py-3">VM</th>
              <th className="border-b border-line px-3 py-3">Job ID</th>
              <th className="border-b border-line px-3 py-3">Created</th>
              <th className="border-b border-line px-3 py-3">Updated</th>
              <th className="border-b border-line px-3 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((job) => {
              const tone = mapJobTone(job.status)
              return (
                <tr key={job.job_id}>
                  <td className="border-b border-line px-3 py-3">{job.vm_name}</td>
                  <td className="border-b border-line px-3 py-3">{job.job_id}</td>
                  <td className="border-b border-line px-3 py-3">{formatDate(job.created_at)}</td>
                  <td className="border-b border-line px-3 py-3">{formatDate(job.updated_at)}</td>
                  <td className="border-b border-line px-3 py-3">
                    <StatusBadge tone={tone}>{job.status}</StatusBadge>
                    {job.error ? <p className="mt-1 text-failed">{job.error}</p> : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

const TerminalPanel = ({ lines }: { lines: string[] }) => (
  <div className="terminal-panel rounded-lg border border-line bg-[#060b17] p-3 font-mono text-xs text-[#45da95]">
    {lines.map((line) => (
      <p key={line} className="py-0.5">{line}</p>
    ))}
    <span className="inline-block h-4 w-2 translate-y-0.5 bg-[#45da95] cursor-blink" />
  </div>
)

export default App
