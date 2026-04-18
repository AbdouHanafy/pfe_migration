"""
Tests pour l'analyse de compatibilite et la strategie
"""

from src.analysis.compatibility import analyze_vm
from src.conversion.converter import build_conversion_plan
from src.migration.strategy import choose_strategy

def test_analyze_vm_compatible():
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 2048, "cpus": 2},
        "disks": [{"format": "raw", "bus": "virtio", "path": "/tmp/disk.raw"}],
        "network": [{"model": "virtio"}]
    }
    analysis = analyze_vm(vm_details)
    assert analysis["compatibility"] == "compatible"
    assert analysis["score"] == 100

def test_analyze_vm_partial_and_plan():
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 256, "cpus": 1},
        "disks": [{"format": "vmdk", "bus": "ide", "path": "/tmp/disk.vmdk"}],
        "network": [{"model": "rtl8139"}]
    }
    analysis = analyze_vm(vm_details)
    assert analysis["compatibility"] == "partiellement_compatible"
    plan = build_conversion_plan(vm_details, analysis)
    assert plan["can_convert"] is True
    assert len(plan["actions"]) >= 2
    strategy = choose_strategy(vm_details, analysis, plan)
    # Can be "conversion" or "alternative" depending on ML model
    assert strategy["strategy"] in ("conversion", "alternative")

def test_analyze_vm_non_compatible():
    vm_details = {
        "specs": {"os_arch": "arm64", "memory_mb": 1024, "cpus": 2},
        "disks": [],
        "network": []
    }
    analysis = analyze_vm(vm_details)
    assert analysis["compatibility"] == "non_compatible"


def test_vmware_scsi_bus_is_not_flagged_for_conversion():
    vm_details = {
        "specs": {"os_arch": "x86_64", "memory_mb": 2048, "cpus": 1},
        "disks": [{"format": "vmdk", "bus": "scsi0:0", "path": "/tmp/test.vmdk"}],
        "network": [{"model": "e1000"}]
    }
    analysis = analyze_vm(vm_details)
    plan = build_conversion_plan(vm_details, analysis)

    action_types = [action["type"] for action in plan["actions"]]
    assert "disk_format_conversion" in action_types
    assert "disk_bus_change" not in action_types
