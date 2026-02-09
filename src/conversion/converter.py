"""
Plan de conversion pour la migration
"""

from typing import Dict, List

SUPPORTED_DISK_FORMATS = {"raw", "qcow2"}
SUPPORTED_DISK_BUSES = {"virtio", "scsi", "sata"}
SUPPORTED_NET_MODELS = {"virtio", "e1000"}

def build_conversion_plan(vm_details: Dict, analysis: Dict) -> Dict:
    """Construit un plan de conversion base sur l'analyse."""
    actions: List[Dict] = []
    warnings: List[str] = []

    if analysis.get("compatibility") == "non_compatible":
        return {
            "can_convert": False,
            "actions": actions,
            "warnings": ["VM non compatible, conversion automatique refusee."]
        }

    for disk in vm_details.get("disks", []):
        fmt = (disk.get("format") or "unknown").lower()
        if fmt not in SUPPORTED_DISK_FORMATS:
            actions.append({
                "type": "disk_format_conversion",
                "disk_path": disk.get("path", ""),
                "from": fmt,
                "to": "raw"
            })

        bus = (disk.get("bus") or "unknown").lower()
        if bus not in SUPPORTED_DISK_BUSES:
            actions.append({
                "type": "disk_bus_change",
                "disk_path": disk.get("path", ""),
                "from": bus,
                "to": "virtio"
            })

    for nic in vm_details.get("network", []):
        model = (nic.get("model") or "unknown").lower()
        if model not in SUPPORTED_NET_MODELS:
            actions.append({
                "type": "network_model_change",
                "mac_address": nic.get("mac_address", ""),
                "from": model,
                "to": "virtio"
            })

    if not actions:
        warnings.append("Aucune conversion requise.")

    return {
        "can_convert": True,
        "actions": actions,
        "warnings": warnings
    }
