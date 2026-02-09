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
    strategy = choose_strategy(analysis, plan)
    assert strategy["strategy"] == "conversion"

def test_analyze_vm_non_compatible():
    vm_details = {
        "specs": {"os_arch": "arm64", "memory_mb": 1024, "cpus": 2},
        "disks": [],
        "network": []
    }
    analysis = analyze_vm(vm_details)
    assert analysis["compatibility"] == "non_compatible"
