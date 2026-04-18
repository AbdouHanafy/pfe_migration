"""
OpenShift/KubeVirt helpers for real migration steps.
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import os
import shutil
import subprocess
import json
from pathlib import Path

from src.config import config

SUPPORTED_BOOT_FIRMWARE = {"auto", "bios", "uefi", "efi"}
SUPPORTED_DISK_BUS = {"auto", "virtio", "scsi", "sata"}


@dataclass
class UploadResult:
    pvc_name: str
    namespace: str
    image_path: str
    size: str
    uploadproxy_url: str


def _run(cmd: list[str]) -> Tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_tools() -> Dict[str, bool]:
    """Retourne la disponibilite des binaires externes requis."""
    return {
        "oc": shutil.which("oc") is not None,
        "virtctl": shutil.which("virtctl") is not None,
        "qemu-img": shutil.which("qemu-img") is not None
    }


def get_uploadproxy_url() -> str:
    if config.OPENSHIFT_UPLOADPROXY_URL:
        return config.OPENSHIFT_UPLOADPROXY_URL
    cmd = [
        "oc", "get", "route",
        "-n", "openshift-cnv",
        "cdi-uploadproxy",
        "-o", "jsonpath={.spec.host}"
    ]
    code, out, err = _run(cmd)
    if code != 0 or not out:
        raise RuntimeError(f"Unable to get uploadproxy route: {err or out}")
    return f"https://{out}"


def ensure_namespace(namespace: str) -> None:
    code, _, _ = _run(["oc", "get", "namespace", namespace])
    if code == 0:
        return
    code, out, err = _run(["oc", "new-project", namespace])
    if code != 0:
        raise RuntimeError(f"Unable to create namespace: {err or out}")


def _build_converted_target_path(source_path: str, output_format: str) -> str:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    source = Path(source_path)
    suffix = ".raw" if output_format == "raw" else f".{output_format}"
    stem = source.stem or "disk"
    return str(Path(config.DATA_DIR) / f"{stem}-converted{suffix}")


def convert_disk_if_needed(source_path: str, source_format: str) -> str:
    source_format = (source_format or "").lower()
    if source_format in ("qcow2", "raw"):
        return source_path

    # Keep qcow2 as the normalized intermediate format for uploads.
    target_path = _build_converted_target_path(source_path, "qcow2")

    cmd = [
        "qemu-img", "convert",
        "-O", "qcow2",
        source_path,
        target_path
    ]
    code, out, err = _run(cmd)
    if code != 0:
        raise RuntimeError(f"Disk conversion failed: {err or out}")
    return target_path


def upload_disk(image_path: str, pvc_name: str, size: str, namespace: str) -> UploadResult:
    uploadproxy_url = get_uploadproxy_url()
    cmd = [
        "virtctl", "image-upload",
        "pvc", pvc_name,
        "--namespace", namespace,
        "--image-path", image_path,
        "--size", size,
        "--uploadproxy-url", uploadproxy_url
    ]
    if config.OPENSHIFT_INSECURE_UPLOAD:
        cmd.append("--insecure")

    code, out, err = _run(cmd)
    if code != 0:
        raise RuntimeError(f"Image upload failed: {err or out}")
    return UploadResult(
        pvc_name=pvc_name,
        namespace=namespace,
        image_path=image_path,
        size=size,
        uploadproxy_url=uploadproxy_url
    )


def _resolve_firmware(firmware: str, source_path: str = "") -> str:
    requested = (firmware or "auto").lower()
    if requested not in SUPPORTED_BOOT_FIRMWARE:
        raise ValueError(f"Unsupported firmware '{firmware}'. Use auto, bios or uefi.")

    if requested in {"uefi", "efi"}:
        return "efi"
    if requested == "bios":
        return "bios"

    # auto: use a conservative default, but honor clear hints in filenames.
    source_hint = Path(source_path or "").name.lower()
    if "uefi" in source_hint or "efi" in source_hint:
        return "efi"
    return "bios"


def _resolve_disk_bus(disk_bus: str, source_format: str = "") -> str:
    requested = (disk_bus or "auto").lower()
    if requested not in SUPPORTED_DISK_BUS:
        raise ValueError(f"Unsupported disk bus '{disk_bus}'. Use auto, sata, scsi or virtio.")

    if requested != "auto":
        return requested

    # Compatibility-first default for first boot after import.
    source_fmt = (source_format or "").lower()
    if source_fmt in {"vmdk", "vhd", "vhdx"}:
        return "sata"
    return "sata"


def _build_disk_device(name: str, disk_bus: str) -> Dict:
    return {
        "name": name,
        "bootOrder": 1,
        "disk": {"bus": disk_bus}
    }


def build_vm_manifest(
    vm_name: str,
    namespace: str,
    pvc_name: str,
    memory: str,
    cpu_cores: int,
    firmware: str = "auto",
    disk_bus: str = "auto",
    source_path: str = "",
    source_format: str = ""
) -> Dict:
    resolved_firmware = _resolve_firmware(firmware, source_path)
    resolved_disk_bus = _resolve_disk_bus(disk_bus, source_format)
    bootloader = {"bios": {}} if resolved_firmware == "bios" else {"efi": {"secureBoot": False}}

    return {
        "apiVersion": "kubevirt.io/v1",
        "kind": "VirtualMachine",
        "metadata": {
            "name": vm_name,
            "namespace": namespace,
            "annotations": {
                "vm.kubevirt.io/validations": "phase1-boot-profile"
            }
        },
        "spec": {
            "running": True,
            "template": {
                "metadata": {"labels": {"kubevirt.io/domain": vm_name}},
                "spec": {
                    "terminationGracePeriodSeconds": 0,
                    "domain": {
                        "machine": {"type": "q35"},
                        "cpu": {"cores": cpu_cores},
                        "resources": {"requests": {"memory": memory}},
                        "devices": {
                            "autoattachSerialConsole": True,
                            "rng": {},
                            "disks": [
                                _build_disk_device("rootdisk", resolved_disk_bus)
                            ],
                            "interfaces": [
                                {"name": "default", "masquerade": {}}
                            ]
                        },
                        "firmware": {"bootloader": bootloader}
                    },
                    "networks": [{"name": "default", "pod": {}}],
                    "volumes": [
                        {"name": "rootdisk", "persistentVolumeClaim": {"claimName": pvc_name}}
                    ]
                }
            }
        }
    }


def apply_manifest(manifest: Dict) -> None:
    data = json.dumps(manifest)
    cmd = ["oc", "apply", "-f", "-"]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = process.communicate(input=data)
    if process.returncode != 0:
        raise RuntimeError(f"Apply manifest failed: {err or out}")
