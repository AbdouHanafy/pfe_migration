#!/usr/bin/env python3
"""
Module de découverte des VMs VMware Workstation via fichiers .vmx
"""

from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================
# VMware guestOS code → OS type + Architecture mapping
# ============================================================

_VMWARE_OS_MAP = {
    # Linux
    "ubuntu": ("ubuntu", "x86"),
    "ubuntu-64": ("Ubuntu", "x86_64"),
    "debian": ("debian", "x86"),
    "debian-64": ("Debian", "x86_64"),
    "rhel": ("rhel", "x86"),
    "rhel-64": ("RHEL", "x86_64"),
    "centos": ("centos", "x86"),
    "centos-64": ("CentOS", "x86_64"),
    "fedora": ("fedora", "x86"),
    "fedora-64": ("Fedora", "x86_64"),
    "sles": ("sles", "x86"),
    "sles-64": ("SLES", "x86_64"),
    "otherlinux": ("other-linux", "x86"),
    "otherlinux-64": ("other-linux", "x86_64"),
    "other-64": ("linux", "x86_64"),
    # Windows
    "windows9": ("Windows 95", "x86"),
    "windows9-64": ("Windows 95", "x86"),
    "winxphome": ("Windows XP", "x86"),
    "winxppro": ("Windows XP", "x86"),
    "winxphome-64": ("Windows XP", "x86_64"),
    "winxppro-64": ("Windows XP", "x86_64"),
    "winnetbusiness": ("Windows Server 2003", "x86"),
    "winnetenterprise": ("Windows Server 2003", "x86"),
    "winnetstandard": ("Windows Server 2003", "x86"),
    "winnetenterprise-64": ("Windows Server 2003", "x86_64"),
    "winnetstandard-64": ("Windows Server 2003", "x86_64"),
    "winlonghorn": ("Windows Server 2008", "x86"),
    "winlonghorn-64": ("Windows Server 2008", "x86_64"),
    "windows7": ("Windows 7", "x86"),
    "windows7-64": ("Windows 7", "x86_64"),
    "windows8": ("Windows 8", "x86"),
    "windows8-64": ("Windows 8", "x86_64"),
    "windows8server-64": ("Windows Server 2012", "x86_64"),
    "windows9": ("Windows 10", "x86"),
    "windows9-64": ("Windows 10", "x86_64"),
    "win11": ("Windows 11", "x86_64"),
    "win11srv-64": ("Windows Server 2022", "x86_64"),
    "win12srv-64": ("Windows Server 2025", "x86_64"),
    # Other
    "other": ("unknown", "unknown"),
}


def _parse_vmware_guest_os(guest_os_code: str) -> tuple:
    """
    Traduit un code VMware guestOS en (os_type, os_arch).

    >>> _parse_vmware_guest_os("ubuntu-64")
    ('Ubuntu', 'x86_64')
    >>> _parse_vmware_guest_os("windows9-64")
    ('Windows 10', 'x86_64')
    >>> _parse_vmware_guest_os("unknown-os")
    ('unknown', 'unknown')
    """
    code = (guest_os_code or "unknown").lower().strip()
    os_type, os_arch = _VMWARE_OS_MAP.get(code, ("unknown", "unknown"))
    return os_type, os_arch


class VMwareWorkstationDiscoverer:
    """Découvre et analyse les VMs VMware Workstation (.vmx)"""

    def __init__(self, search_paths: List[str]):
        self.search_paths = [Path(p).expanduser() for p in (search_paths or [])]

    def list_vms(self) -> List[Dict]:
        """Liste toutes les VMs trouvées"""
        vms = []
        for vmx_path in self._find_vmx_files():
            vmx_data = self._parse_vmx(vmx_path)
            name = vmx_data.get("displayName") or vmx_path.stem
            vms.append(
                {
                    "id": None,
                    "name": name,
                    "uuid": vmx_data.get("uuid.bios") or vmx_data.get("uuid.location") or "",
                    "state": "unknown",
                    "hypervisor": "vmware-workstation",
                    "vmx_path": str(vmx_path),
                }
            )
        return vms

    def get_vm_details(self, vm_name: str) -> Optional[Dict]:
        """Récupère les détails d'une VM spécifique"""
        for vmx_path in self._find_vmx_files():
            vmx_data = self._parse_vmx(vmx_path)
            name = vmx_data.get("displayName") or vmx_path.stem
            if name != vm_name:
                continue
            return {
                "name": name,
                "uuid": vmx_data.get("uuid.bios") or vmx_data.get("uuid.location") or "",
                "state": "unknown",
                "hypervisor": "vmware-workstation",
                "specs": self._extract_specs(vmx_data),
                "disks": self._extract_disks(vmx_data, vmx_path.parent),
                "network": self._extract_network(vmx_data),
                "vmx_path": str(vmx_path),
            }
        return None

    def _find_vmx_files(self) -> List[Path]:
        vmx_files: List[Path] = []
        for base in self.search_paths:
            if not base.exists():
                continue
            if base.is_file() and base.suffix.lower() == ".vmx":
                vmx_files.append(base)
                continue
            for vmx in base.rglob("*.vmx"):
                vmx_files.append(vmx)
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for path in vmx_files:
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        return unique

    def _parse_vmx(self, vmx_path: Path) -> Dict[str, str]:
        data: Dict[str, str] = {}
        try:
            text = vmx_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning(f"Impossible de lire {vmx_path}: {exc}")
            return data
        for line in text.splitlines():
            if not line or line.strip().startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"')
            if key:
                data[key] = value
        return data

    def _extract_specs(self, vmx_data: Dict[str, str]) -> Dict:
        memory_mb = 0
        if vmx_data.get("memsize"):
            try:
                memory_mb = int(vmx_data["memsize"])
            except ValueError:
                memory_mb = 0
        cpus = 1
        if vmx_data.get("numvcpus"):
            try:
                cpus = int(vmx_data["numvcpus"])
            except ValueError:
                cpus = 1

        # --- OS detection ---
        raw_guest_os = vmx_data.get("guestOS", "unknown")
        os_type, os_arch = _parse_vmware_guest_os(raw_guest_os)

        return {
            "memory_mb": memory_mb,
            "cpus": cpus,
            "os_type": os_type,
            "os_arch": os_arch,
            "guestOS": raw_guest_os,
        }

    def _extract_disks(self, vmx_data: Dict[str, str], base_dir: Path) -> List[Dict]:
        disks: List[Dict] = []
        for key, value in vmx_data.items():
            if key.endswith(".fileName") and value.lower().endswith(".vmdk"):
                path = value
                full_path = (base_dir / path).resolve() if not Path(path).is_absolute() else Path(path)

                # Extract bus type from key prefix (e.g., "scsi0:0" → "scsi")
                bus_key = key.split(".")[0]  # e.g., "scsi0:0"
                bus_type = bus_key.rstrip("0123456789").rstrip(":").lower()  # "scsi"

                disks.append(
                    {
                        "type": "file",
                        "device": "disk",
                        "path": str(full_path),
                        "format": "vmdk",
                        "bus": bus_type if bus_type else "scsi",
                        "driver": "vmware",
                    }
                )
        return disks

    def _extract_network(self, vmx_data: Dict[str, str]) -> List[Dict]:
        networks: List[Dict] = []
        # Look for ethernet interfaces: ethernet0, ethernet1, ...
        for key in vmx_data:
            if key.startswith("ethernet") and key.endswith(".present"):
                if vmx_data[key].lower() != "true":
                    continue
                idx = key.split(".")[0]  # e.g., "ethernet0"
                address_type = vmx_data.get(f"{idx}.addressType", "")
                mac = ""
                if address_type.lower() == "static":
                    mac = vmx_data.get(f"{idx}.address", "")
                elif address_type.lower() == "generated":
                    mac = vmx_data.get(f"{idx}.generatedAddress", "")
                network_name = vmx_data.get(f"{idx}.connectionType",
                                            vmx_data.get(f"{idx}.networkName", ""))
                model = vmx_data.get(f"{idx}.virtualDev", "e1000")

                networks.append(
                    {
                        "type": "network",
                        "mac_address": mac,
                        "network": network_name,
                        "model": model,
                    }
                )
        return networks

