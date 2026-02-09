"""
Tests API basiques sans TestClient (evite les blocages libvirt)
"""

import pytest

from src.api.main import (
    kvm_discoverer,
    health_check,
    analyze_vm_for_migration,
    plan_migration,
    start_migration_job,
    get_migration_status
)

def _mock_vm_details(name: str):
    return {
        "name": name,
        "specs": {"os_arch": "x86_64", "memory_mb": 1024, "cpus": 1},
        "disks": [{"format": "raw", "bus": "virtio", "path": "/tmp/disk.raw"}],
        "network": [{"model": "virtio"}]
    }

@pytest.mark.asyncio
async def test_health(monkeypatch):
    monkeypatch.setattr(kvm_discoverer, "connect", lambda: True)
    monkeypatch.setattr(kvm_discoverer, "disconnect", lambda: None)
    monkeypatch.setattr(kvm_discoverer, "conn", object())

    payload = await health_check()
    assert payload["status"] == "healthy"

@pytest.mark.asyncio
async def test_analyze_plan_start_status(monkeypatch):
    monkeypatch.setattr(kvm_discoverer, "connect", lambda: True)
    monkeypatch.setattr(kvm_discoverer, "disconnect", lambda: None)
    monkeypatch.setattr(kvm_discoverer, "conn", object())
    monkeypatch.setattr(kvm_discoverer, "get_vm_details", lambda name: _mock_vm_details(name))

    response = await analyze_vm_for_migration("test-vm")
    assert response["analysis"]["compatibility"] == "compatible"

    response = await plan_migration("test-vm")
    assert response["strategy"]["strategy"] == "direct"

    response = await start_migration_job("test-vm")
    job_id = response["job_id"]
    assert job_id

    status = await get_migration_status(job_id)
    assert status["status"] in ("running", "completed", "queued")
