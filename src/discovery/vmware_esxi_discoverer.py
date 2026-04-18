#!/usr/bin/env python3
"""
Module de decouverte des VMs VMware ESXi / vSphere via pyVmomi.
"""

from __future__ import annotations

import logging
import ssl
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from pyVim.connect import Disconnect, SmartConnect
    try:
        from pyVim.connect import SmartConnectNoSSL
    except Exception:
        SmartConnectNoSSL = None
    from pyVmomi import vim
except Exception:
    Disconnect = None
    SmartConnect = None
    SmartConnectNoSSL = None
    vim = None


def _parse_vsphere_guest_os(guest_id: str, guest_full_name: str = "") -> tuple[str, str]:
    """Traduit les metadonnees vSphere en (os_type, os_arch)."""
    gid = (guest_id or "").lower().strip()
    full = (guest_full_name or "").strip()
    full_lower = full.lower()

    if "ubuntu" in gid:
        os_type = full or "Ubuntu"
    elif "debian" in gid:
        os_type = full or "Debian"
    elif "centos" in gid:
        os_type = full or "CentOS"
    elif "rhel" in gid or "redhat" in gid:
        os_type = full or "RHEL"
    elif "sles" in gid or "suse" in gid:
        os_type = full or "SLES"
    elif "win" in gid or "windows" in gid:
        os_type = full or "Windows"
    elif "linux" in gid:
        os_type = full or "Linux"
    else:
        os_type = full or "unknown"

    if any(token in gid for token in ("64", "x64")) or any(token in full_lower for token in ("64-bit", "x64", "x86_64")):
        os_arch = "x86_64"
    elif gid or full:
        os_arch = "x86"
    else:
        os_arch = "unknown"

    return os_type, os_arch


class VMwareESXiDiscoverer:
    """Decouvre et analyse les VMs VMware ESXi / vSphere."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 443,
        datacenter: str = "",
        verify_ssl: bool = False,
    ):
        self.host = (host or "").strip()
        self.username = (username or "").strip()
        self.password = password or ""
        self.port = int(port or 443)
        self.datacenter = (datacenter or "").strip()
        self.verify_ssl = bool(verify_ssl)

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)

    def list_vms(self) -> List[Dict]:
        """Liste toutes les VMs visibles depuis ESXi / vCenter."""
        service_instance = self._connect()
        container_view = None

        try:
            container_view = self._create_vm_view(service_instance)
            return [self._to_vm_summary(vm) for vm in container_view.view]
        finally:
            if container_view is not None:
                container_view.Destroy()
            self._disconnect(service_instance)

    def get_vm_details(self, vm_name: str) -> Optional[Dict]:
        """Recupere les details complets d'une VM ESXi / vSphere."""
        service_instance = self._connect()
        container_view = None

        try:
            container_view = self._create_vm_view(service_instance)
            for vm in container_view.view:
                if self._get_vm_name(vm) == vm_name:
                    return self._to_vm_details(vm)
            return None
        finally:
            if container_view is not None:
                container_view.Destroy()
            self._disconnect(service_instance)

    def _connect(self):
        if not self.is_configured:
            raise RuntimeError(
                "VMware ESXi/vSphere discovery is not configured. "
                "Define VSPHERE_HOST, VSPHERE_USER and VSPHERE_PASSWORD."
            )
        if SmartConnect is None:
            raise RuntimeError("pyVmomi is not available. Install pyvmomi to enable ESXi discovery.")

        try:
            if not self.verify_ssl:
                if SmartConnectNoSSL is not None:
                    return SmartConnectNoSSL(
                        host=self.host,
                        user=self.username,
                        pwd=self.password,
                        port=self.port,
                    )

                insecure_context = ssl._create_unverified_context()
                return SmartConnect(
                    host=self.host,
                    user=self.username,
                    pwd=self.password,
                    port=self.port,
                    sslContext=insecure_context,
                )

            secure_context = ssl.create_default_context()
            return SmartConnect(
                host=self.host,
                user=self.username,
                pwd=self.password,
                port=self.port,
                sslContext=secure_context,
            )
        except Exception as exc:
            raise RuntimeError(f"Unable to connect to VMware ESXi/vSphere at {self.host}:{self.port}: {exc}") from exc

    def _disconnect(self, service_instance) -> None:
        if service_instance is not None and Disconnect is not None:
            try:
                Disconnect(service_instance)
            except Exception:
                logger.debug("Unable to disconnect cleanly from VMware ESXi/vSphere.", exc_info=True)

    def _create_vm_view(self, service_instance):
        content = service_instance.RetrieveContent()
        search_root = content.rootFolder

        if self.datacenter:
            datacenter = self._find_datacenter(content, self.datacenter)
            if datacenter is None:
                raise RuntimeError(f"Datacenter '{self.datacenter}' not found in VMware inventory.")
            search_root = datacenter.vmFolder

        return content.viewManager.CreateContainerView(search_root, [vim.VirtualMachine], True)

    def _find_datacenter(self, content, datacenter_name: str):
        for entity in getattr(content.rootFolder, "childEntity", []):
            if isinstance(entity, vim.Datacenter) and entity.name == datacenter_name:
                return entity
        return None

    def _to_vm_summary(self, vm) -> Dict:
        summary = getattr(vm, "summary", None)
        config = getattr(summary, "config", None)
        runtime = getattr(summary, "runtime", None)

        return {
            "id": None,
            "name": self._get_vm_name(vm),
            "uuid": getattr(config, "uuid", "") or "",
            "state": self._map_power_state(getattr(runtime, "powerState", None)),
            "hypervisor": "vmware-esxi",
        }

    def _to_vm_details(self, vm) -> Dict:
        summary = getattr(vm, "summary", None)
        config = getattr(summary, "config", None)
        runtime = getattr(summary, "runtime", None)

        return {
            "name": self._get_vm_name(vm),
            "uuid": getattr(config, "uuid", "") or "",
            "state": self._map_power_state(getattr(runtime, "powerState", None)),
            "hypervisor": "vmware-esxi",
            "specs": self._extract_specs(vm),
            "disks": self._extract_disks(vm),
            "network": self._extract_network(vm),
        }

    def _extract_specs(self, vm) -> Dict:
        summary = getattr(vm, "summary", None)
        config = getattr(summary, "config", None)
        guest_id = getattr(config, "guestId", "") or ""
        guest_full_name = getattr(config, "guestFullName", "") or ""
        os_type, os_arch = _parse_vsphere_guest_os(guest_id, guest_full_name)

        return {
            "memory_mb": getattr(config, "memorySizeMB", 0) or 0,
            "cpus": getattr(config, "numCpu", 1) or 1,
            "os_type": os_type,
            "os_arch": os_arch,
            "guestOS": guest_id,
        }

    def _extract_disks(self, vm) -> List[Dict]:
        hardware = getattr(getattr(vm, "config", None), "hardware", None)
        devices = getattr(hardware, "device", []) or []
        controller_map = {getattr(device, "key", None): device for device in devices}

        disks = []
        for device in devices:
            if not isinstance(device, vim.vm.device.VirtualDisk):
                continue

            backing = getattr(device, "backing", None)
            controller = controller_map.get(getattr(device, "controllerKey", None))
            path = getattr(backing, "fileName", "") or ""
            size_gb = round((getattr(device, "capacityInKB", 0) or 0) / (1024 * 1024), 2)

            disks.append(
                {
                    "type": "file",
                    "device": "disk",
                    "path": path,
                    "format": "vmdk",
                    "bus": self._infer_disk_bus(controller),
                    "driver": "vmware",
                    "size_gb": size_gb,
                }
            )

        return disks

    def _extract_network(self, vm) -> List[Dict]:
        hardware = getattr(getattr(vm, "config", None), "hardware", None)
        devices = getattr(hardware, "device", []) or []
        networks = []

        for device in devices:
            if not isinstance(device, vim.vm.device.VirtualEthernetCard):
                continue

            backing = getattr(device, "backing", None)
            network_name = getattr(backing, "deviceName", "") or ""
            if not network_name and getattr(backing, "network", None) is not None:
                network_name = getattr(backing.network, "name", "") or ""

            networks.append(
                {
                    "type": "network",
                    "mac_address": getattr(device, "macAddress", "") or "",
                    "network": network_name,
                    "model": self._infer_net_model(device),
                }
            )

        return networks

    def _get_vm_name(self, vm) -> str:
        summary = getattr(vm, "summary", None)
        config = getattr(summary, "config", None)
        return getattr(config, "name", "") or getattr(vm, "name", "") or "unknown"

    def _infer_disk_bus(self, controller) -> str:
        if controller is None:
            return "scsi"

        controller_name = controller.__class__.__name__.lower()
        if "sata" in controller_name:
            return "sata"
        if "ide" in controller_name:
            return "ide"
        if "nvme" in controller_name:
            return "nvme"
        return "scsi"

    def _infer_net_model(self, nic) -> str:
        nic_name = nic.__class__.__name__.lower()
        if "e1000e" in nic_name:
            return "e1000e"
        if "e1000" in nic_name:
            return "e1000"
        if "vmxnet3" in nic_name:
            return "vmxnet3"
        if "vmxnet" in nic_name:
            return "vmxnet"
        if "pcnet32" in nic_name:
            return "pcnet32"
        return "unknown"

    def _map_power_state(self, power_state) -> str:
        raw = str(power_state or "").lower()
        if raw.endswith("poweredon") or raw == "poweredon":
            return "running"
        if raw.endswith("poweredoff") or raw == "poweredoff":
            return "shut off"
        if raw.endswith("suspended") or raw == "suspended":
            return "suspended"
        return raw or "unknown"
