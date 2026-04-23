#!/usr/bin/env python3
"""
Local agent API for user-side hypervisors.
"""

from __future__ import annotations

import logging
import platform
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import config
from src.discovery.kvm_discoverer import KVMDiscoverer
from src.local_agent.hyperv_discoverer import HyperVDiscoverer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PFE Migration Local Agent",
    description="Agent local pour la decouverte des hyperviseurs sur le poste utilisateur.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.LOCAL_AGENT_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

kvm_discoverer = KVMDiscoverer(connection_uri=config.KVM_CONNECTION_URI)
hyperv_discoverer = HyperVDiscoverer()


def _require_local_agent_auth(x_agent_token: str | None = Header(default=None, alias="X-Agent-Token")):
    if not config.LOCAL_AGENT_TOKEN:
        return
    if x_agent_token != config.LOCAL_AGENT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid local agent token",
        )


def _ensure_local_kvm_connected() -> None:
    if kvm_discoverer.conn is None and not kvm_discoverer.connect():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Local agent cannot connect to KVM via '{kvm_discoverer.connection_uri}'. "
                f"{kvm_discoverer.last_error or 'Check libvirt on the user machine.'}"
            ),
        )


def _select_primary_disk(details: Dict) -> Dict:
    disks = details.get("disks") or []
    candidates = [disk for disk in disks if (disk.get("device") or "disk") == "disk" and disk.get("path")]
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No primary disk was detected for this VM.",
        )
    return candidates[0]


@app.on_event("shutdown")
async def _shutdown_event():
    kvm_discoverer.disconnect()


@app.get("/health")
async def health(_: None = Depends(_require_local_agent_auth)):
    kvm_ready = kvm_discoverer.conn is not None or kvm_discoverer.connect()
    hyperv_ready = hyperv_discoverer.available
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": {
            "host_platform": platform.platform(),
            "python_platform": platform.python_version(),
        },
        "services": {
            "kvm_connection": bool(kvm_ready),
            "kvm_uri": kvm_discoverer.connection_uri,
            "kvm_last_error": kvm_discoverer.last_error or None,
            "hyperv_available": bool(hyperv_ready),
            "hyperv_last_error": hyperv_discoverer.last_error or None,
        },
    }


@app.get("/api/v1/discovery/sources", response_model=List[Dict])
async def list_sources(_: None = Depends(_require_local_agent_auth)):
    return [
        {
            "source": "kvm",
            "available": bool(kvm_discoverer.conn is not None or kvm_discoverer.connect()),
            "uri": kvm_discoverer.connection_uri,
            "last_error": kvm_discoverer.last_error or None,
        },
        {
            "source": "hyperv",
            "available": bool(hyperv_discoverer.available),
            "last_error": hyperv_discoverer.last_error or None,
        },
    ]


@app.get("/api/v1/discovery/kvm", response_model=List[Dict])
async def discover_kvm(_: None = Depends(_require_local_agent_auth)):
    _ensure_local_kvm_connected()
    return kvm_discoverer.list_vms()


@app.get("/api/v1/discovery/kvm/{vm_name}")
async def get_kvm(vm_name: str, _: None = Depends(_require_local_agent_auth)):
    _ensure_local_kvm_connected()
    details = kvm_discoverer.get_vm_details(vm_name)
    if details is None:
        raise HTTPException(status_code=404, detail=f"KVM VM '{vm_name}' not found")
    return details


@app.get("/api/v1/discovery/hyperv", response_model=List[Dict])
async def discover_hyperv(_: None = Depends(_require_local_agent_auth)):
    return hyperv_discoverer.list_vms()


@app.get("/api/v1/discovery/hyperv/{vm_name}")
async def get_hyperv(vm_name: str, _: None = Depends(_require_local_agent_auth)):
    details = hyperv_discoverer.get_vm_details(vm_name)
    if details is None:
        raise HTTPException(status_code=404, detail=f"Hyper-V VM '{vm_name}' not found")
    return details


@app.get("/api/v1/prepare/{source}/{vm_name}")
async def prepare_vm(source: str, vm_name: str, _: None = Depends(_require_local_agent_auth)):
    normalized = (source or "").lower().strip()
    if normalized == "kvm":
        _ensure_local_kvm_connected()
        details = kvm_discoverer.get_vm_details(vm_name)
    elif normalized in {"hyperv", "hyper-v"}:
        details = hyperv_discoverer.get_vm_details(vm_name)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported local source: {source}")

    if details is None:
        raise HTTPException(status_code=404, detail=f"VM '{vm_name}' not found")

    primary_disk = _select_primary_disk(details)
    return {
        "vm_name": vm_name,
        "source": normalized,
        "details": details,
        "primary_disk": {
            "path": primary_disk.get("path", ""),
            "format": primary_disk.get("format", "raw"),
            "bus": primary_disk.get("bus", "auto"),
        },
        "status": "ready-for-next-phase",
        "next_action": (
            "Expose this local agent to the frontend, then add a backend handoff "
            "for disk upload/streaming from the user machine to the bastion."
        ),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.local_agent.main:app",
        host=config.LOCAL_AGENT_HOST,
        port=config.LOCAL_AGENT_PORT,
        reload=config.API_DEBUG,
    )
