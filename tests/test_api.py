"""
Tests API basiques sans TestClient (evite les blocages libvirt)
"""

import pytest
from fastapi import BackgroundTasks
from pathlib import Path

from src.api.main import (
    config,
    job_store,
    kvm_discoverer,
    vmware_esxi_discoverer,
    health_check,
    analyze_vm_for_migration,
    plan_migration,
    start_migration_job,
    get_migration_status,
    discover_vmware_esxi_vms,
    get_vmware_esxi_vm_details,
    migrate_to_openshift,
    OpenShiftMigrationRequest,
    _build_uploaded_bundle_summary
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
async def test_vmware_esxi_discovery_and_plan(monkeypatch):
    monkeypatch.setattr(vmware_esxi_discoverer, "list_vms", lambda: [
        {"name": "esxi-vm", "uuid": "123", "state": "running", "hypervisor": "vmware-esxi"}
    ])
    monkeypatch.setattr(vmware_esxi_discoverer, "get_vm_details", lambda name: _mock_vm_details(name))

    discovered = await discover_vmware_esxi_vms()
    assert discovered[0]["hypervisor"] == "vmware-esxi"

    details = await get_vmware_esxi_vm_details("esxi-vm")
    assert details["name"] == "esxi-vm"

    response = await analyze_vm_for_migration("esxi-vm", source="vmware-esxi")
    assert response["analysis"]["compatibility"] == "compatible"

    response = await plan_migration("esxi-vm", source="vmware-esxi")
    assert response["strategy"]["strategy"] == "direct"


@pytest.mark.asyncio
async def test_migrate_to_openshift_runs_in_background(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_REAL_MIGRATION", True)
    monkeypatch.setattr(config, "OPENSHIFT_CONSOLE_URL", "https://console-openshift.example")
    monkeypatch.setattr(config, "OPENSHIFT_IMPORT_BASE_URL", "http://10.9.21.90:8000")

    calls = []

    def fake_ensure_namespace(namespace):
        calls.append(("namespace", namespace))

    def fake_normalize(path, fmt):
        calls.append(("normalize", path, fmt))
        return "./data/test.qcow2"

    class FakeDvResult:
        pvc_name = "target-vm-disk"
        namespace = "vm-migration"
        image_path = "./data/test.qcow2"
        size = "20Gi"
        import_url = "http://10.9.21.90:8000/api/v1/openshift/imports/test.qcow2"

    def fake_import(image_path, dv_name, size, namespace):
        calls.append(("http-import", image_path, dv_name, size, namespace))
        return FakeDvResult()

    def fake_wait(namespace, dv_name):
        calls.append(("wait", namespace, dv_name))
        return {"status": {"phase": "Succeeded"}}

    def fake_manifest(**kwargs):
        calls.append(("manifest", kwargs["vm_name"], kwargs["namespace"], kwargs["pvc_name"]))
        return {"kind": "VirtualMachine"}

    def fake_apply(manifest):
        calls.append(("apply", manifest["kind"]))

    monkeypatch.setattr("src.api.main.ensure_namespace", fake_ensure_namespace)
    monkeypatch.setattr("src.api.main.normalize_disk_for_http_import", fake_normalize)
    monkeypatch.setattr("src.api.main.build_import_url", lambda path: "http://10.9.21.90:8000/api/v1/openshift/imports/test.qcow2")
    monkeypatch.setattr("src.api.main.create_data_volume_http", fake_import)
    monkeypatch.setattr("src.api.main.wait_for_data_volume", fake_wait)
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
    assert response["import_mode"] == "http"
    assert response["import_url"] == "http://10.9.21.90:8000/api/v1/openshift/imports/test.qcow2"
    assert response["vm_console_url"] == (
        "https://console-openshift.example/k8s/ns/vm-migration/kubevirt.io~v1~VirtualMachine/target-vm"
    )
    assert calls == [("normalize", "/tmp/source.vmdk", "vmdk")]

    await background_tasks()

    status = await get_migration_status(response["job_id"])
    assert status["status"] == "completed"
    assert [step["name"] for step in status["steps"]] == [
        "namespace",
        "conversion",
        "http-import",
        "wait-for-import",
        "apply-manifest"
    ]
    assert [call[0] for call in calls] == [
        "normalize",
        "namespace",
        "normalize",
        "http-import",
        "wait",
        "manifest",
        "apply"
    ]

    # Nettoyage pour eviter tout couplage entre tests.
    job_store._jobs.pop(response["job_id"], None)


def test_build_uploaded_bundle_summary_detects_split_vmdk(tmp_path):
    descriptor = tmp_path / "test.vmdk"
    descriptor.write_text(
        '# Disk DescriptorFile\n'
        'RW 4192256 SPARSE "test-s001.vmdk"\n'
        'RW 4192256 SPARSE "test-s002.vmdk"\n',
        encoding="utf-8"
    )
    (tmp_path / "test-s001.vmdk").write_bytes(b"part1")
    (tmp_path / "test-s002.vmdk").write_bytes(b"part2")
    (tmp_path / "test.vmx").write_text('displayName = "uploaded-test"\n', encoding="utf-8")

    summary = _build_uploaded_bundle_summary(
        tmp_path,
        ["test.vmdk", "test-s001.vmdk", "test-s002.vmdk", "test.vmx"],
        "fallback-name"
    )

    assert Path(summary["primary_disk_path"]).name == "test.vmdk"
    assert summary["detected_format"] == "vmdk"
    assert summary["split_extents"] == ["test-s001.vmdk", "test-s002.vmdk"]
    assert summary["vm_name"] == "uploaded-test"


def test_build_uploaded_bundle_summary_rejects_missing_vmdk_extent(tmp_path):
    descriptor = tmp_path / "test.vmdk"
    descriptor.write_text(
        '# Disk DescriptorFile\n'
        'RW 4192256 SPARSE "test-s001.vmdk"\n',
        encoding="utf-8"
    )

    with pytest.raises(Exception) as exc_info:
        _build_uploaded_bundle_summary(tmp_path, ["test.vmdk"], "fallback-name")

    assert "Bundle VMware incomplet" in str(exc_info.value)
