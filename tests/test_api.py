"""
Tests API basiques sans TestClient (evite les blocages libvirt)
"""

import pytest
from fastapi import BackgroundTasks

from src.api.main import (
    config,
    job_store,
    kvm_discoverer,
    health_check,
    analyze_vm_for_migration,
    plan_migration,
    start_migration_job,
    get_migration_status,
    migrate_to_openshift,
    OpenShiftMigrationRequest
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
    monkeypatch.setattr("src.api.main.check_tools", lambda: {
        "oc": True,
        "virtctl": False,
        "qemu-img": True
    })

    payload = await health_check()
    assert payload["status"] == "healthy"
    assert payload["services"]["tools"] == {
        "oc": True,
        "virtctl": False,
        "qemu-img": True
    }

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


@pytest.mark.asyncio
async def test_migrate_to_openshift_runs_in_background(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_REAL_MIGRATION", True)

    calls = []

    def fake_ensure_namespace(namespace):
        calls.append(("namespace", namespace))

    def fake_convert(path, fmt):
        calls.append(("convert", path, fmt))
        return "./data/test.qcow2"

    class FakeUploadResult:
        pvc_name = "target-vm-disk"
        namespace = "vm-migration"
        image_path = "./data/test.qcow2"
        size = "20Gi"
        uploadproxy_url = "https://uploadproxy.example"

    def fake_upload(image_path, pvc_name, size, namespace):
        calls.append(("upload", image_path, pvc_name, size, namespace))
        return FakeUploadResult()

    def fake_manifest(**kwargs):
        calls.append(("manifest", kwargs["vm_name"], kwargs["namespace"], kwargs["pvc_name"]))
        return {"kind": "VirtualMachine"}

    def fake_apply(manifest):
        calls.append(("apply", manifest["kind"]))

    monkeypatch.setattr("src.api.main.ensure_namespace", fake_ensure_namespace)
    monkeypatch.setattr("src.api.main.convert_disk_if_needed", fake_convert)
    monkeypatch.setattr("src.api.main.upload_disk", fake_upload)
    monkeypatch.setattr("src.api.main.build_vm_manifest", fake_manifest)
    monkeypatch.setattr("src.api.main.apply_manifest", fake_apply)

    request = OpenShiftMigrationRequest(
        source_disk_path="/tmp/source.vmdk",
        source_disk_format="vmdk",
        target_vm_name="target-vm"
    )
    background_tasks = BackgroundTasks()

    response = await migrate_to_openshift("source-vm", request, background_tasks)
    assert response["status"] == "queued"
    assert response["job_id"]
    assert calls == []

    await background_tasks()

    status = await get_migration_status(response["job_id"])
    assert status["status"] == "completed"
    assert [step["name"] for step in status["steps"]] == [
        "namespace",
        "conversion",
        "upload",
        "apply-manifest"
    ]
    assert [call[0] for call in calls] == [
        "namespace",
        "convert",
        "upload",
        "manifest",
        "apply"
    ]

    # Nettoyage pour eviter tout couplage entre tests.
    job_store._jobs.pop(response["job_id"], None)
