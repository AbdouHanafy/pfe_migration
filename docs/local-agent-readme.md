# Local Agent README

## Goal

The local agent is the missing bridge between:

- the UI used by the end user
- the bastion backend used for orchestration
- local hypervisors that only exist on the user machine

This solves the main architecture gap we identified:

- `VMware Workstation local` can already work with a browser-assisted upload flow
- `KVM local` cannot be discovered reliably from the bastion alone
- `Hyper-V local` has the same problem

So the best long-term design is:

1. frontend UI
2. bastion backend
3. local agent on the user machine

## What We Already Completed

### Bastion backend and UI

- built the FastAPI backend for discovery, analysis, planning, and migration orchestration
- built the React UI for:
  - `Health`
  - `Discovery`
  - `Analyze`
  - `Plan`
  - real OpenShift migration
- integrated JWT authentication between frontend and backend

### VMware Workstation flow

- added browser-side parsing for local VMware bundles
- supported `.vmx` + split `.vmdk` bundles
- added backend upload/prepare flow for VMware local files
- validated a real VMware to OpenShift migration end-to-end

### OpenShift migration flow

- disk normalization with `qemu-img`
- DataVolume creation/import
- VM manifest generation
- VM creation in OpenShift Virtualization
- successful validation of a running VM on OpenShift

### KVM improvements already done

- backend supports `KVM_URI`
- KVM source disk can now be inferred automatically during migration
- health/discovery now expose clearer KVM connection diagnostics

## What We Added Now

We introduced a first local-agent slice inside the same repository.

### New code

- [src/local_agent/main.py](/C:/Users/abdou/Desktop/PFE/dev/pfe_migration/src/local_agent/main.py)
- [src/local_agent/hyperv_discoverer.py](/C:/Users/abdou/Desktop/PFE/dev/pfe_migration/src/local_agent/hyperv_discoverer.py)
- [src/local_agent/__init__.py](/C:/Users/abdou/Desktop/PFE/dev/pfe_migration/src/local_agent/__init__.py)

### New config

- `LOCAL_AGENT_HOST`
- `LOCAL_AGENT_PORT`
- `LOCAL_AGENT_TOKEN`
- `LOCAL_AGENT_CORS_ORIGINS`

Defined in [src/config.py](/C:/Users/abdou/Desktop/PFE/dev/pfe_migration/src/config.py).

### New local-agent capabilities

- local `KVM` discovery through libvirt
- local `Hyper-V` discovery through PowerShell
- local health endpoint
- local `prepare` endpoint to expose:
  - VM details
  - primary disk path
  - source disk format

### New startup mode

You can now start the local agent with:

```bash
python src/main.py agent
```

## Current Local Agent API

### Health

```http
GET /health
```

Returns:

- agent host/platform information
- `kvm_connection`
- `kvm_uri`
- `kvm_last_error`
- `hyperv_available`
- `hyperv_last_error`

### Discovery

```http
GET /api/v1/discovery/sources
GET /api/v1/discovery/kvm
GET /api/v1/discovery/kvm/{vm_name}
GET /api/v1/discovery/hyperv
GET /api/v1/discovery/hyperv/{vm_name}
```

### Prepare

```http
GET /api/v1/prepare/{source}/{vm_name}
```

This returns the VM details plus the primary disk information that will be needed in the next phase.

## What Is Still Missing

This is the important truth: the local agent is now scaffolded and wired into the frontend for discovery and planning, but the full UI-only migration path is still not finished yet.

Still missing:

- secure handoff between local agent and bastion backend
- disk upload or streaming from the user machine to the bastion
- Hyper-V disk conversion path validation
- full end-to-end tests for:
  - KVM local -> bastion -> OpenShift
  - Hyper-V local -> bastion -> OpenShift

Already done now in the frontend:

- local agent health check
- local KVM discovery
- local Hyper-V discovery
- local `Analyze`
- local `Plan`
- local `Prepare Via Agent`
- automatic prefilling of the disk path and format in the migration form
- real migration button blocked clearly until the disk handoff phase exists

## Best Next Implementation Plan

### Phase 1: Connect the UI to the local agent

Add in the frontend:

- `Local Agent URL`
- `Agent token`
- buttons to:
  - test local agent health
  - discover KVM locally
  - discover Hyper-V locally

Expected result:

- the user can stay in the UI only
- no bastion shell is needed for local discovery

### Phase 2: Bastion handoff

Add a backend flow where the local agent can:

- upload the selected disk to the bastion
- or stream it to a bastion upload endpoint

Expected result:

- the bastion gets a real local disk without direct access to the user filesystem

### Phase 3: Trigger real migration

Once the disk reaches the bastion:

- backend uses the existing OpenShift migration flow
- same logic as the current VMware migration path

Expected result:

- KVM local and Hyper-V local become real UI-only flows

### Phase 4: Hardening

- add TLS or SSH-tunneled local agent communication
- rotate or mint per-session agent tokens
- restrict allowed origins
- add agent registration / pairing

## Recommended Demo Story For The PFE

Today, the strongest and most honest story is:

1. VMware Workstation local is already validated end-to-end
2. the architecture gap for local KVM and Hyper-V was identified correctly
3. a local-agent solution was chosen because it is the right engineering answer
4. the first usable local-agent slice is now implemented
5. the next milestone is connecting the UI to that agent and then forwarding disks to the bastion

## Runbook

### Start the bastion backend

```bash
python src/main.py api
```

### Start the local agent

```bash
python src/main.py agent
```

### Suggested environment variables

```bash
export LOCAL_AGENT_HOST=127.0.0.1
export LOCAL_AGENT_PORT=8010
export LOCAL_AGENT_TOKEN=change-me
export KVM_URI=qemu:///system
```

On Windows PowerShell:

```powershell
$env:LOCAL_AGENT_HOST="127.0.0.1"
$env:LOCAL_AGENT_PORT="8010"
$env:LOCAL_AGENT_TOKEN="change-me"
```

## Summary

The local agent is now the correct foundation for supporting:

- `KVM local`
- `Hyper-V local`

without forcing end users to access the bastion manually.

The next real milestone is not more hypervisor parsing.  
It is the integration between:

- the UI
- the local agent
- the bastion backend
