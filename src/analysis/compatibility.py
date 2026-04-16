"""
Analyse de compatibilite des VMs pour OpenShift Virtualization
"""

from typing import Dict, List

SUPPORTED_ARCHES = {"x86_64", "amd64"}
SUPPORTED_DISK_FORMATS = {"raw", "qcow2"}
SUPPORTED_DISK_BUSES = {"virtio", "scsi", "sata"}
SUPPORTED_NET_MODELS = {"virtio", "e1000"}

def analyze_vm(vm_details: Dict) -> Dict:
    """Analyse une VM et retourne un rapport de compatibilite."""
    specs = vm_details.get("specs", {})
    disks = vm_details.get("disks", [])
    networks = vm_details.get("network", [])

    issues: List[Dict] = []
    recommendations: List[str] = []
    blockers: List[str] = []
    score = 100

    # --- Architecture ---
    os_arch = (specs.get("os_arch") or "unknown").lower()
    if os_arch not in SUPPORTED_ARCHES:
        blockers.append(f"Architecture non supportee: {os_arch}")
        issues.append({
            "code": "arch_unsupported",
            "severity": "blocker",
            "message": f"Architecture non supportee: {os_arch}"
        })
        score -= 40
    else:
        # Also check if it looks like a known Linux/Windows distro
        os_type_hint = (specs.get("os_type") or "").lower()
        if any(x in os_type_hint for x in ("ubuntu", "debian", "rhel", "centos",
                                            "fedora", "sles", "linux", "win")):
            # OS is known, arch is supported → no issue
            pass

    memory_mb = specs.get("memory_mb", 0) or 0
    if memory_mb < 512:
        issues.append({
            "code": "memory_low",
            "severity": "warning",
            "message": f"RAM faible: {memory_mb} MB"
        })
        recommendations.append("Augmenter la RAM a au moins 1 GB.")
        score -= 10

    cpu_count = specs.get("cpus", 1) or 1
    if cpu_count < 1:
        issues.append({
            "code": "cpu_invalid",
            "severity": "warning",
            "message": "Nombre de CPU invalide"
        })
        score -= 10

    if not disks:
        blockers.append("Aucun disque detecte")
        issues.append({
            "code": "no_disk",
            "severity": "blocker",
            "message": "Aucun disque detecte"
        })
        score -= 40

    for disk in disks:
        fmt = (disk.get("format") or "unknown").lower()
        # Normalize bus: "scsi0:0" → "scsi", "sata0:0" → "sata"
        raw_bus = (disk.get("bus") or "unknown").lower()
        bus = raw_bus.rstrip("0123456789").rstrip(":")
        if fmt not in SUPPORTED_DISK_FORMATS:
            issues.append({
                "code": "disk_format",
                "severity": "warning",
                "message": f"Format disque non optimal: {fmt}"
            })
            recommendations.append(f"Convertir le disque en format raw (actuel: {fmt}).")
            score -= 10
        if bus not in SUPPORTED_DISK_BUSES:
            issues.append({
                "code": "disk_bus",
                "severity": "warning",
                "message": f"Bus disque non supporte: {bus}"
            })
            recommendations.append("Changer le bus disque vers virtio ou scsi.")
            score -= 10

    for nic in networks:
        model = (nic.get("model") or "unknown").lower()
        if model not in SUPPORTED_NET_MODELS:
            issues.append({
                "code": "net_model",
                "severity": "warning",
                "message": f"Modele reseau non optimal: {model}"
            })
            recommendations.append("Utiliser une carte reseau virtio.")
            score -= 10

    if blockers:
        compatibility = "non_compatible"
    elif issues:
        compatibility = "partiellement_compatible"
    else:
        compatibility = "compatible"

    score = max(0, min(100, score))

    return {
        "compatibility": compatibility,
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
        "detected": {
            "os_arch": os_arch,
            "memory_mb": memory_mb,
            "cpu_count": cpu_count,
            "disks_count": len(disks),
            "network_count": len(networks)
        }
    }
