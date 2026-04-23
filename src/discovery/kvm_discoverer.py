#!/usr/bin/env python3
"""
Module de decouverte des VMs KVM.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

try:
    import libvirt
except Exception:
    libvirt = None


logger = logging.getLogger(__name__)


class KVMDiscoverer:
    """Decouvre et analyse les VMs KVM."""

    def __init__(self, connection_uri: str = "qemu:///system"):
        self.connection_uri = connection_uri
        self.conn = None
        self.last_error = ""

    def connect(self) -> bool:
        """Etablit la connexion a libvirt."""
        self.last_error = ""
        if libvirt is None:
            self.last_error = "libvirt-python non installe (discovery KVM indisponible)."
            logger.error(self.last_error)
            return False

        try:
            self.conn = libvirt.open(self.connection_uri)
            if self.conn is None:
                self.last_error = f"Impossible de se connecter a {self.connection_uri}"
                logger.error(self.last_error)
                return False
            logger.info("Connecte a KVM: %s", self.connection_uri)
            return True
        except libvirt.libvirtError as exc:
            self.last_error = f"Erreur de connexion libvirt vers {self.connection_uri}: {exc}"
            logger.error(self.last_error)
            self.conn = None
            return False

    def disconnect(self):
        """Ferme la connexion."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def list_vms(self) -> List[Dict]:
        """Liste toutes les VMs disponibles."""
        if not self.conn:
            self.last_error = self.last_error or f"Non connecte a KVM ({self.connection_uri})"
            logger.warning(self.last_error)
            return []

        vms = []
        try:
            domains = self.conn.listAllDomains(0)

            for domain in domains:
                vm_info = {
                    "id": domain.ID() if domain.ID() != -1 else None,
                    "name": domain.name(),
                    "uuid": domain.UUIDString(),
                    "state": self._get_vm_state(domain),
                    "hypervisor": "kvm",
                }
                vms.append(vm_info)

        except libvirt.libvirtError as exc:
            self.last_error = f"Erreur lors de la liste des VMs KVM: {exc}"
            logger.error(self.last_error)

        return vms

    def get_vm_details(self, vm_name: str) -> Optional[Dict]:
        """Recupere les details d'une VM specifique."""
        if not self.conn:
            self.last_error = self.last_error or f"Non connecte a KVM ({self.connection_uri})"
            return None

        try:
            domain = self.conn.lookupByName(vm_name)
            xml_desc = domain.XMLDesc(0)

            details = {
                "name": vm_name,
                "uuid": domain.UUIDString(),
                "state": self._get_vm_state(domain),
                "hypervisor": "kvm",
                "specs": self._parse_vm_specs(xml_desc),
                "disks": self._parse_disks(xml_desc),
                "network": self._parse_network(xml_desc),
                "performance": self._get_performance_stats(domain),
            }

            return details

        except libvirt.libvirtError as exc:
            self.last_error = f"Erreur details VM {vm_name}: {exc}"
            logger.error(self.last_error)
            return None

    def _get_vm_state(self, domain) -> str:
        """Convertit l'etat de la VM en texte."""
        state_map = {
            0: "no state",
            1: "running",
            2: "blocked",
            3: "paused",
            4: "shutdown",
            5: "shut off",
            6: "crashed",
            7: "suspended",
        }
        state, _ = domain.state()
        return state_map.get(state, "unknown")

    def _parse_vm_specs(self, xml_desc: str) -> Dict:
        """Extrait les specifications de la VM depuis le XML."""
        root = ET.fromstring(xml_desc)

        specs = {
            "memory_mb": 0,
            "cpus": 1,
            "os_type": "unknown",
            "os_arch": "unknown",
        }

        memory_elem = root.find(".//memory")
        if memory_elem is not None:
            specs["memory_mb"] = self._convert_memory_to_mb(
                int(memory_elem.text),
                memory_elem.get("unit", "KiB"),
            )

        vcpu_elem = root.find(".//vcpu")
        if vcpu_elem is not None:
            specs["cpus"] = int(vcpu_elem.text)

        os_type_elem = root.find(".//os/type")
        if os_type_elem is not None:
            specs["os_type"] = (os_type_elem.text or "").strip() or "unknown"
            specs["os_arch"] = os_type_elem.get("arch", "unknown")

        return specs

    def _parse_disks(self, xml_desc: str) -> List[Dict]:
        """Extrait les informations des disques."""
        root = ET.fromstring(xml_desc)
        disks = []

        for disk in root.findall(".//devices/disk"):
            if disk.get("device") == "disk":
                source = disk.find("source")
                driver = disk.find("driver")
                path = ""
                if source is not None:
                    path = source.get("file") or source.get("dev") or source.get("name") or ""
                    protocol = source.get("protocol")
                    if protocol and source.get("name"):
                        path = f"{protocol}://{source.get('name')}"

                disk_info = {
                    "type": disk.get("type", "file"),
                    "device": disk.get("device", "disk"),
                    "path": path,
                    "format": driver.get("type") if driver is not None else "raw",
                    "bus": disk.find("target").get("bus") if disk.find("target") is not None else "virtio",
                    "driver": driver.get("name") if driver is not None else "qemu",
                }
                disks.append(disk_info)

        return disks

    def _parse_network(self, xml_desc: str) -> List[Dict]:
        """Extrait les informations reseau."""
        root = ET.fromstring(xml_desc)
        networks = []

        for interface in root.findall(".//devices/interface"):
            mac = interface.find("mac")
            source = interface.find("source")
            model = interface.find("model")

            network_name = ""
            if source is not None:
                network_name = source.get("network") or source.get("bridge") or source.get("dev") or ""

            net_info = {
                "type": interface.get("type", "network"),
                "mac_address": mac.get("address") if mac is not None else "",
                "network": network_name,
                "model": model.get("type") if model is not None else "virtio",
            }
            networks.append(net_info)

        return networks

    def _get_performance_stats(self, domain) -> Dict:
        """Recupere les statistiques de performance."""
        try:
            info = domain.info()
            return {
                "cpu_time": info[4],
                "max_memory": info[1],
                "memory_usage": info[2],
                "cpu_count": info[3],
            }
        except Exception:
            return {}

    def _convert_memory_to_mb(self, value: int, unit: str) -> int:
        """Convertit la memoire en MB selon l'unite libvirt."""
        unit = (unit or "").lower()
        if unit in ("kib", "kb"):
            return value // 1024
        if unit in ("mib", "mb"):
            return value
        if unit in ("gib", "gb"):
            return value * 1024
        return value // 1024


def main():
    """Fonction principale pour tests."""
    import json

    print("=== DECOUVREUR KVM - PFE MIGRATION ===")

    discoverer = KVMDiscoverer()

    if discoverer.connect():
        vms = discoverer.list_vms()
        print(f"\n{len(vms)} VM(s) trouvee(s):")

        for vm in vms:
            print(f"  - {vm['name']} ({vm['state']})")

        if vms:
            print(f"\nDetails de '{vms[0]['name']}':")
            details = discoverer.get_vm_details(vms[0]["name"])
            if details:
                print(json.dumps(details, indent=2, default=str))

        discoverer.disconnect()
        print("\nModule de decouverte KVM fonctionnel !")


if __name__ == "__main__":
    main()
