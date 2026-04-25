import { useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import Input from '../components/Input'

const SETTINGS_KEY = 'migration-tool-settings'

const defaultSettings = {
  kubeconfig: '',
  storageClass: 'ocs-storagecluster-ceph-rbd',
  cdiOption: 'optimized',
  virtV2vOption: 'balanced',
  notifyEmail: true,
  notifyInApp: true,
  notifyWebhook: false,
  webhookUrl: '',
}

const SettingsPage = () => {
  const [settings, setSettings] = useState(() => {
    try {
      const raw = window.localStorage.getItem(SETTINGS_KEY)
      if (!raw) return defaultSettings
      const parsed = JSON.parse(raw)
      return { ...defaultSettings, ...parsed }
    } catch {
      return defaultSettings
    }
  })
  const [saved, setSaved] = useState(false)

  const update = (key, value) => {
    setSaved(false)
    setSettings((prev) => ({ ...prev, [key]: value }))
  }

  const onSave = () => {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
    setSaved(true)
  }

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Configure cluster connectivity, migration defaults, and notification behavior.</p>
        </div>
      </header>

      <section className="grid">
        <Card className="wide" title="Cluster Configuration" actions={<Button onClick={onSave}>Save Settings</Button>}>
          <div className="settings-layout">
            <label className="field">
              <span className="field-label">Cluster kubeconfig</span>
              <textarea
                className="input settings-textarea"
                rows="7"
                value={settings.kubeconfig}
                onChange={(e) => update('kubeconfig', e.target.value)}
                placeholder="Paste kubeconfig content here"
              />
            </label>
            <label className="field">
              <span className="field-label">Default Storage Class</span>
              <Input value={settings.storageClass} onChange={(e) => update('storageClass', e.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">CDI Option</span>
              <select className="input" value={settings.cdiOption} onChange={(e) => update('cdiOption', e.target.value)}>
                <option value="optimized">Optimized</option>
                <option value="safe">Safe</option>
                <option value="fast">Fast</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">virt-v2v Option</span>
              <select className="input" value={settings.virtV2vOption} onChange={(e) => update('virtV2vOption', e.target.value)}>
                <option value="balanced">Balanced</option>
                <option value="compatibility">Compatibility-first</option>
                <option value="performance">Performance-first</option>
              </select>
            </label>
          </div>
        </Card>

        <Card title="Notification Preferences">
          <div className="toggle-list">
            <label><input type="checkbox" checked={settings.notifyEmail} onChange={(e) => update('notifyEmail', e.target.checked)} /> Email notifications</label>
            <label><input type="checkbox" checked={settings.notifyInApp} onChange={(e) => update('notifyInApp', e.target.checked)} /> In-app alerts</label>
            <label><input type="checkbox" checked={settings.notifyWebhook} onChange={(e) => update('notifyWebhook', e.target.checked)} /> Webhook</label>
            {settings.notifyWebhook ? (
              <Input placeholder="https://hooks.example.com/migration" value={settings.webhookUrl} onChange={(e) => update('webhookUrl', e.target.value)} />
            ) : null}
          </div>
          {saved ? <p className="success">Settings saved locally.</p> : null}
        </Card>
      </section>
    </div>
  )
}

export default SettingsPage
