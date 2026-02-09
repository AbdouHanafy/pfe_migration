#!/usr/bin/env python3
"""
Module de découverte des VMs KVM
"""

try:
    import libvirt
except Exception:
    libvirt = None
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class KVMDiscoverer:
    """Découvre et analyse les VMs KVM"""
    
    def __init__(self, connection_uri: str = 'qemu:///system'):
        self.connection_uri = connection_uri
        self.conn = None
        
    def connect(self) -> bool:
        """Établit la connexion à libvirt"""
        if libvirt is None:
            logger.error("libvirt-python non installé (discovery KVM indisponible).")
            return False
        try:
            self.conn = libvirt.open(self.connection_uri)
            if self.conn is None:
                logger.error(f"Impossible de se connecter à {self.connection_uri}")
                return False
            logger.info(f"Connecté à KVM: {self.connection_uri}")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Erreur de connexion libvirt: {e}")
            return False
    
    def disconnect(self):
        """Ferme la connexion"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def list_vms(self) -> List[Dict]:
        """Liste toutes les VMs disponibles"""
        if not self.conn:
            logger.warning("Non connecté à KVM")
            return []
        
        vms = []
        try:
            domains = self.conn.listAllDomains(0)  # 0 = toutes les VMs
            
            for domain in domains:
                vm_info = {
                    'id': domain.ID() if domain.ID() != -1 else None,
                    'name': domain.name(),
                    'uuid': domain.UUIDString(),
                    'state': self._get_vm_state(domain),
                    'hypervisor': 'kvm'
                }
                vms.append(vm_info)
                
        except libvirt.libvirtError as e:
            logger.error(f"Erreur lors de la liste des VMs: {e}")
        
        return vms
    
    def get_vm_details(self, vm_name: str) -> Optional[Dict]:
        """Récupère les détails d'une VM spécifique"""
        if not self.conn:
            return None
        
        try:
            domain = self.conn.lookupByName(vm_name)
            xml_desc = domain.XMLDesc(0)
            
            details = {
                'name': vm_name,
                'uuid': domain.UUIDString(),
                'state': self._get_vm_state(domain),
                'hypervisor': 'kvm',
                'specs': self._parse_vm_specs(xml_desc),
                'disks': self._parse_disks(xml_desc),
                'network': self._parse_network(xml_desc),
                'performance': self._get_performance_stats(domain)
            }
            
            return details
            
        except libvirt.libvirtError as e:
            logger.error(f"Erreur détails VM {vm_name}: {e}")
            return None
    
    def _get_vm_state(self, domain) -> str:
        """Convertit l'état de la VM en texte"""
        state_map = {
            0: 'no state',
            1: 'running',
            2: 'blocked',
            3: 'paused',
            4: 'shutdown',
            5: 'shut off',
            6: 'crashed',
            7: 'suspended'
        }
        state, _ = domain.state()
        return state_map.get(state, 'unknown')
    
    def _parse_vm_specs(self, xml_desc: str) -> Dict:
        """Extrait les spécifications de la VM depuis le XML"""
        root = ET.fromstring(xml_desc)
        
        specs = {
            'memory_mb': 0,
            'cpus': 1,
            'os_type': 'unknown',
            'os_arch': 'unknown'
        }
        
        # Mémoire
        memory_elem = root.find('.//memory')
        if memory_elem is not None:
            specs['memory_mb'] = self._convert_memory_to_mb(
                int(memory_elem.text),
                memory_elem.get('unit', 'KiB')
            )
        
        # CPUs
        vcpu_elem = root.find('.//vcpu')
        if vcpu_elem is not None:
            specs['cpus'] = int(vcpu_elem.text)
        
        # Type d'OS
        os_type_elem = root.find('.//os/type')
        if os_type_elem is not None:
            specs['os_type'] = (os_type_elem.text or '').strip() or 'unknown'
            specs['os_arch'] = os_type_elem.get('arch', 'unknown')
        
        return specs
    
    def _parse_disks(self, xml_desc: str) -> List[Dict]:
        """Extrait les informations des disques"""
        root = ET.fromstring(xml_desc)
        disks = []
        
        for disk in root.findall('.//devices/disk'):
            if disk.get('device') == 'disk':
                source = disk.find('source')
                driver = disk.find('driver')
                path = ''
                if source is not None:
                    path = source.get('file') or source.get('dev') or source.get('name') or ''
                    protocol = source.get('protocol')
                    if protocol and source.get('name'):
                        path = f"{protocol}://{source.get('name')}"

                disk_info = {
                    'type': disk.get('type', 'file'),
                    'device': disk.get('device', 'disk'),
                    'path': path,
                    'format': driver.get('type') if driver is not None else 'raw',
                    'bus': disk.find('target').get('bus') if disk.find('target') is not None else 'virtio',
                    'driver': driver.get('name') if driver is not None else 'qemu'
                }
                disks.append(disk_info)
        
        return disks
    
    def _parse_network(self, xml_desc: str) -> List[Dict]:
        """Extrait les informations réseau"""
        root = ET.fromstring(xml_desc)
        networks = []
        
        for interface in root.findall('.//devices/interface'):
            mac = interface.find('mac')
            source = interface.find('source')
            model = interface.find('model')
            
            network_name = ''
            if source is not None:
                network_name = source.get('network') or source.get('bridge') or source.get('dev') or ''

            net_info = {
                'type': interface.get('type', 'network'),
                'mac_address': mac.get('address') if mac is not None else '',
                'network': network_name,
                'model': model.get('type') if model is not None else 'virtio'
            }
            networks.append(net_info)
        
        return networks
    
    def _get_performance_stats(self, domain) -> Dict:
        """Récupère les statistiques de performance"""
        try:
            info = domain.info()
            return {
                'cpu_time': info[4],  # Temps CPU en nanosecondes
                'max_memory': info[1],  # Mémoire max en KB
                'memory_usage': info[2],  # Mémoire utilisée en KB
                'cpu_count': info[3]  # Nombre de CPUs
            }
        except:
            return {}

    def _convert_memory_to_mb(self, value: int, unit: str) -> int:
        """Convertit la memoire en MB selon l'unite libvirt"""
        unit = (unit or '').lower()
        if unit in ('kib', 'kb'):
            return value // 1024
        if unit in ('mib', 'mb'):
            return value
        if unit in ('gib', 'gb'):
            return value * 1024
        return value // 1024

def main():
    """Fonction principale pour tests"""
    import json
    
    print("=== DÉCOUVREUR KVM - PFE MIGRATION ===")
    
    discoverer = KVMDiscoverer()
    
    if discoverer.connect():
        # Lister toutes les VMs
        vms = discoverer.list_vms()
        print(f"\n📊 {len(vms)} VM(s) trouvée(s):")
        
        for vm in vms:
            print(f"  • {vm['name']} ({vm['state']})")
        
        # Détails de la première VM
        if vms:
            print(f"\n🔍 Détails de '{vms[0]['name']}':")
            details = discoverer.get_vm_details(vms[0]['name'])
            if details:
                print(json.dumps(details, indent=2, default=str))
        
        discoverer.disconnect()
        print("\n✅ Module de découverte KVM fonctionnel !")

if __name__ == "__main__":
    main()
