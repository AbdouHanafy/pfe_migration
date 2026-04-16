"""
Feature engineering — extraction de caracteristiques numeriques
a partir des resultats d'analyse et des metadonnees d'une VM.

Ces features servent d'entree au modele de classification scikit-learn.
"""

from typing import Dict, List, Tuple
import os
import numpy as np

# ============================================================
# NOMENCLATURE DES FEATURES
# ============================================================
#
#  0  : is_x86_64              — architecture supportee (1) ou non (0)
#  1  : memory_mb              — RAM en MB
#  2  : cpu_count              — nombre de vCPU
#  3  : disk_count             — nombre de disques
#  4  : has_raw_disk           — au moins un disque raw (1/0)
#  5  : has_qcow2_disk         — au moins un disque qcow2 (1/0)
#  6  : needs_disk_conversion  — proportion de disques a convertir (0.0-1.0)
#  7  : has_virtio_bus         — au moins un bus virtio (1/0)
#  8  : needs_bus_change       — proportion de disques a changer de bus (0.0-1.0)
#  9  : has_virtio_net         — au moins une interface virtio (1/0)
# 10  : needs_net_change       — proportion de NICs a changer (0.0-1.0)
# 11  : compatibility_score    — score de compatibilite (0-100)
# 12  : issue_count             — nombre total d'issues detectees
# 13  : blocker_count           — nombre de blockers
# 14  : warning_count           — nombre de warnings
# 15  : conversion_action_count — nombre d'actions de conversion necessaires
# 16  : has_windows_os          — OS Windows detecte (1/0)
# 17  : has_linux_os            — OS Linux detecte (1/0)
# 18  : total_disk_size_gb_est  — estimation taille totale disques (GB)
# 19  : is_multi_disk           — plusieurs disques (1/0)
#
# Total: 20 features

FEATURE_NAMES = [
    "is_x86_64",
    "memory_mb",
    "cpu_count",
    "disk_count",
    "has_raw_disk",
    "has_qcow2_disk",
    "needs_disk_conversion",
    "has_virtio_bus",
    "needs_bus_change",
    "has_virtio_net",
    "needs_net_change",
    "compatibility_score",
    "issue_count",
    "blocker_count",
    "warning_count",
    "conversion_action_count",
    "has_windows_os",
    "has_linux_os",
    "total_disk_size_gb_est",
    "is_multi_disk",
]


def extract_features(vm_details: Dict, analysis: Dict, conversion_plan: Dict) -> np.ndarray:
    """
    Extrait un vecteur de 20 features numeriques a partir des donnees VM.

    Parameters
    ----------
    vm_details : dict
        Details bruts de la VM (disks, network, specs).
    analysis : dict
        Resultat de l'analyse de compatibilite.
    conversion_plan : dict
        Plan de conversion avec actions.

    Returns
    -------
    numpy.ndarray
        Vecteur de shape (1, 20).
    """
    specs = vm_details.get("specs", {})
    disks = vm_details.get("disks", [])
    networks = vm_details.get("network", [])
    issues = analysis.get("issues", [])
    score = analysis.get("score", 50)
    actions = conversion_plan.get("actions", [])

    # --- Architecture ---
    os_arch = (specs.get("os_arch") or "").lower()
    is_x86_64 = 1 if os_arch in ("x86_64", "amd64", "i686") else 0

    # --- Hardware ---
    memory_mb = float(specs.get("memory_mb", 512) or 512)
    cpu_count = float(specs.get("cpus", 1) or 1)
    disk_count = float(len(disks))

    # --- Disks ---
    disk_formats = [(d.get("format") or "unknown").lower() for d in disks]
    raw_buses = [(d.get("bus") or "unknown").lower() for d in disks]
    disk_buses = [b.rstrip("0123456789").rstrip(":") for b in raw_buses]

    has_raw = 1 if "raw" in disk_formats else 0
    has_qcow2 = 1 if "qcow2" in disk_formats else 0

    unsupported_fmts = {"vmdk", "vhdx", "vhd", "ova", "iso", "unknown"}
    disks_needing_conversion = sum(1 for f in disk_formats if f in unsupported_fmts)
    needs_disk_conversion = disks_needing_conversion / max(len(disks), 1)

    has_virtio_bus = 1 if "virtio" in disk_buses else 0
    unsupported_buses = {"ide", "unknown"}
    disks_needing_bus = sum(1 for b in disk_buses if b in unsupported_buses)
    needs_bus_change = disks_needing_bus / max(len(disks), 1)

    # --- Network ---
    net_models = [(n.get("model") or "unknown").lower() for n in networks]
    has_virtio_net = 1 if "virtio" in net_models else 0
    unsupported_nets = {"rtl8139", "unknown"}
    nets_needing_change = sum(1 for m in net_models if m in unsupported_nets)
    needs_net_change = nets_needing_change / max(len(networks), 1)

    # --- Issues ---
    issue_count = len(issues)
    blocker_count = sum(1 for i in issues if i.get("severity") == "blocker")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")

    # --- OS detection ---
    os_type = (specs.get("os_type") or "").lower()
    guest_os = (specs.get("guestOS", "") or "").lower()
    os_hint = os_type + " " + guest_os
    has_windows = 1 if any(x in os_hint for x in ("windows", "win")) else 0
    has_linux = 1 if any(x in os_hint for x in ("linux", "ubuntu", "centos", "rhel", "debian")) else 0

    # --- Disk size estimate ---
    total_disk_gb = 0.0
    for d in disks:
        path = (d.get("path") or "")
        size_gb = d.get("size_gb")
        if path and os.path.exists(path):
            total_disk_gb += os.path.getsize(path) / (1024 ** 3)
        elif size_gb is not None:
            total_disk_gb += float(size_gb)
        elif path:
            total_disk_gb += 20.0

    is_multi_disk = 1 if len(disks) > 1 else 0

    features = np.array([[
        is_x86_64,
        memory_mb,
        cpu_count,
        disk_count,
        has_raw,
        has_qcow2,
        needs_disk_conversion,
        has_virtio_bus,
        needs_bus_change,
        has_virtio_net,
        needs_net_change,
        score,
        issue_count,
        blocker_count,
        warning_count,
        len(actions),
        has_windows,
        has_linux,
        total_disk_gb,
        is_multi_disk,
    ]], dtype=np.float64)

    return features


def extract_features_from_analysis_only(analysis: Dict, conversion_plan: Dict) -> np.ndarray:
    """
    Version simplifiee quand on n'a que l'analyse et le plan de conversion.
    Utilise comme fallback pour l'API.

    Parameters
    ----------
    analysis : dict
        Resultat de l'analyse.
    conversion_plan : dict
        Plan de conversion.

    Returns
    -------
    numpy.ndarray
        Vecteur de shape (1, 20).
    """
    detected = analysis.get("detected", {})
    issues = analysis.get("issues", [])
    score = analysis.get("score", 50)
    actions = conversion_plan.get("actions", [])

    features = np.array([[
        1,                     # is_x86_64 (assume oui par defaut)
        float(detected.get("memory_mb", 512)),
        float(detected.get("cpu_count", 1)),
        float(detected.get("disks_count", 1)),
        0,                     # has_raw_disk (inconnu)
        0,                     # has_qcow2_disk (inconnu)
        0.5,                   # needs_disk_conversion (estimate)
        0,                     # has_virtio_bus (inconnu)
        0.3,                   # needs_bus_change (estimate)
        0,                     # has_virtio_net (inconnu)
        0.3,                   # needs_net_change (estimate)
        float(score),
        len(issues),
        sum(1 for i in issues if i.get("severity") == "blocker"),
        sum(1 for i in issues if i.get("severity") == "warning"),
        len(actions),
        0,                     # has_windows_os (inconnu)
        1,                     # has_linux_os (assume oui)
        40.0,                  # total_disk_size_gb_est (estimate)
        0,                     # is_multi_disk
    ]], dtype=np.float64)

    return features
