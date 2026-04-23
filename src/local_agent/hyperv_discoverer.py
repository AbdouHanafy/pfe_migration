#!/usr/bin/env python3
"""
Hyper-V discovery helpers for the local agent.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HyperVDiscoverer:
    """Discover Hyper-V VMs by calling PowerShell on Windows."""

    def __init__(self):
        self.last_error = ""

    @property
    def available(self) -> bool:
        return self._run_ps(
            "Get-Command Get-VM -ErrorAction Stop | Select-Object -ExpandProperty Name"
        ) is not None

    def list_vms(self) -> List[Dict]:
        self.last_error = ""
        payload = self._run_ps_json(
            """
            Get-VM |
              Select-Object Name, Id, State, ProcessorCount, MemoryStartup, Generation |
              ConvertTo-Json -Depth 4
            """
        )
        if payload is None:
            return []

        vms = []
        for item in self._ensure_list(payload):
            vms.append(
                {
                    "id": item.get("Id"),
                    "name": item.get("Name"),
                    "uuid": item.get("Id"),
                    "state": str(item.get("State", "unknown")).lower(),
                    "hypervisor": "hyper-v",
                }
            )
        return vms

    def get_vm_details(self, vm_name: str) -> Optional[Dict]:
        self.last_error = ""
        vm_payload = self._run_ps_json(
            f"""
            $vm = Get-VM -Name '{vm_name}' -ErrorAction Stop
            $vm | Select-Object Name, Id, State, ProcessorCount, MemoryStartup, Generation |
              ConvertTo-Json -Depth 4
            """
        )
        if vm_payload is None:
            return None

        disk_payload = self._run_ps_json(
            f"""
            Get-VMHardDiskDrive -VMName '{vm_name}' -ErrorAction SilentlyContinue |
              Select-Object Path, ControllerType, ControllerNumber, ControllerLocation |
              ConvertTo-Json -Depth 4
            """
        )
        network_payload = self._run_ps_json(
            f"""
            Get-VMNetworkAdapter -VMName '{vm_name}' -ErrorAction SilentlyContinue |
              Select-Object SwitchName, MacAddress, Name |
              ConvertTo-Json -Depth 4
            """
        )

        return {
            "name": vm_payload.get("Name", vm_name),
            "uuid": vm_payload.get("Id", ""),
            "state": str(vm_payload.get("State", "unknown")).lower(),
            "hypervisor": "hyper-v",
            "specs": {
                "memory_mb": int(vm_payload.get("MemoryStartup", 0) or 0) // (1024 * 1024),
                "cpus": int(vm_payload.get("ProcessorCount", 1) or 1),
                "os_type": "unknown",
                "os_arch": "x86_64",
                "generation": vm_payload.get("Generation"),
            },
            "disks": [
                {
                    "type": "file",
                    "device": "disk",
                    "path": item.get("Path", ""),
                    "format": self._guess_disk_format(item.get("Path", "")),
                    "bus": str(item.get("ControllerType", "scsi")).lower(),
                    "driver": "hyperv",
                }
                for item in self._ensure_list(disk_payload)
                if item.get("Path")
            ],
            "network": [
                {
                    "type": "switch",
                    "network": item.get("SwitchName", ""),
                    "mac_address": item.get("MacAddress", ""),
                    "model": "hyperv-net",
                    "name": item.get("Name", ""),
                }
                for item in self._ensure_list(network_payload)
            ],
        }

    def _run_ps_json(self, script: str):
        output = self._run_ps(script)
        if output is None or not output.strip():
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            self.last_error = f"Invalid PowerShell JSON output: {exc}"
            logger.error(self.last_error)
            return None

    def _run_ps(self, script: str) -> Optional[str]:
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
        except FileNotFoundError:
            self.last_error = "PowerShell not found. Hyper-V discovery is available only on Windows."
            logger.error(self.last_error)
            return None
        except subprocess.TimeoutExpired:
            self.last_error = "PowerShell command timed out during Hyper-V discovery."
            logger.error(self.last_error)
            return None

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            self.last_error = stderr or "Hyper-V discovery command failed."
            logger.error(self.last_error)
            return None

        return result.stdout

    def _ensure_list(self, value) -> List[Dict]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _guess_disk_format(self, path: str) -> str:
        lower = (path or "").lower()
        if lower.endswith(".vhdx"):
            return "vhdx"
        if lower.endswith(".vhd"):
            return "vhd"
        return "raw"
