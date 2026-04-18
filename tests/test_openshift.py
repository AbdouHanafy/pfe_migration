"""
Tests pour le profil de boot KubeVirt / OpenShift.
"""

from src.openshift.client import build_vm_manifest


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
