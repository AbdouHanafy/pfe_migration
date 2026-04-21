"""
Tests pour le profil de boot KubeVirt / OpenShift.
"""

from src.openshift.client import build_vm_manifest, build_vm_console_url, resolve_upload_size


def test_build_vm_manifest_auto_prefers_sata_and_bios_for_vmdk():
    manifest = build_vm_manifest(
        vm_name="test-vm",
        namespace="vm-migration",
        pvc_name="test-vm-disk",
        memory="2Gi",
        cpu_cores=2,
        firmware="auto",
        disk_bus="auto",
        source_path="/tmp/test.vmdk",
        source_format="vmdk",
    )

    domain = manifest["spec"]["template"]["spec"]["domain"]
    disk = domain["devices"]["disks"][0]

    assert manifest["spec"]["runStrategy"] == "Always"
    assert "annotations" not in manifest["metadata"]
    assert domain["firmware"]["bootloader"] == {"bios": {}}
    assert disk["disk"]["bus"] == "sata"
    assert disk["bootOrder"] == 1
    assert domain["machine"]["type"] == "q35"


def test_build_vm_manifest_explicit_uefi_and_virtio():
    manifest = build_vm_manifest(
        vm_name="uefi-vm",
        namespace="vm-migration",
        pvc_name="uefi-vm-disk",
        memory="4Gi",
        cpu_cores=4,
        firmware="uefi",
        disk_bus="virtio",
        source_path="/tmp/uefi-disk.qcow2",
        source_format="qcow2",
    )

    domain = manifest["spec"]["template"]["spec"]["domain"]
    disk = domain["devices"]["disks"][0]

    assert domain["firmware"]["bootloader"] == {"efi": {"secureBoot": False}}
    assert disk["disk"]["bus"] == "virtio"


def test_resolve_upload_size_uses_virtual_disk_size_with_filesystem_overhead(monkeypatch):
    monkeypatch.setattr(
        "src.openshift.client._qemu_img_info",
        lambda path: {
            "virtual-size": 15 * 1024 ** 3,
            "actual-size": int(10.85 * 1024 ** 3),
        },
    )

    assert resolve_upload_size("/tmp/test-converted.qcow2", "12Gi") == "16Gi"


def test_build_vm_console_url_uses_configured_console_base(monkeypatch):
    monkeypatch.setattr("src.openshift.client.config.OPENSHIFT_CONSOLE_URL", "https://console-openshift.example")

    assert (
        build_vm_console_url("test-vm", "vm-migration")
        == "https://console-openshift.example/k8s/ns/vm-migration/kubevirt.io~v1~VirtualMachine/test-vm"
    )
