#!/usr/bin/env python3
"""
Module de découverte des VMs VMware Workstation via fichiers .vmx
"""

from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


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
        return {
            "memory_mb": memory_mb,
            "cpus": cpus,
            "os_type": vmx_data.get("guestOS", "unknown"),
            "os_arch": vmx_data.get("guestOS", "unknown"),
        }

    def _extract_disks(self, vmx_data: Dict[str, str], base_dir: Path) -> List[Dict]:
        disks: List[Dict] = []
        for key, value in vmx_data.items():
            if key.endswith(".fileName") and value.lower().endswith(".vmdk"):
                path = value
                full_path = (base_dir / path).resolve() if not Path(path).is_absolute() else Path(path)
                disks.append(
                    {
                        "type": "file",
                        "device": "disk",
                        "path": str(full_path),
                        "format": "vmdk",
                        "bus": key.split(".")[0] if "." in key else "scsi",
                        "driver": "vmware",
                    }
                )
        return disks

    def _extract_network(self, vmx_data: Dict[str, str]) -> List[Dict]:
        networks: List[Dict] = []
        for key, value in vmx_data.items():
            if key.endswith(".networkName"):
                networks.append(
                    {
                        "type": "network",
                        "mac_address": vmx_data.get(key.replace("networkName", "address"), ""),
                        "network": value,
                        "model": vmx_data.get(key.replace("networkName", "virtualDev"), "e1000"),
                    }
                )
        return networks

