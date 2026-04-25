import { useState } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'

const vmSeed = [
  { id: 'vm-501', name: 'erp-vm', namespace: 'prod-vms', status: 'Running', cpu: 54, ram: 61, disk: 73, console: 'https://console-openshift.example/vm/erp-vm' },
  { id: 'vm-502', name: 'legacy-payroll', namespace: 'finance-vms', status: 'Stopped', cpu: 0, ram: 0, disk: 49, console: 'https://console-openshift.example/vm/legacy-payroll' },
  { id: 'vm-503', name: 'analytics-node', namespace: 'data-vms', status: 'Running', cpu: 22, ram: 43, disk: 58, console: 'https://console-openshift.example/vm/analytics-node' },
]

const clampUsage = (value) => `${Math.min(100, Math.max(0, value))}%`

const VmManagementPage = () => {
  const [vms, setVms] = useState(vmSeed)

  const updateStatus = (id, status) => {
    setVms((prev) => prev.map((vm) => (vm.id === id ? { ...vm, status } : vm)))
  }

  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <h1>VM Management</h1>
          <p>Operate migrated OpenShift VMs and monitor resource usage from one panel.</p>
        </div>
      </header>

      <section className="grid">
        <Card className="wide" title="Migrated VMs">
          <div className="list vm-list">
            {vms.map((vm) => (
              <div key={vm.id} className="item item-stack">
                <div className="row-between">
                  <div>
                    <strong>{vm.name}</strong>
                    <p className="micro">{vm.namespace}</p>
                  </div>
                  <span className="pill">{vm.status}</span>
                </div>
                <div className="row">
                  <Button variant="ghost" onClick={() => updateStatus(vm.id, 'Running')}>Start</Button>
                  <Button variant="ghost" onClick={() => updateStatus(vm.id, 'Stopped')}>Stop</Button>
                  <Button variant="ghost" onClick={() => updateStatus(vm.id, 'Restarting')}>Restart</Button>
                  <Button onClick={() => window.open(vm.console, '_blank', 'noopener,noreferrer')}>Open VNC Console</Button>
                </div>
                <div className="usage-grid">
                  <div>
                    <p className="micro">CPU</p>
                    <div className="progress-track"><div className="progress-fill" style={{ width: clampUsage(vm.cpu) }} /></div>
                  </div>
                  <div>
                    <p className="micro">RAM</p>
                    <div className="progress-track"><div className="progress-fill" style={{ width: clampUsage(vm.ram) }} /></div>
                  </div>
                  <div>
                    <p className="micro">Disk</p>
                    <div className="progress-track"><div className="progress-fill" style={{ width: clampUsage(vm.disk) }} /></div>
                  </div>
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
