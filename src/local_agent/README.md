# Local Agent

This package contains the user-side local agent for hypervisors that are not directly visible from the bastion backend.

## Current scope

- local `KVM` discovery
- local `Hyper-V` discovery
- local health endpoint
- local prepare endpoint to expose the main disk path and VM metadata

## Start

```bash
python src/main.py agent
```

## Main endpoints

- `GET /health`
- `GET /api/v1/discovery/sources`
- `GET /api/v1/discovery/kvm`
- `GET /api/v1/discovery/kvm/{vm_name}`
- `GET /api/v1/discovery/hyperv`
- `GET /api/v1/discovery/hyperv/{vm_name}`
- `GET /api/v1/prepare/{source}/{vm_name}`

## Next step

Wire the frontend to this local agent, then add a bastion upload/handoff flow so KVM and Hyper-V can be migrated from the UI only.
